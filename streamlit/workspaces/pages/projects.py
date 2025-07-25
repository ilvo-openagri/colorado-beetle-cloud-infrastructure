from resources.database import load_database_connections
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
import pandas as pd
import streamlit as st



# Initialise the session storage
if "runs" not in st.session_state:
    st.session_state.database_api = load_database_connections(["cloud", "edge"])
    st.session_state.data_filter = {
        "environment": list(st.session_state.database_api.keys()),
        "project": [],
    }
    st.session_state.runs = 0
st.session_state.runs += 1

# Get all the required data:
openagri_projects = []
for openagri_environment in st.session_state.data_filter["environment"]:
    for openagri_project in st.session_state.database_api[
        openagri_environment
    ].get_project():
        openagri_project["environment"] = openagri_environment
        openagri_projects.append(openagri_project)
        
# Prepare grid:
dataframe = pd.DataFrame(openagri_projects)
grid_options = {
    "columnDefs": [
        {
            "headerName": "Environment",
            "field": "environment",
            "editable": False,
        },
        {
            "headerName": "ID",
            "field": "id",
            "hide": False,
        },
        {
            "headerName": "Project name",
            "field": "name",
            "hide": False,
        },
    ],
    "rowSelection": "single",
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

# Add project:
with st.popover("Create new project"):
    st.write("Create a new project")
    project_name = st.text_input("Project name")
    environment = st.selectbox(
        "Select environment",
        st.session_state.data_filter["environment"],
        key="environment",
    )
    if st.button("Create project"):
        st.write("Creating project...")
        project_name = project_name.strip()
        if project_name:
            try:
                st.session_state.database_api[environment].post_project(name=project_name)
            except RuntimeError as error:
                st.error(f"Error creating project: {error}")
                st.stop()
            st.success("Project created successfully.")
            st.rerun()
        else:
            st.error("Project name cannot be empty.")