from typing import Literal
from pydantic import BaseModel, Field, field_validator

Color = str


class SilhouetteOptions(BaseModel):
    image_data: str = Field(max_length=8_500_000)
    filename: str = Field(default="image.png", max_length=200)
    width_mm: float = Field(default=55, ge=10, le=300)
    thickness_mm: float = Field(default=3, ge=0.6, le=25)
    threshold: int = Field(default=140, ge=1, le=254)
    invert: bool = False
    mode: Literal["filled", "cutouts", "lines"] = "filled"
    smoothing_mm: float = Field(default=0.10, ge=0, le=2)
    attach_loop: bool = True
    loop_side: Literal["top", "bottom", "left", "right"] = "top"
    loop_position: float = Field(default=0.5, ge=0, le=1)
    loop_hole_mm: float = Field(default=5.0, ge=2, le=12)
    loop_wall_mm: float = Field(default=2.3, ge=1, le=6)
    color: Color = "#2c3439"

    @field_validator("color")
    @classmethod
    def valid_color(cls, value: str) -> str:
        if len(value) != 7 or value[0] != "#" or any(c not in "0123456789abcdefABCDEF" for c in value[1:]):
            raise ValueError("Color must be in #RRGGBB format")
        return value.upper()


class PlateOptions(BaseModel):
    text: str = Field(default="МОЙ БРЕЛОК", min_length=1, max_length=120)
    width_mm: float = Field(default=80, ge=20, le=300)
    height_mm: float = Field(default=32, ge=12, le=200)
    thickness_mm: float = Field(default=3, ge=0.8, le=25)
    shape: Literal["rounded", "rectangle", "oval", "circle", "hexagon"] = "rounded"
    corner_radius_mm: float = Field(default=6, ge=0, le=50)
    font: Literal["sans", "serif", "mono", "bold"] = "sans"
    font_size_mm: float = Field(default=8, ge=2, le=60)
    text_align: Literal["left", "center", "right"] = "center"
    line_spacing_mm: float = Field(default=1.5, ge=0, le=15)
    text_x_mm: float = Field(default=0, ge=-150, le=150)
    text_y_mm: float = Field(default=0, ge=-100, le=100)
    text_depth_mm: float = Field(default=0.8, ge=0.2, le=5)
    text_style: Literal["raised", "inlay", "engraved"] = "raised"
    base_color: Color = "#1E647D"
    text_color: Color = "#F8FBFA"

    @field_validator("base_color", "text_color")
    @classmethod
    def valid_color(cls, value: str) -> str:
        if len(value) != 7 or value[0] != "#" or any(c not in "0123456789abcdefABCDEF" for c in value[1:]):
            raise ValueError("Color must be in #RRGGBB format")
        return value.upper()


class GenerateRequest(BaseModel):
    kind: Literal["silhouette", "plate"]
    silhouette: SilhouetteOptions | None = None
    plate: PlateOptions | None = None


class MeshPart(BaseModel):
    name: str
    color: str
    vertices: list[list[float]]
    faces: list[list[int]]


class Preview(BaseModel):
    parts: list[MeshPart]
    size_mm: list[float]
    warnings: list[str]
