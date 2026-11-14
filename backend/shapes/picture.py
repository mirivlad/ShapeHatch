"""Palette reduction for printing: preserve flat-color artwork, avoid blur,
and use the identical indexed image for the live preview and printable parts."""
import base64
from functools import lru_cache
import io

import cv2
import numpy as np
from PIL import Image

from .image_trace import _read_image
from .schemas import PictureSettings


def _rgb(color: str):
    return tuple(int(color[i:i+2], 16) for i in (1, 3, 5))


def _hex(rgb):
    return "#" + "".join(f"{int(x):02X}" for x in rgb)


def _nearest(pixels: np.ndarray, palette: np.ndarray):
    colors=np.asarray(palette,dtype=np.int16)
    result=np.empty(pixels.shape[:2],dtype=np.uint8)
    for y in range(len(pixels)):
        row=pixels[y].astype(np.int16)
        distance=((row[:,None,:]-colors[None,:,:]).astype(np.int32)**2).sum(axis=2)
        result[y]=distance.argmin(axis=1)
    return result


def _diffuse(pixels, palette, mode):
    """Floyd–Steinberg and Atkinson error diffusion with serpentine scanning."""
    colors=np.asarray(palette,dtype=np.float32)
    src=pixels.astype(np.float32).copy()
    h,w=src.shape[:2]
    indices=np.zeros((h,w),dtype=np.uint8)
    kernel=([(1,0,7/16),(-1,1,3/16),(0,1,5/16),(1,1,1/16)]
            if mode=="floyd" else
            [(1,0,1/8),(2,0,1/8),(-1,1,1/8),(0,1,1/8),(1,1,1/8),(0,2,1/8)])
    for y in range(h):
        sign=1 if y%2==0 else -1
        for x in (range(w) if sign==1 else range(w-1,-1,-1)):
            sample=np.clip(src[y,x],0,255)
            d=colors-sample
            j=int((d*d).sum(axis=1).argmin())
            indices[y,x]=j
            error=sample-colors[j]
            for dx,dy,weight in kernel:
                nx=x+dx*sign
                ny=y+dy
                if 0<=nx<w and ny<h:
                    src[ny,nx]+=error*weight
    return indices


def _bayer(pixels, palette):
    matrix=np.asarray([[0,8,2,10],[12,4,14,6],[3,11,1,9],[15,7,13,5]],dtype=np.float32)
    h,w=pixels.shape[:2]
    offset=(np.tile(matrix,((h+3)//4,(w+3)//4))[:h,:w]-7.5)*4
    return _nearest(np.clip(pixels.astype(np.float32)+offset[:,:,None],0,255).astype(np.uint8),
                    palette)


def _dominant_logo_colors(pixels, valid, count):
    """Find dominant solid colors rather than averaging the antialiased boundary.

    Quantizing 4 high bits per channel groups JPEG noise around true colors.
    Rare boundary shades are not given their own expensive plastic.
    """
    flat=pixels[valid]
    if not len(flat):
        return np.array([],dtype=np.uint8).reshape(0,3)
    bins=(flat.astype(np.int32)//16)
    keys=(bins[:,0]*256+bins[:,1]*16+bins[:,2])
    freq=np.bincount(keys,minlength=4096)
    order=np.argsort(-freq,kind="stable")
    palette=[]
    min_count=max(2,round(len(flat)*0.0007))
    for key in order:
        if freq[key]<min_count:
            break
        sample=flat[keys==key]
        candidate=np.median(sample,axis=0).astype(np.uint8)
        if all(np.sum((candidate.astype(np.int32)-color.astype(np.int32))**2)>=38**2
               for color in palette):
            palette.append(candidate)
        if len(palette)>=count:
            break
    if not palette:
        palette=[np.median(flat,axis=0).astype(np.uint8)]
    return np.asarray(palette,dtype=np.uint8)


def _median_colors(pixels, valid, count):
    img=Image.fromarray(pixels,"RGB")
    pal=img.quantize(colors=count,method=Image.Quantize.MEDIANCUT,
                     dither=Image.Dither.NONE)
    palette=pal.getpalette()
    used=sorted(set(np.array(pal)[valid].flat))
    return np.asarray([palette[i*3:i*3+3] for i in used],dtype=np.uint8)


def _kmeans_colors(pixels, valid, count):
    sample=pixels[valid].reshape(-1,3).astype(np.float32)
    unique=np.unique(sample,axis=0)
    count=min(count,len(unique))
    if count==1:
        return unique.astype(np.uint8)
    cv2.setRNGSeed(17)
    _,_,centers=cv2.kmeans(sample,count,None,
         (cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER,20,0.15),
         3,cv2.KMEANS_PP_CENTERS)
    return np.clip(np.rint(centers),0,255).astype(np.uint8)


@lru_cache(maxsize=12)
def _quantize(image_data: str, algorithm: str, count: int, resolution: int,
              filament_palette: tuple, overrides: tuple,
              dithering: str="none", image_kind: str="logo"):
    if not image_data:
        raise ValueError("Загрузите изображение для таблички.")
    image=_read_image(image_data)
    # Logo edges stay sharp. Photographs use smooth reduction; this is *not*
    # a physical-mm setting and never changes the plate dimensions.
    if max(image.size)>resolution:
        image.thumbnail((resolution,resolution),
                        Image.Resampling.NEAREST if image_kind=="logo"
                        else Image.Resampling.LANCZOS)
    rgba=np.asarray(image.convert("RGBA"))
    valid=rgba[:,:,3]>=128
    if not valid.any():
        raise ValueError("В изображении нет непрозрачных пикселей.")
    pixels=rgba[:,:,:3].copy()
    unique=np.unique(pixels[valid].reshape(-1,3),axis=0)
    legacy_dither=algorithm=="floyd"
    if legacy_dither:
        algorithm="median"
        if dithering=="none":dithering="floyd"

    if filament_palette:
        # The precise filament colors are authoritative and never re-quantized.
        colors=np.asarray([_rgb(x) for x in filament_palette[:count]],dtype=np.uint8)
    elif algorithm=="original":
        if len(unique)>count:
            raise ValueError(
                f"В исходном рисунке {len(unique)} цветов, лимит {count}. "
                "Выберите «Авто (логотип)» либо увеличьте число цветов.")
        colors=unique.astype(np.uint8)
    elif len(unique)<=count:
        # Critical no-loss fast path: no K-means, no blended anti-aliasing,
        # even if the selected reduction algorithm is Median Cut or K-means.
        colors=unique.astype(np.uint8)
    elif algorithm=="kmeans":
        colors=_kmeans_colors(pixels,valid,count)
    elif algorithm in ("auto","nearest") and image_kind=="logo":
        colors=_dominant_logo_colors(pixels,valid,count)
    elif algorithm=="auto" and image_kind=="photo":
        colors=_kmeans_colors(pixels,valid,count)
    else:
        colors=_median_colors(pixels,valid,count)
    if len(colors)==0:
        raise ValueError("Не удалось определить цвета изображения.")
    if not filament_palette:
        # Order stable across invocations, saving and manual overrides.
        colors=colors[np.lexsort((colors[:,2],colors[:,1],colors[:,0]))]
    exact=(not filament_palette and len(unique)<=count)
    if dithering=="floyd" and not exact:
        indices=_diffuse(pixels,colors,"floyd")
    elif dithering=="atkinson" and not exact:
        indices=_diffuse(pixels,colors,"atkinson")
    elif dithering=="bayer" and not exact:
        indices=_bayer(pixels,colors)
    else:
        indices=_nearest(pixels,colors)
    # Replacing one color changes only its material assignment, never
    # re-runs the quantizer or changes a pixel's color-region index.
    colors=colors.copy()
    for i,color in enumerate(overrides):
        if i<len(colors):colors[i]=_rgb(color)
    indices[~valid]=255
    output=np.zeros((*indices.shape,4),dtype=np.uint8)
    output[valid,:3]=colors[indices[valid]]
    output[valid,3]=255
    buffer=io.BytesIO()
    Image.fromarray(output,"RGBA").save(buffer,format="PNG")
    return (indices,tuple(_hex(c) for c in colors),
            "data:image/png;base64,"+base64.b64encode(buffer.getvalue()).decode())


def optimized_picture(options: PictureSettings):
    return _quantize(options.image_data,options.algorithm,options.color_count,
                     options.resolution,tuple(options.filament_palette),
                     tuple(options.color_overrides),
                     options.dithering,options.image_kind)


def picture_summary(options: PictureSettings):
    indices,colors,url=optimized_picture(options)
    return {"image_url":url,"colors":list(colors),
            "pixel_width":int(indices.shape[1]),"pixel_height":int(indices.shape[0]),
            "pixel_counts":[int(np.count_nonzero(indices==i)) for i in range(len(colors))]}
