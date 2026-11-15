"""Parametric storage boxes with integrated dividers and printable slip-over lids.

Every body is a *single* watertight solid. The horizontal base closes the
bottoms of the cavities; all partitions are integral with the shell and never
overlap separate meshes. The lid is a second printable solid, laid flat next
to the box (cavity upward) for support-free FDM printing.
"""
from shapely import constrained_delaunay_triangles
from shapely.affinity import translate
from shapely.geometry import Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
import numpy as np
import trimesh

from .schemas import BoxOptions, MeshPart, Preview


def rounded_rectangle(width: float, depth: float, radius: float) -> Polygon:
    r = min(radius, width / 2 - 0.001, depth / 2 - 0.001)
    if r <= 0.00001:
        return box(-width / 2, -depth / 2, width / 2, depth / 2)
    return box(-width / 2 + r, -depth / 2 + r,
               width / 2 - r, depth / 2 - r).buffer(r, quad_segs=8)


def shell_mesh(outer: Polygon, openings: list[Polygon], bottom: float,
               height: float, name: str, color: str) -> MeshPart:
    """Triangulate the floor, cavity bottoms, rim, and both wall directions.

    The rim at Z=height is one polygon with N holes, matching the vertical
    walls of each cavity. No overlapping wall/floor meshes or floating faces.
    """
    if not outer.is_valid or outer.area <= 0 or not openings:
        raise ValueError("Недопустимый контур коробочки.")
    if bottom <= 0 or bottom >= height:
        raise ValueError("Дно должно быть ниже высоты коробочки.")
    for opening in openings:
        if opening.is_empty or not isinstance(opening, Polygon) or not opening.is_valid:
            raise ValueError("Слишком узкие отделения коробочки.")
        if not outer.contains(opening):
            raise ValueError("Отделения выходят за пределы стенок.")
    union = unary_union(openings)
    solid = outer.difference(union)
    if not isinstance(solid, Polygon) or not solid.is_valid:
        raise ValueError("Не удалось построить стенки и перегородки.")

    vertices: list[list[float]] = []
    faces: list[list[int]] = []
    lookup: dict[tuple[float, float, float], int] = {}

    def vertex(x: float, y: float, z: float) -> int:
        key = (round(float(x), 6), round(float(y), 6), round(float(z), 6))
        if key not in lookup:
            lookup[key] = len(vertices)
            vertices.append(list(key))
        return lookup[key]

    def cap(region: Polygon, z: float, upward: bool):
        for triangle in constrained_delaunay_triangles(region).geoms:
            if not region.covers(triangle.representative_point()):
                continue
            corners = list(orient(triangle, sign=1.0).exterior.coords)[:3]
            if len(corners) != 3:
                continue
            indices = [vertex(x, y, z) for x, y in corners]
            faces.append(indices if upward else list(reversed(indices)))

    def wall(boundary, z0: float, z1: float, inward: bool):
        coords = list(boundary.coords)
        # Exterior rings use CCW direction. Cavity walls are reversed so the
        # face normal points into each cavity, away from the printed solid.
        for (ax, ay), (bx, by) in zip(coords, coords[1:]):
            a0, b0 = vertex(ax, ay, z0), vertex(bx, by, z0)
            a1, b1 = vertex(ax, ay, z1), vertex(bx, by, z1)
            if inward:
                faces.extend(([a0, b1, b0], [a0, a1, b1]))
            else:
                faces.extend(([a0, b0, b1], [a0, b1, a1]))

    cap(outer, 0, upward=False)
    cap(solid, height, upward=True)
    wall(orient(outer, sign=1.0).exterior, 0, height, inward=False)
    for opening in openings:
        cap(opening, bottom, upward=True)
        wall(orient(opening, sign=1.0).exterior, bottom, height, inward=True)

    mesh = trimesh.Trimesh(vertices=np.asarray(vertices), faces=np.asarray(faces),
                           process=False)
    if (not mesh.is_watertight or not mesh.is_winding_consistent
            or mesh.volume <= 0):
        raise ValueError("Не удалось построить замкнутую сетку коробочки.")
    return MeshPart(name=name, color=color,
                    vertices=vertices, faces=faces)


def box_openings(opts: BoxOptions, outer: Polygon) -> list[Polygon]:
    if opts.wall_mm * 2 + 10 >= min(opts.width_mm, opts.depth_mm):
        raise ValueError("Стенки слишком толстые для выбранных габаритов.")
    inner = outer.buffer(-opts.wall_mm, join_style="mitre" if not opts.corner_radius_mm else "round",
                         quad_segs=8)
    if inner.is_empty or not isinstance(inner, Polygon):
        raise ValueError("Внутренняя полость коробочки слишком мала.")
    if opts.mode != "divided":
        return [inner]

    xmin, ymin, xmax, ymax = inner.bounds
    available_w = xmax - xmin - opts.divider_mm * (opts.columns - 1)
    available_d = ymax - ymin - opts.divider_mm * (opts.rows - 1)
    cell_w = available_w / opts.columns
    cell_d = available_d / opts.rows
    if cell_w < 8 or cell_d < 8:
        raise ValueError("Отделения должны быть не меньше 8 × 8 мм. Уменьшите число перегородок.")
    cavities = []
    for row in range(opts.rows):
        for col in range(opts.columns):
            x0 = xmin + col * (cell_w + opts.divider_mm)
            y0 = ymin + row * (cell_d + opts.divider_mm)
            opening = inner.intersection(box(x0, y0, x0 + cell_w, y0 + cell_d))
            if opening.is_empty or not isinstance(opening, Polygon):
                raise ValueError("Не удалось построить отделение.")
            cavities.append(opening)
    return cavities


def build_box(opts: BoxOptions) -> Preview:
    if opts.bottom_mm >= opts.height_mm - 4:
        raise ValueError("После дна должно оставаться не менее 4 мм полезной высоты.")
    if opts.corner_radius_mm > min(opts.width_mm, opts.depth_mm) / 2:
        raise ValueError("Скругление больше половины меньшей стороны коробочки.")

    outer = rounded_rectangle(opts.width_mm, opts.depth_mm, opts.corner_radius_mm)
    cavities = box_openings(opts, outer)
    body = shell_mesh(outer, cavities, opts.bottom_mm, opts.height_mm,
                      "Коробочка", opts.body_color)
    parts = [body]
    warnings: list[str] = []

    if opts.mode == "lid":
        # Slip-over cover: the cavity has exactly lid_clearance_mm free space
        # around the outside box perimeter. In print orientation its closed
        # exterior face touches the bed and its skirt points up.
        gap = opts.lid_clearance_mm
        thick = opts.lid_wall_mm
        inner_radius = opts.corner_radius_mm + gap
        outer_radius = inner_radius + thick
        lid_inside = rounded_rectangle(opts.width_mm + 2 * gap,
                                       opts.depth_mm + 2 * gap, inner_radius)
        lid_outside = rounded_rectangle(opts.width_mm + 2 * (gap + thick),
                                        opts.depth_mm + 2 * (gap + thick),
                                        outer_radius)
        lid = shell_mesh(lid_outside, [lid_inside], opts.lid_top_mm,
                         opts.lid_top_mm + opts.lid_skirt_mm,
                         "Съёмная крышка", opts.lid_color)
        lid_width = opts.width_mm + 2 * (gap + thick)
        # 12 mm clear travel space between printed parts.
        shift_x = opts.width_mm / 2 + lid_width / 2 + 12
        lid.vertices = [[round(x + shift_x, 6), y, z]
                        for x, y, z in lid.vertices]
        parts.append(lid)
        warnings.append("Крышка лежит рядом с коробочкой лицевой стороной на столе. "
                        "После печати переверните крышку для установки.")

    coordinates = [v for part in parts for v in part.vertices]
    spans = [max(p[i] for p in coordinates) - min(p[i] for p in coordinates)
             for i in range(3)]
    if len(coordinates) > 160_000:
        raise ValueError("Модель слишком сложна.")
    return Preview(parts=parts, size_mm=[round(v, 2) for v in spans],
                   warnings=warnings)