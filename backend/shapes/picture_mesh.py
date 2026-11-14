"""Convert indexed color regions into non-overlapping face-down print volumes.

Physical placement is derived *after* plate dimensions are selected.
The indexed raster, region masks, and extrusion meshes have independent keys.
"""
from functools import lru_cache

from shapely.geometry import box
from shapely.ops import unary_union
from .picture import optimized_picture
from .geometry import extrude


def placement_dimensions(settings, plate, raster_width: int, raster_height: int):
    if raster_width<=0 or raster_height<=0:
        raise ValueError("Неизвестные размеры изображения.")
    margin=0.8
    avail_w=max(0.5,plate.bounds[2]-plate.bounds[0]-2*margin)
    avail_h=max(0.5,plate.bounds[3]-plate.bounds[1]-2*margin)
    aspect=raster_height/raster_width
    mode=settings.fit_mode
    if mode=="manual":
        width=settings.width_mm
        height=width*aspect
    elif mode=="fit":
        if settings.preserve_aspect:
            width=min(avail_w,avail_h/aspect)
            height=width*aspect
        else:
            width,height=avail_w,avail_h
    elif mode=="fill":
        if settings.preserve_aspect:
            width=max(avail_w,avail_h/aspect)
            height=width*aspect
        else:
            width,height=avail_w,avail_h
    elif mode=="width":
        width,height=avail_w,avail_w*aspect
    elif mode=="height":
        width,height=avail_h/aspect,avail_h
    else:
        raise ValueError("Неизвестный режим масштабирования.")
    return width*settings.scale,height*settings.scale


@lru_cache(maxsize=8)
def _image_regions(image_data: str, algorithm: str, color_count: int,
                   resolution: int, filament_palette: tuple,
                   width_mm: float, height_mm: float,
                   x_mm: float, y_mm: float,
                   dithering: str="none", image_kind: str="logo"):
    from .schemas import PictureSettings
    options=PictureSettings(image_data=image_data,algorithm=algorithm,
        color_count=color_count,resolution=resolution,
        filament_palette=list(filament_palette),
        dithering=dithering,image_kind=image_kind)
    indices,colors,_=optimized_picture(options)
    h,w=indices.shape
    cell_w=width_mm/w
    cell_h=height_mm/h
    left=x_mm-width_mm/2
    bottom=y_mm-height_mm/2
    regions=[]
    for idx in range(len(colors)):
        spans=[]
        for y in range(h):
            x=0
            while x<w:
                while x<w and indices[y,x]!=idx:x+=1
                start=x
                while x<w and indices[y,x]==idx:x+=1
                if start<x:
                    x0=left+start*cell_w
                    x1=left+x*cell_w
                    y0=bottom+(h-y-1)*cell_h
                    y1=bottom+(h-y)*cell_h
                    spans.append(box(x0,y0,x1,y1))
        if not spans:
            regions.append(None)
            continue
        if len(spans)>6500:
            raise ValueError("Слишком много мелких цветных областей. Уменьшите детализацию или включите режим логотипа.")
        regions.append(unary_union(spans))
    return regions


def picture_shapes(settings,plate):
    indices,colors,preview=optimized_picture(settings)
    height_px,width_px=indices.shape
    image_width,image_height=placement_dimensions(settings,plate,width_px,height_px)
    regions=_image_regions(settings.image_data,settings.algorithm,settings.color_count,
           settings.resolution,tuple(settings.filament_palette),
           round(image_width,6),round(image_height,6),
           settings.x_mm,settings.y_mm,settings.dithering,settings.image_kind)
    # Crop instead of rejecting larger pictures: Fill intentionally extends
    # beyond the plate boundary. This also supports round/oval plate shapes.
    allowed=plate.buffer(-0.15)
    if allowed.is_empty:
        raise ValueError("Табличка слишком мала для изображения.")
    clipped=[]
    for region,color in zip(regions,colors):
        if region is None:
            continue
        cut=region.intersection(allowed)
        if cut.is_empty or cut.area<0.000001:
            continue
        clipped.append((cut,color))
    if not clipped:
        raise ValueError("Картинка не попадает на табличку. Измените масштаб или положение.")
    used=unary_union([region for region,_ in clipped])
    return clipped,used,preview,list(colors),(image_width,image_height)


def image_plate_parts(shape,options):
    depth=options.picture.layer_mm
    thickness=options.thickness_mm
    if depth>thickness-0.6:
        raise ValueError("Над цветной картинкой нужно оставить не менее 0,6 мм основы.")
    regions,used,preview,palette,dimensions=picture_shapes(options.picture,shape)
    parts=[extrude(shape,depth,thickness,"Основа · задняя часть",
                   options.base_color,options.top_round_mm)]
    background=shape.difference(used)
    if not background.is_empty and background.area>0.0001:
        parts.append(extrude(background,0,depth,"Основа · лицевая часть",options.base_color))
    for index,(region,color) in enumerate(regions,1):
        parts.append(extrude(region,0,depth,
                     f"Изображение · цвет {index} · {color}",color))
    return parts,preview,palette,dimensions
