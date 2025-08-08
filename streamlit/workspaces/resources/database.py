from database import DatabaseApi
from resources.helpers import check_remote_port
import os
import streamlit as st



@st.cache_resource
def load_database_connections() -> DatabaseApi:
    return DatabaseApi(
        config={
            "pg_host": os.environ.get("PG_CLOUD_HOST"),
            "pg_port": int(os.environ.get("PG_CLOUD_PORT")),
            "pg_database": os.environ.get("PG_CLOUD_DATABASE"),
            "pg_user": os.environ.get("PG_CLOUD_USER"),
            "pg_password": os.environ.get("PG_CLOUD_PASSWORD"),
        }
    )
