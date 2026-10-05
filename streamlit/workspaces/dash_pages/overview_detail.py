import base64
import io
import os
from functools import lru_cache
from typing import Any, cast

from dash import (
    Input,
    Output,
    Patch,
    State,
    callback,
    dash_table,
    dcc,
    html,
    no_update,
    register_page,
)
import dash_bootstrap_components as dbc
from PIL import Image, ImageDraw
import plotly.graph_objects as go

from database import DatabaseApi
from s3 import MinioController

register_page(__name__, path="/overview/detail", name="Overview Detail")


@lru_cache(maxsize=1)
def _build_database_api(
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> DatabaseApi:
    return DatabaseApi(
        config={
            "pg_host": pg_host,
            "pg_port": pg_port,
            "pg_database": pg_database,
            "pg_user": pg_user,
            "pg_password": pg_password,
        }
    )


def load_database_api() -> DatabaseApi:
    pg_host = os.environ.get("PG_CLOUD_HOST")
    pg_port_raw = os.environ.get("PG_CLOUD_PORT")
    pg_database = os.environ.get("PG_CLOUD_DATABASE")
    pg_user = os.environ.get("PG_CLOUD_USER")
    pg_password = os.environ.get("PG_CLOUD_PASSWORD")

    missing = [
        key
        for key, value in {
            "PG_CLOUD_HOST": pg_host,
            "PG_CLOUD_PORT": pg_port_raw,
            "PG_CLOUD_DATABASE": pg_database,
            "PG_CLOUD_USER": pg_user,
            "PG_CLOUD_PASSWORD": pg_password,
        }.items()
        if value is None or value == ""
    ]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    pg_host = cast(str, pg_host)
    pg_port_raw = cast(str, pg_port_raw)
    pg_database = cast(str, pg_database)
    pg_user = cast(str, pg_user)
    pg_password = cast(str, pg_password)

    try:
        pg_port = int(pg_port_raw)
    except (TypeError, ValueError) as error:
        raise RuntimeError("PG_CLOUD_PORT must be a valid integer") from error

    return _build_database_api(pg_host, pg_port, pg_database, pg_user, pg_password)


@lru_cache(maxsize=1)
def get_minio_controller() -> dict[str, MinioController]:
    return {
        "edge": MinioController(
            minio_url=f"http://{os.environ.get('MINIO_EDGE_URL')}",
            access_key=cast(str, os.environ.get("MINIO_EDGE_ACCESS_KEY")),
            secret_key=cast(str, os.environ.get("MINIO_EDGE_SECRET_KEY")),
        ),
        "cloud": MinioController(
            minio_url=f"http://{os.environ.get('MINIO_CLOUD_URL')}",
            access_key=cast(str, os.environ.get("MINIO_CLOUD_ACCESS_KEY")),
            secret_key=cast(str, os.environ.get("MINIO_CLOUD_SECRET_KEY")),
        ),
    }


def _parse_gps(gps_value: Any) -> tuple[float | None, float | None]:
    if not isinstance(gps_value, str):
        return None, None
    value = gps_value.strip()
    if not value.startswith("(") or not value.endswith(")"):
        return None, None
    parts = value[1:-1].split(",")
    if len(parts) != 2:
        return None, None
    try:
        lat = float(parts[0].strip())
        lon = float(parts[1].strip())
    except ValueError:
        return None, None
    return lat, lon


def _extract_clicked_image_id(click_data: dict[str, Any] | None) -> int | None:
    if not click_data:
        return None

    points = click_data.get("points")
    if not isinstance(points, list) or not points:
        return None

    point = points[0]
    if not isinstance(point, dict):
        return None

    customdata_value: Any = point.get("customdata")
    if isinstance(customdata_value, list) and customdata_value:
        customdata_value = customdata_value[0]

    if isinstance(customdata_value, int):
        return customdata_value

    if isinstance(customdata_value, float):
        return int(customdata_value)

    if isinstance(customdata_value, str):
        try:
            return int(customdata_value)
        except ValueError:
            pass

    point_index = point.get("pointIndex")
    if point_index is None:
        return None

    try:
        return int(point_index)
    except (TypeError, ValueError):
        return None


def _build_image_placeholder() -> Any:
    return dbc.Alert(
        "Click a point on the map to view the annotated beetle image.",
        color="info",
    )


def _build_annotated_image_preview(
    api: DatabaseApi,
    rows: list[dict[str, Any]],
    environment: str,
    image_id: int,
) -> Any:
    selected_row = next(
        (row for row in rows if int(row.get("image_id") or -1) == image_id),
        None,
    )
    if selected_row is None:
        return dbc.Alert(
            "Selected image was not found in the current flight.",
            color="warning",
        )

    bucket_name = (
        os.environ.get("MINIO_EDGE_RAW_BUCKET")
        if environment == "edge"
        else os.environ.get("MINIO_CLOUD_RAW_BUCKET")
    )
    if not bucket_name:
        return dbc.Alert(
            "Missing MinIO bucket configuration for the selected flight.",
            color="warning",
        )

    object_name = str(selected_row.get("s3_location") or "")
    if not object_name:
        return dbc.Alert(
            "The selected image does not have a storage location.",
            color="warning",
        )

    minio_controller = get_minio_controller().get(environment)
    if minio_controller is None:
        return dbc.Alert(
            "Missing MinIO client configuration for the selected flight.",
            color="warning",
        )

    detections = api.get_detections(image_id=image_id, confidence=0.5)
    image_bytes = minio_controller.get_object_bytes(bucket_name, object_name)

    with Image.open(io.BytesIO(image_bytes)) as image:
        annotated_image = image.convert("RGB")
        draw = ImageDraw.Draw(annotated_image)
        for detection in detections:
            position_raw = detection.get("position")
            if not isinstance(position_raw, str):
                continue

            parts = position_raw[1:-1].split(",")
            if len(parts) != 2:
                continue

            try:
                x_pos = float(parts[0].strip())
                y_pos = float(parts[1].strip())
            except ValueError:
                continue

            draw.rectangle(
                [(x_pos - 32, y_pos - 32), (x_pos + 32, y_pos + 32)],
                outline="red",
                width=5,
            )

        buffer = io.BytesIO()
        annotated_image.save(buffer, format="JPEG")

    encoded_image = base64.b64encode(buffer.getvalue()).decode("ascii")
    detection_count = len(detections)

    return html.Div(
        [
            html.H6(f"Image {image_id}", className="mb-2"),
            html.P(
                f"Annotated detections: {detection_count}",
                className="text-muted mb-2",
            ),
            html.Div(
                className="openagri-magnifier",
                children=[
                    html.Div(
                        className="openagri-magnifier-stage",
                        children=[
                            html.Img(
                                src=f"data:image/jpeg;base64,{encoded_image}",
                                className="openagri-magnifier-image",
                            )
                        ],
                    ),
                    html.Div(className="openagri-magnifier-result"),
                ],
                **{
                    "data-zoom": "5",
                    "data-lens-size": "180",
                    "data-result-size": "280",
                },
            ),
        ]
    )


def _build_detail_data(flight_id: int, confidence: float = 0.5) -> list[dict[str, Any]]:
    api = load_database_api()
    images = api.get_images(flight_id=flight_id, confidence=confidence)

    rows: list[dict[str, Any]] = []
    for image in images:
        detections = api.get_detections(image_id=image["id"], confidence=confidence)
        lat, lon = _parse_gps(image.get("gps_location"))
        rows.append(
            {
                "image_id": image.get("id"),
                "latitude": lat,
                "longitude": lon,
                "detection_count": len(detections),
                "model_runtime": (
                    image.get("model_runtime")
                    if image.get("model_runtime") is not None
                    else -1
                ),
                "s3_location": image.get("storage_location", ""),
            }
        )

    rows.sort(key=lambda row: int(row["image_id"]))
    return rows


def _format_timestamp(epoch_value: Any) -> str:
    try:
        epoch = float(epoch_value)
    except (TypeError, ValueError):
        return "-"
    if epoch <= 0:
        return "-"
    from datetime import datetime

    return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M:%S")


def _build_map_figure(rows: list[dict[str, Any]], show_heatmap: bool) -> go.Figure:
    # Extract all data rows
    data_rows = [
        row
        for row in rows
        if row["latitude"] is not None and row["longitude"] is not None
    ]
    data_latitudes = [row["latitude"] for row in data_rows]
    data_longitudes = [row["longitude"] for row in data_rows]

    if not data_latitudes or not data_longitudes:
        return go.Figure()

    # Extract all rows with detections > 0 for heatmap
    colorado_beetle_rows = [row for row in data_rows if row["detection_count"] > 0]
    colorado_beetle_latitudes = [row["latitude"] for row in colorado_beetle_rows]
    colorado_beetle_longitudes = [row["longitude"] for row in colorado_beetle_rows]

    # Create the heatmap
    figure = go.Figure()

    if show_heatmap:
        heat_values = [
            float(row.get("detection_count") or 0) for row in colorado_beetle_rows
        ]
        z_max = max(1.0, max(heat_values) if heat_values else 1.0)
        figure.add_trace(
            go.Densitymapbox(
                lat=colorado_beetle_latitudes,
                lon=colorado_beetle_longitudes,
                z=heat_values,
                radius=66,
                opacity=1.0,
                colorscale="YlOrRd",
                zmin=0,
                zmax=z_max,
                hoverinfo="skip",
                name="Heatmap",
            )
        )

    data_texts = [
        f"Image {row['image_id']} - beetles: {row['detection_count']}"
        for row in data_rows
    ]
    data_customdata = [row["image_id"] for row in data_rows]
    figure.add_trace(
        go.Scattermapbox(
            lat=data_latitudes,
            lon=data_longitudes,
            mode="markers+lines",
            text=data_texts,
            customdata=data_customdata,
            marker={"size": 9, "color": "#0d6efd", "opacity": 0.9},
            line={"width": 2, "color": "#0d6efd"},
            hovertemplate="%{text}<extra></extra>",
            name="Flight path",
        )
    )

    center_lat = sum(data_latitudes) / len(data_latitudes)
    center_lon = sum(data_longitudes) / len(data_longitudes)
    figure.update_layout(
        mapbox={
            "style": "open-street-map",
            "zoom": 19,
            "center": {"lat": center_lat, "lon": center_lon},
        },
        clickmode="event+select",
        uirevision="overview-detail-map",
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        height=520,
    )
    return figure


def layout(
    flight_id: str | None = None,
    project_id: str | None = None,
    **_: Any,
):
    return dbc.Container(
        [
            dcc.Store(
                id="overview-detail-context",
                data={
                    "flight_id": flight_id,
                    "project_id": project_id,
                },
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Button(
                            "Back to overview",
                            href="/overview",
                            color="secondary",
                            outline=True,
                        ),
                        width="auto",
                    ),
                    dbc.Col(
                        dbc.Button(
                            "Refresh", id="overview-detail-refresh", color="primary"
                        ),
                        width="auto",
                    ),
                    dbc.Col(
                        dbc.Switch(
                            id="overview-detail-heatmap",
                            label="Heatmap overlay",
                            value=True,
                        ),
                        width="auto",
                    ),
                ],
                class_name="g-2 mb-3",
            ),
            dbc.Alert(id="overview-detail-status", is_open=False, class_name="mb-3"),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H6("Project", className="text-muted mb-1"),
                                    html.Div(id="metric-project"),
                                ]
                            ),
                            class_name="h-100",
                        ),
                        md=4,
                    ),
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H6("Flight", className="text-muted mb-1"),
                                    html.Div(id="metric-flight"),
                                ]
                            ),
                            class_name="h-100",
                        ),
                        md=4,
                    ),
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H6("Timestamp", className="text-muted mb-1"),
                                    html.Div(id="metric-time"),
                                ]
                            ),
                            class_name="h-100",
                        ),
                        md=4,
                    ),
                ],
                class_name="g-3 mb-3",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H6("Images", className="text-muted mb-1"),
                                    html.Div(id="metric-images"),
                                ]
                            ),
                            class_name="h-100",
                        ),
                        md=6,
                    ),
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H6(
                                        "Detected colorado beetles",
                                        className="text-muted mb-1",
                                    ),
                                    html.Div(id="metric-beetles"),
                                ]
                            ),
                            class_name="h-100",
                        ),
                        md=6,
                    ),
                ],
                class_name="g-3 mb-3",
            ),
            dbc.Card(
                [
                    dbc.CardHeader(html.H5("Flight map", className="mb-0")),
                    dbc.CardBody(
                        dcc.Graph(
                            id="overview-detail-map", config={"displayModeBar": True}
                        )
                    ),
                ],
                class_name="mb-4 shadow-sm border-0",
            ),
            dbc.Card(
                [
                    dbc.CardHeader(html.H5("Annotated image", className="mb-0")),
                    dbc.CardBody(html.Div(id="overview-detail-image")),
                ],
                class_name="mb-4 shadow-sm border-0",
            ),
            dbc.Card(
                [
                    dbc.CardHeader(html.H5("Image statistics", className="mb-0")),
                    dbc.CardBody(
                        dash_table.DataTable(
                            id="overview-detail-table",
                            columns=[
                                {"name": "Image ID", "id": "image_id"},
                                {"name": "Latitude", "id": "latitude"},
                                {"name": "Longitude", "id": "longitude"},
                                {"name": "Detections", "id": "detection_count"},
                                {"name": "Model runtime [s]", "id": "model_runtime"},
                                {"name": "S3 location", "id": "s3_location"},
                            ],
                            data=[],
                            page_size=15,
                            style_table={"overflowX": "auto"},
                            style_cell={"textAlign": "left", "padding": "0.5rem"},
                            style_header={"fontWeight": "bold"},
                        )
                    ),
                ],
                class_name="shadow-sm border-0",
            ),
        ],
        fluid=True,
    )


@callback(
    Output("overview-detail-table", "data"),
    Output("overview-detail-map", "figure"),
    Output("overview-detail-image", "children"),
    Output("overview-detail-status", "children"),
    Output("overview-detail-status", "color"),
    Output("overview-detail-status", "is_open"),
    Output("metric-project", "children"),
    Output("metric-flight", "children"),
    Output("metric-time", "children"),
    Output("metric-images", "children"),
    Output("metric-beetles", "children"),
    Input("overview-detail-refresh", "n_clicks"),
    Input("overview-detail-heatmap", "value"),
    Input("overview-detail-context", "data"),
    Input("overview-detail-map", "clickData"),
)
def refresh_detail(
    _refresh_clicks: int,
    show_heatmap: bool,
    context: dict[str, Any] | None,
    click_data: dict[str, Any] | None,
):
    context = context or {}
    flight_id_raw = context.get("flight_id")
    project_id_raw = context.get("project_id")

    if not flight_id_raw:
        empty = go.Figure()
        return (
            [],
            empty,
            _build_image_placeholder(),
            "Missing flight selection context.",
            "warning",
            True,
            "-",
            "-",
            "-",
            "0",
            "0",
        )

    try:
        flight_id = int(str(flight_id_raw))
    except ValueError:
        empty = go.Figure()
        return (
            [],
            empty,
            _build_image_placeholder(),
            "Invalid flight id in context.",
            "danger",
            True,
            "-",
            "-",
            "-",
            "0",
            "0",
        )

    try:
        rows = _build_detail_data(flight_id=flight_id)
        figure = _build_map_figure(rows, show_heatmap=bool(show_heatmap))

        api = load_database_api()
        project_name = "-"
        project_id_display = str(project_id_raw or "-")
        if project_id_raw is not None and str(project_id_raw) != "":
            try:
                project_data = api.get_project(id=int(str(project_id_raw)))
                if project_data:
                    project_name = str(project_data[0].get("name") or "-")
                    project_id_display = str(
                        project_data[0].get("id") or project_id_display
                    )
            except Exception:
                pass

        flight_name = "-"
        environment = "-"
        timestamp = "-"
        try:
            flight_data = api.get_flight(id=flight_id)
            if flight_data:
                flight_name = str(flight_data[0].get("name") or "-")
                environment = str(flight_data[0].get("environment") or "-")
                timestamp = _format_timestamp(flight_data[0].get("timestamp_epoch"))
                if project_id_display == "-":
                    project_id_display = str(flight_data[0].get("project_id") or "-")
        except Exception:
            pass

        image_count = len(rows)
        beetle_count = sum(int(row.get("detection_count") or 0) for row in rows)

        selected_image_id = _extract_clicked_image_id(click_data)
        if selected_image_id is None:
            image_preview = _build_image_placeholder()
        else:
            try:
                image_preview = _build_annotated_image_preview(
                    api=api,
                    rows=rows,
                    environment=environment,
                    image_id=selected_image_id,
                )
            except Exception as error:
                image_preview = dbc.Alert(
                    f"Error loading annotated image: {error}",
                    color="danger",
                )

        status = f"Loaded detail data for flight {flight_id}."
        return (
            rows,
            figure,
            image_preview,
            status,
            "secondary",
            True,
            f"{project_name} [{project_id_display}]",
            f"{flight_name} [{flight_id}] ({environment})",
            str(timestamp),
            str(image_count),
            str(beetle_count),
        )
    except Exception as error:
        empty = go.Figure()
        return (
            [],
            empty,
            _build_image_placeholder(),
            f"Error loading overview detail: {error}",
            "danger",
            True,
            "-",
            "-",
            "-",
            "0",
            "0",
        )
