# Changelog

All notable changes to WhiskyWise are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.5.4] — 2026-05-06 🧹 The Field-Clearing Fix

### Fixed

- **Clearing optional fields via the Android app now actually saves** — when a
  user edited a whisky and wiped a field (distillery, region, age, store,
  barcode, tasting notes, score, price, etc.), the change was silently
  discarded. Gson's default behaviour omits `null` values from the JSON body;
  `_fill_whisky_from_json` only updates fields that are present in the payload,
  so absent keys were skipped and the old value remained in the database. A new
  `_str_or_none()` helper correctly maps `null` JSON values to SQL `NULL`, and
  all string fields in `_fill_whisky_from_json` now use it. Mobile clients
  can clear any optional field by sending the key with a `null` value; omitting
  the key still leaves the field untouched (partial-update semantics preserved).

---

## [1.5.3] — 2026-05-06 🤫 The Quiet Dram

### Fixed

- **Score slider no longer defaults to 0 on unscored whiskies** — when adding a
  new bottle the range slider was rendering at `0`, leaving the hidden score input
  and the visual display out of sync. Moving the slider even slightly would then
  commit `0.0` as the score without the user intending to. The slider now parks
  at the neutral midpoint (`5`) while the hidden input stays empty; a score is
  only submitted when the user deliberately moves the slider or types a value.

- **Photo replaced via the API no longer deletes the old file before the DB
  commit succeeds** — `POST /api/v1/whisky/<id>/photo/<slot>` was deleting the
  existing photo from disk, then writing the new filename to the database. If the
  commit failed (e.g. a brief DB lock), the old photo was gone and the new
  filename was never persisted, leaving a broken slot with no recovery path. The
  old file is now held until after a successful commit; if the commit fails the
  newly-written file is cleaned up instead and a `500` with a clear error message
  is returned.

- **Arbitrary strings can no longer be stored in the `status` field** — the form
  and JSON API paths both accepted any value for `status` without validation.
  Both `_fill_whisky` and `_fill_whisky_from_json` now reject values outside
  `{'stashed', 'open', 'finished'}`, silently falling back to `'stashed'`.
  Existing data is unaffected.

- **`_init_db` startup migration no longer kills the process on failure** — the
  `ALTER TABLE` migration for the `is_admin` column was wrapped only in an outer
  `finally` block, meaning any exception (e.g. a locked DB or a permissions
  error) propagated uncaught and crashed the container before it could serve a
  single request. The migration is now wrapped in its own inner `try/except`;
  failures emit a `[WhiskyWise] WARNING:` log line and allow startup to continue.

### Security

- **SRI integrity hash added to ZXing CDN script** — the `@zxing/browser@0.1.5`
  bundle was loaded from `unpkg.com` with no `integrity` attribute. A compromised
  or tampered CDN response would have executed arbitrary JavaScript in users'
  browsers. The `integrity="sha384-..."` attribute is now present; browsers will
  refuse to execute the script if the hash doesn't match.

### Documentation

- **`docker-compose.yml` — `SESSION_COOKIE_SECURE` guidance added** — a comment
  block now explains that `SESSION_COOKIE_SECURE` and `REMEMBER_COOKIE_SECURE`
  are intentionally absent (safe for LAN-only deploys) and documents the exact
  environment variables to add when running behind an HTTPS reverse proxy.

- **`docker-compose.yml` — version now read from `whiskywise/config.yaml`** —
  `APP_VERSION` is no longer a static placeholder. The `build.args` block now
  uses the same `grep`/`sed` pipeline as `run.sh` to extract the version at
  build time, so standalone Docker builds always report the correct version in
  the UI without any manual edits.

---

## [1.5.2] — 2026-05-06 📸 Photos Actually Work on Mobile Now
 
### Fixed
 
- **Photos not loading in the Android app** — `GET /api/photo/<filename>` was
  decorated with `@login_required`, which only accepts browser session cookies.
  Mobile clients send `Authorization: Bearer <token>` instead, which
  Flask-Login's standard decorator silently ignores — redirecting to `/login`
  and returning an HTML page in place of the image. Changed the decorator to
  `@api_login_required`, which accepts both Bearer tokens and session cookies.
  Browser behaviour is unchanged; mobile clients now receive the actual photo.
  Note: `rotate_photo` received the same fix in 1.5.1. `serve_photo` was
  the last remaining endpoint still using the wrong decorator.

---

## [1.5.1] — 2026-05-03 🏷️ Dominant Flavours & House-keeping

### Added

- **Three new dominant flavour options** — `Mixed`, `Undefinable`, and `Complicated`
  join the existing 13 presets, bringing the total to 16. Because not every dram
  fits neatly into a single box — and some actively resist the attempt.

### Changed

- **"Flavor Profile" renamed to "Dominant Flavour"** everywhere in the UI, API
  response payloads, CSV export headers, and inline documentation. The underlying
  database column (`flavor_profile`) and API query parameter (`flavor`) are
  unchanged for backwards compatibility.
- **Dominant flavour tag now capitalised** in the collection list and whisky detail
  views — `smoky` → `Smoky`, `complicated` → `Complicated`, etc.
- **`config.yaml` version field** is now managed exclusively by the GitHub Actions
  `sync-version` job. A `# NOTE:` comment makes this explicit; the field must not
  be edited by hand.

### Fixed

- **`config.yaml` was stale** — version showed `1.4.3` despite the app shipping
  as `1.5.0`. Corrected to `1.5.0`; future releases are kept in sync automatically.
- **`rotate_photo` now accepts Bearer token auth** — the endpoint was decorated
  with `@login_required` (session only) while the rest of the photo API used
  `@api_login_required`. Mobile clients can now rotate photos without a browser
  session.
- **Orphaned photo files are now deleted from disk** when a whisky is deleted
  (browser route, API, or admin user-delete), when a photo slot is cleared via
  `DELETE /api/v1/whisky/<id>/photo/<slot>`, and when a slot is replaced by a
  new upload. Previously deleted photos accumulated indefinitely in `data/uploads/`.
- **Input length caps on all free-text fields** — `name`, `distillery`, `store`
  capped at 200 chars; `region` at 100; `age` and `barcode` at 20 and 100
  respectively; tasting notes (`nose`, `palate`, `finish`, `notes`,
  `wishlist_notes`) capped at 4 000 chars. Applies to both browser form and
  JSON API paths. SQLite does not enforce column widths, so the cap now lives
  in Python.

### Workflow

- **`extract-version` no longer reads `config.yaml`** — the CI job now derives
  the version from the git tag (`git describe --tags --abbrev=0`) on push and
  `workflow_dispatch` triggers, and from the release tag on `release` events.
  `config.yaml` is a write-only destination for the HA supervisor; it is no
  longer a source of truth for any part of the build pipeline.
- `fetch-depth: 0` added to the `extract-version` checkout step so that
  `git describe` can see the full tag history.

---
 
## [1.5.0] — 2026-05-03 📱🔐 Mobile API & Security
 
### Added
 
- **Mobile / third-party JSON API** — a full REST API has been added to
  `app.py`, enabling Android, iOS, or any HTTP client to interact with
  WhiskyWise without a browser. All endpoints return `{"data": ...}` on
  success and `{"error": "..."}` on failure.
- **API token authentication** — a new `ApiToken` database model stores
  personal access tokens as SHA-256 hashes (the plain-text value is shown
  exactly once at creation and never persisted). Tokens are passed via an
  `Authorization: Bearer <token>` header. Session-cookie auth continues to
  work unchanged for browser callers. New token management endpoints:
  - `POST /api/auth/token` — exchange username + password for a Bearer token.
  - `GET /api/auth/tokens` — list your tokens (metadata only; no secrets returned).
  - `DELETE /api/auth/token/<id>` — revoke a token.
- **Collection & wishlist API endpoints:**
  - `GET /api/v1/collection` — list collection with optional filtering
    (`q`, `flavor`, `min_score`, `max_price`, `status`) and pagination
    (`limit`, `offset`).
  - `GET /api/v1/wishlist` — list wishlist.
  - `POST /api/v1/wishlist` — create a wishlist item.
  - `PUT /api/v1/wishlist/<id>` — update a wishlist item (partial update).
  - `GET /api/v1/stats` — dashboard counts (total, open, stashed, wishlist)
    plus the top-10 scored whiskies and the full flavour profile list.
- **Whisky CRUD API endpoints:**
  - `GET /api/v1/whisky/<id>` — full detail for a single whisky, including
    all tasting notes, photo URLs, radar values, and timestamps.
  - `POST /api/v1/whisky` — create a collection entry. Only `name` is
    required; all other fields are optional. Photos are uploaded separately.
  - `PUT /api/v1/whisky/<id>` — partial update; only fields present in the
    request body are changed. Send `null` to explicitly clear a field.
  - `DELETE /api/v1/whisky/<id>` — delete a whisky (collection or wishlist).
- **Photo management API endpoints:**
  - `POST /api/v1/whisky/<id>/photo/<slot>` — upload or replace a photo via
    multipart form-data (`photo` field). Accepted formats: jpg, jpeg, png, webp.
    `slot` must be one of `front`, `back`, `cask`, `barcode`.
  - `DELETE /api/v1/whisky/<id>/photo/<slot>` — remove a photo (clears the
    slot; does not delete the file on disk).
- **Radar chart axes persisted to database** — the seven flavour radar axes
  (`woody`, `smoky`, `cereal`, `floral`, `fruity`, `medicinal`, `fiery`) are
  now stored as dedicated integer columns on the `Whisky` model (each 0–5,
  defaulting to 0). Previously the interactive radar chart wrote values to
  the form but they were never saved. Existing databases are auto-migrated on
  first boot via `db.create_all()` with no data loss.
- **Radar axes exposed in the API** — every whisky returned by the API now
  includes a `radar` object:
  ```json
  "radar": {
    "woody": 2, "smoky": 4, "cereal": 1,
    "floral": 0, "fruity": 3, "medicinal": 5, "fiery": 2
  }
  ```
  The `POST /api/v1/whisky` and `PUT /api/v1/whisky/<id>` endpoints accept
  radar values in either a nested dict (`{"radar": {"smoky": 4}}`) or flat
  keys (`{"radar_smoky": 4}`). Values are clamped to 0–5 server-side.
- **Minimum password length of 8 characters** — all three password-setting
  paths (self-service change, admin create user, admin reset password) now
  enforce a minimum length of 8 characters, up from 6. A single
  `MIN_PASSWORD_LEN = 8` constant controls all three locations.
- **Forced password change on first login** — if a user logs in with the
  default password (`whiskywise`), a `must_change_password` flag is set in
  their session and a `before_request` hook redirects every subsequent
  request to `/change-password` until they comply. The change-password page
  in forced mode omits the "Current Password" field (redundant given we
  already know it), blocks reuse of the default password, and hides the
  Cancel button so the user cannot bypass the prompt.
- **`/change-password` route** — a dedicated `GET`/`POST` route at
  `/change-password` is used as the forced-change destination. The updated
  `change_password.html` template accepts a `forced` context variable to
  render the appropriate UI in either forced or voluntary mode.
### Fixed
 
- **Radar chart not displayed on detail page** — `render_radar_svg()` in
  read-only mode (`interactive=False`) was ignoring the seven saved
  `radar_*` columns entirely. Instead it derived the chart shape from
  `flavor_profile` + `score`, meaning only a single axis ever had a value
  and it was a rough approximation rather than the actual tasting data. The
  function now reads `radar_woody` through `radar_fiery` directly for both
  the data polygon and the dot positions, matching what the edit form shows.
### Changed
 
- **`_fill_whisky`** — now saves the seven `radar_*` fields from the web
  form, so the interactive radar chart on the Add / Edit pages is fully
  persistent for the first time.
- **`_whisky_to_dict`** — serialises all whisky fields including the new
  `radar` nested object and correctly resolves photo filenames to relative
  URLs via the existing `serve_photo` route.
### Security
 
- **`api_login_required` decorator** — API routes use a dedicated decorator
  that accepts Bearer tokens or session cookies and returns a JSON `401`
  (not an HTML redirect) on failure, making error handling straightforward
  for mobile clients.
- **CSRF exemption for API routes** — all `POST`, `PUT` and `DELETE` API
  endpoints are decorated with `@csrf.exempt`; they are protected instead by
  Bearer token auth which provides equivalent request forgery protection for
  non-browser clients.
- **Rate limiting on token creation** — `POST /api/auth/token` is limited to
  10 requests per minute per IP via the existing Flask-Limiter instance,
  preventing brute-force credential stuffing against the token endpoint.
- **Token hash storage** — raw token values are never written to the
  database. Only the SHA-256 digest is stored; a database leak does not
  expose live credentials.
### Notes
 
- **Database migration** — `db.create_all()` will add the seven new
  `radar_*` columns and the `api_token` table automatically on first boot.
  For existing databases managed outside of `db.create_all()` (e.g. Alembic),
  apply the following manually:
  ```sql
  ALTER TABLE whisky ADD COLUMN radar_woody     INTEGER DEFAULT 0;
  ALTER TABLE whisky ADD COLUMN radar_smoky     INTEGER DEFAULT 0;
  ALTER TABLE whisky ADD COLUMN radar_cereal    INTEGER DEFAULT 0;
  ALTER TABLE whisky ADD COLUMN radar_floral    INTEGER DEFAULT 0;
  ALTER TABLE whisky ADD COLUMN radar_fruity    INTEGER DEFAULT 0;
  ALTER TABLE whisky ADD COLUMN radar_medicinal INTEGER DEFAULT 0;
  ALTER TABLE whisky ADD COLUMN radar_fiery     INTEGER DEFAULT 0;
  ```
- Only `app.py` and `templates/change_password.html` were changed. All other
  templates, static files, Docker configuration, and the Home Assistant
  add-on are unaffected.
- All existing data, photos, and passwords are preserved.
- `APP_VERSION` bumped to `1.5.0`.

---

## [1.4.3] - 2026-05-01

### Fixed
- **Flavour Radar not clickable** — the interactive radar chart on the Add/Edit
  Whisky form could not be clicked. `render_radar_svg()` was only ever emitting
  a static SVG; the 35 clickable wedge-cell polygons (`class="radar-cell"`) that
  the form's JavaScript expects were never generated. All ring segments are now
  rendered with the correct `onclick="radarSetVal(...)"` handler and hover
  highlight so intensity can be set by clicking any cell.
- **Existing radar selection not shown on Edit page** — when editing a saved
  whisky, the previously chosen intensity levels appeared blank. The JS
  `_radarUpdatePolygon()` restores highlights by querying `polygon.radar-cell`
  elements on page load; because those elements were missing (see above) no
  cells were ever highlighted and the data polygon collapsed to zero. Now that
  the cells are present, stored values are correctly reflected when the edit
  form loads.
- **Radar axis mismatch** — `render_radar_svg()` was drawing 13 spokes using
  the generic `FLAVOR_PROFILES` list (`floral`, `peaty`, `sweet`, …) while the
  form's hidden inputs and JavaScript both use the 7 dedicated radar axes
  (`woody`, `smoky`, `cereal`, `floral`, `fruity`, `medicinal`, `fiery`). The
  function now always uses the correct 7-axis set, matching the database columns
  and the JS `_RADAR_AXES` constant exactly.

### Notes
- Only `app.py` was changed (`render_radar_svg` function). No template, JS,
  or database changes. All data, photos and passwords are preserved.

---
 
## [1.4.2] - 2026-05-01

### Security
- **Security response headers** — `@after_request` handler now sets
  `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: strict-origin-when-cross-origin`, and a
  `Content-Security-Policy` on every response. These were listed in the
  v1.1.0 changelog but were never wired into `app.py`.
- **Cookie hardening** — `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE`,
  `REMEMBER_COOKIE_HTTPONLY`, and `REMEMBER_COOKIE_SAMESITE` are now explicitly
  set in app config. Previously relied on Flask defaults.
- **Constant-time login** — the `/login` POST handler now always calls
  `check_password_hash()` regardless of whether the username exists, using a
  pre-computed `_DUMMY_HASH`. Previously the `and` short-circuit let unknown
  usernames return measurably faster, enabling timing-based username enumeration.
- **`SECRET_KEY` guard** — if `SECRET_KEY` is absent or a known placeholder,
  an ephemeral cryptographically random key is generated at startup with a
  prominent log warning. The app no longer silently uses a predictable key.
- **`gif` removed from `ALLOWED_EXTENSIONS`** — removed in v1.1.0 per the
  changelog, but re-added in a later commit. Removed again.
- **Pillow decompression bomb guard** — `Image.MAX_IMAGE_PIXELS` capped at
  40 MP. Listed in v1.1.0 changelog; not set in code until now.
- **`CSRFError` handler** — expired/missing CSRF tokens now produce a friendly
  flash message and redirect instead of a raw HTTP 400.
- **`rotate_photo` error sanitisation** — the endpoint no longer returns
  `str(exc)` to the client. Full detail is logged server-side only.

### Fixed
- **`whiskywise/templates/change_password.html` missing CSRF token** — the
  HA add-on copy was missing the `_csrf_token` hidden input. Fixed at source.

### Changed
- **`libzbar` removed from `Dockerfile`** — never used server-side; barcode
  scanning is entirely client-side. Reduces image size by ~6 MB.

### Removed
- **`__pycache__`** removed from repository tree.
- **`whiskywise/templates/templates/`** accidental nested duplicate removed.

### Notes
- No database schema changes. All data, photos, and passwords are preserved.

---
 
## [1.4.1] - 2026-04-30
 
### Fixed
- **App fails to start with Flask-SQLAlchemy 3.x** — `db.engine` can no longer be
  accessed at module import time outside an application context. Two call sites were
  affected:
  - Removed the module-level `@event.listens_for(db.engine, 'connect')` WAL-mode
    listener. WAL mode is now enabled inside `_init_db()` where an app context is
    already established, using `db.engine.connect()` and SQLAlchemy's `db.text()`.
  - Removed the stale `from sqlalchemy import event` import that became unused after
    the above fix.
- **Worker boot crash in gunicorn** — the above changes resolve the
  `RuntimeError: Working outside of application context` that caused every gunicorn
  worker to exit with code 3 on startup.
### Changed
- WAL journal mode for SQLite is now set once during `_init_db()` rather than on
  every new database connection. Behaviour for end users is identical.
  
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
