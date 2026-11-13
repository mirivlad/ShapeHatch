"""Contour-relative snap anchors and printable flat/upright keyring mounts."""
from math import hypot
import numpy as np
import trimesh
from shapely.geometry import LineString, Point, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from .geometry import extrude, polygons
from .schemas import MeshPart


def primary_outline(shape) -> LineString:
    """The largest exterior island; never snap to holes or loose tiny islands."""
    islands = polygons(shape)
    if not islands:
        raise ValueError("Не найден внешний контур для крепления.")
    main = orient(max(islands, key=lambda p: p.area), sign=1.0)
    return LineString(main.exterior.coords)


def contour_samples(line: LineString, count: int = 384) -> list[list[float]]:
    return [[round(line.interpolate(i * line.length / count).x, 4),
             round(line.interpolate(i * line.length / count).y, 4)]
            for i in range(count + 1)]


def _side_fraction(line: LineString, side: str, position: float) -> float:
    """Migrate legacy side/percent positions onto an exact outline parameter."""
    x0, y0, x1, y1 = line.bounds
    if side in ("top", "bottom"):
        x = x0 + (x1 - x0) * position
        cross = line.intersection(LineString([(x, y0 - 1), (x, y1 + 1)]))
        if not cross.is_empty:
            target = Point(x, cross.bounds[3] if side == "top" else cross.bounds[1])
        else:
            target = Point(x, y1 if side == "top" else y0)
    else:
        y = y0 + (y1 - y0) * position
        cross = line.intersection(LineString([(x0 - 1, y), (x1 + 1, y)]))
        if not cross.is_empty:
            target = Point(cross.bounds[0] if side == "left" else cross.bounds[2], y)
        else:
            target = Point(x0 if side == "left" else x1, y)
    return line.project(target) / line.length


def mount_placement(line: LineString, fraction: float | None,
                    side: str, position: float):
    """Return exact anchor, outward normal, tangent and contour fraction."""
    f = _side_fraction(line, side, position) if fraction is None else fraction % 1.0
    d = f * line.length
    anchor = line.interpolate(d)
    eps = min(0.25, line.length / 1000)
    before = line.interpolate((d - eps) % line.length)
    after = line.interpolate((d + eps) % line.length)
    dx, dy = after.x - before.x, after.y - before.y
    length = hypot(dx, dy)
    if length < 1e-9:
        raise ValueError("Не удалось определить направление контура.")
    tangent = (dx / length, dy / length)
    # Exterior ring is counter-clockwise: right-hand normal points outwards.
    normal = (tangent[1], -tangent[0])
    return anchor, normal, tangent, f


def flat_mount(shape, anchor: Point, normal: tuple[float, float],
               hole: float, wall: float, mode: str):
    inner = hole / 2
    nx, ny = normal
    if mode == "hole":
        center = Point(anchor.x - nx * (inner + wall + 0.3),
                       anchor.y - ny * (inner + wall + 0.3))
        opening = center.buffer(inner, quad_segs=48)
        if not shape.buffer(-wall + 0.00001).covers(opening):
            raise ValueError("Отверстие не помещается с заданной толщиной стенки. Измените положение или размеры.")
        return shape.difference(opening).buffer(0)

    center = Point(anchor.x + nx * (inner + 0.85),
                   anchor.y + ny * (inner + 0.85))
    opening = center.buffer(inner, quad_segs=48)
    if opening.intersects(shape.buffer(0.05)):
        raise ValueError("Отверстие петельки пересекает брелок. Переместите петельку по контуру.")
    eyelet = center.buffer(inner + wall, quad_segs=48)
    bridge = LineString([
        (anchor.x - nx * max(0.7, wall * 0.45),
         anchor.y - ny * max(0.7, wall * 0.45)),
        (center.x, center.y)
    ]).buffer(wall / 2, quad_segs=16)
    united = unary_union([shape, eyelet, bridge]).difference(opening).buffer(0)
    if len(polygons(united)) != len(polygons(shape)):
        raise ValueError("Петелька не соединена с основой. Выберите другое место.")
    return united


def _mesh(part: MeshPart) -> trimesh.Trimesh:
    return trimesh.Trimesh(vertices=np.asarray(part.vertices),
                           faces=np.asarray(part.faces), process=False)


def upright_eyelet(anchor: Point, normal: tuple[float, float],
                   tangent: tuple[float, float], thickness: float,
                   hole: float, wall: float, color: str) -> MeshPart:
    """Vertical annular plate: hole axis is tangent to the outline.

    A broad foot intersects the host plate in real volume so the manifold
    union makes one printable solid, not overlapping disconnected meshes.
    """
    inner = hole / 2
    outer = inner + wall
    # Local X: outwards from contour. Local Y: physical model Z.
    center_s = -wall * 0.65
    center_z = thickness + inner + wall * 0.45
    outline = Point(center_s, center_z).buffer(outer, quad_segs=48)
    opening = Point(center_s, center_z).buffer(inner, quad_segs=48)
    leg_bottom = max(0.15, thickness * 0.25)
    leg_top = thickness + wall * 0.20
    foot = box(center_s - outer * 0.53, leg_bottom,
               center_s + outer * 0.40, leg_top)
    section = unary_union([outline, foot]).difference(opening)
    tangential_width = max(2.0, min(4.0, wall * 1.4))
    local = extrude(section, -tangential_width / 2, tangential_width / 2,
                    "Перпендикулярная петелька", color)
    nx, ny = normal
    tx, ty = tangent
    vertices = [
        [anchor.x + nx * s + tx * along,
         anchor.y + ny * s + ty * along, z]
        for s, z, along in local.vertices
    ]
    # The local-to-world transform mirrors winding; flip every triangle.
    faces = [[a, c, b] for a, b, c in local.faces]
    return MeshPart(name=local.name, color=color, vertices=vertices, faces=faces)


def combine_upright(parts: list[MeshPart], ear: MeshPart,
                    count_base: int, name: str, color: str) -> list[MeshPart]:
    """Union all same-color body layers and the new ear into one watertight body."""
    solids = [_mesh(p) for p in parts[:count_base]] + [_mesh(ear)]
    try:
        result = trimesh.boolean.union(solids, engine="manifold")
    except Exception as exc:
        raise ValueError("Не удалось соединить перпендикулярную петельку с основой.") from exc
    if result is None or not result.is_watertight or result.volume <= 0:
        raise ValueError("Не получилось построить цельную петельку. Измените её положение.")
    body = MeshPart(name=name, color=color,
                    vertices=result.vertices.round(6).tolist(),
                    faces=result.faces.tolist())
    return [body] + parts[count_base:]
