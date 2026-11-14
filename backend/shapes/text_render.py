"""Turn Cyrillic-capable text into 2D polygons at print scale."""
from pathlib import Path
from functools import lru_cache
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely import affinity

from .image_trace import polygons_from_mask
from .schemas import PlateOptions

BUNDLED = Path(__file__).resolve().parent.parent / "fonts"

FONT_PATHS = {
    "sans": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "bold": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "mono": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "serif": "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "russo": BUNDLED / "russo.ttf",
    "play": BUNDLED / "play.ttf",
    "pt-sans": BUNDLED / "pt-sans.ttf",
    "lobster": BUNDLED / "lobster.ttf",
    "rubik-mono": BUNDLED / "rubik-mono.ttf",
    "unbounded": BUNDLED / "unbounded.ttf",
    "comfortaa": BUNDLED / "comfortaa.ttf",
    "terminus": BUNDLED / "terminus.ttf",
}
PIXELS_PER_MM = 8


@lru_cache(maxsize=24)
def _text_cached(content: str, font: str, font_size_mm: float,
                 line_spacing_mm: float, text_align: str,
                 text_x_mm: float, text_y_mm: float):
    # Only layout parameters participate in text regeneration.
    options=PlateOptions(text=content,font=font,font_size_mm=font_size_mm,
        line_spacing_mm=line_spacing_mm,text_align=text_align,
        text_x_mm=text_x_mm,text_y_mm=text_y_mm)
    return _text_geometry_uncached(options)


def text_geometry(options: PlateOptions):
    return _text_cached(options.text,options.font,options.font_size_mm,
                        options.line_spacing_mm,options.text_align,
                        options.text_x_mm,options.text_y_mm)


def _text_geometry_uncached(options: PlateOptions):
    # Preserve intentional line breaks; Windows and classic Mac pasted text are normalized.
    content = options.text.replace("\r\n", "\n").replace("\r", "\n")
    if not content.strip():
        raise ValueError("Введите непустую надпись.")
    font_size = max(8, round(options.font_size_mm * PIXELS_PER_MM))
    font = ImageFont.truetype(FONT_PATHS[options.font], font_size)
    spacing = round(options.line_spacing_mm * PIXELS_PER_MM)
    measure = ImageDraw.Draw(Image.new("L", (1, 1), 0))
    bounds = measure.multiline_textbbox(
        (0, 0), content, font=font, spacing=spacing, align=options.text_align)
    tw = int(np.ceil(bounds[2] - bounds[0]))
    th = int(np.ceil(bounds[3] - bounds[1]))
    if tw <= 0 or th <= 0:
        raise ValueError("Введите непустую надпись.")
    if tw > 8000 or th > 8000:
        raise ValueError("Надпись слишком большая.")
    img = Image.new("L", (tw + 16, th + 16), 0)
    draw = ImageDraw.Draw(img)
    draw.multiline_text(
        (8 - bounds[0], 8 - bounds[1]), content, font=font,
        spacing=spacing, align=options.text_align, fill=255)
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
