from typing import Literal
from pydantic import BaseModel, Field, field_validator

Color = str


class InnerContourOption(BaseModel):
    id: str = Field(pattern=r"^inner-[0-9]+$", max_length=20)
    fill: Literal["same", "other", "empty"] = "same"
    color: Color = "#F26C50"

    @field_validator("color")
    @classmethod
    def valid_color(cls, value: str) -> str:
        if len(value) != 7 or value[0] != "#" or any(c not in "0123456789abcdefABCDEF" for c in value[1:]):
            raise ValueError("Color must be in #RRGGBB format")
        return value.upper()


class InnerContourPreview(BaseModel):
    id: str
    points: list[list[float]]
    fill: Literal["same", "other", "empty"]


class MagnetPosition(BaseModel):
    x_mm: float = Field(ge=-150, le=150)
    y_mm: float = Field(ge=-150, le=150)


class MagnetSettings(BaseModel):
    shape: Literal["round", "rectangle"] = "round"
    diameter_mm: float = Field(default=6.0, ge=2, le=30)
    width_mm: float = Field(default=10.0, ge=2, le=50)
    height_mm: float = Field(default=5.0, ge=2, le=50)
    depth_mm: float = Field(default=2.0, ge=0.5, le=10)
    clearance_mm: float = Field(default=0.2, ge=0, le=1)
    positions: list[MagnetPosition] = Field(default_factory=lambda: [MagnetPosition(x_mm=0,y_mm=0)], max_length=8)


class PictureSettings(BaseModel):
    image_data: str = Field(default="", max_length=8_500_000)
    filename: str = Field(default="", max_length=200)
    algorithm: Literal["nearest", "median", "kmeans", "floyd"] = "median"
    color_count: int = Field(default=4, ge=2, le=16)
    resolution: int = Field(default=48, ge=16, le=96)
    filament_palette: list[Color] = Field(default_factory=list, max_length=16)
    color_overrides: list[Color] = Field(default_factory=list, max_length=16)
    width_mm: float = Field(default=45, ge=5, le=280)
    x_mm: float = Field(default=0, ge=-150, le=150)
    y_mm: float = Field(default=0, ge=-100, le=100)
    layer_mm: float = Field(default=0.4, ge=0.2, le=2)

    @field_validator("filament_palette", "color_overrides")
    @classmethod
    def colors_ok(cls, palette: list[str]) -> list[str]:
        result = []
        for color in palette:
            if len(color)!=7 or color[0]!="#" or any(ch not in "0123456789ABCDEFabcdef" for ch in color[1:]):
                raise ValueError("Colors must be #RRGGBB")
            result.append(color.upper())
        return result


class SilhouetteOptions(BaseModel):
    image_data: str = Field(max_length=8_500_000)
    filename: str = Field(default="image.png", max_length=200)
    width_mm: float = Field(default=55, ge=10, le=300)
    thickness_mm: float = Field(default=3, ge=0.6, le=25)
    threshold: int = Field(default=140, ge=1, le=254)
    invert: bool = False
    mode: Literal["filled", "cutouts", "lines"] = "filled"
    smoothing_mm: float = Field(default=0.10, ge=0, le=2)
    top_round_mm: float = Field(default=0.3, ge=0, le=0.4)
    inlay_depth_mm: float = Field(default=0.8, ge=0.2, le=5)
    inner_contours: list[InnerContourOption] = Field(default_factory=list, max_length=24)
    attach_loop: bool = True
    mount_type: Literal["none", "hole", "loop", "upright", "magnets"] | None = None
    magnets: MagnetSettings = Field(default_factory=MagnetSettings)
    loop_side: Literal["top", "bottom", "left", "right"] = "top"
    loop_orientation: Literal["flat", "upright"] = "flat"
    loop_contour_t: float | None = Field(default=None, ge=0, le=1)
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
    top_round_mm: float = Field(default=0.3, ge=0, le=0.4)
    mount_type: Literal["none", "hole", "loop", "upright", "magnets"] = "none"
    magnets: MagnetSettings = Field(default_factory=MagnetSettings)
    content_type: Literal["text", "image"] = "text"
    picture: PictureSettings = Field(default_factory=PictureSettings)
    mount_contour_t: float | None = Field(default=None, ge=0, le=1)
    mount_side: Literal["top", "bottom", "left", "right"] = "top"
    mount_position: float = Field(default=0.5, ge=0, le=1)
    mount_hole_mm: float = Field(default=5.0, ge=2, le=12)
    mount_wall_mm: float = Field(default=2.3, ge=1, le=6)
    font: Literal["sans", "serif", "mono", "bold", "russo", "play", "pt-sans", "lobster", "rubik-mono", "unbounded", "comfortaa", "terminus"] = "sans"
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
    mount_contour: list[list[float]] = Field(default_factory=list)
    mount_fraction: float | None = None
    mount_surface_z: float = 0.0
    text_bounds_mm: list[float] | None = None
    text_surface_z: float = 0.0
    inner_contours: list[InnerContourPreview] = Field(default_factory=list)
    image_preview_url: str | None = None
    image_palette: list[str] = Field(default_factory=list)
    magnet_positions: list[list[float]] = Field(default_factory=list)
    magnet_surface_z: float = 0.0
