from database import DatabaseApi
from resources.helpers import check_remote_port
import os
import streamlit as st



@st.cache_resource
def load_database_connections(environments: list) -> dict:
    return_dict = {}
    if "cloud" in environments and check_remote_port(os.environ.get("PG_CLOUD_HOST"), int(os.environ.get("PG_CLOUD_PORT"))):
        return_dict["cloud"] = DatabaseApi(
            config={
                "pg_host": os.environ.get("PG_CLOUD_HOST"),
                "pg_port": int(os.environ.get("PG_CLOUD_PORT")),
                "pg_database": os.environ.get("PG_CLOUD_DATABASE"),
                "pg_user": os.environ.get("PG_CLOUD_USER"),
                "pg_password": os.environ.get("PG_CLOUD_PASSWORD"),
            }
        )
    if False:
        if "edge" in environments and check_remote_port(edge, 5432):
            return_dict["edge"] = DatabaseApi(
                config={
                    "pg_host": edge,
                    "pg_database": "openagri_edge",
                    "pg_user": "openagri_user",
                    "pg_password": "QkEaDeYwNZRrirZ",
                    "pg_port": 5432,
                }
            )
    return return_dict
