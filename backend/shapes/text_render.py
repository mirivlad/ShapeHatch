"""Turn Cyrillic-capable text into 2D polygons at print scale."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely import affinity

from .image_trace import polygons_from_mask
from .schemas import PlateOptions

FONT_PATHS = {
    "sans": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "bold": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "mono": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "serif": "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
}
PIXELS_PER_MM = 8


def text_geometry(options: PlateOptions):
    font_size = max(8, round(options.font_size_mm * PIXELS_PER_MM))
    font = ImageFont.truetype(FONT_PATHS[options.font], font_size)
    bounds = font.getbbox(options.text, stroke_width=0)
    tw = bounds[2] - bounds[0]
    th = bounds[3] - bounds[1]
    if not tw or not th:
        raise ValueError("Введите непустую надпись.")
    if tw > 8000 or th > 1000:
        raise ValueError("Надпись слишком большая.")
    img = Image.new("L", (tw + 16, th + 16), 0)
    draw = ImageDraw.Draw(img)
    draw.text((8 - bounds[0], 8 - bounds[1]), options.text, font=font, fill=255)
    mask = np.asarray(img) >= 100
    ink = polygons_from_mask(mask, preserve_holes=True)
    # Pixel-space image has Y-down coordinates; polygons_from_mask already flips Y.
    ink = affinity.scale(ink, xfact=1/PIXELS_PER_MM, yfact=1/PIXELS_PER_MM, origin=(0, 0))
    min_x, min_y, max_x, max_y = ink.bounds
    ink = affinity.translate(ink,
            xoff=options.text_x_mm - (min_x + max_x)/2,
            yoff=options.text_y_mm - (min_y + max_y)/2)
    # Simplify fine font curves before constrained triangulation.
    return ink.simplify(0.045, preserve_topology=True)
