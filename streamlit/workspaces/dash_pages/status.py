import datetime as dt
import json
import os

from dash import Input, Output, callback, dcc, html, register_page
import dash_bootstrap_components as dbc

from drone import IlvoDrone

register_page(__name__, path="/status", name="Status")


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


def _format_status_payload(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, default=str)


layout = dbc.Container(
    [
        dcc.Interval(id="drone-status-interval", interval=10_000, n_intervals=0),
        dbc.Card(
            [
                dbc.CardHeader(html.H5("Drone Status", className="mb-0")),
                dbc.CardBody(
                    [
                        dbc.Row(
                            [
                                dbc.Col(
                                    dbc.Badge(
                                        "Status: unknown",
                                        id="drone-status-badge",
                                        color="secondary",
                                        class_name="p-2",
                                    ),
                                    width="auto",
                                ),
                                dbc.Col(
                                    dbc.Button(
                                        "Refresh now",
                                        id="drone-status-refresh",
                                        color="primary",
                                    ),
                                    width="auto",
                                ),
                                dbc.Col(
                                    html.Div(
                                        id="drone-status-last-update",
                                        className="text-muted mt-2",
                                    ),
                                    width="auto",
                                ),
                            ],
                            class_name="g-2 align-items-center",
                        ),
                        dbc.Alert(
                            id="drone-status-alert",
                            is_open=False,
                            class_name="mt-3 mb-3",
                        ),
                        html.Div(
                            id="drone-status-endpoint", className="text-muted mb-2"
                        ),
                        html.Pre(
                            id="drone-status-json",
                            style={
                                "backgroundColor": "#0f172a",
                                "color": "#e2e8f0",
                                "padding": "1rem",
                                "borderRadius": "0.5rem",
                                "overflowX": "auto",
                                "maxHeight": "480px",
                            },
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
    Output("drone-status-badge", "children"),
    Output("drone-status-badge", "color"),
    Output("drone-status-alert", "children"),
    Output("drone-status-alert", "color"),
    Output("drone-status-alert", "is_open"),
    Output("drone-status-endpoint", "children"),
    Output("drone-status-json", "children"),
    Output("drone-status-last-update", "children"),
    Input("drone-status-refresh", "n_clicks"),
    Input("drone-status-interval", "n_intervals"),
)
def refresh_drone_status(_n_clicks: int, _n_intervals: int):
    timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        drone = _build_drone_client()
        status_payload = drone.get_status()

        endpoint = f"Endpoint: http://{drone._url}:{drone._port}/status"
        payload_text = _format_status_payload(status_payload)

        running = False
        if isinstance(status_payload, dict):
            running = bool(status_payload.get("status"))

        if running:
            badge_text = "Status: running"
            badge_color = "success"
        else:
            badge_text = "Status: idle"
            badge_color = "warning"

        return (
            badge_text,
            badge_color,
            "Status fetched successfully.",
            "secondary",
            True,
            endpoint,
            payload_text,
            f"Last update: {timestamp}",
        )
    except Exception as error:
        return (
            "Status: unavailable",
            "danger",
            f"Failed to fetch drone status: {error}",
            "danger",
            True,
            "Endpoint: unavailable",
            "{}",
            f"Last update: {timestamp}",
        )
