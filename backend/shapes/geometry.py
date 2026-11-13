"""2D shapes and watertight 3D extrusions without external triangulation binaries."""
from math import cos, pi, sin
import numpy as np
import trimesh
from shapely import constrained_delaunay_triangles
from shapely.affinity import scale as scale_shape
from shapely.geometry import GeometryCollection, LineString, MultiPolygon, Point, Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import nearest_points, unary_union

from .schemas import MeshPart, PlateOptions, SilhouetteOptions


def polygons(geometry):
    if geometry.is_empty:
        return []
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, (MultiPolygon, GeometryCollection)):
        return [p for g in geometry.geoms for p in polygons(g)]
    return []


def extrude(geometry, z0: float, z1: float, name: str, color: str) -> MeshPart:
    """Create indexed manifold triangles from constrained triangulation and boundary rings."""
    if z1 <= z0:
        raise ValueError("Высота выдавливания должна быть положительной.")
    verts: list[list[float]] = []
    faces: list[list[int]] = []
    indices: dict[tuple[float, float, float], int] = {}

    def vertex(x, y, z):
        key = (round(float(x), 6), round(float(y), 6), round(float(z), 6))
        if key not in indices:
            indices[key] = len(verts)
            verts.append(list(key))
        return indices[key]

    for raw in polygons(geometry):
        poly = orient(raw, sign=1.0)
        if poly.area < 0.0001:
            continue
        triangles = constrained_delaunay_triangles(poly)
        for tri in polygons(triangles):
            pts = list(orient(tri, sign=1.0).exterior.coords)[:3]
            if len(pts) != 3:
                continue
            a, b, c = pts
            faces.append([vertex(*a, z1), vertex(*b, z1), vertex(*c, z1)])
            faces.append([vertex(*c, z0), vertex(*b, z0), vertex(*a, z0)])
        rings = [poly.exterior, *poly.interiors]
        for ring in rings:
            pts = list(ring.coords)
            for a, b in zip(pts, pts[1:]):
                a0, b0 = vertex(*a, z0), vertex(*b, z0)
                a1, b1 = vertex(*a, z1), vertex(*b, z1)
                faces.append([a0, b0, b1])
                faces.append([a0, b1, a1])

    if not faces:
        raise ValueError("Не получилось построить замкнутую 3D-модель.")
    mesh = trimesh.Trimesh(vertices=np.array(verts), faces=np.array(faces), process=True)
    if not mesh.is_watertight or mesh.volume <= 0:
        raise ValueError("Не удалось создать корректную сетку. Измените параметры.")
    # Export the cleaned, consistently wound geometry.
    return MeshPart(name=name, color=color,
                    vertices=mesh.vertices.round(6).tolist(), faces=mesh.faces.tolist())


def ring_on_shape(shape, options: SilhouetteOptions):
    x0, y0, x1, y1 = shape.bounds
    pos = options.loop_position
    side = options.loop_side
    if side == "top":
        sample = Point(x0 + (x1 - x0) * pos, y1 + 100)
        direction = (0, 1)
    elif side == "bottom":
        sample = Point(x0 + (x1 - x0) * pos, y0 - 100)
        direction = (0, -1)
    elif side == "left":
        sample = Point(x0 - 100, y0 + (y1 - y0) * pos)
        direction = (-1, 0)
    else:
        sample = Point(x1 + 100, y0 + (y1 - y0) * pos)
        direction = (1, 0)
    anchor = nearest_points(shape.boundary, sample)[0]
    cx, cy = anchor.x, anchor.y
    hx, hy = direction
    inner = options.loop_hole_mm / 2
    outer = inner + options.loop_wall_mm
    distance = inner + 0.85
    center = Point(cx + hx * distance, cy + hy * distance)
    outside = center.buffer(outer, resolution=48)
    opening = center.buffer(inner, resolution=48)
    # A short connector merges the ring and the nearest contour instead of leaving tangent shells.
    connector = LineString([(cx - hx * 0.7, cy - hy * 0.7), (center.x, center.y)])
    connected = unary_union([shape, outside, connector.buffer(options.loop_wall_mm / 2, resolution=16)])
    return connected.difference(opening).buffer(0)


def silhouette_parts(shape, options: SilhouetteOptions):
    warnings = []
    if options.attach_loop:
        shape = ring_on_shape(shape, options)
    if len(polygons(shape)) > 1:
        warnings.append("Есть несвязанные фрагменты — они будут печататься отдельно.")
    if shape.minimum_clearance < 0.8:
        warnings.append("В модели есть детали или зазоры уже 0,8 мм — проверьте прочность.")
    return [extrude(shape, 0, options.thickness_mm, "Силуэт", options.color)], warnings


def plate_shape(opts: PlateOptions):
    w, h = opts.width_mm, opts.height_mm
    if opts.shape == "rectangle":
        return box(-w/2, -h/2, w/2, h/2)
    if opts.shape == "rounded":
        r = min(opts.corner_radius_mm, w/2 - 0.01, h/2 - 0.01)
        return box(-w/2+r, -h/2+r, w/2-r, h/2-r).buffer(r, resolution=24)
    if opts.shape == "oval":
        return scale_shape(Point(0, 0).buffer(1, resolution=96), xfact=w/2, yfact=h/2)
    if opts.shape == "circle":
        return Point(0, 0).buffer(min(w, h)/2, resolution=96)
    return Polygon([(w/2 * cos(pi/3*i), h/2 * sin(pi/3*i)) for i in range(6)])


def _plate_edge(shape, side: str, position: float):
    """Find the real boundary point at a fraction of an edge's span.

    Intersecting a slice with the shape avoids projecting to the middle of an
    ellipse when a ring is requested close to one of its ends.
    """
    x0, y0, x1, y1 = shape.bounds
    if side in ("top", "bottom"):
        x = x0 + (x1 - x0) * position
        section = shape.intersection(LineString([(x, y0 - 1), (x, y1 + 1)]))
        if section.is_empty:
            raise ValueError("Не удалось найти край плашки для крепления.")
        return Point(x, section.bounds[3] if side == "top" else section.bounds[1]), (0, 1 if side == "top" else -1)
    y = y0 + (y1 - y0) * position
    section = shape.intersection(LineString([(x0 - 1, y), (x1 + 1, y)]))
    if section.is_empty:
        raise ValueError("Не удалось найти край плашки для крепления.")
    return Point(section.bounds[0] if side == "left" else section.bounds[2], y), (-1 if side == "left" else 1, 0)


def plate_with_mount(shape, opts: PlateOptions):
    """Add a same-plane keyring eyelet or drill a through-hole in the plate."""
    if opts.mount_type == "none":
        return shape
    anchor, (nx, ny) = _plate_edge(shape, opts.mount_side, opts.mount_position)
    inner = opts.mount_hole_mm / 2
    wall = opts.mount_wall_mm
    if opts.mount_type == "hole":
        # The hole must be fully enclosed, with enough material around it.
        center = Point(anchor.x - nx * (inner + wall + 0.3),
                       anchor.y - ny * (inner + wall + 0.3))
        opening = center.buffer(inner, resolution=48)
        if not shape.buffer(-wall + 0.00001).covers(opening):
            raise ValueError("Отверстие не помещается с заданной толщиной стенки. Измените положение или размеры.")
        return shape.difference(opening).buffer(0)

    center = Point(anchor.x + nx * (inner + 0.85),
                   anchor.y + ny * (inner + 0.85))
    outer = center.buffer(inner + wall, resolution=48)
    opening = center.buffer(inner, resolution=48)
    # Overlap the plate and eyelet; never leave a barely touching ring.
    connector = LineString([
        (anchor.x - nx * 0.7, anchor.y - ny * 0.7),
        (center.x, center.y),
    ]).buffer(wall / 2, resolution=16)
    result = unary_union([shape, outer, connector]).difference(opening).buffer(0)
    if len(polygons(result)) != 1:
        raise ValueError("Не удалось надёжно соединить ушко с плашкой. Измените положение.")
    return result


def plate_parts(base_shape, text_shape, opts: PlateOptions):
    warnings = []
    depth = opts.text_depth_mm
    t = opts.thickness_mm
    if opts.text_style != "raised":
        depth = min(depth, t-0.4)
    if text_shape.is_empty:
        raise ValueError("Текст не помещается на основу.")
    if opts.text_style == "raised":
        return [
            extrude(base_shape, 0, t, "Основа", opts.base_color),
            extrude(text_shape, t, t+depth, "Надпись", opts.text_color)
        ], warnings
    lower = extrude(base_shape, 0, t-depth, "Основа, нижний слой", opts.base_color)
    upper_shape = base_shape.difference(text_shape)
    upper = extrude(upper_shape, t-depth, t, "Основа, верхний слой", opts.base_color)
    if opts.text_style == "inlay":
        letters = extrude(text_shape, t-depth, t, "Цветная вставка", opts.text_color)
        return [lower, upper, letters], warnings
    return [lower, upper], warnings
