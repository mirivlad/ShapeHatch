"""Composable ShapeHatch generator: shared attachments, image/text branches.

Each mesh is cached by its precise geometry/parameters in geometry.extrude;
the image optimizer likewise caches the unchanged raster stage. Returning to
an earlier wizard step invalidates only parts whose inputs really changed.
"""
from shapely.ops import unary_union

from .attachments import prepare_mount, mount_spec, finish_post, cut_magnet_pockets
from .boxes import build_box
from .geometry import extrude, plate_parts, plate_shape, silhouette_parts
from .image_trace import trace_artwork
from .mounts import contour_samples
from .picture_mesh import image_plate_parts
from .picture import optimized_picture
from .schemas import GenerateRequest, Preview, InnerContourPreview
from .text_render import text_geometry


def generate(request:GenerateRequest)->Preview:
    if request.kind == "box":
        if request.box is None:
            raise ValueError("Не заданы параметры коробочки.")
        return build_box(request.box)
    current_fraction=None
    text_bounds=None
    text_surface_z=0.0
    image_preview=None
    image_palette=[]
    inner_previews=[]
    magnet_positions=[]
    magnet_surface_z=0.0
    if request.kind=="silhouette":
        if request.silhouette is None:
            raise ValueError("Не заданы параметры силуэта.")
        opts=request.silhouette
        mode,hole,wall,*_=mount_spec(opts,True)
        effective=(hole+2*wall if mode=="upright" else opts.thickness_mm)
        geo_opts=opts.model_copy(update={"thickness_mm":effective,"attach_loop":False})
        shape,enclosed=trace_artwork(opts)
        styles={x.id:x for x in opts.inner_contours}
        voids=[]
        colored=[]
        for contour_id,area in enclosed:
            choice=styles.get(contour_id)
            fill=choice.fill if choice else ("empty" if opts.mode=="cutouts" else "same")
            if fill=="empty":voids.append(area)
            elif fill=="other":colored.append((area,choice.color))
            if hasattr(area,"exterior"):
                points=[[round(float(x),3),round(float(y),3)]
                        for x,y in list(area.exterior.coords)[:-1]]
                inner_previews.append(InnerContourPreview(id=contour_id,points=points,fill=fill))
        if voids:
            shape=shape.difference(unary_union(voids)).buffer(0)
        shape,outline,current_fraction,attachment=prepare_mount(shape,opts,True)
        parts,warnings=silhouette_parts(shape,geo_opts,colored)
        parts=finish_post(parts,attachment,effective,opts.color,1)
        if mode=="magnets":
            parts=cut_magnet_pockets(parts,shape,opts.magnets,effective)
            magnet_positions=[[p.x_mm,p.y_mm] for p in opts.magnets.positions]
            magnet_surface_z=0
    elif request.kind=="plate":
        if request.plate is None:
            raise ValueError("Не заданы параметры плашки.")
        opts=request.plate
        mode,hole,wall,*_=mount_spec(opts)
        effective=(hole+2*wall if mode=="upright" else opts.thickness_mm)
        geo_opts=opts.model_copy(update={"thickness_mm":effective})
        shape=plate_shape(opts)
        shape,outline,current_fraction,attachment=prepare_mount(shape,opts)
        if opts.content_type=="image":
            # Before the image is loaded the user should still see the selected
            # plate shape and dimensions, not an empty 3D viewer with an error.
            if opts.picture.image_data:
                parts,image_preview,image_palette,(img_width,img_height)=image_plate_parts(shape,geo_opts)
                text_bounds=[
                    round(opts.picture.x_mm-img_width/2,3),
                    round(opts.picture.y_mm-img_height/2,3),
                    round(opts.picture.x_mm+img_width/2,3),
                    round(opts.picture.y_mm+img_height/2,3)]
                text_surface_z=-1.35  # drag handle below the image face
            else:
                parts=[extrude(shape,0,effective,"Основа",opts.base_color,opts.top_round_mm)]
            warnings=[]
            parts=finish_post(parts,attachment,effective,opts.base_color,1)
        else:
            text=text_geometry(opts)
            text_bounds=[round(float(x),3) for x in text.bounds]
            text_surface_z=effective+(opts.text_depth_mm if opts.text_style=="raised" else 0)
            if not shape.buffer(-max(0.25,opts.top_round_mm+0.1)).covers(text):
                raise ValueError("Надпись выходит за границы основы или пересекает отверстие.")
            parts,warnings=plate_parts(shape,text,geo_opts)
            parts=finish_post(parts,attachment,effective,opts.base_color,
                              1 if opts.text_style=="raised" else 2)
            if opts.text_style=="engraved":
                warnings.append("Гравировка не добавляет второго материала.")
        if mode=="magnets":
            if opts.content_type=="text" and opts.text_style in ("inlay","engraved"):
                if opts.magnets.depth_mm+opts.text_depth_mm>effective-0.6:
                    raise ValueError("Магнитное углубление пересекается с гравировкой/вставкой.")
            parts=cut_magnet_pockets(parts,shape,opts.magnets,effective,
                 image_face_bottom=opts.content_type=="image",
                 image_depth=opts.picture.layer_mm if opts.content_type=="image" else 0)
            magnet_positions=[[p.x_mm,p.y_mm] for p in opts.magnets.positions]
            magnet_surface_z=effective if opts.content_type=="image" else 0
    else:
        raise ValueError("Неизвестный генератор.")

    coords=[v for part in parts for v in part.vertices]
    if not coords:raise ValueError("Пустая модель.")
    if len(coords)>160_000:
        raise ValueError("Модель слишком сложна; уменьшите детализацию изображения.")
    size=[max(v[i] for v in coords)-min(v[i] for v in coords) for i in range(3)]
    return Preview(parts=parts,size_mm=[round(v,2) for v in size],
        warnings=warnings,mount_contour=contour_samples(outline),
        mount_fraction=current_fraction,mount_surface_z=effective,
        text_bounds_mm=text_bounds,text_surface_z=text_surface_z,
        inner_contours=inner_previews,image_preview_url=image_preview,
        image_palette=image_palette,magnet_positions=magnet_positions,
        magnet_surface_z=magnet_surface_z)