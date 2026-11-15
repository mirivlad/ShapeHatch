"""Parametric storage boxes with integrated dividers and printable slip-over lids.

Every body is a *single* watertight solid. The horizontal base closes the
bottoms of the cavities; all partitions are integral with the shell and never
overlap separate meshes. The lid is a second printable solid, laid flat next
to the box (cavity upward) for support-free FDM printing.
"""
from shapely import constrained_delaunay_triangles
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


def _axis_spans(weights: list[float], count: int, available: float) -> list[float]:
    """Turn saved relative sizes into real cavity dimensions, in mm."""
    if weights and len(weights) != count:
        raise ValueError("Число размеров не соответствует числу строк или столбцов.")
    values = weights or [1.0] * count
    result = [available * w / sum(values) for w in values]
    if any(v < 8 - 1e-7 for v in result):
        raise ValueError("Каждое отделение должно быть не уже 8 мм. Измените размеры секций.")
    return result


def box_openings(opts: BoxOptions, outer: Polygon) -> list[Polygon]:
    if opts.wall_mm * 2 + 10 >= min(opts.width_mm, opts.depth_mm):
        raise ValueError("Стенки слишком толстые для выбранных габаритов.")
    inner = outer.buffer(-opts.wall_mm, join_style="mitre" if not opts.corner_radius_mm else "round",
                         quad_segs=8)
    if inner.is_empty or not isinstance(inner, Polygon):
        raise ValueError("Внутренняя полость коробочки слишком мала.")
    enabled = opts.sections_enabled if opts.sections_enabled is not None else opts.mode == "divided"
    if not enabled:
        return [inner]

    xmin, ymin, xmax, ymax = inner.bounds
    available_w = xmax - xmin - opts.divider_mm * (opts.columns - 1)
    available_d = ymax - ymin - opts.divider_mm * (opts.rows - 1)
    if available_w <= 0 or available_d <= 0:
        raise ValueError("Не осталось места для отделений и перегородок.")
    widths = _axis_spans(opts.column_weights, opts.columns, available_w)
    depths = _axis_spans(opts.row_weights, opts.rows, available_d)
    xs = [xmin]
    # The editor shows row 0 at the top; +Y is up in the 3D top view.
    row_tops = [ymax]
    for index in range(opts.columns - 1):
        xs.append(xs[-1] + widths[index] + opts.divider_mm)
    for index in range(opts.rows - 1):
        row_tops.append(row_tops[-1] - depths[index] - opts.divider_mm)

    occupied: set[tuple[int, int]] = set()
    regions = []
    for merged in opts.merged_cells:
        if merged.col + merged.colspan > opts.columns or merged.row + merged.rowspan > opts.rows:
            raise ValueError("Объединённая ячейка выходит за размеры таблицы.")
        if merged.colspan * merged.rowspan < 2:
            raise ValueError("Объединение должно включать не менее двух ячеек.")
        for row in range(merged.row, merged.row + merged.rowspan):
            for col in range(merged.col, merged.col + merged.colspan):
                if (col, row) in occupied:
                    raise ValueError("Объединённые секции пересекаются.")
                occupied.add((col, row))
        regions.append((merged.col, merged.row, merged.colspan, merged.rowspan))
    for row in range(opts.rows):
        for col in range(opts.columns):
            if (col, row) not in occupied:
                regions.append((col, row, 1, 1))

    openings = []
    for col, row, colspan, rowspan in regions:
        x1 = xs[col + colspan - 1] + widths[col + colspan - 1]
        y0 = row_tops[row + rowspan - 1] - depths[row + rowspan - 1]
        opening = inner.intersection(box(xs[col], y0, x1, row_tops[row]))
        if opening.is_empty or not isinstance(opening, Polygon) or opening.area < 32:
            raise ValueError("Секция слишком мала или не помещается в корпус.")
        openings.append(opening)
    return openings


def inset_lid_mesh(outer: Polygon, inner: Polygon, opts: BoxOptions,
                   openings: list[Polygon]) -> MeshPart:
    """One manifold stepped mesh: overhanging plate + inner locating lip.

    The plate rests on the box rim. The lip protrudes inside it by the chosen
    depth; in build orientation the entire flat outside plate touches Z=0.
    """
    plug_outer = inner.buffer(-opts.lid_clearance_mm, quad_segs=8)
    plug_inner = plug_outer.buffer(-opts.lid_wall_mm, quad_segs=8)
    if (not isinstance(plug_outer, Polygon) or not isinstance(plug_inner, Polygon)
            or plug_inner.is_empty or not plug_outer.is_valid or not plug_inner.is_valid):
        raise ValueError("Вставной бортик крышки не помещается внутри коробки.")
    cover = outer
    # Full-height dividers meet the inside wall. Cut relief gaps in the inset
    # lip at every divider end, otherwise the fitted lid would not close.
    rings = plug_outer.difference(plug_inner)
    if len(openings) > 1:
        partitions = inner.difference(unary_union(openings))
        if not partitions.is_empty:
            rings = rings.difference(partitions.buffer(opts.lid_clearance_mm + 0.15,
                                                       join_style="mitre"))
    if rings.is_empty or rings.area < 2:
        raise ValueError("Вставной бортик не помещается между перегородками.")

    def polygon_parts(geometry):
        if geometry.is_empty:
            return []
        if isinstance(geometry, Polygon):
            return [geometry]
        return [part for sub in geometry.geoms for part in polygon_parts(sub)]

    verts: list[list[float]] = []
    faces: list[list[int]] = []
    registry: dict[tuple[float, float, float], int] = {}

    def v(x, y, z):
        key = (round(float(x), 6), round(float(y), 6), round(float(z), 6))
        if key not in registry:
            registry[key] = len(verts)
            verts.append(list(key))
        return registry[key]

    def cap(shape, z, upward):
        for region in polygon_parts(shape):
            for tri in constrained_delaunay_triangles(region).geoms:
                if not region.covers(tri.representative_point()):
                    continue
                corners = list(orient(tri, sign=1.0).exterior.coords)[:3]
                indices = [v(x, y, z) for x, y in corners]
                faces.append(indices if upward else list(reversed(indices)))

    def wall(ring, z0, z1, inward):
        for (ax, ay), (bx, by) in zip(ring.coords, list(ring.coords)[1:]):
            a0, b0 = v(ax, ay, z0), v(bx, by, z0)
            a1, b1 = v(ax, ay, z1), v(bx, by, z1)
            faces.extend(([a0, b1, b0], [a0, a1, b1]) if inward else
                         ([a0, b0, b1], [a0, b1, a1]))

    top = opts.lid_top_mm
    edge = top + opts.lid_skirt_mm
    cap(cover, 0, upward=False)
    cap(cover.difference(rings), top, upward=True)
    cap(rings, edge, upward=True)
    wall(orient(cover, sign=1.0).exterior, 0, top, inward=False)
    for region in polygon_parts(rings):
        poly = orient(region, sign=1.0)
        wall(poly.exterior, top, edge, inward=False)
        for hole in poly.interiors:
            wall(hole, top, edge, inward=False)  # holes are clockwise already

    mesh = trimesh.Trimesh(vertices=np.asarray(verts), faces=np.asarray(faces), process=False)
    if not mesh.is_watertight or not mesh.is_winding_consistent or mesh.volume <= 0:
        raise ValueError("Не удалось построить замкнутую вставную крышку.")
    return MeshPart(name="Вставная крышка", color=opts.lid_color, vertices=verts, faces=faces)


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

    lid_type = opts.lid_type if opts.lid_type is not None else (
        "over" if opts.mode == "lid" else "none")
    if lid_type != "none":
        if opts.lid_skirt_mm >= opts.height_mm - opts.bottom_mm:
            raise ValueError("Глубина крышки должна быть меньше полезной высоты коробочки.")
        if lid_type == "over":
            gap = opts.lid_clearance_mm
            thick = opts.lid_wall_mm
            lid_inside = rounded_rectangle(opts.width_mm + 2 * gap,
                                           opts.depth_mm + 2 * gap,
                                           opts.corner_radius_mm + gap)
            lid_outside = rounded_rectangle(opts.width_mm + 2 * (gap + thick),
                                            opts.depth_mm + 2 * (gap + thick),
                                            opts.corner_radius_mm + gap + thick)
            lid = shell_mesh(lid_outside, [lid_inside], opts.lid_top_mm,
                             opts.lid_top_mm + opts.lid_skirt_mm,
                             "Накладная крышка", opts.lid_color)
        elif lid_type == "inset":
            inner = outer.buffer(-opts.wall_mm, quad_segs=8)
            lid = inset_lid_mesh(outer, inner, opts, cavities)
            if len(cavities) > 1:
                warnings.append("Вставной бортик имеет промежутки напротив перегородок, "
                                "чтобы крышка надевалась без столкновений.")
        else:
            raise ValueError("Неизвестный вариант крышки.")
        lid_left = min(x for x,_,_ in lid.vertices)
        # 12 mm gap on the printing bed between the body and lid.
        shift_x = opts.width_mm / 2 + 12 - lid_left
        lid.vertices = [[round(x + shift_x, 6), y, z] for x, y, z in lid.vertices]
        parts.append(lid)
        warnings.append("Крышка расположена рядом с коробочкой наружной стороной на столе. "
                        "После печати переверните её для установки; проверьте посадочный зазор.")

    coordinates = [v for part in parts for v in part.vertices]
    spans = [max(p[i] for p in coordinates) - min(p[i] for p in coordinates)
             for i in range(3)]
    if len(coordinates) > 160_000:
        raise ValueError("Модель слишком сложна.")
    return Preview(parts=parts, size_mm=[round(v, 2) for v in spans],
                   warnings=warnings)