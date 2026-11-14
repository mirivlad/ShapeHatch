"""Convert bounded palette pixels into distinct printable volumes.

The actual masks and their polygonization are cached independently of the
mount configuration, slice height and color replacement. Repositioning a
magnet does not re-vectorize or retriangulate the picture.
"""
from functools import lru_cache

import numpy as np
from shapely.geometry import box
from shapely.ops import unary_union

from .picture import optimized_picture
from .geometry import extrude
from .schemas import PictureSettings

@lru_cache(maxsize=8)
def _image_regions(image_data:str, algorithm:str, color_count:int, resolution:int,
                   filament_palette:tuple, width_mm:float,x_mm:float,y_mm:float):
    settings=PictureSettings(
        image_data=image_data,algorithm=algorithm,color_count=color_count,
        resolution=resolution,filament_palette=list(filament_palette),
        width_mm=width_mm,x_mm=x_mm,y_mm=y_mm)
    indices,colors,_=optimized_picture(settings)
    h,w=indices.shape
    pixel=settings.width_mm/w
    center=(w*pixel/2,h*pixel/2)
    materials=[]
    for idx in range(len(colors)):
        spans=[]
        for y in range(h):
            x=0
            while x<w:
                while x<w and indices[y,x]!=idx:x+=1
                start=x
                while x<w and indices[y,x]==idx:x+=1
                if start<x:
                    x0=settings.x_mm+start*pixel-center[0]
                    x1=settings.x_mm+x*pixel-center[0]
                    y0=settings.y_mm+(h-y-1)*pixel-center[1]
                    y1=settings.y_mm+(h-y)*pixel-center[1]
                    spans.append(box(x0,y0,x1,y1))
        if not spans:
            materials.append(None)
            continue
        if len(spans)>1800:
            raise ValueError("Слишком много мелких цветных областей. Уменьшите детализацию картинки.")
        materials.append(unary_union(spans))
    union=unary_union([g for g in materials if g is not None])
    return materials,union


def picture_shapes(settings:PictureSettings,plate):
    indices,colors,preview=optimized_picture(settings)
    regions,all_regions=_image_regions(
        settings.image_data,settings.algorithm,settings.color_count,
        settings.resolution,tuple(settings.filament_palette),settings.width_mm,
        settings.x_mm,settings.y_mm)
    if not plate.buffer(-0.25).covers(all_regions):
        raise ValueError("Картинка выходит за границы таблички. Уменьшите её или переместите.")
    return [(region,color) for region,color in zip(regions,colors)
            if region is not None],all_regions,preview,list(colors)


def image_plate_parts(shape,options):
    depth=options.picture.layer_mm
    thickness=options.thickness_mm
    if depth>thickness-0.6:
        raise ValueError("Над цветной картинкой нужно оставить не менее 0,6 мм основы.")
    regions,used,preview,palette=picture_shapes(options.picture,shape)
    # The colored picture starts directly on the print bed at Z=0.
    parts=[extrude(shape,depth,thickness,"Основа · задняя часть",
                  options.base_color,options.top_round_mm)]
    background=shape.difference(used)
    if not background.is_empty and background.area>0.0001:
        parts.append(extrude(background,0,depth,"Основа · лицевая часть",options.base_color))
    for index,(region,color) in enumerate(regions,1):
        parts.append(extrude(region,0,depth,
                    f"Изображение · цвет {index} · {color}",color))
    return parts,preview,palette
