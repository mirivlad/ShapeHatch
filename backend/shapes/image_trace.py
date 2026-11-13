"""Safe raster/SVG import and polygon extraction in millimetres."""
import base64
import io
import re

import cairosvg
import cv2
import numpy as np
from PIL import Image, ImageOps
from shapely.affinity import scale, translate
from shapely.geometry import Polygon
from shapely.ops import unary_union

from .schemas import SilhouetteOptions

MAX_UPLOAD_BYTES = 5_000_000
MAX_RENDER_EDGE = 1200


def _read_image(data_url: str) -> Image.Image:
    match = re.fullmatch(r"data:(image/(?:png|jpeg|webp|svg\+xml));base64,([A-Za-z0-9+/=\s]+)", data_url, re.S)
    if match is None:
        raise ValueError("Поддерживаются только PNG, JPG, WebP и SVG.")
    encoded = match.group(2).strip()
    if len(encoded) > 7_000_000:
        raise ValueError("Файл слишком большой (максимум 5 МБ).")
    try:
        data = base64.b64decode(encoded, validate=True)
    except ValueError as ex:
        raise ValueError("Неверное кодирование файла.") from ex
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("Файл слишком большой (максимум 5 МБ).")

    if match.group(1) == "image/svg+xml":
        lower = data.lower()
        # Block all possible external resource fetches and active SVG content.
        if (b"<!doctype" in lower or b"<!entity" in lower or b"<script" in lower
                or b"<foreignobject" in lower or b"@import" in lower
                or re.search(rb"(?:xlink:)?href\s*=\s*['\"](?!#)", lower)
                or re.search(rb"url\s*\(\s*['\"]?\s*(?:https?:|file:|/)", lower)):
            raise ValueError("SVG содержит запрещённые внешние ресурсы или скрипты.")
        try:
            root_match = re.search(rb"<svg\b([^>]*)>", data, re.I | re.S)
            if root_match is None:
                raise ValueError("SVG не содержит корневой элемент.")
            attrs = root_match.group(1)
            viewbox = re.search(rb"\bviewBox\s*=\s*['\"]([^'\"]+)['\"]", attrs, re.I)
            if viewbox:
                values = re.split(rb"[,\s]+", viewbox.group(1).strip())
                if len(values) != 4:
                    raise ValueError("Некорректный viewBox SVG.")
                svg_w, svg_h = float(values[2]), float(values[3])
            else:
                def svg_dimension(name):
                    found = re.search(name + rb"\s*=\s*['\"]([0-9.]+)", attrs, re.I)
                    return float(found.group(1)) if found else 512.0
                svg_w, svg_h = svg_dimension(rb"\bwidth"), svg_dimension(rb"\bheight")
            if not np.isfinite(svg_w) or not np.isfinite(svg_h) or svg_w <= 0 or svg_h <= 0:
                raise ValueError("Некорректный размер SVG.")
            factor = MAX_RENDER_EDGE / max(svg_w, svg_h)
            out_w = max(1, round(svg_w * factor))
            out_h = max(1, round(svg_h * factor))
            png = cairosvg.svg2png(bytestring=data, output_width=out_w, output_height=out_h)
            img = Image.open(io.BytesIO(png))
        except Exception as ex:
            raise ValueError("Не удалось открыть SVG.") from ex
    else:
        try:
            img = Image.open(io.BytesIO(data))
            img.verify()
            img = Image.open(io.BytesIO(data))
        except (OSError, ValueError) as ex:
            raise ValueError("Не удалось открыть изображение.") from ex

    if img.width < 2 or img.height < 2 or img.width * img.height > 25_000_000:
        raise ValueError("Неверный размер изображения.")
    img = ImageOps.exif_transpose(img).convert("RGBA")
    img.thumbnail((MAX_RENDER_EDGE, MAX_RENDER_EDGE))
    return img


def polygons_from_mask(mask: np.ndarray, preserve_holes: bool = True):
    """Convert a binary mask to a Shapely polygonal object; image Y is inverted."""
    mask = np.ascontiguousarray(mask.astype(np.uint8) * 255)
    retrieval = cv2.RETR_CCOMP if preserve_holes else cv2.RETR_EXTERNAL
    contours, hierarchy = cv2.findContours(mask, retrieval, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        raise ValueError("На изображении не найден силуэт.")
    h = hierarchy[0]
    objects = []
    for i, curve in enumerate(contours):
        if h[i][3] != -1:
            continue
        ext = _ring(curve)
        if len(ext) < 3:
            continue
        holes = []
        if preserve_holes:
            child = h[i][2]
            while child != -1:
                hole = _ring(contours[child])
                if len(hole) >= 3:
                    holes.append(hole)
                child = h[child][0]
        poly = Polygon(ext, holes)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.area >= 6:  # remove isolated noise pixels
            objects.append(poly)
    if not objects:
        raise ValueError("На изображении не найден подходящий контур.")
    return unary_union(objects)


def _ring(contour):
    return [(float(p[0][0]), -float(p[0][1])) for p in contour]


def trace_silhouette(options: SilhouetteOptions):
    image = _read_image(options.image_data)
    rgba = np.array(image)
    rgb = rgba[:, :, :3]
    alpha = rgba[:, :, 3]
    if alpha.min() < 250:
        mask = alpha > options.threshold
    else:
        grey = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        mask = grey < options.threshold
    if options.invert:
        mask = ~mask

    if options.mode == "lines":
        # Preserve the drawn strokes, including their interior holes.
        preserve_holes = True
    else:
        preserve_holes = options.mode == "cutouts"
    object_px = polygons_from_mask(mask, preserve_holes=preserve_holes)
    x0, y0, x1, y1 = object_px.bounds
    width_px = x1 - x0
    if width_px <= 0:
        raise ValueError("Контур не имеет ширины.")
    factor = options.width_mm / width_px
    object_mm = translate(scale(object_px, xfact=factor, yfact=factor, origin=(0, 0)),
                          xoff=-(x0 + x1) * factor / 2, yoff=-(y0 + y1) * factor / 2)
    if options.smoothing_mm:
        object_mm = object_mm.simplify(options.smoothing_mm, preserve_topology=True)
    if not object_mm.is_valid:
        object_mm = object_mm.buffer(0)
    if object_mm.is_empty:
        raise ValueError("После обработки контур оказался пустым.")
    return object_mm
