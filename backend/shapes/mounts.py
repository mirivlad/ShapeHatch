"""Contour-snap anchors and flat loops or cross-drilled cylindrical posts."""
from math import hypot
import numpy as np
import trimesh
from shapely.geometry import LineString, Point
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from .geometry import polygons
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
    # At an exact polygon vertex both possible face normals are valid.
    # Offset by only a few microns along the same contour to avoid unstable
    # boolean intersections at a shared vertex/coplanar segment junction.
    if any((anchor.x - x) ** 2 + (anchor.y - y) ** 2 < 1e-12
           for x, y in line.coords):
        d = (d + max(0.002, line.length * 0.00001)) % line.length
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
    """A rounded cross-drilled peg projecting along the outside XY normal.

    Construct and drill in local coordinates for numerical stability at
    arbitrary contour angles, then rotate the finished solid onto the edge.
    Local X is the outward axis, local Y the contour tangent, and Z is depth.
    The bore axis is local Y (visible from the side of the keychain).
    """
    inner = hole / 2
    outer = inner + wall
    diameter = 2 * outer
    # Leave a tiny sub-nozzle clearance from the plate's coplanar Z surfaces.
    # Exact coincident cylinder/plate faces can create non-manifold boolean edges.
    peg_radius = outer - 0.04
    if abs(thickness - diameter) > 1e-4:
        raise ValueError("Толщина брелка должна совпадать с диаметром столбика.")

    cap_s = outer * 1.25
    root_s = -outer * 1.3
    center_z = outer

    def cylinder(radius: float, length: float, axis: tuple[float, float, float],
                 center: tuple[float, float, float]):
        result = trimesh.creation.cylinder(radius=radius, height=length, sections=48)
        result.apply_transform(trimesh.geometry.align_vectors((0, 0, 1), axis))
        result.apply_translation(center)
        return result

    shaft = cylinder(peg_radius, cap_s - root_s, (1, 0, 0),
                     ((cap_s + root_s) / 2, 0, center_z))
    cap_center = (cap_s, 0, center_z)
    round_cap = trimesh.creation.icosphere(subdivisions=3, radius=peg_radius)
    round_cap.apply_translation(cap_center)
    cross_hole = cylinder(inner, diameter * 3, (0, 1, 0), cap_center)

    try:
        solid = trimesh.boolean.union([shaft, round_cap], engine="manifold")
        solid = trimesh.boolean.difference([solid, cross_hole], engine="manifold")
    except Exception as exc:
        raise ValueError("Не удалось построить поперечное отверстие столбика.") from exc
    if solid is None or not solid.is_watertight or solid.volume <= 0:
        raise ValueError("Столбик не удалось построить как замкнутую модель.")

    nx, ny = normal
    tx, ty = tangent
    verts = [
        [anchor.x + nx * s + tx * along,
         anchor.y + ny * s + ty * along, z]
        for s, along, z in solid.vertices
    ]
    return MeshPart(
        name="Столбик с поперечным отверстием", color=color,
        vertices=[[round(float(c), 6) for c in v] for v in verts],
        faces=solid.faces.tolist(),
    )

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
