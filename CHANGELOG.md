# Changelog

All notable changes to WhiskyWise are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.2.0] — 2026-04-24 🏠 The Home Assistant Update

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
