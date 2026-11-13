# ShapeHatch

**ShapeHatch** — open-source browser-based parametric 3D workshop. Turn silhouettes into keychains, create multicolor text nameplates, preview in 3D, and export ready-to-slice STL/3MF.

[Документация на русском](docs/README.ru.md)

## First MVP features

- Silhouette from PNG, JPG, WebP or SVG: image-to-polygon, dimensions, thickness, planar ring with a hole, inversion and cutout modes.
- Text plates: five shapes; DejaVu fonts with Cyrillic; embossed, inlaid, engraved text; separate colors.
- 3D viewer with mouse orbit, pan, zoom, orthographic camera shortcuts and orientation cube.
- STL, multipart STL ZIP, grouped multicolor 3MF.
- Local editable gallery powered by IndexedDB (no account, no server-side gallery yet).
- All necessary services via Docker Compose.

## Quick start

    git clone https://github.com/mirivlad/ShapeHatch
    cd ShapeHatch
    docker compose up -d --build

Open **http://localhost:8086** on the Docker host. By default the web service binds to **127.0.0.1**; publish securely behind an HTTPS reverse proxy, or change the binding knowingly.

## Development

Backend: Python 3.12, FastAPI, OpenCV, Pillow, CairoSVG, Shapely, Trimesh.

    cd backend
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    .venv/bin/uvicorn app:app --reload

Frontend: Node 22+, TypeScript, React, react-three-fiber / Three.js.

    cd frontend
    npm install
    npm run dev

Vite proxies API requests to http://localhost:8000.

Run backend tests in the API container:

    docker compose run --rm api python -m unittest discover -s tests -v

## Notes

- **3MF** has grouped colored components. A slicer must still map materials to filaments. Use **STL ZIP** if grouped colors are unsupported. Plain **STL is colorless**.
- Models are validated for watertight geometry. Thin walls and details may still be unprintable; real printer tests are required.
- The gallery is **local browser storage**, not a public multi-user service. Clearing browser data destroys locally saved projects.
- SVG sanitization is intentionally strict; external resources and active scripts are rejected. Keep the API isolated and resource-limited.

Roadmap: shared gallery, drag placement of ring/text, multiple text objects, model thumbnails, new generators (vases/boxes/housings), slicer validation.

## License

AGPL-3.0-only. See LICENSE.
