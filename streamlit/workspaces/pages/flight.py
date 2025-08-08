from drone import IlvoDrone
from resources.database import load_database_connections
from resources.dotenv import load_environment

import os
import streamlit as st
import streamlit.components.v1 as st_components
import time


# Load dotenv:
load_environment()


# Initialise the session storage
if "ilvo_drone" not in st.session_state:
    st.session_state.database_api = load_database_connections()
    st.session_state.ilvo_drone = IlvoDrone(
        os.environ.get("DRONE_HOST"), int(os.environ.get("DRONE_HTTP_PORT"))
    )
    st.session_state.environments = ["cloud", "edge"]

# Load the drone connection:
ilvo_drone_status = st.session_state.ilvo_drone.get_status()

# Show page depending on the drone status:
if not ilvo_drone_status["status"]:
    with st.form("Start drone"):
        st.header("Start the drone", divider="gray")
        environment = st.selectbox("Select environment", st.session_state.environments)
        projects = {
            project["name"]: project["id"]
            for project in st.session_state.database_api.get_project()
        }
        project_name = st.selectbox(
            "Select project",
            list(projects.keys()),
        )
        flight_name = st.text_input("Flight name")
        start = st.form_submit_button("Start")

        if start:
            if not flight_name:
                st.error("Flight name is required.")
                st.stop()
            if project_name is None:
                st.error("No projects.")
                st.stop()
            project_id = projects[project_name]
            try:
                flight_id = st.session_state.database_api.post_flight(
                    project_id=project_id,
                    flight_name=flight_name,
                    environment=environment,
                    timestamp_epoch=int(time.time()),
                )
            except RuntimeError as ex:
                st.error(f"Issue during flight creation: {ex}")
                st.stop()
            st.session_state.ilvo_drone.start(
                project_id=project_id,
                flight_id=flight_id,
                ads=environment,
            )
            time.sleep(1)
            st.rerun()
else:
    if "flight_id" in ilvo_drone_status:
        flight = st.session_state.database_api.get_flight(id=ilvo_drone_status["flight_id"])
    if "project_id" in ilvo_drone_status:
        project = st.session_state.database_api.get_project(id=ilvo_drone_status["project_id"])

    st.text(ilvo_drone_status)
    stop = st.button("Stop flight")
#    iframe_src = os.environ.get("GRAFANA_URL")
#    try:
#        st_components.iframe(iframe_src, height=1024, scrolling=True)
#    except Exception as e:
#        st.error(f"Unable to load the iframe: {e}")

    if stop:
        st.session_state.ilvo_drone.stop()
        time.sleep(5)
        st.rerun()
