import logging
import json

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from gallery import get_store, owner_from_key, PER_PROJECT_BYTES
from shapes.build import generate
from shapes.exporter import make_3mf, make_stl, make_stl_zip
from shapes.schemas import GenerateRequest, PictureSettings
from shapes.picture import picture_summary

logger = logging.getLogger("shapehatch.geometry")
app = FastAPI(title="ShapeHatch API", version="0.5.1")
# In production Nginx serves frontend + /api on one origin.
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
                   allow_credentials=False, allow_methods=["GET", "POST", "PUT", "DELETE"],
                   allow_headers=["Content-Type", "X-Gallery-Key"])


@app.get("/api/health")
def health():
    return {"ok": True, "version": "0.5.1"}


@app.post("/api/preview")
def preview(request: GenerateRequest):
    try:
        return generate(request)
    except ValueError as error:
        opts = {"plate": request.plate, "silhouette": request.silhouette,
                "box": request.box}[request.kind]
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
    if format not in ("3mf", "3mf-anycubic", "stl", "stl-zip"):
        raise HTTPException(status_code=404, detail="Неизвестный формат.")
    try:
        model = generate(request)
        if format in ("3mf", "3mf-anycubic"):
            profile = "orca" if format == "3mf-anycubic" else "core"
            data, mime, ext = make_3mf(model, slicer_profile=profile), "model/3mf", "3mf"
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


@app.get("/api/gallery/projects")
def gallery_list(x_gallery_key: str | None = Header(default=None)):
    return get_store().list(owner_from_key(x_gallery_key))


@app.get("/api/gallery/projects/{project_id}")
def gallery_get(project_id: str, x_gallery_key: str | None = Header(default=None)):
    return get_store().get(owner_from_key(x_gallery_key), project_id)


@app.put("/api/gallery/projects/{project_id}")
async def gallery_put(project_id: str, request: Request,
                      x_gallery_key: str | None = Header(default=None)):
    owner = owner_from_key(x_gallery_key)
    size = request.headers.get("content-length")
    if size:
        try:
            content_length = int(size)
        except ValueError as error:
            raise HTTPException(status_code=400, detail="Неверный Content-Length.") from error
        if content_length > PER_PROJECT_BYTES + 1000:
            raise HTTPException(status_code=413, detail="Проект слишком большой.")
    raw = await request.body()
    if len(raw) > PER_PROJECT_BYTES + 1000:
        raise HTTPException(status_code=413, detail="Проект слишком большой.")
    try:
        project = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as error:
        raise HTTPException(status_code=422, detail="Неверный JSON проекта.") from error
    return get_store().put(owner, project_id, project)


@app.delete("/api/gallery/projects/{project_id}")
def gallery_delete(project_id: str, x_gallery_key: str | None = Header(default=None)):
    get_store().delete(owner_from_key(x_gallery_key), project_id)
    return {"ok": True}