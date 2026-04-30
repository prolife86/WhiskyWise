# Changelog

All notable changes to WhiskyWise are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---
 
## [1.3.4] — 2026-04-30 🔒🧹 Security, Code Quality & Compatibility
 
### Security
- **Photo ownership enforced** — the `serve_photo` route now confirms that the
  requested filename belongs to a `Whisky` record owned by the current user
  before serving it. Previously any logged-in user could view another user's
  photos by guessing the filename. Returns `403 Forbidden` on ownership
  mismatch.
- **CSRF protection wired up** — `Flask-WTF`'s `CSRFProtect` is now
  initialised on the app. All 13 POST forms already carried a
  `{{ csrf_token() }}` hidden field and the `<meta name="csrf-token">` tag
  (used by AJAX calls) was already present in `base.html`; this change makes
  the backend actually validate those tokens on every state-changing request.
  A friendly flash message is shown if a token has expired rather than a raw
  `400` response. The `/api/photo/.../rotate` AJAX endpoint is exempted via
  `@csrf.exempt` (it sends the token as an `X-CSRF-Token` header instead).
- **Login rate limiting** — the `/login` POST endpoint is now limited to
  5 attempts per minute per IP using `Flask-Limiter`. Relevant for
  installations exposed via a reverse proxy (Nginx + Tailscale).
- **SQLite WAL mode enabled** — `PRAGMA journal_mode=WAL` is now set on every
  new database connection via a `sqlalchemy.event` hook. Improves concurrent
  read performance under the 4-thread Gunicorn configuration and prevents
  reader/writer contention.
### Fixed
- **`change_password.html` missing CSRF token** — the standalone change
  password template was the only form without a `{{ csrf_token() }}` hidden
  field. Added.
### Changed
- **`APP_VERSION` driven from git tag** — `APP_VERSION` is no longer hardcoded
  in `app.py`. It is now read from the `APP_VERSION` environment variable
  (injected at Docker build time via `--build-arg APP_VERSION=...`), falling
  back to `'dev'` for local builds. The CI workflow injects the version from
  the git tag (`refs/tags/v1.3.4` → `1.3.4`) automatically on every release.
  `app.py` and `Dockerfile` no longer need touching for a version bump.
- **`datetime.utcnow()` replaced** — all five occurrences replaced with
  `datetime.now(timezone.utc)` following Python 3.12+'s deprecation of
  `datetime.utcnow()`. Model `default=` columns now use a `lambda` wrapper
  as required by SQLAlchemy's callable default convention.
- **Wishlist routes deduplicated** — `new_wishlist_item` and
  `edit_wishlist_item` previously each manually set 7 fields that are a
  subset of `_fill_whisky`. Both routes now call `_fill_whisky(w,
  request.form)` directly, eliminating the duplication and the risk of the
  two code paths drifting out of sync.
### Added
- **`Flask-WTF==1.2.2`** and **`Flask-Limiter==3.9.0`** added to
  `requirements.txt`.
### Notes
- No database schema changes — upgrading from v1.3.3 requires no migration.
  All data, photos and passwords are preserved.
- The `__pycache__` directory previously tracked by git should be removed
  with `git rm -r --cached __pycache__` — the `.gitignore` already excludes
  it but git continues tracking previously committed files until explicitly
  removed.
  
---
 
## [1.3.3] — 2026-04-28 🔐🐍📦 Security, Compatibility & Dependency Update
 
### Security
- Removed `ENV SECRET_KEY=change-me-in-production` from `Dockerfile`.
  Hardcoding secrets in `ENV` instructions bakes them into image layers,
  making them readable via `docker inspect` or `docker history` by anyone
  with access to the image. `SECRET_KEY` must now be supplied at runtime
  via `docker-compose.yml` (already the recommended approach) or the
  Home Assistant Supervisor configuration tab.
### Fixed
- `SQLAlchemy` bumped from `2.0.25` to `2.0.49`. SQLAlchemy 2.0.25 is
  incompatible with Python 3.13 due to changes in Python's typing internals
  (`__firstlineno__` and `__static_attributes__` attributes), causing the app
  to crash on boot with an `AssertionError`.
### Added
- `MAX_CONTENT_LENGTH` set to 64 MB in `app.py` — previously unlimited, meaning
  large uploads could silently exhaust memory. Flask now rejects requests over
  64 MB at the WSGI layer before they reach the upload handler.
- 413 error handler in `app.py` — when an upload exceeds the limit, the user
  now sees a friendly flash message ("Upload too large. Please use smaller
  photos (max 64 MB total).") and is redirected back to the originating page
  rather than receiving a raw HTTP 413 response.
### Changed
- `Flask` bumped from `3.0.0` to `3.1.3` (latest stable).
- `Werkzeug` bumped from `3.0.1` to `3.1.8` — required by Flask 3.1.x
  (`Flask>=3.1` mandates `Werkzeug>=3.1`).
- `gunicorn` bumped from `21.2.0` to `25.3.0` (latest stable). v25 introduces
  per-app worker allocation and HTTP/2 beta support; fully compatible with the
  existing single-worker, 4-thread configuration.
- `Flask-SQLAlchemy==3.1.1`, `Flask-Login==0.6.3`, `Pillow==11.2.1` and
  `SQLAlchemy==2.0.49` confirmed as latest versions — no change needed.

---

## [1.3.2] — 2026-04-28 🐍 Fix Python / Pillow Compatibility
 
### Changed
- `Pillow` bumped from `10.2.0` to `11.2.1` in `requirements.txt`.
  Pillow 10.x cannot build on Python 3.13 — support was added in Pillow 11.0.0.
  This affects both the standalone Docker image and the Home Assistant add-on.
- `whiskywise/Dockerfile` base image kept at `3.13-alpine3.21` (reverted from
  the interim `3.12` workaround in v1.3.1).
- Main `Dockerfile` base image bumped from `python:3.11-slim` to `python:3.13-slim`
  to align with the HA add-on and benefit from Python 3.13 improvements.

---

## [1.3.1] — 2026-04-28 🐳 Fix Home Assistant Base Image

### Fixed
- `whiskywise/Dockerfile` base image corrected from the non-existent
  `ghcr.io/home-assistant/base-python:3.11` to the valid
  `ghcr.io/home-assistant/base-python:3.13-alpine3.21`. The shorthand
  `base-python:3.11` tag was never published by the HA team — the correct
  format requires both a Python version and an Alpine version
  (e.g. `3.13-alpine3.21`). This caused the add-on build to fail immediately
  on every HA installation.

### Notes
- As of HA base image release 2026.03.1, all images are published as
  multi-arch (amd64 + aarch64). No architecture prefix is needed.

---

## [1.3.0] — 2026-04-28 ⬆️ Dependency & Actions Update

### Changed
- Bumped all GitHub Actions to Node.js 24 compatible versions ahead of the
  June 2nd, 2026 forced migration deadline:
  - `actions/checkout` `v4` → `v6`
  - `docker/login-action` `v3` → `v4`
  - `docker/metadata-action` `v5` → `v6`
  - `docker/setup-buildx-action` `v3` → `v4`
  - `docker/build-push-action` `v5` → `v7`
  - `sigstore/cosign-installer` `v3.5.0` → `v4.1.0` (also required for Cosign v3+ support)
- Removed pinned SHA hashes from action references in favour of version tags
  for improved readability and maintainability.
- Docker image versioned tag changed from `type=semver` to `type=raw` so the
  version-specific tag (e.g. `:v1.3.0`) is now correctly applied on every push
  to `main`, not only on git tag pushes. Previously only `:latest` was tagged.
- Fixed incorrect Home Assistant navigation in the auto-generated release body
  (`Settings → Add-ons → ⋮ → Repositories`, not "Add-on Store").
- `APP_VERSION` bumped to `1.3.0`.

---

## [1.2.1] — 2026-04-28 🔧 Home Assistant Add-on Fix

### Added
- **Home Assistant add-on support** — WhiskyWise can now be installed directly
  as a Home Assistant add-on. Add the repository URL to HA and install like
  any other add-on. No Docker commands or compose files required.
- **`whiskywise/config.yaml`** — add-on manifest conforming to the HA Supervisor
  specification. Supports `aarch64` and `amd64` architectures.
- **`whiskywise/Dockerfile`** — add-on specific Dockerfile using
  `ghcr.io/home-assistant/base-python:3.11` directly, compatible with
  Supervisor 2026.04.0 and later (no deprecated `BUILD_FROM` ARG pattern).
- **`whiskywise/run.sh`** — bashio entrypoint that reads `secret_key` from the
  HA Supervisor configuration and starts WhiskyWise via Gunicorn.
- **`whiskywise/DOCS.md`** — configuration guide displayed inside the HA add-on UI.
- **`repository.yaml`** at the repo root — required by the HA Supervisor to
  recognise the repository. Contains `name`, `url` and `maintainer` fields.
- **Consolidated CI/CD pipeline** — `docker-image.yml`, `docker-publish.yml`
  and the add-on workflow merged into a single `.github/workflows/docker.yml`.
  Jobs run in strict order: sync version → build & push → create release.
  On PRs, only the build check runs (no push, no signing, no release).

### Changed
- `APP_VERSION` bumped to `1.2.1`.
- GitHub Actions: version is now automatically read from `app.py` and synced
  into `whiskywise/config.yaml` on every push to `main`. App source files
  (`app.py`, `requirements.txt`, `templates/`) are copied into `whiskywise/`
  by CI so the HA build context is always up to date.
- Docker image signing (cosign) preserved from the previous `docker-publish.yml`
  pipeline.

### Fixed
- Removed `build.yaml` — deprecated since Supervisor 2026.04.0; base images
  are now set directly in the Dockerfile via `FROM`.
- Removed `ARG BUILD_FROM` / `FROM ${BUILD_FROM}` pattern from the add-on
  Dockerfile — no longer supported by the HA builder.
- Removed `map: data:rw` from `config.yaml` — `/data` is always mounted
  writable by default; declaring it caused a validation warning.
- Removed invalid `armhf` and `armv7` arch values from `config.yaml` —
  the HA Supervisor only accepts `aarch64` and `amd64`.
- Corrected `ports_description` key format to match the `ports` key exactly.
- `repository.yaml` moved to repo root (was incorrectly placed inside the
  add-on subfolder in the initial draft).

### Notes
- No database migration required — all data, photos and passwords are preserved.
- Home Assistant users: data is persisted to `/data` automatically; back up
  via the standard HA backup system.

---

## [1.2.0] — 2026-04-27 🏠 The Home Assistant Update

### Added
- **Home Assistant add-on support** — WhiskyWise can now be installed directly
  as a Home Assistant add-on via the `homeassistant/` subfolder. Includes
  `config.yaml`, `build.yaml`, `run.sh`, and `DOCS.md` conforming to the
  HA Supervisor add-on specification.
- **Multi-arch Docker image** — CI now publishes `linux/amd64`, `linux/arm64`,
  and `linux/arm/v7` images to GHCR on every push to `main`.
- **GitHub Actions workflow** (`sync-ha-addon.yml`) — automatically syncs the
  version from `app.py` into `homeassistant/config.yaml`, builds and pushes
  the Docker image, and creates a GitHub Release whenever `app.py`,
  `requirements.txt`, `templates/`, or `homeassistant/` changes.
- `repository.yaml` — marks the repo as a valid Home Assistant add-on
  repository for direct installation from the HA add-on store.

### Changed
- `APP_VERSION` bumped to `1.2.0`.

### Notes
- Upgrading from v1.1.0 requires no database migration — all data, photos,
  and passwords are preserved.
- Home Assistant users: map `/data` to a persistent volume; see
  `homeassistant/DOCS.md` for full setup instructions.

---

## [1.1.0] — 2026-04-21

### Added
- **Flavour Radar Chart** — interactive spider/radar chart on the add, edit and detail pages with seven axes: Woody, Smoky, Cereal, Floral, Fruity, Medicinal and Fiery, each scored 1–5. Tap any segment to set intensity; tap again to clear. Stored in seven new `radar_*` database columns, auto-migrated on first boot.
- **Photo rotation** — ↻ button overlaid on each photo slot on the detail and edit pages rotates the stored image 90° clockwise and refreshes in place without a page reload.
- **EXIF orientation auto-correction** — portrait photos taken on a phone are automatically rotated to the correct orientation on upload; no more sideways bottle labels.
- **Camera access on Android Chrome** — added `capture="environment"` to all photo file inputs so Chrome on Android now opens the live camera directly instead of routing through the gallery.
- **Version number** — `APP_VERSION` constant in `app.py` and displayed on the Settings page and mobile nav footer.
- **Self-service settings page** — combined username and password change into a single `/settings` route, replacing the old `/change-password` page.
- **Multi-user support** — multiple accounts per installation, each with their own independent collection.
- **Admin panel** (`/admin`) — create users, rename users, reset passwords, grant/revoke admin rights, delete accounts and all associated data.
- **Username changes** — any user can change their own username from the Settings page; admins can rename any account.
- **Wishlist edit page** — dedicated edit form for wishlist entries showing only relevant fields, rather than the full whisky form.
- **404 error page** — friendly not-found page added alongside the existing 403 page.
- **`.gitignore`** — added to prevent `__pycache__`, `.pyc`, `.db` and data directories from being committed.

### Changed
- **Price display** — all price fields throughout the app now consistently show two decimal places (e.g. €49.95).
- **Radar chart label fix** — expanded SVG viewBox from `290×290` to `400×340` so long labels (particularly "Medicinal") are never clipped. Labels split onto two lines with score shown separately; font size increased to 11px.
- **Photo slots** — photo inputs now use `capture="environment"` for direct camera access on mobile.
- **Score display** — formatted to one decimal place throughout (e.g. `8.5` not `8.5000`); score of `0.0` correctly shown rather than hidden.
- **Whisky detail** — status pill now hidden for wishlist items (was incorrectly showing "stashed").
- **Delete confirmation** — JavaScript `confirm()` dialogs now read names from `data-*` attributes instead of inline Jinja string interpolation, preventing breakage on names containing apostrophes or quotes.
- **Collection empty state** — distinguishes between "no bottles in collection" and "no results matching filters".
- **`import math`** — moved from mid-file to the standard top-level imports block.
- **`render_radar_svg`** — defined before `context_processor` references it, fixing the definition-order issue.

### Security
- **CSRF protection** — all 12 POST forms now include a session-bound CSRF token (`_csrf_token`). A `@before_request` hook validates the token on every state-changing request. JavaScript `fetch()` calls include an `X-CSRF-Token` header read from a `<meta>` tag.
- **Security response headers** — `after_request` handler adds `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin` and a `Content-Security-Policy` to every response.
- **Cookie hardening** — session and remember-me cookies now set `HttpOnly=True` and `SameSite=Lax`.
- **SECRET_KEY guard** — if no `SECRET_KEY` is configured (or the default placeholder is used), the app generates a cryptographically random key at startup and logs a prominent warning rather than silently using a weak value.
- **Pillow decompression bomb limit** — `Image.MAX_IMAGE_PIXELS` capped at 40 megapixels to prevent memory exhaustion from crafted image uploads.
- **Constant-time login** — `check_password_hash()` now always runs regardless of whether the username exists, preventing timing-based username enumeration.
- **Error message sanitisation** — `rotate_photo` returns a generic error message to the client; full exception detail is logged server-side only.
- **GIF uploads removed** — `gif` removed from `ALLOWED_EXTENSIONS` to reduce unnecessary attack surface.
- **Open redirect protection** — `_safe_next()` validates the `?next=` login parameter, rejecting any URL with a scheme or host component.
- **Path traversal prevention** — `serve_photo` strips directory components from the filename using `os.path.basename()`.
- **ORM bulk delete consistency** — `synchronize_session='fetch'` used when bulk-deleting a user's whiskies to keep the SQLAlchemy identity map consistent.

### Fixed
- **Missing `{% endblock %}`** — `whisky_detail.html` was missing the closing tag for `{% block content %}`, causing a Jinja2 `TemplateSyntaxError` on the whisky detail page.
- **Score slider** — slider default changed from 5 to 0 when no score is set, so the unset state is visually clear.
- **`_float_or_none`** — explicitly handles `None` input in addition to empty string; correctly returns `0.0` for inputs of `'0'` and `'0.0'`.
- **`_fill_whisky`** — no longer overwrites `w.wishlist`; editing a wishlist item via the shared edit route no longer moves it to the collection.
- **`db.session.expire_all()`** — called after the schema migration so SQLAlchemy re-reads the updated column list rather than serving stale cached metadata, fixing the `no such column: user.is_admin` startup error on existing databases.
- **SQLite absolute path** — `DATABASE_PATH` always resolved to an absolute path at startup so SQLite opens the correct file regardless of working directory.
- **Admin toggle JS** — confirm dialog for granting/revoking admin now reads the username from a `data-username` attribute rather than inline Jinja interpolation.
- **`Whisky.query.filter_by(...).delete()`** — uses `synchronize_session='fetch'` to avoid ORM cache inconsistency when deleting a user's collection.

### Removed
- **`/change-password` route** — replaced by the new `/settings` page.
- **Login credentials hint** — removed the "Default: admin / whiskywise" hint from the login page.
- **`python-barcode` dependency** — removed unused package from `requirements.txt`.
- **`GIF` from allowed upload types** — see Security above.

---

## [1.0.0] — 2026-04-10

### Added
- Initial stable release.
- Whisky collection management — track Open, Stashed and Finished bottles.
- Tasting notes — Nose, Palate, Finish and General Notes (free text).
- 10-point scoring with 0.1 decimal precision, IMDB-style badge display.
- 13 flavour profiles, alphabetically sorted.
- Four photo slots per bottle — Front Label, Back Label, Cask/Bottle and Barcode.
- Barcode scanning via `@zxing/browser` (iOS Safari, Android Chrome, Firefox) with native `BarcodeDetector` fallback and manual entry fallback.
- Aiming reticle overlay on the scanner video feed.
- Purchase tracking — price, store and retired status.
- Collection status — Open / Stashed / Finished with Retired flag.
- Wishlist — note-style wishlist cards with name, distillery, region, price, store and notes.
- Search and filter — by name, distillery, region, barcode, flavour profile, minimum score, maximum price and status.
- Animated Top 10 rating chart on the home page.
- CSV export — full collection download, UTF-8 BOM encoded for Excel compatibility.
- User authentication — login required throughout; password changeable.
- Multi-user admin panel — create, rename, reset passwords, toggle admin, delete users.
- Automatic database migration — new columns added to existing databases on first boot without data loss.
- Docker deployment — single `docker-compose up -d` with persistent named volume for database and photos.
- Non-root container user (`appuser`) for improved container security.
- UnRaid template (`my-WhiskyWise.xml`).
- Mobile-first responsive design — tested on Android Chrome and iOS Safari.
- Version number displayed on Settings page and mobile nav footer.

---

## [0.0.6] — 2026-04-10 (pre-release)

Final pre-release iteration. Established the core Flask/SQLAlchemy/Flask-Login architecture, Docker packaging, and the full feature set that became v1.0.0.

---

## [0.0.1] – [0.0.5] — 2026-03-xx (pre-release)

Iterative development builds. Core CRUD, authentication, photo upload, barcode scanning, wishlist and collection management progressively added and stabilised.
