from shapely.geometry import Polygon

from .geometry import plate_parts, plate_shape, silhouette_parts
from .image_trace import trace_silhouette
from .schemas import GenerateRequest, Preview
from .text_render import text_geometry


def generate(request: GenerateRequest) -> Preview:
    if request.kind == "silhouette":
        if request.silhouette is None:
            raise ValueError("Не заданы параметры силуэта.")
        shape = trace_silhouette(request.silhouette)
        parts, warnings = silhouette_parts(shape, request.silhouette)
    elif request.kind == "plate":
        if request.plate is None:
            raise ValueError("Не заданы параметры плашки.")
        options = request.plate
        base = plate_shape(options)
        text = text_geometry(options)
        if not base.buffer(-0.25).covers(text):
            raise ValueError("Надпись выходит за границы основы. Уменьшите текст или измените его положение.")
        parts, warnings = plate_parts(base, text, options)
        if options.text_style == "engraved":
            warnings.append("Для гравировки показан цвет основы: второй цвет не печатается.")
    else:
        raise ValueError("Неизвестный генератор.")

    coords = [v for part in parts for v in part.vertices]
    if not coords:
        raise ValueError("Пустая модель.")
    bounds = [max(v[i] for v in coords) - min(v[i] for v in coords) for i in range(3)]
    if len(coords) > 160_000:
        raise ValueError("Модель слишком сложна; уменьшите детализацию изображения.")
    return Preview(parts=parts, size_mm=[round(v, 2) for v in bounds], warnings=warnings)
