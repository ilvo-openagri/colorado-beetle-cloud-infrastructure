from components.grid import create_grid
from dotenv import load_dotenv
from database import DatabaseApi, OpenagriImage
from resources.database import load_database_connections
import datetime
import folium
import os
import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit_folium as stf
import time


@st.cache_resource
def load_basemaps() -> dict:
    return {
        "Google Maps": folium.TileLayer(
            tiles="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
            attr="Google",
            name="Google Maps",
            overlay=True,
            control=True,
        ),
        "Google Satellite": folium.TileLayer(
            tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
            attr="Google",
            name="Google Satellite",
            overlay=True,
            control=True,
            max_zoom=100,
            max_native_zoom=18,
        ),
        "Google Terrain": folium.TileLayer(
            tiles="https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}",
            attr="Google",
            name="Google Terrain",
            overlay=True,
            control=True,
        ),
        "Google Satellite Hybrid": folium.TileLayer(
            tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
            attr="Google",
            name="Google Satellite",
            overlay=True,
            control=True,
        ),
        "Esri Satellite": folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri",
            name="Esri Satellite",
            overlay=True,
            control=True,
        ),
    }


def fetch_data(
    database_connection: DatabaseApi, project_id: int, flight_id: int
) -> list[OpenagriImage]:
    """Fetch the required data to generate the OpenAgri visualisation

    Args:
        project_id (int): Project ID
        flight_id (int): flight ID

    Returns:
        list[GridInputData]: A list containing input data for visualisation
    """
    images = database_connection.get_images(flight_id)
    if not images:
        return []

    data = []
    for image in images:
        gps_location = image["gps_location"][1:-1].split(",")
        gps_location = [float(entry) for entry in gps_location]
        if ("model_runtime" not in image) or (image["model_runtime"] is None):
            image["model_runtime"] = -1.0
        data.append(
            OpenagriImage(
                image_id=image["id"],
                gps_coordinate=gps_location,
                number_beetles=float(image["detection_count"]),
                model_runtime=float(image["model_runtime"]),
            )
        )

    return sorted(data, key=lambda x: x.image_id)


def _style_function(feature):
    geometry_type = feature["geometry"]["type"]
    if geometry_type == "MultiLineString":
        return {
            "color": "blue",
            "weight": 1,
            "opacity": 0.7,  # Set opacity for LineString
            "dashArray": "5, 10",  # Dash pattern for the line
        }
    else:
        return {
            "fillColor": feature["properties"].get(
                "fill", "#228B22"
            ),  # Default green if not set
            "color": "#000000",  # Set the border color (black)
            "weight": 2,  # Set the border width
            "fillOpacity": 0.6,  # Set the transparency of the fill color
        }


def create_map(input_data):
    farm_map = folium.Map()
    basemaps["Google Satellite"].add_to(farm_map)
    folium.GeoJson(
        create_grid(input_data, 15),
        style_function=_style_function,
        marker=folium.Circle(radius=0.33, fill_color="grey", fill_opacity=0.4),
    ).add_to(farm_map)
    farm_map.fit_bounds(farm_map.get_bounds(), padding=(30, 30))
    # farm_map_data = stf.folium_static(farm_map, width=1024)
    return farm_map


def visualise(map_placeholder):
    with map_placeholder:
        left, right = st.columns(2)
        with left:
            stf.folium_static(create_map(st.session_state.data))
        with right:
            data = {
                "Category": [],
                "Value [s]": [],
            }
            for image in st.session_state.data:
                if image.model_runtime <= 0.0:
                    continue
                data["Category"].append("Execution time")
                data["Value [s]"].append(image.model_runtime)
            df = pd.DataFrame(data)

            # Create a boxplot using Plotly
            fig = px.box(
                df,
                y="Value [s]",
                title=f"Model [{st.session_state.openagri_environment}] execution time",
            )

            # Display the boxplot in Streamlit
            st.plotly_chart(fig)


# st.set_page_config(layout="wide")

# Load the dotenv file:
load_dotenv(".env")

# Using object notation
add_selectbox = st.sidebar.selectbox(
    "How would you like to be contacted?", ("Email", "Home phone", "Mobile phone")
)
with st.sidebar:
    add_radio = st.radio(
        "Choose a shipping method", ("Standard (5-15 days)", "Express (2-5 days)")
    )
"""
# OpenAgri - SIP3
Welcome to the OpenAgri Streamlit interface for SIP3
"""
# Load dependencies:
database_api = load_database_connections(["cloud", "edge"])
openagri_environments = list(database_api.keys())
basemaps = load_basemaps()

# Give the user some choice:
# - Environment:
if len(openagri_environments) == 0:
    st.error(
        "No database connection available. Please check your environment variables."
    )
    st.stop()

if "openagri_environment" not in st.session_state:
    st.session_state.openagri_environment = openagri_environments[-1]
st.session_state.openagri_environment = st.selectbox(
    "Select cloud/edge",
    openagri_environments,
    index=openagri_environments.index(st.session_state.openagri_environment),
)

# - Projects:
openagri_projects = {
    project["name"]: project["id"]
    for project in database_api[st.session_state.openagri_environment].get_project()
}

if len(openagri_projects) == 0:
    st.error("No projects available. Please create a project first.")
    st.stop()

if "openagri_project" not in st.session_state:
    st.session_state.openagri_project = list(openagri_projects.keys())[0]
st.session_state.openagri_project = st.selectbox(
    "Select a project",
    list(openagri_projects.keys()),
    index=list(openagri_projects.keys()).index(st.session_state.openagri_project),
)

# - flights:
openagri_flights = dict(
    sorted(
        {
            flight["timestamp_epoch"]: flight["id"]
            for flight in database_api[
                st.session_state.openagri_environment
            ].get_flight(
                project_id=openagri_projects[st.session_state.openagri_project]
            )
        }.items(),
        reverse=True,
    )
)
if "openagri_flight" not in st.session_state:
    st.session_state.openagri_flight = list(openagri_flights.keys())[0]
st.session_state.openagri_flight = st.selectbox(
    "Select a flight",
    list(openagri_flights.keys()),
    format_func=lambda x: datetime.datetime.fromtimestamp(x).strftime(
        "%d-%m-%Y %H:%M:%S"
    ),
    index=list(openagri_flights.keys()).index(st.session_state.openagri_flight),
)

# Apply!
if st.button("Apply"):
    map_placeholder = st.empty()
    st.session_state.data = None

    while True:
        new_data = fetch_data(
            database_connection=database_api[st.session_state.openagri_environment],
            project_id=openagri_projects[st.session_state.openagri_project],
            flight_id=openagri_flights[st.session_state.openagri_flight],
        )
        if not new_data:
            continue
        if new_data != st.session_state.data:  # Check if data has changed
            st.session_state.data = new_data  # Update session state
            visualise(map_placeholder)
            # st.table(
            # pd.DataFrame.from_records([s.dict() for s in st.session_state.data])
            # )

        time.sleep(2)  # Wait for 10 seconds before checking for new data
