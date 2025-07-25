import dataclasses
import pyproj


@dataclasses.dataclass
class OpenagriImage:
    gps_coordinate: tuple
    image_id: int
    number_beetles: int = 0
    model_runtime: float = 0.0
    s3_location: str = ""
    detections: list = dataclasses.field(default_factory=list)

    def __post_init__(self):
        self._transformer_to_utm = pyproj.Transformer.from_crs(
            "EPSG:4326", "EPSG:31370", always_xy=True
        )

    @property
    def utm_coordinate(self) -> tuple:
        return self._transformer_to_utm.transform(
            self.gps_coordinate[1], self.gps_coordinate[0]
        )

    def dict(self):
        return {k: str(v) for k, v in dataclasses.asdict(self).items()}
