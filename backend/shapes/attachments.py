"""Shared attachment strategy for plates and traced silhouettes.

Planar eyelets/holes, transverse posts and printable magnet pockets use
the same validated configuration and consistent preview coordinates.
"""
import numpy as np
import trimesh
from shapely.geometry import Point, box

from .geometry import extrude
from .mounts import contour_samples, flat_mount, mount_placement, primary_outline, upright_eyelet, combine_upright
from .schemas import MagnetSettings, MeshPart

def mount_spec(opts, silhouette=False):
    if silhouette:
        mode = opts.mount_type
        if mode is None:  # migrate saved 0.1 / 0.2 projects
            mode=("upright" if opts.loop_orientation=="upright" else "loop") if opts.attach_loop else "none"
        return mode, opts.loop_hole_mm, opts.loop_wall_mm, opts.loop_contour_t, opts.loop_side, opts.loop_position
    return opts.mount_type, opts.mount_hole_mm, opts.mount_wall_mm, opts.mount_contour_t, opts.mount_side, opts.mount_position

def prepare_mount(shape, opts, silhouette=False):
    mode,hole,wall,fraction,side,pos=mount_spec(opts,silhouette)
    outline=primary_outline(shape)
    anchor=normal=tangent=actual=None
    if mode in ("hole","loop","upright"):
        anchor,normal,tangent,actual=mount_placement(outline,fraction,side,pos)
        if mode in ("hole","loop"):
            shape=flat_mount(shape,anchor,normal,hole,wall,mode)
    return shape,outline,actual,(mode,anchor,normal,tangent,hole,wall)

def finish_post(parts, placement, thickness, color, base_count=1):
    mode,anchor,normal,tangent,hole,wall=placement
    if mode!="upright":
        return parts
    ear=upright_eyelet(anchor,normal,tangent,thickness,hole,wall,color)
    return combine_upright(parts,ear,base_count,"Основа и поперечная петелька",color)

def _pocket(point, settings):
    x,y=point.x_mm,point.y_mm
    c=settings.clearance_mm
    if settings.shape=="round":
        return Point(x,y).buffer(settings.diameter_mm/2+c,quad_segs=32)
    return box(x-settings.width_mm/2-c,y-settings.height_mm/2-c,
               x+settings.width_mm/2+c,y+settings.height_mm/2+c)

def cut_magnet_pockets(parts: list[MeshPart], shape, settings:MagnetSettings,
                       thickness:float, image_face_bottom=False, image_depth=0):
    """Open pockets on the BACK: at z=0 for text/silhouette, top for a bottom image.

    The cavities remove material but are *not* exported as separate 'magnet'
    objects: the magnet itself is a physical insert, not printable plastic.
    """
    if not settings.positions:
        raise ValueError("Добавьте хотя бы одно посадочное место под магнит.")
    if settings.depth_mm > thickness - (image_depth if image_face_bottom else 0) - 0.6:
        raise ValueError("Под магнитом необходимо оставить не менее 0,6 мм пластика.")
    cuts=[_pocket(p,settings) for p in settings.positions]
    for i,cut in enumerate(cuts):
        if not shape.buffer(-0.8).covers(cut):
            raise ValueError(f"Магнит {i+1} не помещается: переместите его дальше от края.")
        for j in range(i):
            if cut.distance(cuts[j]) < 0.8:
                raise ValueError("Между магнитами необходимо оставить хотя бы 0,8 мм пластика.")
    from shapely.ops import unary_union
    # A single manifold subtraction is more stable than one subtraction per pocket.
    cut_shape=unary_union(cuts)
    if image_face_bottom:
        z0=thickness-settings.depth_mm
        z1=thickness+0.25
    else:
        z0=-0.25
        z1=settings.depth_mm
    blank=extrude(cut_shape,z0,z1,"Служебный объём магнитов","#FFFFFF")
    cutters=trimesh.Trimesh(vertices=blank.vertices,faces=blank.faces,process=False)
    result=[]
    for part in parts:
        mesh=trimesh.Trimesh(vertices=part.vertices,faces=part.faces,process=False)
        # Skip non-overlapping layers (e.g. front-side multicolor picture).
        if mesh.bounds[1,2] <= z0+0.000001 or mesh.bounds[0,2] >= z1-0.000001:
            result.append(part)
            continue
        try:
            carved=trimesh.boolean.difference([mesh,cutters],engine="manifold")
        except Exception as error:
            raise ValueError("Не удалось вырезать посадочные места под магниты.") from error
        if carved is None or carved.is_empty or not carved.is_watertight or carved.volume<=0:
            raise ValueError("Посадочное место под магнит повреждает модель.")
        result.append(MeshPart(name=part.name+" (карманы магнитов)",
              color=part.color,vertices=carved.vertices.round(6).tolist(),
              faces=carved.faces.tolist()))
    return result
