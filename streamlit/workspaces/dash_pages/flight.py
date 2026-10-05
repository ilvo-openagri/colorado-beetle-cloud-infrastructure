import datetime as dt
import json
import os
import time
from functools import lru_cache
from typing import Any, cast

from dash import Input, Output, State, callback, dcc, html, no_update, register_page
import dash_bootstrap_components as dbc

from database import DatabaseApi
from drone import IlvoDrone

register_page(__name__, path="/flight", name="Flight")


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


def _build_drone_client() -> IlvoDrone:
    host = os.environ.get("DRONE_HOST")
    port_raw = os.environ.get("DRONE_HTTP_PORT")

    if not host:
        raise RuntimeError("DRONE_HOST is not configured")
    if not port_raw:
        raise RuntimeError("DRONE_HTTP_PORT is not configured")

    try:
        port = int(port_raw)
    except ValueError as error:
        raise RuntimeError("DRONE_HTTP_PORT must be an integer") from error

    return IlvoDrone(host, port)


def _format_payload(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, default=str)


def _project_options() -> list[dict[str, Any]]:
    projects = load_database_api().get_project()
    return [{"label": project["name"], "value": project["id"]} for project in projects]


layout = dbc.Container(
    [
        dcc.Interval(id="flight-status-interval", interval=10_000, n_intervals=0),
        dcc.Store(id="flight-refresh-token", data=0),
        dcc.Store(id="flight-status-store", data={}),
        dbc.Card(
            [
                dbc.CardHeader(
                    dbc.Row(
                        [
                            dbc.Col(html.H5("Flight", className="mb-0")),
                            dbc.Col(
                                dbc.Button(
                                    "Refresh now",
                                    id="flight-refresh",
                                    color="secondary",
                                    size="sm",
                                ),
                                width="auto",
                            ),
                        ],
                        class_name="g-2 align-items-center",
                        justify="between",
                    )
                ),
                dbc.CardBody(
                    [
                        dbc.Row(
                            [
                                dbc.Col(
                                    dbc.Badge(
                                        "Drone status: unknown",
                                        id="flight-status-badge",
                                        color="secondary",
                                        class_name="p-2",
                                    ),
                                    width="auto",
                                ),
                                dbc.Col(
                                    html.Div(
                                        id="flight-status-last-update",
                                        className="text-muted",
                                    ),
                                    width="auto",
                                ),
                            ],
                            class_name="g-2 align-items-center",
                        ),
                        html.Div(
                            id="flight-status-endpoint", className="text-muted mt-2"
                        ),
                        html.Pre(
                            id="flight-status-json",
                            style={
                                "backgroundColor": "#0f172a",
                                "color": "#e2e8f0",
                                "padding": "1rem",
                                "borderRadius": "0.5rem",
                                "overflowX": "auto",
                                "maxHeight": "280px",
                                "marginTop": "0.75rem",
                            },
                        ),
                        dbc.Alert(
                            id="flight-status-alert",
                            is_open=False,
                            class_name="mb-0",
                        ),
                    ]
                ),
            ],
            class_name="shadow-sm border-0",
        ),
        dbc.Card(
            [
                dbc.CardHeader(html.H5("Start Flight", className="mb-0")),
                dbc.CardBody(
                    [
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        dbc.Label("Environment"),
                                        dcc.Dropdown(
                                            id="flight-environment",
                                            options=[
                                                {"label": "cloud", "value": "cloud"},
                                                {"label": "edge", "value": "edge"},
                                            ],
                                            value="edge",
                                            clearable=False,
                                        ),
                                    ],
                                    md=4,
                                ),
                                dbc.Col(
                                    [
                                        dbc.Label("Project"),
                                        dcc.Dropdown(
                                            id="flight-project",
                                            options=[],
                                            placeholder="Select a project",
                                        ),
                                    ],
                                    md=4,
                                ),
                                dbc.Col(
                                    [
                                        dbc.Label("Flight name"),
                                        dbc.Input(
                                            id="flight-name",
                                            type="text",
                                            placeholder="Flight name",
                                        ),
                                    ],
                                    md=4,
                                ),
                            ],
                            class_name="g-3",
                        ),
                        dbc.Button(
                            "Start flight",
                            id="flight-start",
                            color="primary",
                            class_name="mt-3",
                        ),
                        dbc.Alert(
                            id="flight-start-alert",
                            is_open=False,
                            class_name="mt-3 mb-0",
                        ),
                    ]
                ),
            ],
            id="flight-start-card",
            class_name="shadow-sm border-0 mt-4",
        ),
        dbc.Card(
            [
                dbc.CardHeader(html.H5("Active Flight", className="mb-0")),
                dbc.CardBody(
                    [
                        html.Div(id="flight-active-details", className="mb-3"),
                        dbc.Button("Stop flight", id="flight-stop", color="danger"),
                        dbc.Alert(
                            id="flight-stop-alert",
                            is_open=False,
                            class_name="mt-3 mb-0",
                        ),
                    ]
                ),
            ],
            id="flight-active-card",
            class_name="shadow-sm border-0 mt-4",
        ),
    ],
    fluid=True,
)


@callback(
    Output("flight-project", "options"),
    Input("flight-refresh-token", "data"),
)
def refresh_project_options(_refresh_token: int):
    try:
        return _project_options()
    except Exception:
        return []


@callback(
    Output("flight-status-store", "data"),
    Output("flight-status-badge", "children"),
    Output("flight-status-badge", "color"),
    Output("flight-status-endpoint", "children"),
    Output("flight-status-json", "children"),
    Output("flight-status-last-update", "children"),
    Output("flight-status-alert", "children"),
    Output("flight-status-alert", "color"),
    Output("flight-status-alert", "is_open"),
    Input("flight-status-interval", "n_intervals"),
    Input("flight-refresh", "n_clicks"),
    Input("flight-refresh-token", "data"),
)
def refresh_flight_status(_n_intervals: int, _n_clicks: int, _refresh_token: int):
    timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        drone = _build_drone_client()
        payload = drone.get_status()
        running = isinstance(payload, dict) and bool(payload.get("status"))

        return (
            payload,
            "Drone status: running" if running else "Drone status: idle",
            "success" if running else "warning",
            f"Endpoint: http://{drone._url}:{drone._port}/status",
            _format_payload(payload),
            f"Last update: {timestamp}",
            "Status fetched successfully.",
            "secondary",
            True,
        )
    except Exception as error:
        return (
            {},
            "Drone status: unavailable",
            "danger",
            "Endpoint: unavailable",
            "{}",
            f"Last update: {timestamp}",
            f"Failed to fetch drone status: {error}",
            "danger",
            True,
        )


@callback(
    Output("flight-start-card", "style"),
    Output("flight-active-card", "style"),
    Output("flight-active-details", "children"),
    Input("flight-status-store", "data"),
)
def render_flight_sections(status_payload: dict[str, Any]):
    if status_payload.get("status"):
        details = [
            html.Div(f"Flight ID: {status_payload.get('flight_id', '-')}"),
            html.Div(f"Project ID: {status_payload.get('project_id', '-')}"),
            html.Div(f"Environment: {status_payload.get('ads', '-')}"),
        ]
        return {"display": "none"}, {}, details

    return {}, {"display": "none"}, "No active flight."


@callback(
    Output("flight-refresh-token", "data", allow_duplicate=True),
    Output("flight-start-alert", "children"),
    Output("flight-start-alert", "color"),
    Output("flight-start-alert", "is_open"),
    Output("flight-name", "value"),
    Input("flight-start", "n_clicks"),
    State("flight-refresh-token", "data"),
    State("flight-project", "value"),
    State("flight-environment", "value"),
    State("flight-name", "value"),
    prevent_initial_call=True,
)
def start_flight(
    n_clicks: int,
    refresh_token: int,
    project_id: int | None,
    environment: str | None,
    flight_name_value: str | None,
):
    if not n_clicks:
        return no_update, no_update, no_update, no_update, no_update

    flight_name = (flight_name_value or "").strip()
    if not flight_name:
        return no_update, "Flight name is required.", "warning", True, no_update
    if project_id is None:
        return no_update, "Please select a project.", "warning", True, no_update

    ads_environment = environment or "cloud"
    try:
        flight_id = load_database_api().post_flight(
            project_id=int(project_id),
            flight_name=flight_name,
            environment=ads_environment,
            timestamp_epoch=int(time.time()),
        )
        started = _build_drone_client().start(
            project_id=int(project_id),
            flight_id=int(flight_id),
            ads=ads_environment,
        )
    except Exception as error:
        return (
            no_update,
            f"Issue during flight creation: {error}",
            "danger",
            True,
            no_update,
        )

    if not started:
        return (
            no_update,
            "Flight was created but drone did not acknowledge start.",
            "warning",
            True,
            no_update,
        )

    return (
        refresh_token + 1,
        "Flight started successfully.",
        "success",
        True,
        "",
    )


@callback(
    Output("flight-refresh-token", "data", allow_duplicate=True),
    Output("flight-stop-alert", "children"),
    Output("flight-stop-alert", "color"),
    Output("flight-stop-alert", "is_open"),
    Input("flight-stop", "n_clicks"),
    State("flight-refresh-token", "data"),
    prevent_initial_call=True,
)
def stop_flight(n_clicks: int, refresh_token: int):
    if not n_clicks:
        return no_update, no_update, no_update, no_update

    try:
        stopped = _build_drone_client().stop()
    except Exception as error:
        return no_update, f"Failed to stop flight: {error}", "danger", True

    if not stopped:
        return (
            no_update,
            "Drone did not acknowledge stop.",
            "warning",
            True,
        )

    return refresh_token + 1, "Flight stopped successfully.", "success", True
