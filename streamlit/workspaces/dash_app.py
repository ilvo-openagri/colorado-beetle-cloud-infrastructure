from dash import Dash, Input, Output, html, page_container
from resources.dotenv import load_environment
import argparse
import dash_bootstrap_components as dbc
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Run the OpenAgri Dash app.")
    parser.add_argument(
        "--env-file",
        help="Optional path to a .env file to load before starting the app.",
    )
    return parser.parse_args()


args = parse_args()

load_environment(args.env_file)

app = Dash(
    __name__,
    use_pages=True,
    pages_folder="dash_pages",
    title="OpenAgri SIP3 - Dashboard",
    # external_stylesheets=[dbc.icons.BOOTSTRAP, dbc.themes.FLATLY],
    external_stylesheets=["/assets/bootstrap.min.css"],
    assets_folder=str(Path(__file__).resolve().parent / "assets"),
)

app.layout = html.Div(
    id="app-container",
    children=[
        dbc.Navbar(
            dbc.Container(
                [
                    html.A(
                        # Use row and col to control vertical alignment of logo / brand
                        dbc.Row(
                            [
                                dbc.Col(
                                    html.Img(
                                        src=app.get_asset_url("openagri-title.png"),
                                        height="64px",
                                    )
                                ),
                                dbc.Col(
                                    dbc.NavbarBrand(
                                        "SIP3 - Colorado Beetle Detection",
                                        class_name="ms-2 font-weight-bold",
                                    )
                                ),
                            ],
                            align="center",
                            className="g-0",
                        ),
                        style={"textDecoration": "none"},
                    ),
                ],
                fluid=True,
            ),
            color="white",
            dark=False,
            style={
                "borderBottom": "2px solid #A3CC00",
            },
            class_name="openagri-navbar",
        ),
        dbc.Container(
            [
                dbc.Row(
                    [
                        dbc.Col(
                            dbc.Card(
                                dbc.CardBody(
                                    [
                                        html.Div(
                                            children=[
                                                dbc.Button(
                                                    html.I(
                                                        className="bi bi-chevron-left"
                                                    ),
                                                    id="sidebar-toggle",
                                                    color="light",
                                                    class_name="openagri-sidebar-toggle w-32 mb-3",
                                                    n_clicks=0,
                                                ),
                                            ],
                                            className="d-flex justify-content-end",
                                        ),
                                        dbc.Nav(
                                            [
                                                dbc.NavLink(
                                                    [
                                                        html.I(
                                                            className="bi bi-folder me-2"
                                                        ),
                                                        html.Span(
                                                            "Projects",
                                                            className="sidebar-link-label",
                                                        ),
                                                    ],
                                                    href="/",
                                                    active="exact",
                                                    class_name="sidebar-nav-link",
                                                ),
                                                dbc.NavLink(
                                                    [
                                                        html.I(
                                                            className="bi bi-bar-chart-line me-2"
                                                        ),
                                                        html.Span(
                                                            "Overview",
                                                            className="sidebar-link-label",
                                                        ),
                                                    ],
                                                    href="/overview",
                                                    active="exact",
                                                    class_name="sidebar-nav-link",
                                                ),
                                                dbc.NavLink(
                                                    [
                                                        html.I(
                                                            className="bi bi-broadcast-pin me-2"
                                                        ),
                                                        html.Span(
                                                            "Status",
                                                            className="sidebar-link-label",
                                                        ),
                                                    ],
                                                    href="/status",
                                                    active="exact",
                                                    class_name="sidebar-nav-link",
                                                ),
                                                dbc.NavLink(
                                                    [
                                                        html.I(
                                                            className="bi bi-airplane me-2"
                                                        ),
                                                        html.Span(
                                                            "Flight",
                                                            className="sidebar-link-label",
                                                        ),
                                                    ],
                                                    href="/flight",
                                                    active="exact",
                                                    class_name="sidebar-nav-link",
                                                ),
                                            ],
                                            vertical=True,
                                            pills=True,
                                            class_name="gap-1 sidebar-nav",
                                        ),
                                    ]
                                ),
                                class_name="h-100 border-0 shadow-sm openagri-sidebar",
                                id="sidebar-card",
                            ),
                            xs=12,
                            md=3,
                            lg=2,
                            id="sidebar-col",
                            class_name="mb-3 mb-md-0",
                        ),
                        dbc.Col(
                            dbc.Container(
                                page_container, fluid=True, class_name="px-0"
                            ),
                            xs=12,
                            md=9,
                            lg=10,
                            id="content-col",
                        ),
                    ],
                    class_name="g-3 py-3",
                    id="main-layout",
                ),
            ],
            fluid=True,
        ),
    ],
)


@app.callback(
    Output("sidebar-card", "class_name"),
    Output("sidebar-col", "md"),
    Output("sidebar-col", "lg"),
    Output("content-col", "md"),
    Output("content-col", "lg"),
    Output("sidebar-toggle", "children"),
    Input("sidebar-toggle", "n_clicks"),
)
def toggle_sidebar(n_clicks):
    is_collapsed = bool(n_clicks and n_clicks % 2 == 1)

    if is_collapsed:
        return (
            "h-100 border-0 shadow-sm openagri-sidebar openagri-sidebar-collapsed",
            1,
            1,
            11,
            11,
            html.I(className="bi bi-chevron-right"),
        )

    return (
        "h-100 border-0 shadow-sm openagri-sidebar",
        3,
        2,
        9,
        10,
        html.I(className="bi bi-chevron-left"),
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True, use_reloader=True)
