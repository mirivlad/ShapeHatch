"""Generate watertight printable meshes and perimeter-based drag anchors."""
from .geometry import plate_parts, plate_shape, silhouette_parts
from .image_trace import trace_silhouette
from .mounts import (combine_upright, contour_samples, flat_mount, mount_placement,
                     primary_outline, upright_eyelet)
from .schemas import GenerateRequest, Preview
from .text_render import text_geometry


def generate(request: GenerateRequest) -> Preview:
    current_fraction = None
    text_bounds = None
    text_surface_z = 0.0
    if request.kind == "silhouette":
        if request.silhouette is None:
            raise ValueError("Не заданы параметры силуэта.")
        options = request.silhouette
        upright = options.attach_loop and options.loop_orientation == "upright"
        effective_thickness = (options.loop_hole_mm + 2 * options.loop_wall_mm
                               if upright else options.thickness_mm)
        geometry_options = options.model_copy(
            update={"thickness_mm": effective_thickness, "attach_loop": False})
        shape = trace_silhouette(options)
        outline = primary_outline(shape)
        if options.attach_loop:
            anchor, normal, tangent, current_fraction = mount_placement(
                outline, options.loop_contour_t, options.loop_side, options.loop_position)
            if upright:
                parts, warnings = silhouette_parts(shape, geometry_options)
                ear = upright_eyelet(anchor, normal, tangent, effective_thickness,
                                    options.loop_hole_mm, options.loop_wall_mm, options.color)
                parts = combine_upright(parts, ear, 1, "Силуэт с петелькой", options.color)
            else:
                shape = flat_mount(shape, anchor, normal,
                                   options.loop_hole_mm, options.loop_wall_mm, "loop")
                parts, warnings = silhouette_parts(shape, geometry_options)
        else:
            parts, warnings = silhouette_parts(shape, geometry_options)
    elif request.kind == "plate":
        if request.plate is None:
            raise ValueError("Не заданы параметры плашки.")
        options = request.plate
        upright = options.mount_type == "upright"
        effective_thickness = (options.mount_hole_mm + 2 * options.mount_wall_mm
                               if upright else options.thickness_mm)
        geometry_options = options.model_copy(update={"thickness_mm": effective_thickness})
        shape = plate_shape(options)
        outline = primary_outline(shape)
        if options.mount_type != "none":
            anchor, normal, tangent, current_fraction = mount_placement(
                outline, options.mount_contour_t, options.mount_side, options.mount_position)
            if options.mount_type in ("hole", "loop"):
                shape = flat_mount(shape, anchor, normal,
                                   options.mount_hole_mm, options.mount_wall_mm, options.mount_type)
        text = text_geometry(options)
        text_bounds = [round(float(v), 3) for v in text.bounds]
        text_surface_z = effective_thickness + (options.text_depth_mm if options.text_style == "raised" else 0)
        if not shape.buffer(-0.25).covers(text):
            raise ValueError("Надпись выходит за границы основы или пересекает отверстие. Измените размеры или положение.")
        parts, warnings = plate_parts(shape, text, geometry_options)
        if upright:
            ear = upright_eyelet(anchor, normal, tangent, effective_thickness,
                                options.mount_hole_mm, options.mount_wall_mm, options.base_color)
            parts = combine_upright(parts, ear, 1 if options.text_style == "raised" else 2,
                                    "Основа с перпендикулярной петелькой", options.base_color)
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
    return Preview(parts=parts, size_mm=[round(v, 2) for v in bounds], warnings=warnings,
                   mount_contour=contour_samples(outline), mount_fraction=current_fraction,
                   mount_surface_z=effective_thickness,
                   text_bounds_mm=text_bounds, text_surface_z=text_surface_z)
