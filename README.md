# ShapeHatch

**ShapeHatch** — open-source browser-based parametric 3D workshop. Turn silhouettes into keychains, create multicolor text nameplates, preview in 3D, and export ready-to-slice STL/3MF.

[Документация на русском](docs/README.ru.md)

## First MVP features

- Silhouette from PNG, JPG, WebP or SVG: filled or outline artwork, selectable enclosed regions (same material, inlaid second material, or through-holes), dimensions and thickness, flat loop or edge-mounted rounded post with a transverse ring hole.
- Geometric upper-edge rounding, adjustable from 0 to 0.4 mm (default 0.3 mm), for silhouettes and plates.
- Text plates: five shapes; 12 Cyrillic-capable fonts (DejaVu, Russo One, Play Bold, PT Sans, Lobster, Rubik Mono One, Unbounded, Comfortaa, Terminus TTF); multiline text with left/center/right alignment and adjustable line spacing; optional through-hole, flat loop or cross-drilled mounting post; embossed, inlaid, engraved text; separate colors.
- 3D viewer with mouse orbit, pan, zoom, orthographic camera shortcuts and orientation cube. Drag the turquoise handle to snap a mount to the real external contour; drag the orange handle to move plate lettering in X/Y.
- STL, multipart STL ZIP, grouped multicolor 3MF.
- Single-open accordion settings in the editor (the first section opens by default); ring-hole diameter and wall thickness retained between new projects in browser localStorage.
- Local editable gallery powered by IndexedDB (no account, no server-side gallery yet).
- Install with Docker Compose for development, or the ready-made [Portainer Git stack](docs/PORTAINER.md) using GHCR images for manual Pull and redeploy.

## Quick start

    git clone https://github.com/mirivlad/ShapeHatch
    cd ShapeHatch
    docker compose up -d --build

Open **http://localhost:8086** on the machine running Docker Compose. From another device on your LAN, use **http://SERVER_IP:8086**, replacing SERVER_IP with that machine's IP address. Docker Compose publishes port 8086 on all host interfaces by default; restrict it with your firewall or bind to localhost if needed. Configure HTTPS and access controls before exposing the service to the internet.

## Updating via Portainer

The [Portainer stack](portainer-stack.yml) uses published `latest` images from GHCR.
After CI passes for `main`, use **Stacks → shapehatch → Pull and redeploy**
to pull and run the new version. Port 8086 remains unchanged. See
[Portainer instructions](docs/PORTAINER.md).

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
- Models are validated for watertight geometry. For the cross-drilled post, model thickness is set automatically to the nominal post diameter (hole diameter + twice the wall thickness). Thin walls and details may still be unprintable; real printer tests are required.
- The gallery is **local browser storage**, not a public multi-user service. Clearing browser data destroys locally saved projects.
- SVG sanitization is intentionally strict; external resources and active scripts are rejected. Keep the API isolated and resource-limited.
- The eight extra bundled fonts are licensed under SIL OFL 1.1; see [font attribution and license copies](backend/fonts/README.md). Text with narrow strokes (especially Terminus) must be verified before printing.

Roadmap: shared gallery, multiple text objects, model thumbnails, new generators (vases/boxes/housings), slicer validation.

## License

AGPL-3.0-only. See LICENSE.
