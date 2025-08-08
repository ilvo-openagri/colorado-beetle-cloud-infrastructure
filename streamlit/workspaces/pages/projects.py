from resources.database import load_database_connections
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
import pandas as pd
import streamlit as st



# Initialise the session storage
if "runs" not in st.session_state:
    st.session_state.database_api = load_database_connections()
    st.session_state.data_filter = {
        "environment": ["cloud", "edge"],
        "project": [],
    }
    st.session_state.runs = 0
st.session_state.runs += 1

# Get all the required data:
openagri_projects = []
try:
    for openagri_project in st.session_state.database_api.get_project():
        openagri_projects.append(openagri_project)
except RuntimeError as error:
    st.error(f"Error fetching projects: {error}")
    st.stop()
            
# Prepare grid:
dataframe = pd.DataFrame(openagri_projects)
grid_options = {
    "columnDefs": [
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
    if st.button("Create project"):
        st.write("Creating project...")
        project_name = project_name.strip()
        if project_name:
            try:
                st.session_state.database_api.post_project(name=project_name)
            except RuntimeError as error:
                st.error(f"Error creating project: {error}")
                st.stop()
            st.success("Project created successfully.")
            st.rerun()
        else:
            st.error("Project name cannot be empty.")