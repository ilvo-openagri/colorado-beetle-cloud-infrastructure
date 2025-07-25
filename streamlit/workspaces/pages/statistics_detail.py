from components.grid import create_grid, create_path
from database import DatabaseApi, OpenagriImage, OpenagriDetection
from PIL import Image, ImageDraw
import folium
import minio
import pandas as pd
import time
import plotly.express as px
import streamlit as st
import streamlit_folium as stf


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


@st.cache_resource
def get_minio_client():
    # Creates a Minio S3 client
    return {
        "edge": minio.Minio(
            endpoint="192.168.30.1:9000",
            access_key="OpenagriDrone",
            secret_key="i4wjQvNvb4D7RHc",
            secure=False,
            region="us-east-1",
        ),
        "cloud": minio.Minio(
            endpoint="172.17.150.112:9000",
            access_key="OpenagriWebserver",
            secret_key="pqWkT+gax9hP-9L",
            secure=False,
            region="us-east-1",
        ),
    }


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
            "radius": feature["properties"].get("radiius", 1),
        }


def create_map(input_data) -> folium.Map:
    farm_map = folium.Map()
    # Add CSS for auto-scaling
    st.markdown(
        """
        <style>
            iframe {
                width: 100%;
                min-height: 750px;
                height: 100%:
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    basemaps = load_basemaps()
    basemaps["Google Satellite"].add_to(farm_map)

    folium.GeoJson(
        create_grid(input_data, 15),
        style_function=_style_function,
        marker=folium.Circle(radius=0.33, fill_color="grey", fill_opacity=0.4),
    ).add_to(farm_map)
    folium.GeoJson(
        create_path(input_data),
        style_function=_style_function,
        marker=folium.Circle(radius=0.33, fill_color="grey", fill_opacity=0.4),
        tooltip=folium.features.GeoJsonTooltip(
            fields=["image_id", "number_beetles", "latitude", "longitude"],
            aliases=["Image ID:", "Number of beetles:", "Latitude", "Longitude"],
            localize=True,
            labels=True,
            sticky=False,
        ),
    ).add_to(farm_map)
    farm_map.fit_bounds(farm_map.get_bounds())
    return farm_map


@st.fragment
def visualise(map_placeholder, statistics: list):
    tabs = map_placeholder.tabs(["Map", "Statistics"])
    selected_flight = st.session_state.flight_selection.iloc[0]
    with tabs[0]:
        left, right = st.columns([1, 1])
        with left:
            map = create_map(statistics)
            map_output = stf.st_folium(map, width=1024)
        with right:
            if (
                map_output["last_active_drawing"] is not None
                and map_output["last_active_drawing"]["geometry"]["type"] == "Point"
            ):

                drone_image = "static/drone_image.jpg"
                drone_image_annotated = "static/drone_image_annotated.jpg"
                image_id = map_output["last_active_drawing"]["properties"]["image_id"]
                if (
                    "last_image_id" not in st.session_state
                    or image_id != st.session_state.last_image_id
                ):
                    # Download the selected image
                    st.session_state.last_image_id = image_id
                    image = list(
                        filter(
                            lambda x: x.image_id == image_id,
                            st.session_state.statistics_detailed,
                        )
                    ).pop()
                    minio_client = get_minio_client()[selected_flight["environment"]]
                    minio_client.fget_object(
                        bucket_name="openagri-raw-images",
                        object_name=image.s3_location,
                        file_path=drone_image,
                    )

                    with Image.open(drone_image) as im:
                        draw = ImageDraw.Draw(im)
                        for detection in image.detections:
                            draw.rectangle(
                                [
                                    (
                                        detection.position[0] - 32,
                                        detection.position[1] - 32,
                                    ),
                                    (
                                        detection.position[0] + 32,
                                        detection.position[1] + 32,
                                    ),
                                ],
                                outline="red",
                                width=5,
                            )
                        im.save(drone_image_annotated)
                    # st.write(image.detections)

                # Display the image using `st.markdown`
                st.markdown(
                    f"""
                    <a href="app/{drone_image_annotated}?{int(time.time())}" target="_blank">
                        <img src="app/{drone_image_annotated}?{int(time.time())}" width="100%">
                    </a>
                    """,
                    unsafe_allow_html=True,
                )

    with tabs[1]:
        data = {
            "Category": [],
            "Value [s]": [],
        }
        for image in statistics:
            if image.model_runtime <= 0.0:
                continue
            data["Category"].append("Execution time")
            data["Value [s]"].append(image.model_runtime)
        df = pd.DataFrame(data)

        # Create a boxplot using Plotly
        fig = px.box(
            df,
            y="Value [s]",
            title=f"Model [{selected_flight['environment']}] execution time",
            height=750,
        )

        # Display the boxplot in Streamlit
        st.plotly_chart(fig, height=750)


def fetch_images(
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
                s3_location=image["storage_location"],
                detections=[
                    OpenagriDetection(
                        id=detection["id"],
                        image_id=detection["image_id"],
                        confidence=detection["confidence"],
                        position=list(map(int, detection["position"][1:-1].split(","))),
                        s3_location=detection["storage_location"],
                    )
                    for detection in database_connection.get_detections(image["id"])
                ],
            )
        )

    return sorted(data, key=lambda x: x.image_id)


def event_back():
    """Event triggered when user presses the back button"""
    del st.session_state["flight_selection"]
    del st.session_state["init_stats"]
    del st.session_state["last_image_id"]


def event_live_toggle():
    """Event triggered when user togggles the live updates"""
    st.session_state.init_stats = True


def run():
    st.session_state.statistics_detailed = []

    # Header
    header_columns = st.columns([1, 5, 1])
    header_columns[0].button(
        "Back",
        icon=":material/arrow_back:",
        on_click=event_back,
    )
    live_updates = header_columns[2].toggle(
        "Live updates", value=False, on_change=event_live_toggle
    )
    selected_flight = st.session_state.flight_selection.iloc[0]

    # Metric cards:
    metrics_placeholder = st.empty()
    map_placeholder = st.empty()

    if "init_stats" not in st.session_state:
        st.session_state.init_stats = True

    while live_updates or st.session_state.init_stats:
        new_data = fetch_images(
            database_connection=st.session_state.database_api[
                selected_flight["environment"]
            ],
            project_id=selected_flight["project_id"],
            flight_id=selected_flight["flight_id"],
        )

        if (
            new_data != st.session_state.statistics_detailed
        ):  # Check if data has changed
            if not st.session_state.statistics_detailed:
                st.session_state.statistics_detailed = new_data
            # Metric cards:
            with metrics_placeholder:
                n_images = (
                    len(new_data),
                    len(st.session_state.statistics_detailed),
                )
                n_beetles = (
                    int(sum([entry.number_beetles for entry in new_data])),
                    int(
                        sum(
                            [
                                entry.number_beetles
                                for entry in st.session_state.statistics_detailed
                            ]
                        )
                    ),
                )
                metrics = metrics_placeholder.columns(4)
                metrics[0].metric(
                    "Project",
                    f"{selected_flight['name']} [{selected_flight['flight_id']}]",
                    border=True,
                )
                metrics[1].metric(
                    "Time", selected_flight["timestamp_epoch"], border=True
                )
                metrics[2].metric("Images with beetles", *n_images, border=True)
                metrics[3].metric("Detected colorado beetles", *n_beetles, border=True)

            # Map + statistics
            visualise(map_placeholder, new_data)

            st.session_state.statistics_detailed = new_data  # Update session state
        st.session_state.init_stats = False
        # time.sleep(5)
