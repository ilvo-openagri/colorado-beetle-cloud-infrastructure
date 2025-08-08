from resources.database import load_database_connections
from s3 import MinioController
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
import datetime
import importlib
import os
import pandas as pd
import streamlit as st
import time
import traceback
import warnings

warnings.simplefilter(action="ignore", category=FutureWarning)


@st.dialog("Filter statistics")
def data_filter(api):
    # 1. Project:
    projects = set()
    projects.update([project["name"] for project in api.get_project()])
    project_selection = list(projects & set(st.session_state.data_filter["project"]))
    project_selection = st.multiselect("Select project", projects, project_selection)

    if st.button("Submit"):
        st.session_state.data_filter["project"] = project_selection
        st.rerun()


def event_submit_details():
    st.session_state.flight_selection = st.session_state.grid_selection.selected_rows


def event_flight_delete():
    st.session_state.delete_flight = st.session_state.grid_selection.selected_rows


# Initialise the session storage
if "init_statistics" not in st.session_state:
    st.session_state.database_api = load_database_connections()
    st.session_state.data_filter = {
        "environment": ["cloud", "edge"],
        "project": [],
    }
    st.session_state.minio_controller = MinioController(
        minio_url=os.environ.get("MINIO_URL"),
        access_key=os.environ.get("MINIO_ACCESS_KEY"),
        secret_key=os.environ.get("MINIO_SECRET_KEY"),
    )
    st.session_state.date_filter = {}
    st.session_state.init_statistics = 0
st.session_state.init_statistics += 1

if "flight_selection" in st.session_state:
    spec = importlib.util.spec_from_file_location("page", "pages/statistics_detail.py")
    page = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(page)
    page.run()  # Call the `run()` function in the loaded page module
    st.stop()

if "delete_flight" in st.session_state:
    for index in range(len(st.session_state["delete_flight"]["flight_id"])):
        # Delete the flight from the database:
        st.session_state.database_api.delete_flight(
            flight_id=st.session_state["delete_flight"]["flight_id"][index]
        )

        # Delete the flight from the S3 bucket:
        s3_filename = f"{st.session_state['delete_flight']['project_id'][index]}/{st.session_state['delete_flight']['flight_id'][index]}"
        st.session_state.minio_controller.delete_file(
            bucket_name=os.environ.get("MINIO_RAW_BUCKET"),
            object_name=s3_filename,
            recursive=True,
        )

    del st.session_state["delete_flight"]

# Filter:
filter_columns = st.columns([1, 1, 5])
# 1. Date filter
filter_min_date = datetime.datetime(2024, 10, 1)
filter_max_date = datetime.datetime.now()
st.session_state.date_filter = filter_columns[0].date_input(
    "Date input", (filter_min_date, filter_max_date), format="DD/MM/YYYY"
)
# 2. Data filter
filter_columns[1].write('<div style="height: 30px;"> </div>', unsafe_allow_html=True)
if filter_columns[1].button("Filter", icon=":material/filter_alt:"):
    data_filter(st.session_state.database_api)


# Get all the required data:
openagri_projects = []
try:
    for openagri_project in st.session_state.database_api.get_project_summary(
        relational_data=True,
        start=time.mktime(st.session_state.date_filter[0].timetuple()),
        end=time.mktime(st.session_state.date_filter[-1].timetuple()) + 24 * 60 * 60,
    ):
        if (
            st.session_state.data_filter["project"]
            and openagri_project["name"] not in st.session_state.data_filter["project"]
        ):
            continue
        openagri_projects.append(openagri_project)
except RuntimeError as ex:
    st.write(f"Error encountered while grabbing projects: {traceback.format_exc()}")

dataframe = pd.DataFrame(openagri_projects)
if openagri_projects:
    dataframe = dataframe.sort_values("timestamp_epoch", ascending=False)
    dataframe["timestamp_epoch"] = pd.to_datetime(
        dataframe["timestamp_epoch"], unit="s"
    )

grid_options = {
    "columnDefs": [
        {
            "headerName": "Timestamp",
            "field": "timestamp_epoch",
            "hide": False,
            "checkboxSelection": True,
        },
        {
            "headerName": "Environment",
            "field": "environment",
            "editable": False,
        },
        {
            "headerName": "Flight name",
            "field": "flight_name",
            "hide": False,
        },
        {
            "headerName": "Flight ID",
            "field": "flight_id",
            "hide": True,
        },
        {
            "headerName": "Project ID",
            "field": "project_id",
            "hide": True,
        },
        {
            "headerName": "Project name",
            "field": "name",
            "hide": False,
        },
        {
            "headerName": "#images",
            "field": "image_count",
            "hide": False,
        },
        {
            "headerName": "#detections",
            "field": "detection_count",
            "hide": False,
        },
        {
            "headerName": "#beetles",
            "field": "beetle_count",
            "hide": False,
        },
    ],
    "rowSelection": "multiple",
    "rowMultiSelectWithClick": False,
    "suppressRowDeselection": False,
    "suppressRowClickSelection": False,
    "groupSelectsChildren": False,
    "groupSelectsFiltered": True,
}

st.session_state.grid_selection = AgGrid(
    dataframe,
    grid_options,
    fit_columns_on_grid_load=True,
    update_mode=GridUpdateMode.SELECTION_CHANGED,
    reload_data=False,
)

button_columns = st.columns([0.06, 1])
with button_columns[0]:
    st.button(
        "View details",
        disabled=st.session_state.grid_selection.selected_rows is None or len(st.session_state.grid_selection.selected_rows) != 1,
        on_click=event_submit_details,
    )
with button_columns[1]:
    st.button(
        "Delete",
        disabled=st.session_state.grid_selection.selected_rows is None,
        on_click=event_flight_delete,
    )
