from drone import IlvoDrone
from resources.database import load_database_connections
from resources.dotenv import load_environment

import os
import streamlit as st
import streamlit.components.v1 as st_components


# Load dotenv:
load_environment()

# Show the grafana dashboard:
iframe_src = os.environ.get("GRAFANA_URL")
try:
    st_components.iframe(iframe_src, height=1024, scrolling=True)
except Exception as e:
    st.error(f"Unable to load the iframe: {e}")
