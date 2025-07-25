import dataclasses
import pyproj


@dataclasses.dataclass
class OpenagriDetection:
    id: int
    image_id: int
    confidence: float = 0.0
    position: tuple = (
        0,
        0,
    )
    s3_location: str = ""

    def __post_init__(self):
        pass

    # @property
    # def utm_coordinate(self) -> tuple:
    #     return self._transformer_to_utm.transform(
    #         self.gps_coordinate[1], self.gps_coordinate[0]
    #     )

    def dict(self):
        return {k: str(v) for k, v in dataclasses.asdict(self).items()}
