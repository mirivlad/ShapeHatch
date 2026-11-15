# ShapeHatch

**ShapeHatch** — open-source browser-based parametric 3D workshop. Turn silhouettes into keychains, create multicolor text nameplates, preview in 3D, and export ready-to-slice STL/3MF.

[Документация на русском](docs/README.ru.md)

## First MVP features

- Silhouette from PNG, JPG, WebP or SVG: filled or outline artwork, selectable enclosed regions (same material, inlaid second material, or through-holes), dimensions and thickness, flat loop or edge-mounted rounded post with a transverse ring hole.
- Geometric upper-edge rounding, adjustable from 0 to 0.4 mm (default 0.3 mm), for silhouettes and plates.
- **0.3.3 face-down orientation:** imported images are automatically mirrored horizontally in print XY coordinates (not in the 2D optimizer), so after flipping the printed part over its front face matches the source. Bottom view uses the matching face-on camera orientation; do not manually mirror again in the slicer.
- **0.3.2 mesh stability:** multicolor islands touching only at corners or colored regions with kissing holes now retain separate manifold boundaries; a sub-micron cleanup is applied only to invalid-contact regions. An error overlay clearly distinguishes the previous valid model from current failed generation, and backend logs include printable part/geometry context without logging uploaded image data.
- **Plate wizard:** choose text or picture. The shared step-by-step wizard (five steps for silhouettes/text plates, six for image plates) keeps all earlier steps editable. Only dependency-affected contours, text meshes, image regions and extrusion geometry are rebuilt (bounded per-worker caches).
- **Multicolor image plates:** choose plate shape and dimensions **before** importing the picture, then fit/cover/stretch/scale and drag the picture on the plate. Auto logo palette detection preserves already-compatible colors instead of requantizing them; nearest, Median Cut, K-Means and original palette modes (2–16 colors). Floyd–Steinberg, Atkinson and Bayer dithering are separate optional modes. Live before/after preview, adjustable raster detail independently of physical size, real filament palette, and printable face-down color volumes on Z=0.
- **Shared attachment wizard for plates and silhouettes:** no mount, through-hole, flat loop, transverse post or up to eight open magnet pockets. Round/rectangular pockets have adjustable dimensions, clearance, depth and per-pocket X/Y positions; move pockets in 3D. Picture plates have pockets on the rear (top) surface.
- Text plates: five shapes; 12 Cyrillic-capable fonts (DejaVu, Russo One, Play Bold, PT Sans, Lobster, Rubik Mono One, Unbounded, Comfortaa, Terminus TTF); multiline text with left/center/right alignment and adjustable line spacing; optional through-hole, flat loop or cross-drilled mounting post; embossed, inlaid, engraved text; separate colors.
- 3D viewer with mouse orbit, pan, zoom, orthographic camera shortcuts and orientation cube. Drag the turquoise handle to snap a mount to the real external contour; drag the orange handle to move plate lettering in X/Y.
- STL, multipart STL ZIP, grouped multicolor 3MF, and experimental Anycubic Slicer Next / Orca-style 3MF with per-part extruder assignments. Core-spec material resources now use the correct namespace, with named parts and per-object palette indexes.
- Per-step editing with back/next and direct step navigation; ring-hole diameter and wall thickness retained between new projects in browser localStorage.
- Private server-backed galleries stored in SQLite with persistent Docker volume and client-generated recovery keys; IndexedDB remains a local fallback. Reopen, edit, and re-export projects from any browser with the key.
- Install with Docker Compose for development, or the ready-made [Portainer Git stack](docs/PORTAINER.md) using GHCR images for manual Pull and redeploy.

## Installation

ShapeHatch runs as **two services**: `web` (Nginx serves the UI and proxies `/api/`)
and `api` (FastAPI generates models). Both installation methods expose only the
web service on **port 8086** by default. A persistent Docker volume stores
server-side project galleries; the browser also keeps a local copy.

**Requirements:** Docker Engine with the Docker Compose v2 plugin for option A,
or Portainer connected to a Docker environment for option B. Portainer images
are currently published for **linux/amd64**. A reverse proxy with HTTPS and
access controls is strongly recommended for public deployment.

### Option A — Docker Compose (build from source)

Run on the machine where Docker is installed:

```bash
git clone https://github.com/mirivlad/ShapeHatch.git
cd ShapeHatch
docker compose up -d --build
docker compose ps
```

After both services start, open `http://localhost:8086` on the Docker host or
`http://SERVER_IP:8086` from another device. Check the API through Nginx:

```bash
curl -fsS http://localhost:8086/api/health
```

The default mapping `8086:80` is defined in **`compose.yaml`**. If port 8086
is busy, change the **host-side** port there (e.g. `8090:80`) and recreate the
services. The `SHAPEHATCH_HTTP_PORT` variable described below is **not** used
by this source-build Compose file.

To update from the Git repository (run from the cloned directory):

```bash
git pull --ff-only
docker compose up -d --build
```

Troubleshooting and shutdown:

```bash
docker compose logs --tail=100 api web
docker compose down
```

`docker compose down` removes containers and the network but **retains named
volumes**. Do **not** use `docker compose down -v` unless you intentionally
want to delete the saved project database.

### Option B — Portainer (ready-made GHCR images)

No source checkout or local build is needed on the Portainer-managed host.

1. Open **Stacks → Add stack**, choose **Repository** (Git repository).
2. Set **Name** to `shapehatch`.
3. Set **Repository URL** to `https://github.com/mirivlad/ShapeHatch`.
4. Set **Repository reference** to `refs/heads/main`.
5. Set **Compose path** to `portainer-stack.yml` (**not** `compose.yaml`).
6. Optional: add the environment variable `SHAPEHATCH_HTTP_PORT=8090` to use
   port 8090 instead of the default 8086.
7. Click **Deploy the stack**. When `api` and `web` are running, visit
   `http://DOCKER_HOST_IP:8086` (or your custom port) and
   `http://DOCKER_HOST_IP:8086/api/health`.

The stack pulls the public images
`ghcr.io/mirivlad/shapehatch-api:latest` and
`ghcr.io/mirivlad/shapehatch-web:latest`; **no GitHub token is needed for
public packages**. Portainer must be able to reach GitHub and GHCR.

To update: wait for the **Publish Docker images** GitHub Actions workflow for
`main` to succeed (both images must be published), then open
**Stacks → shapehatch → Pull and redeploy** and enable the image re-pull option
if your Portainer version offers one. A simple restart without pulling images
will not install the new release.

For screenshots-independent details and troubleshooting, see the
**[Portainer guide (Russian)](docs/PORTAINER.md)**.

### Saved projects and data safety (both methods)

- The API stores project data in SQLite at `/data/gallery.sqlite3` in the
  persistent named volume `gallery-data`. Docker/Portainer usually prefixes
  the actual volume name with the Compose project/stack name; inspect it using
  `docker volume ls` or Portainer → Volumes.
- Back up that volume regularly; use a **SQLite-consistent backup** while the
  service is running (or stop the API before copying its database). Never
  remove the volume while upgrading or recreating the stack.
- Local browser projects are stored separately in IndexedDB. A project is
  copied to the server when saved from the editor; older browser-only projects
  can be transferred using the gallery's upload action.
- Save the **64-character gallery recovery key** in a secure place. It grants
  access to all projects in that gallery. Without the key or browser data,
  projects cannot be recovered through the application.
- The HTTP port binds to all host interfaces by default. **Do not expose this
  beta service directly to the Internet without HTTPS, access controls and
  request-rate limits**: the server gallery uses bearer keys, not accounts.

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

- **3MF** uses the standards-compliant core `<basematerials>` resource and named colored components. Individual slicers may still require **manual assignment of objects to actual filaments/AMS slots**; generic 3MF material display colors are not printer-specific filament assignments. Use **STL ZIP** if grouped colors are unsupported. Plain **STL is colorless**.
- Models are validated for watertight geometry. For the cross-drilled post, model thickness is set automatically to the nominal post diameter (hole diameter + twice the wall thickness). Thin walls and details may still be unprintable; real printer tests are required.
- Galleries are **private bearer-key archives**: keep your recovery key somewhere safe before clearing browser data or changing devices. Anyone with this key can access or delete your saved models. Server-side copies persist in the Docker volume; no accounts or password recovery yet.
- SVG sanitization is intentionally strict; external resources and active scripts are rejected. Keep the API isolated and resource-limited.
- The eight extra bundled fonts are licensed under SIL OFL 1.1; see [font attribution and license copies](backend/fonts/README.md). Text with narrow strokes (especially Terminus) must be verified before printing.

Roadmap: verify Anycubic/Orca 3MF against a real slicer, model thumbnails, per-user authentication and abuse prevention, multiple text objects, box generator. Enclosed magnets are deferred pending holding-force tests.

## Numeric input (0.4.1)

All editable numeric fields, including magnet X/Y coordinates, now accept both decimal dots and commas, negative values and temporary blank input. Press Enter or leave the field to normalize it; arrow up/down adjusts by the field step.

## Saved projects

Click **Save project** in the editor. The complete source image and parameters are
saved to both the browser and a private server gallery. Under **My gallery** you
can reopen and change a design, or download its 3MF again directly.

To use the same gallery on another device, use **Copy recovery key** on the first
device, then **Restore gallery by key** on the second. The key is 64 hex digits and
grants full read/write access; store it like a password. Existing browser-only
projects can be uploaded individually from the gallery. If the server is offline,
local saving still works; no implicit upload of old projects takes place.

Server data lives in the named Docker volume mounted at `/data`, in
`gallery.sqlite3`. Back up this volume (including SQLite WAL files when present).
The current limits are 100 projects and 80 MB per gallery, 9 MB per project,
and 500 MB overall. The anonymous key-based server gallery is an early beta;
deploy behind HTTPS, and consider access/rate limiting before opening writes
to a large public audience. It is **not an account system**.

The extra **3MF Anycubic / Orca** download adds slicer-specific filament slot
metadata. It is experimental and targets Orca-based Anycubic Slicer Next;
standard 3MF export is retained. Verify filament-to-slot mapping and printer
settings before printing; older Anycubic Slicer versions may ignore this metadata.

## License

AGPL-3.0-only. See LICENSE.