import os
from functools import lru_cache
from typing import cast

from dash import (
    Input,
    Output,
    State,
    callback,
    dcc,
    dash_table,
    html,
    no_update,
    register_page,
)
import dash_bootstrap_components as dbc

from database import DatabaseApi

register_page(__name__, path="/", name="Projects")


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


def list_projects() -> list[dict]:
    projects = []
    for project in load_database_api().get_project():
        projects.append(project)
    return projects


layout = dbc.Container(
    [
        dcc.Store(id="projects-refresh-token", data=0),
        dcc.Store(id="selected-project", data=None),
        dbc.Card(
            [
                dbc.CardHeader(
                    dbc.Row(
                        [
                            dbc.Col(html.H5("Projects", className="mb-0")),
                            dbc.Col(
                                dbc.Button(
                                    "Refresh",
                                    id="refresh-projects",
                                    n_clicks=0,
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
                        dash_table.DataTable(
                            id="projects-table",
                            columns=[
                                {"name": "ID", "id": "id"},
                                {"name": "Project name", "id": "name"},
                            ],
                            data=[],
                            row_selectable="single",
                            selected_rows=[],
                            style_table={"overflowX": "auto"},
                            style_cell={"textAlign": "left", "padding": "0.5rem"},
                            style_header={"fontWeight": "bold"},
                        ),
                        dbc.Alert(
                            id="projects-status",
                            color="secondary",
                            class_name="mt-3 mb-0",
                            is_open=False,
                        ),
                    ]
                ),
            ],
            class_name="shadow-sm border-0",
        ),
        dbc.Card(
            [
                dbc.CardHeader(html.H5("Create New Project", className="mb-0")),
                dbc.CardBody(
                    [
                        dbc.InputGroup(
                            [
                                dbc.Input(
                                    id="project-name-input",
                                    type="text",
                                    placeholder="Project name",
                                ),
                                dbc.Button(
                                    "Create project",
                                    id="create-project",
                                    n_clicks=0,
                                    color="primary",
                                ),
                            ],
                            class_name="mb-3",
                        ),
                        dbc.Alert(
                            id="create-project-status", class_name="mb-0", is_open=False
                        ),
                    ]
                ),
            ],
            class_name="mt-4 shadow-sm border-0",
        ),
    ],
    fluid=True,
)


@callback(
    Output("projects-table", "data"),
    Output("projects-status", "children"),
    Output("projects-status", "color"),
    Output("projects-status", "is_open"),
    Input("projects-refresh-token", "data"),
    Input("refresh-projects", "n_clicks"),
)
def refresh_projects(_refresh_token: int, _refresh_clicks: int):
    try:
        projects = list_projects()
        status = f"Loaded {len(projects)} project(s)."
        return projects, status, "secondary", True
    except Exception as error:
        message = f"Error fetching projects: {error}"
        return [], message, "danger", True


@callback(
    Output("selected-project", "data"),
    Input("projects-table", "selected_rows"),
    Input("projects-table", "data"),
)
def set_selected_project(selected_rows: list[int], table_data: list[dict]):
    if not selected_rows:
        return None
    if not table_data:
        return None
    selected_idx = selected_rows[0]
    if selected_idx >= len(table_data):
        return None
    return table_data[selected_idx]


@callback(
    Output("projects-refresh-token", "data", allow_duplicate=True),
    Output("project-name-input", "value"),
    Output("create-project-status", "children"),
    Output("create-project-status", "color"),
    Output("create-project-status", "is_open"),
    Input("create-project", "n_clicks"),
    State("projects-refresh-token", "data"),
    State("project-name-input", "value"),
    prevent_initial_call=True,
)
def create_project(n_clicks: int, refresh_token: int, project_name_value: str | None):
    if not n_clicks:
        return no_update, no_update, no_update, no_update, no_update

    project_name = (project_name_value or "").strip()
    if not project_name:
        return (
            no_update,
            no_update,
            "Project name cannot be empty.",
            "warning",
            True,
        )

    try:
        load_database_api().post_project(name=project_name)
    except Exception as error:
        return (
            no_update,
            no_update,
            f"Error creating project: {error}",
            "danger",
            True,
        )

    return (
        refresh_token + 1,
        "",
        "Project created successfully.",
        "success",
        True,
    )
