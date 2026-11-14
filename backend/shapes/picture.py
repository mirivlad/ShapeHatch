"""Small, bounded palette optimizer shared by the live preview and the printable meshes."""
import base64
from functools import lru_cache
import io

import cv2
import numpy as np
from PIL import Image

from .image_trace import _read_image
from .schemas import PictureSettings

def _rgb(color: str):
    return tuple(int(color[i:i+2],16) for i in (1,3,5))

def _hex(rgb):
    return "#" + "".join(f"{int(x):02X}" for x in rgb)

def _nearest(pixels, palette):
    colors = np.asarray(palette,dtype=np.int16)
    result = np.empty(pixels.shape[:2], dtype=np.uint8)
    # Explicit row loops avoid a huge N*colors intermediate for large uploads.
    for y in range(len(pixels)):
        row=pixels[y].astype(np.int16)
        distance=((row[:,None,:]-colors[None,:,:]).astype(np.int32)**2).sum(axis=2)
        result[y] = distance.argmin(axis=1)
    return result

def _floyd(pixels,palette):
    colors=np.array(palette,dtype=np.float32)
    src=pixels.astype(np.float32).copy()
    h,w=src.shape[:2]
    indices=np.zeros((h,w),dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            delta=colors-src[y,x]
            j=int(np.argmin((delta*delta).sum(axis=1)))
            indices[y,x]=j
            error=src[y,x]-colors[j]
            if x+1<w: src[y,x+1]+=error*(7/16)
            if y+1<h:
                if x>0: src[y+1,x-1]+=error*(3/16)
                src[y+1,x]+=error*(5/16)
                if x+1<w:src[y+1,x+1]+=error*(1/16)
    return indices

@lru_cache(maxsize=24)
def _quantize(image_data: str, algorithm:str, count:int, resolution:int,
              filament_palette:tuple, overrides:tuple):
    if not image_data:
        raise ValueError("Загрузите изображение для таблички.")
    img=_read_image(image_data)
    img.thumbnail((resolution,resolution),Image.Resampling.LANCZOS)
    rgba=np.array(img.convert("RGBA"))
    alpha=rgba[:,:,3]>=128
    pixels=rgba[:,:,:3].copy()
    if not alpha.any():
        raise ValueError("В изображении нет непрозрачных пикселей.")
    if filament_palette:
        colors=np.asarray([_rgb(x) for x in filament_palette[:count]],dtype=np.uint8)
    elif algorithm=="kmeans":
        cv2.setRNGSeed(17)
        sample=pixels[alpha].reshape(-1,3).astype(np.float32)
        k=min(count,len(np.unique(sample,axis=0)))
        _,labels,centers=cv2.kmeans(sample,k,None,
                  (cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER,16,0.3),
                  3,cv2.KMEANS_PP_CENTERS)
        colors=np.clip(centers,0,255).astype(np.uint8)
    else:
        flattened=Image.fromarray(pixels,"RGB")
        pal=flattened.quantize(colors=count,method=Image.Quantize.MEDIANCUT,
                               dither=Image.Dither.NONE)
        values=pal.getpalette()
        used=sorted(set(np.array(pal)[alpha].flat))
        colors=np.array([values[i*3:i*3+3] for i in used],dtype=np.uint8)
    if len(colors)==0:raise ValueError("Не удалось подобрать цвета.")
    # Sorted color order is stable for palette overrides and saves.
    colors=colors[np.lexsort((colors[:,2],colors[:,1],colors[:,0]))]
    src_colors=colors.copy()
    if algorithm=="floyd":
        indices=_floyd(pixels,src_colors)
    else:
        indices=_nearest(pixels,src_colors)
    for i,color in enumerate(overrides):
        if i<len(colors):colors[i]=_rgb(color)
    indices[~alpha]=255
    rendered=np.zeros((*indices.shape,4),dtype=np.uint8)
    rendered[alpha,:3]=colors[indices[alpha]]
    rendered[alpha,3]=255
    preview=Image.fromarray(rendered,"RGBA")
    buffer=io.BytesIO()
    preview.save(buffer,format="PNG")
    url="data:image/png;base64,"+base64.b64encode(buffer.getvalue()).decode()
    return indices,tuple(_hex(c) for c in colors),url

def optimized_picture(options: PictureSettings):
    return _quantize(options.image_data,options.algorithm,options.color_count,
                     options.resolution,tuple(options.filament_palette),
                     tuple(options.color_overrides))

def picture_summary(options:PictureSettings):
    indices,colors,url=optimized_picture(options)
    return {"image_url":url,"colors":list(colors),
            "pixel_width":int(indices.shape[1]),"pixel_height":int(indices.shape[0]),
            "pixel_counts":[int(np.count_nonzero(indices==i)) for i in range(len(colors))]}
