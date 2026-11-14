import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from shapes.build import generate
from shapes.exporter import make_3mf, make_stl, make_stl_zip
from shapes.schemas import GenerateRequest, PictureSettings
from shapes.picture import picture_summary

logger = logging.getLogger("shapehatch.geometry")
app = FastAPI(title="ShapeHatch API", version="0.3.2")
# In production Nginx serves frontend + /api on one origin.
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
                   allow_credentials=False, allow_methods=["GET", "POST"],
                   allow_headers=["Content-Type"])


@app.get("/api/health")
def health():
    return {"ok": True, "version": "0.3.2"}


@app.post("/api/preview")
def preview(request: GenerateRequest):
    try:
        return generate(request)
    except ValueError as error:
        opts = request.plate if request.kind == "plate" else request.silhouette
        logger.warning(
            "Preview 422 kind=%s content=%s size_mm=%sx%s rounding_mm=%s "
            "picture_colors=%s raster_resolution=%s: %s",
            request.kind,
            getattr(opts, "content_type", "-"),
            getattr(opts, "width_mm", "-"),
            getattr(opts, "height_mm", "-"),
            getattr(opts, "top_round_mm", "-"),
            getattr(getattr(opts, "picture", None), "color_count", "-"),
            getattr(getattr(opts, "picture", None), "resolution", "-"),
            str(error),
        )
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/export/{format}")
def export(request: GenerateRequest, format: str):
    if format not in ("3mf", "stl", "stl-zip"):
        raise HTTPException(status_code=404, detail="Неизвестный формат.")
    try:
        model = generate(request)
        if format == "3mf":
            data, mime, ext = make_3mf(model), "model/3mf", "3mf"
        elif format == "stl":
            data, mime, ext = make_stl(model), "model/stl", "stl"
        else:
            data, mime, ext = make_stl_zip(model), "application/zip", "zip"
        return Response(content=data, media_type=mime,
                        headers={"Content-Disposition": f'attachment; filename="shapehatch.{ext}"'})
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/picture/preview")
def picture_preview(options: PictureSettings):
    try:
        return picture_summary(options)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
