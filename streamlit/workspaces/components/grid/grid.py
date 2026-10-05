from database import OpenagriImage
from scipy.signal import convolve2d
from scipy.spatial import ConvexHull, QhullError
import json
import logging
import math
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyproj
import rotating_calipers as rc
import sys


def _interpolate(p1: tuple, p2: tuple, factor: float):
    lat = p1[0] + factor * (p2[0] - p1[0])
    lon = p1[1] + factor * (p2[1] - p1[1])
    return (float(lat), float(lon))


def _normalize(value, vmin=0, vmax=100):
    value = max(min(value, vmax), vmin)
    # Normalize the value to a range between 0 and 1
    return (value - vmin) / (vmax - vmin)


def _value_to_color(value, vmin=0, vmax=100):
    normalized_value = _normalize(value, vmin, vmax)

    # Interpolate between white and red
    r = 255  # Red stays 255
    g = int(255 * (1 - normalized_value))  # Green decreases from 255 to 0
    b = int(255 * (1 - normalized_value))  # Blue decreases from 255 to 0

    return "#{:02x}{:02x}{:02x}".format(r, g, b)


def _get_bounding_box(coordinates):
    hull = ConvexHull(coordinates)
    _, bounding_box = rc.smallest_rectangle(hull.points.tolist(), rc.compare_area)

    points_sorted_longitude = sorted(bounding_box, key=lambda point: point[0])
    left_points = sorted(points_sorted_longitude[0:2], key=lambda point: point[1])
    right_points = sorted(points_sorted_longitude[2:4], key=lambda point: point[1])
    return {
        "bottom_left": left_points[0],
        "top_left": left_points[1],
        "bottom_right": right_points[0],
        "top_right": right_points[1],
    }


def _get_bounding_box_grid(bound_box: dict, num_rows: int, num_cols: int):
    # Generate evenly spaced interpolation factors
    row_factors = np.linspace(0, 1, num_rows + 1)
    col_factors = np.linspace(0, 1, num_cols + 1)

    # Determine the grid points
    grid_points = []
    for row_index, row_factor in enumerate(row_factors):
        grid_points.append([])
        # Interpolate along the left and right edges to get the intermediate "vertical" points
        left_point = _interpolate(
            bound_box["bottom_left"], bound_box["top_left"], row_factor
        )
        right_point = _interpolate(
            bound_box["bottom_right"], bound_box["top_right"], row_factor
        )

        # Now interpolate horizontally between the left and right points
        for col_factor in col_factors:
            grid_points[row_index].append(
                _interpolate(left_point, right_point, col_factor)
            )
    return np.array(grid_points)


def _get_grid_geojson(grid_values: np.ndarray, grid_cells: np.ndarray):
    # Determine the grid polygons
    features = []
    vmax = min(10, max(1, np.amax(grid_values) if len(grid_values) != 0 else 0))
    for row in range(len(grid_cells) - 1):
        for column in range(len(grid_cells[0]) - 1):

            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [
                                    grid_cells[row][column][1],
                                    grid_cells[row][column][0],
                                ],
                                [
                                    grid_cells[row + 1][column][1],
                                    grid_cells[row + 1][column][0],
                                ],
                                [
                                    grid_cells[row + 1][column + 1][1],
                                    grid_cells[row + 1][column + 1][0],
                                ],
                                [
                                    grid_cells[row][column + 1][1],
                                    grid_cells[row][column + 1][0],
                                ],
                                [
                                    grid_cells[row][column][1],
                                    grid_cells[row][column][0],
                                ],
                            ]
                        ],
                    },
                    "properties": {
                        "stroke": "#ff0000",
                        "stroke-width": 2,
                        "stroke-opacity": 1,
                        "fill": _value_to_color(
                            value=grid_values.loc[row, column],
                            vmax=vmax,
                        ),
                        "fill-opacity": 0.5,
                        "value_normalized": _normalize(
                            value=grid_values.loc[row, column],
                            vmax=vmax,
                        ),
                    },
                }
            )

    return features


def _calculate_grid(
    input_data: list[OpenagriImage],
    bounding_box: dict,
    num_rows: int,
    num_cols: int,
) -> pd.DataFrame:
    logger = logging.getLogger("_calculate_grid")

    df = pd.DataFrame(0, index=range(num_rows), columns=range(num_cols))
    df_count = pd.DataFrame(0, index=range(num_rows), columns=range(num_cols))

    # Vector along the top edge (columns) and vector along the left edge (rows)
    vec_bottom = np.array(bounding_box["bottom_right"]) - np.array(
        bounding_box["bottom_left"]
    )
    vec_left = np.array(bounding_box["top_left"]) - np.array(
        bounding_box["bottom_left"]
    )

    # Step 2: Create normalized vectors
    vec_bottom_norm = vec_bottom / np.linalg.norm(vec_bottom)
    vec_left_norm = vec_left / np.linalg.norm(vec_left)

    # Step 3: Calculate the total grid length along the top and left vectors
    bottom_length = np.linalg.norm(vec_bottom)
    left_length = np.linalg.norm(vec_left)

    for entry in input_data:
        coordinate = entry.utm_coordinate
        # Step 4: Find the relative position of the point in the grid's coordinate system
        point_vec = np.array(coordinate[0:2]) - np.array(bounding_box["bottom_left"])

        proj_onto_bottom = np.dot(
            point_vec, vec_bottom_norm
        )  # Projection onto the top vector
        proj_onto_left = np.dot(
            point_vec, vec_left_norm
        )  # Projection onto the left vector

        # Step 5: Calculate the column and row indices (fractional values)
        col_position = proj_onto_bottom / bottom_length
        row_position = proj_onto_left / left_length

        # Step 6: Convert to integer grid indices
        col_index = int(col_position * num_cols)
        row_index = int(row_position * num_rows)

        # Ensure indices are within bounds
        col_index = max(0, min(col_index, num_cols - 1))
        row_index = max(0, min(row_index, num_rows - 1))

        df.loc[row_index, col_index] += len(entry.detections)
        if entry.model_runtime > 0:
            df.loc[row_index, col_index] += 0.5
        df_count.loc[row_index, col_index] += 1
    df = (df / df_count).replace(np.inf, np.nan).fillna(0)
    return df


def _data_2_geojson(
    openagri_images: list[OpenagriImage],
    grid_values: list,
    grid_cells: list,
) -> dict:
    logger = logging.getLogger("_data_2_geojson")
    geo_json = {"type": "FeatureCollection", "features": []}

    grid_features = _get_grid_geojson(grid_values, grid_cells)
    geo_json["features"].extend(grid_features)

    for openagri_image in openagri_images:
        geo_json["features"].append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        openagri_image.gps_coordinate[1],
                        openagri_image.gps_coordinate[0],
                    ],
                },
                "properties": {
                    "image_id": openagri_image.image_id,
                    "number_beetles": len(openagri_image.detections),
                    "latitude": f"{openagri_image.gps_coordinate[1]:.10f}",
                    "longitude": f"{openagri_image.gps_coordinate[0]:.10f}",
                    "radius": 0.2,
                },
            }
        )

    multilinestring = []
    for index in range(0, len(openagri_images) - 1):
        point_a = openagri_images[index].gps_coordinate
        point_b = openagri_images[index + 1].gps_coordinate
        multilinestring.append(
            [
                [
                    point_a[1],
                    point_a[0],
                ],
                [
                    point_b[1],
                    point_b[0],
                ],
            ]
        )
    if multilinestring:
        geo_json["features"].append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "MultiLineString",
                    "coordinates": multilinestring,
                },
                "properties": {
                    "strokeColor": "#FF0000",
                    "stroke": "#ff0000",
                    "stroke-width": 10,
                    "stroke-opacity": 1,
                },
            }
        )

    return geo_json


def create_grid(input_data: list[OpenagriImage], cell_size: int = 5):
    logger = logging.getLogger("create_grid")

    try:
        utm_bounding_box = _get_bounding_box([x.utm_coordinate for x in input_data])
    except QhullError as e:
        raise ValueError(
            "At least 3 unique coordinates are required to form a grid."
        ) from e

    bounding_box_width = math.dist(
        utm_bounding_box["bottom_left"], utm_bounding_box["bottom_right"]
    )
    bounding_box_height = math.dist(
        utm_bounding_box["bottom_left"], utm_bounding_box["top_left"]
    )
    rows = math.ceil(bounding_box_height / cell_size)
    cols = math.ceil(bounding_box_width / cell_size)
    grid_values = _calculate_grid(input_data, utm_bounding_box, rows, cols)
    utm_grid_cells = _get_bounding_box_grid(utm_bounding_box, rows, cols)

    # Convert back to GPS:
    transformer_to_gps = pyproj.Transformer.from_crs(
        "EPSG:31370", "EPSG:4326", always_xy=True
    )
    # - Bounding box
    bounding_box = {}
    for entry, value in utm_bounding_box.items():
        bounding_box[entry] = transformer_to_gps.transform(*value)[::-1]

    # - Grid cells:
    grid_cells = []
    for row_index, row in enumerate(utm_grid_cells):
        grid_cells.append([])
        for cell in row:
            grid_cells[row_index].append(transformer_to_gps.transform(*cell)[::-1])

    return _data_2_geojson([], grid_values, grid_cells)


def create_path(input_data: list[OpenagriImage]):
    return _data_2_geojson(input_data, [], [])


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        format="[%(levelname)s %(name)s @ %(asctime)s] %(message)s", level=logging.DEBUG
    )
    logger = logging.getLogger(__name__)

    coordinates = [
        (50.98009862118664, 3.7744574614539084, 1),
        (50.98070542382654, 3.7753757714077687, 5),
        (50.9802965490995, 3.7764843618025186, 15),
        (50.979387636330166, 3.77505312196452, 21),
    ]

    geo_json_data = create_grid(coordinates, cell_size=30)
    readable_result = json.dumps(geo_json_data, indent=2)
    if False:
        logger.info(readable_result)
