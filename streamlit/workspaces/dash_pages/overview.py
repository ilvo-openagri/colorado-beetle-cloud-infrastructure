import datetime as dt
import os
from functools import lru_cache
from urllib.parse import urlencode
from typing import Any, cast

from dash import (
    Input,
    Output,
    State,
    callback,
    dash_table,
    dcc,
    html,
    no_update,
    register_page,
)
import dash_bootstrap_components as dbc

from database import DatabaseApi
from s3 import MinioController

register_page(__name__, path="/overview", name="Overview")


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


def _parse_epoch(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _format_timestamp(epoch_value: float) -> str:
    if epoch_value <= 0:
        return ""
    return dt.datetime.fromtimestamp(epoch_value).strftime("%Y-%m-%d %H:%M:%S")


def _parse_iso_date(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    return dt.datetime.combine(dt.date.fromisoformat(value), dt.time.min)


def list_project_options() -> list[dict[str, str]]:
    projects = load_database_api().get_project()
    options = [
        {"label": project["name"], "value": project["name"]} for project in projects
    ]
    options.sort(key=lambda entry: entry["label"].lower())
    return options


def list_overview_rows(
    start_date: str | None,
    end_date: str | None,
    selected_projects: list[str] | None,
) -> list[dict[str, Any]]:
    rows = load_database_api().get_project_summary()
    selected_set = set(selected_projects or [])

    start_dt = _parse_iso_date(start_date)
    end_dt = _parse_iso_date(end_date)
    if end_dt is not None:
        end_dt = end_dt + dt.timedelta(days=1)

    output_rows: list[dict[str, Any]] = []
    for row in rows:
        timestamp_epoch = _parse_epoch(row.get("timestamp_epoch"))
        row_dt = (
            dt.datetime.fromtimestamp(timestamp_epoch) if timestamp_epoch > 0 else None
        )

        if start_dt and row_dt and row_dt < start_dt:
            continue
        if end_dt and row_dt and row_dt >= end_dt:
            continue
        if selected_set and row.get("name") not in selected_set:
            continue

        output_rows.append(
            {
                "timestamp": _format_timestamp(timestamp_epoch),
                "environment": row.get("environment"),
                "flight_name": row.get("flight_name"),
                "name": row.get("name"),
                "flight_id": row.get("flight_id"),
                "project_id": row.get("project_id"),
            }
        )

    output_rows.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
    return output_rows


def _delete_selected_flights(
    selected_rows: list[int], table_data: list[dict[str, Any]]
) -> int:
    api = load_database_api()
    minio_controller = get_minio_controller()

    delete_count = 0
    for selected_idx in selected_rows:
        if selected_idx >= len(table_data):
            continue

        row = table_data[selected_idx]
        flight_id = row.get("flight_id")
        project_id = row.get("project_id")
        environment = row.get("environment")
        if (
            flight_id is None
            or project_id is None
            or environment not in {"cloud", "edge"}
        ):
            continue

        api.delete_flight(flight_id=int(flight_id))

        s3_filename = f"{project_id}/{flight_id}"
        bucket_name = (
            os.environ.get("MINIO_EDGE_RAW_BUCKET")
            if environment == "edge"
            else os.environ.get("MINIO_CLOUD_RAW_BUCKET")
        )
        if bucket_name:
            minio_controller[environment].delete_file(
                bucket_name=bucket_name,
                object_name=s3_filename,
                recursive=True,
            )

        delete_count += 1

    return delete_count


layout = dbc.Container(
    [
        dcc.Store(id="overview-refresh-token", data=0),
        dcc.Location(id="overview-location", refresh=True),
        dbc.Card(
            [
                dbc.CardHeader(html.H5("Overview", className="mb-0")),
                dbc.CardBody(
                    [
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        dbc.Label("Date range"),
                                        dcc.DatePickerRange(
                                            id="overview-date-range",
                                            min_date_allowed=dt.date(2026, 1, 1),
                                            start_date=dt.date(2026, 1, 1),
                                            end_date=dt.date.today(),
                                            display_format="YYYY-MM-DD",
                                        ),
                                    ],
                                    lg=5,
                                    md=12,
                                ),
                                dbc.Col(
                                    [
                                        dbc.Label("Projects"),
                                        dcc.Dropdown(
                                            id="overview-project-filter",
                                            options=[],
                                            value=[],
                                            multi=True,
                                            placeholder="All projects",
                                        ),
                                    ],
                                    lg=5,
                                    md=12,
                                ),
                                dbc.Col(
                                    dbc.Button(
                                        "Refresh",
                                        id="overview-refresh",
                                        color="secondary",
                                        class_name="w-100 mt-4",
                                    ),
                                    lg=2,
                                    md=12,
                                ),
                            ],
                            class_name="g-3",
                        ),
                        dash_table.DataTable(
                            id="overview-table",
                            columns=[
                                {"name": "Timestamp", "id": "timestamp"},
                                {"name": "Environment", "id": "environment"},
                                {"name": "Flight name", "id": "flight_name"},
                                {"name": "Project name", "id": "name"},
                            ],
                            data=[],
                            row_selectable="multi",
                            selected_rows=[],
                            style_table={"overflowX": "auto", "marginTop": "1rem"},
                            style_cell={"textAlign": "left", "padding": "0.5rem"},
                            style_header={"fontWeight": "bold"},
                            page_size=15,
                        ),
                        dbc.Row(
                            [
                                dbc.Col(
                                    dbc.Button(
                                        "View details",
                                        id="overview-view-details",
                                        color="info",
                                        outline=True,
                                    ),
                                    width="auto",
                                ),
                                dbc.Col(
                                    dbc.Button(
                                        "Delete", id="overview-delete", color="danger"
                                    ),
                                    width="auto",
                                ),
                            ],
                            class_name="g-2 mt-2",
                        ),
                        dbc.Alert(
                            id="overview-status", class_name="mt-3 mb-0", is_open=False
                        ),
                    ]
                ),
            ],
            class_name="shadow-sm border-0",
        ),
    ],
    fluid=True,
)


@callback(
    Output("overview-project-filter", "options"),
    Input("overview-refresh-token", "data"),
)
def refresh_project_filter_options(_refresh_token: int):
    try:
        return list_project_options()
    except Exception:
        return []


@callback(
    Output("overview-table", "data"),
    Output("overview-status", "children"),
    Output("overview-status", "color"),
    Output("overview-status", "is_open"),
    Input("overview-refresh-token", "data"),
    Input("overview-refresh", "n_clicks"),
    Input("overview-date-range", "start_date"),
    Input("overview-date-range", "end_date"),
    Input("overview-project-filter", "value"),
)
def refresh_overview_table(
    _refresh_token: int,
    _refresh_clicks: int,
    start_date: str | None,
    end_date: str | None,
    selected_projects: list[str] | None,
):
    try:
        rows = list_overview_rows(
            start_date=start_date,
            end_date=end_date,
            selected_projects=selected_projects,
        )
        return rows, f"Loaded {len(rows)} flight(s).", "secondary", True
    except Exception as error:
        return [], f"Error loading overview data: {error}", "danger", True


@callback(
    Output("overview-refresh-token", "data", allow_duplicate=True),
    Output("overview-table", "selected_rows"),
    Output("overview-status", "children", allow_duplicate=True),
    Output("overview-status", "color", allow_duplicate=True),
    Output("overview-status", "is_open", allow_duplicate=True),
    Input("overview-delete", "n_clicks"),
    State("overview-refresh-token", "data"),
    State("overview-table", "selected_rows"),
    State("overview-table", "data"),
    prevent_initial_call=True,
)
def delete_selected_flights(
    n_clicks: int,
    refresh_token: int,
    selected_rows: list[int] | None,
    table_data: list[dict[str, Any]] | None,
):
    if not n_clicks:
        return no_update, no_update, no_update, no_update, no_update

    if not selected_rows or not table_data:
        return (
            no_update,
            no_update,
            "Select at least one flight to delete.",
            "warning",
            True,
        )

    try:
        delete_count = _delete_selected_flights(selected_rows, table_data)
        return (
            refresh_token + 1,
            [],
            f"Deleted {delete_count} flight(s).",
            "success",
            True,
        )
    except Exception as error:
        return (
            no_update,
            no_update,
            f"Error deleting selected flights: {error}",
            "danger",
            True,
        )


@callback(
    Output("overview-status", "children", allow_duplicate=True),
    Output("overview-status", "color", allow_duplicate=True),
    Output("overview-status", "is_open", allow_duplicate=True),
    Output("overview-location", "href", allow_duplicate=True),
    Input("overview-view-details", "n_clicks"),
    State("overview-table", "selected_rows"),
    State("overview-table", "data"),
    prevent_initial_call=True,
)
def view_details_notice(
    n_clicks: int,
    selected_rows: list[int] | None,
    table_data: list[dict[str, Any]] | None,
):
    if not n_clicks:
        return no_update, no_update, no_update, no_update

    if not selected_rows or len(selected_rows) != 1 or not table_data:
        return (
            "Select exactly one flight to view details.",
            "warning",
            True,
            no_update,
        )

    selected_idx = selected_rows[0]
    if selected_idx >= len(table_data):
        return (
            "Selection is out of range. Please select a row again.",
            "warning",
            True,
            no_update,
        )

    row = table_data[selected_idx]
    search = urlencode(
        {
            "flight_id": row.get("flight_id", ""),
            "project_id": row.get("project_id", ""),
        }
    )

    return "Opening details...", "info", True, f"/overview/detail?{search}"
