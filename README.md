# ShapeHatch

[![Угостить разработчика кофе / Buy me a coffee](https://img.shields.io/badge/Support-Buy%20me%20a%20coffee-7055a5?style=flat-square&logo=buymeacoffee&logoColor=white)](https://mirv.top/support/)

**ShapeHatch** — open-source browser-based parametric 3D workshop. Turn silhouettes into keychains, create multicolor text nameplates, preview in 3D, and export ready-to-slice STL/3MF.

[Документация на русском](docs/README.ru.md)

## Features — current version 0.5.1

ShapeHatch is an open-source workshop for making printable models, from simple
keychains to multicolor signs. Built for experimenting and sharing designs.

### What's new in 0.5.x

- **0.5.1 — Independent box compartments and covers.** Instead of a
  mutually exclusive "box mode", enable compartments and select a lid separately.
  Draw a proportional table of compartments with variable column widths and
  row depths (millimetres), drag divider boundaries, merge rectangular areas,
  and split them again.
  Examples include one full-width cavity beside three narrower compartments.
  Choose no lid, a slip-over lid, or a **recessed/inset lid** with user-set
  insertion depth, lip thickness and fit clearance. The inset lip has relief
  gaps near full-height internal partitions so it can actually fit.
  Existing v0.5.0 box designs are migrated when reopened; hinges are planned
  separately and **not** included in this version.
- **0.5.0 — Parametric boxes.** Generate an open-top storage box, a box with a
  removable slip-over lid, or a box with integral grid dividers. Configure
  outer dimensions, floor and wall thickness, corner radius, divider grid,
  lid skirt and fit clearance. Body and dividers form a single watertight mesh;
  a lid is exported as a separate watertight part placed beside the box in a
  printable orientation. The generator reuses preview, STL/3MF exports and
  persistent project galleries.

### What's new in 0.4.x

- **0.4.1 — Easier numeric editing.** All editable numbers, including magnet X/Y
  positions, allow an initial minus sign, either `.` or `,` as a decimal separator,
  and clearing the whole field before entering another number. Incomplete input
  does not force zero or overwrite the last valid setting. Arrow keys still work.
- **0.4.0 — Persistent project gallery.** Save source images and all editing
  parameters to both browser storage and a private SQLite gallery on the server.
  Reopen and modify projects, re-export 3MF, migrate older browser-only projects,
  and recover your gallery on another device using a 64-character access key.
  The database lives in a persistent Docker volume.
- **0.4.0 — Anycubic / Orca export.** In addition to standard 3MF, export an
  experimental Orca-style 3MF with per-part extruder assignments and filament
  colors for Anycubic Slicer Next. The actual filament-to-slot mapping still
  needs verification in the slicer before printing.

### Model creation and editing

- **Silhouettes:** import PNG, JPG, WebP or SVG. Generate filled shapes or
  outlines, adjust dimensions, smoothing and thickness, and choose how enclosed
  regions are handled: same material, colored inlay or through-hole.
- **Text plates:** five base shapes, 12 Cyrillic-capable fonts, multiline text,
  alignment and line spacing. Choose raised, inlaid or engraved lettering,
  separate colors, and move the text on the plate.
- **Image plates:** set the plate dimensions before loading a picture; fit,
  fill/crop, stretch or manually scale and position it. Preserve compatible
  source palettes or reduce to 2–16 colors using nearest-color, Median Cut or
  K-Means. Optional Floyd–Steinberg, Atkinson and Bayer dithering, plus a live
  before/after preview and adjustable image detail.
- **Attachments for both generators:** no attachment, through-hole, flat loop,
  edge-mounted post with a transverse hole, or up to eight open round/rectangular
  magnet pockets with adjustable size, clearance, depth and independent X/Y
  positions. Handles can be dragged directly in the 3D viewer.
- **3D preview and navigation:** orbit, pan, zoom, orthographic views and an
  orientation cube; drag handles to reposition attachments, image or text.
  A step-by-step editor lets you revisit earlier settings without starting over.
- **Printable geometry:** adjustable upper-edge rounding (0–0.4 mm), optimized
  reconstruction and validated watertight meshes. For face-down multicolor
  printing, image geometry is mirrored automatically so the finished front face
  matches the original picture after the print is flipped over.
- **Exports:** plain STL, multipart STL ZIP, grouped multicolor standard 3MF,
  and the experimental Anycubic / Orca 3MF profile. Color parts are separately
  named; actual printer filament slots should always be confirmed in the slicer.
- **Browser preferences:** ring-hole diameter and wall thickness are retained
  for new projects. Projects can also be reopened from the gallery for later
  editing and printing.
- **Self-hosting:** Docker Compose builds from source; the
  [Portainer Git stack](docs/PORTAINER.md) uses prebuilt GHCR images.

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

Roadmap: verify Anycubic/Orca 3MF against a real slicer, vase generator, more box lid designs, model thumbnails, per-user authentication and abuse prevention, multiple text objects. Enclosed magnets are deferred pending holding-force tests.

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

## Поддержать разработчика / Support development

Если проект оказался полезен, вы можете добровольно поддержать его развитие. / If this project is useful to you, you can voluntarily support its development.

[Страница поддержки / Support page](https://mirv.top/support/)
