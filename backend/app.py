from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from shapes.build import generate
from shapes.exporter import make_3mf, make_stl, make_stl_zip
from shapes.schemas import GenerateRequest

app = FastAPI(title="ShapeHatch API", version="0.2.0")
# In production Nginx serves frontend + /api on one origin.
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
                   allow_credentials=False, allow_methods=["GET", "POST"],
                   allow_headers=["Content-Type"])


@app.get("/api/health")
def health():
    return {"ok": True, "version": "0.2.0"}


@app.post("/api/preview")
def preview(request: GenerateRequest):
    try:
        return generate(request)
    except ValueError as error:
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
