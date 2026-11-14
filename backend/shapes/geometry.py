"""2D shapes and watertight 3D extrusions without external triangulation binaries."""
from math import cos, pi, sin
from functools import lru_cache
from shapely import wkb
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


def _compute_extrusion(geometry, z0: float, z1: float, name: str, color: str,
                       top_round_mm: float = 0.0, round_limit=None) -> MeshPart:
    """Build a watertight extrusion with an optional true curved top edge.

    The upper edge is made from four offset profiles along a quarter circle.
    'round_limit' allows rounding the plate/silhouette perimeter without
    altering vertical walls around colored inlays or text recesses.
    """
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

    def cap(surface, z: float, upper: bool):
        for raw in polygons(surface):
            for tri in polygons(constrained_delaunay_triangles(raw)):
                pts = list(orient(tri, sign=1.0).exterior.coords)[:3]
                if len(pts) != 3:
                    continue
                a, b, c = pts
                faces.append([vertex(*a, z), vertex(*b, z), vertex(*c, z)]
                             if upper else
                             [vertex(*c, z), vertex(*b, z), vertex(*a, z)])

    limit = round_limit if round_limit is not None else geometry
    radius = min(float(top_round_mm), (z1-z0) * 0.8)
    if radius < 0.0001:
        radius = 0.0

    # Keep all islands and holes: if a corner is too narrow for the requested
    # radius, reduce the radius rather than destroy an engraving or fragment.
    profiles = [geometry]
    levels = [z1]
    if radius:
        original_topology = [(len(poly.interiors)) for poly in polygons(geometry)]
        for _ in range(7):
            candidate_profiles = [geometry]
            candidate_levels = [z1-radius]
            valid = True
            for fraction in (0.25, 0.5, 0.75, 1.0):
                delta = radius * (1 - (1 - fraction * fraction) ** 0.5)
                inset = limit.buffer(-delta, quad_segs=8)
                profile = geometry.intersection(inset)
                if not profile.is_valid:
                    profile = profile.buffer(0)
                if (profile.is_empty or
                        sorted(len(poly.interiors) for poly in polygons(profile))
                        != sorted(original_topology)):
                    valid = False
                    break
                candidate_profiles.append(profile)
                candidate_levels.append(z1-radius+radius*fraction)
            if valid:
                profiles, levels = candidate_profiles, candidate_levels
                break
            radius *= 0.5
        else:
            radius = 0.0
            profiles, levels = [geometry], [z1]

    cap(geometry, z0, upper=False)
    cap(profiles[-1], z1, upper=True)
    for raw in polygons(geometry):
        poly = orient(raw, sign=1.0)
        for ring in [poly.exterior, *poly.interiors]:
            for a, b in zip(ring.coords, list(ring.coords)[1:]):
                # Only the original outer/hole edges of the rounding limit
                # are curved. Text and color-inlay borders stay vertical.
                fixed = (radius and
                         limit.boundary.distance(Point((a[0]+b[0])/2,
                                                      (a[1]+b[1])/2)) > 0.0001)
                # Use the original edge's orientation for outward walls.
                top = z1 if fixed else levels[0]
                a0, b0 = vertex(*a, z0), vertex(*b, z0)
                a1, b1 = vertex(*a, top), vertex(*b, top)
                faces.append([a0, b0, b1])
                faces.append([a0, b1, a1])

    if radius:
        for i in range(len(profiles)-1):
            outer, inner = profiles[i], profiles[i+1]
            band = outer.difference(inner)
            if band.is_empty:
                continue
            for region in polygons(band):
                for tri in polygons(constrained_delaunay_triangles(region)):
                    pts = list(orient(tri, sign=1.0).exterior.coords)[:3]
                    if len(pts) != 3:
                        continue
                    z_pts = [levels[i+1] if inner.boundary.distance(Point(*p)) < 0.00001
                             else levels[i] for p in pts]
                    faces.append([vertex(*p, z) for p, z in zip(pts, z_pts)])

    if not faces:
        raise ValueError("Не получилось построить замкнутую 3D-модель.")
    mesh = trimesh.Trimesh(vertices=np.array(verts), faces=np.array(faces), process=True)
    if not mesh.is_watertight or mesh.volume <= 0:
        raise ValueError("Не удалось создать замкнутую сетку детали. Проверьте контуры изображения.")
    return MeshPart(name=name, color=color,
                    vertices=mesh.vertices.round(6).tolist(), faces=mesh.faces.tolist())


@lru_cache(maxsize=16)
def _cached_extrusion(geometry_wkb: bytes, z0: float, z1: float,
                      radius: float, limit_wkb: bytes | None):
    geometry = wkb.loads(geometry_wkb)
    limit = wkb.loads(limit_wkb) if limit_wkb is not None else None
    # A single material can contain many disjoint islands. Two islands may
    # meet only at a corner (diagonal pixel neighbors). Merging their vertex
    # indices makes otherwise valid 3D shells non-manifold. Keep one indexed
    # shell per connected polygon, even when coordinates happen to coincide.
    pieces = polygons(geometry)
    if not pieces:
        raise ValueError("В контуре не осталось печатаемых областей.")

    vertices, faces = [], []
    # Detect exact corner contacts between separately valid islands. Even
    # when each shell is watertight, slicers that weld duplicate positions
    # could turn a touching corner into a non-manifold vertex/edge.
    owners: dict[tuple[float, float], int] = {}
    corner_touching: set[int] = set()
    for index, poly in enumerate(pieces):
        for ring in [poly.exterior, *poly.interiors]:
            for x, y in list(ring.coords)[:-1]:
                point = (round(float(x), 6), round(float(y), 6))
                previous = owners.setdefault(point, index)
                if previous != index:
                    corner_touching.update((index, previous))
    for index, piece in enumerate(pieces):
        if index in corner_touching:
            # Two tenth-micrometre offsets produce a gap far below typical
            # slicer/print tolerances, but make the shells independent even
            # if the slicer welds all coincident coordinates.
            inset=piece.buffer(-0.0001,join_style=2)
            if not inset.is_empty and inset.area>piece.area*0.995:
                piece=inset
        # GEOS can represent two picture holes that kiss at exactly one pixel
        # corner as a valid single polygon. Such a boundary extrudes into a
        # non-manifold vertical edge used by four faces. A microscopic inward
        # cleanup separates those holes, without changing any visible pixel.
        repaired_parts = None
        for cleanup in (0.0, 0.0001, 0.001, 0.003):
            source = (piece if cleanup == 0 else
                      piece.buffer(-cleanup, join_style=2))
            if source.is_empty or (piece.area-source.area) > piece.area*0.005:
                continue
            try:
                candidates = [_compute_extrusion(item,z0,z1,"cache","#000000",
                                                  radius,limit)
                              for item in polygons(source)]
                if not candidates:
                    continue
            except ValueError:
                continue
            repaired_parts = candidates
            break
        if repaired_parts is None:
            raise ValueError("В цветной области есть самокасающиеся контуры, "
                             "которые не удалось разделить.")
        for part in repaired_parts:
            offset=len(vertices)
            vertices.extend(part.vertices)
            faces.extend([[index+offset for index in face] for face in part.faces])
    # Process=False intentionally preserves the independent vertex indices.
    # The geometry is an assembly of watertight printable pieces, not one
    # connected manifold.
    model = trimesh.Trimesh(vertices=np.asarray(vertices),faces=np.asarray(faces),
                            process=False)
    if not model.is_watertight or model.volume <= 0:
        raise ValueError("Не удалось объединить замкнутые фрагменты рисунка.")
    return vertices,faces


def extrude(geometry, z0: float, z1: float, name: str, color: str,
            top_round_mm: float = 0.0, round_limit=None) -> MeshPart:
    """Reuse identical geometry across steps, independent of material and part name."""
    try:
        vertices,faces=_cached_extrusion(geometry.wkb,round(z0,6),round(z1,6),
            round(top_round_mm,6),round_limit.wkb if round_limit is not None else None)
    except ValueError as error:
        raise ValueError(f"Деталь «{name}»: {error}") from error
    return MeshPart(name=name,color=color,vertices=vertices,faces=faces)


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


def silhouette_parts(shape, options: SilhouetteOptions, color_inlays=None):
    warnings = []
    if options.attach_loop:
        shape = ring_on_shape(shape, options)
    if len(polygons(shape)) > 1:
        warnings.append("Есть несвязанные фрагменты — они будут печататься отдельно.")
    if shape.minimum_clearance < 0.8:
        warnings.append("В модели есть детали или зазоры уже 0,8 мм — проверьте прочность.")
    inlays = color_inlays or []
    if not inlays:
        return [extrude(shape, 0, options.thickness_mm, "Силуэт", options.color,
                        options.top_round_mm)], warnings
    depth = min(options.inlay_depth_mm, options.thickness_mm - 0.3)
    inserts = unary_union([area for area, color in inlays])
    if not shape.buffer(-max(0.1, options.top_round_mm + 0.08)).covers(inserts):
        raise ValueError("Цветная вставка слишком близка к внешнему краю.")
    upper = shape.difference(inserts)
    parts = [
        extrude(shape, 0, options.thickness_mm - depth, "Силуэт, нижний слой", options.color),
        extrude(upper, options.thickness_mm - depth, options.thickness_mm,
                "Силуэт, верхний слой", options.color,
                options.top_round_mm, round_limit=shape),
    ]
    parts.extend(extrude(area, options.thickness_mm - depth, options.thickness_mm,
                         f"Вставка {i+1}", color)
                 for i, (area, color) in enumerate(inlays))
    return parts, warnings


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
            extrude(base_shape, 0, t, "Основа", opts.base_color, opts.top_round_mm),
            extrude(text_shape, t, t+depth, "Надпись", opts.text_color)
        ], warnings
    lower = extrude(base_shape, 0, t-depth, "Основа, нижний слой", opts.base_color)
    upper_shape = base_shape.difference(text_shape)
    upper = extrude(upper_shape, t-depth, t, "Основа, верхний слой", opts.base_color,
                    opts.top_round_mm, round_limit=base_shape)
    if opts.text_style == "inlay":
        letters = extrude(text_shape, t-depth, t, "Цветная вставка", opts.text_color)
        return [lower, upper, letters], warnings
    return [lower, upper], warnings
