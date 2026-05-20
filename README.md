<img src="Icons/Icon 1.png" alt="WhiskyWise" width="80" align="left" style="margin-right:16px"/>

# WhiskyWise — *Your Personal Spirits Guide*

Track your whisky collection, log tasting notes, and analyse flavour profiles — all in a self-hosted web app.

---

## ✨ Features

- 📝 Tasting journal (Nose, Palate, Finish)
- ⭐ 10-point rating system with IMDB-style badge display
- 🧠 Flavour profiles (16 presets + interactive radar chart)
- 🗂 Collection tracking (Stashed, Open, Finished, Retired)
- 📸 Photo storage — up to 4 slots per bottle (front label, back label, cask/bottle, barcode)
- 💰 Purchase tracking (price, store, retired status)
- 💱 Configurable currency symbol — set once in Server Settings, applies everywhere
- 🔍 Search & filtering (name, distillery, barcode, flavour, score, price, status, retired)
- 🔀 Sort by name, distillery, price, score, last updated, or last tasted
- 📊 Top 10 chart + dashboard stats (Total, Open, Stashed, Finished, Wishlist)
- 📦 CSV export & import (full data ownership, round-trip compatible)
- 📷 Barcode scanning (camera-based, browser-native)
- 👥 Multi-user support with admin panel
- 📋 Wishlist with cover photo, age, ABV, and promote-to-collection
- 💾 Backup & Restore via Admin Panel (ZIP containing database + all photos)
- 📱 Full REST API for mobile and third-party clients
- 🔐 Session & token management — view and revoke per-device sessions
- 🤖 Native Android companion app

---

## ❓ Why WhiskyWise?

- No cloud lock-in — your data stays local
- Built for whisky, not generic note-taking apps
- Fast, lightweight, and self-hosted
- Home Assistant add-on support built in

---

## 📱 Android Companion App

A native Android app is available for WhiskyWise. It connects to your self-hosted server via the REST API and requires server ≥ v1.5.9.

**→ [WhiskyWise Android App](https://github.com/prolife86/WhiskyWise-app)**

---

## 🚀 Getting Started

WhiskyWise can be installed in several ways depending on your setup.

---

### 🏠 Home Assistant Add-on

The easiest way to run WhiskyWise if you already have a Home Assistant instance. No Docker commands, no compose files required.

**Prerequisites:** Home Assistant OS or Supervised installation.

1. Go to **Settings → Add-ons**
2. Click **⋮** (top-right) → **Repositories**
3. Paste in the repository URL and click **Add**:
   ```
   https://github.com/prolife86/WhiskyWise
   ```
4. Find **WhiskyWise** in the add-on list and click **Install**
5. Open the **Configuration** tab and set your `secret_key`
6. Go to the **Info** tab and click **Start**

All data is stored in the add-on's persistent `/data` volume — your collection and photos survive restarts and updates.

> See [`whiskywise/DOCS.md`](whiskywise/DOCS.md) for full configuration options.

---

### 🐳 Docker Compose *(Recommended for standalone installs)*

```bash
# 1. Clone / download this folder
cd whiskywise

# 2. Set a strong SECRET_KEY in docker-compose.yml

# 3. Build and run
docker-compose up -d

# 4. Open in your browser
http://localhost:5000
```

---

### 📦 Unraid

WhiskyWise is available on the Unraid Community Applications (CA) store. Search for **WhiskyWise** and install directly from there.

---

## 🖥️ Configuration

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `change-this-...` | Flask session secret — **must be changed** |
| `DATABASE_PATH` | `/data/db/whiskywise.db` | SQLite database path |
| `UPLOAD_FOLDER` | `/data/uploads` | Photo upload directory |

For Home Assistant users, these are configured via the add-on **Configuration** tab in the HA UI.

---

## 💿 Data Persistence

All data is stored in a named Docker volume (`whiskywise_data`):

- Database: `/data/db/whiskywise.db` (SQLite)
- Photos: `/data/uploads/`

### Admin Panel Backup *(recommended)*

The easiest way to back up and restore is via **Admin Panel → 💾 Backup & Restore**.

- **Download** — produces a timestamped ZIP containing the full database and all photos. Works in any browser, no command line needed.
- **Restore** — upload any ZIP produced by the download. The previous database is automatically saved as `whiskywise.db.bak` before being replaced.

### Manual Backup (Docker)

```bash
docker run --rm -v whiskywise_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/whiskywise-backup.tar.gz /data
```

To restore:

```bash
docker run --rm -v whiskywise_data:/data -v $(pwd):/backup alpine \
  tar xzf /backup/whiskywise-backup.tar.gz -C /
```

> Home Assistant users: data lives in the add-on's `/data` folder, mapped automatically to a persistent volume. Back up via the standard HA backup system or the Admin Panel.

---

## 🖥 Server Settings

Admins have access to a **Server Settings** section within ⚙ Settings. Currently this controls:

- **Display Currency** — choose the currency symbol shown before prices throughout the web UI (EUR, GBP, USD, CHF, SEK, NOK, DKK, JPY, AUD, CAD, or any custom symbol). The Android companion app reads this from the API and applies it automatically.

---

## 🛠 Advanced Configuration

### Docker Compose Example

```yaml
services:
  whiskywise:
    image: ghcr.io/prolife86/whiskywise:latest
    ports:
      - "5000:5000"
    volumes:
      - /mnt/user/appdata/WhiskyWise:/data
    environment:
      - SECRET_KEY=change-this-to-a-long-random-secret
      - DATABASE_PATH=/data/db/whiskywise.db
      - UPLOAD_FOLDER=/data/uploads
    restart: unless-stopped
```

> **Critical:** Always map the data directory to a local volume. Deleting the container without a volume mapping will permanently lose your collection data and photos.

---

## 🔐 Security Notes

- You will be prompted to change the default admin password on first login
- Passwords must be at least 8 characters
- Use a strong `SECRET_KEY`
- For external access, run behind a reverse proxy (Nginx, Traefik, etc.)
- HTTPS is recommended for camera features and security
- Do not expose directly to the internet without a reverse proxy and HTTPS

### Default login

- **Username:** `admin`
- **Password:** `whiskywise`

> ⚠️ You will be prompted to change this on first login.

For the admin panel, navigate to `http://[IP]:[Port]/admin`

---

## 📱 REST API

WhiskyWise includes a full REST API for use by Android/iOS apps or any HTTP client. All endpoints are user-scoped — a token only ever grants access to that user's own data.

### Authentication

```bash
curl -X POST http://localhost:5000/api/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "yourpassword", "name": "My Android"}'
```

```json
{
  "data": {
    "token": "a3f9...",
    "id": 1,
    "name": "My Android",
    "created": "2026-05-02T10:00:00+00:00"
  }
}
```

Include the token on every subsequent request:

```
Authorization: Bearer a3f9...
```

### Client Version Header

API clients are encouraged to send their app version on every request:

```
X-Client-Version: 0.3.2
```

The server records this on the token row and updates it on each request, so admins can see which app version is behind each active token.

### Endpoint Reference

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/auth/token` | Exchange credentials for a Bearer token |
| `GET` | `/api/auth/tokens` | List your tokens (metadata + IP + version) |
| `DELETE` | `/api/auth/token/<id>` | Revoke a token |
| `GET` | `/api/auth/sessions` | List your active browser sessions |
| `DELETE` | `/api/auth/session/<id>` | Revoke a browser session |
| `GET` | `/api/v1/stats` | Dashboard counts + top-10 + flavour list + **currency symbol** |
| `GET` | `/api/barcode-lookup` | Look up a barcode in the user's collection |
| `GET` | `/api/v1/collection` | Collection list (filterable + paginated) |
| `GET` | `/api/v1/wishlist` | Wishlist |
| `POST` | `/api/v1/wishlist` | Add wishlist item |
| `PUT` | `/api/v1/wishlist/<id>` | Update wishlist item |
| `GET` | `/api/v1/whisky/<id>` | Full detail for a single whisky |
| `POST` | `/api/v1/whisky` | Create a collection entry |
| `PUT` | `/api/v1/whisky/<id>` | Update a collection entry (partial) |
| `DELETE` | `/api/v1/whisky/<id>` | Delete a whisky |
| `POST` | `/api/v1/whisky/<id>/photo/<slot>` | Upload a photo (`front`, `back`, `cask`, `barcode`) |
| `DELETE` | `/api/v1/whisky/<id>/photo/<slot>` | Remove a photo |
| `POST` | `/api/photo/<id>/<slot>/rotate` | Rotate a saved photo 90° clockwise |
| `GET` | `/api/photo/<filename>` | Authenticated photo serving |

### Collection Filters

`GET /api/v1/collection` accepts the following query parameters:

| Parameter | Description |
|---|---|
| `q` | Free-text search (name, distillery, region, barcode) |
| `flavor` | Exact flavour profile match |
| `min_score` | Minimum score (inclusive) |
| `max_price` | Maximum price (inclusive) |
| `status` | `open`, `stashed`, or `finished` |
| `retired` | `yes`, `no`, or omit for all |
| `sort` | `score` (default), `name`, `distillery`, `added`, `price`, `updated`, `last_tasted` |
| `order` | `desc` (default) or `asc` |
| `limit` | Max results (default 200) |
| `offset` | Pagination offset (default 0) |

### Stats Response

`GET /api/v1/stats` returns:

```json
{
  "data": {
    "total": 42,
    "open": 8,
    "stashed": 30,
    "finished": 4,
    "wishlist_count": 12,
    "top10": [...],
    "dominant_flavours": [...],
    "currency_code": "EUR",
    "currency_symbol": "€"
  }
}
```

### Radar Chart

Every whisky in the API response includes a `radar` object with seven flavour axes, each scored 0–5:

```json
"radar": {
  "woody": 2, "smoky": 4, "cereal": 1,
  "floral": 0, "fruity": 3, "medicinal": 5, "fiery": 2
}
```

Send radar values when creating or updating using either a nested dict or flat keys:

```json
{ "radar": { "smoky": 4, "fruity": 2 } }
```

### Response Format

All successful responses use `{"data": ...}`. All errors use `{"error": "..."}` with an appropriate HTTP status code.

---

## 🔖 Barcode Scanning

Barcode scanning uses the browser's `BarcodeDetector` API (available in Chrome 83+ and Safari 17+). Works best on Android Chrome and iOS Safari 17+. If the API is unavailable, type the barcode manually.

---

## 📱 Accessing on Mobile (LAN)

1. Find your server's local IP (e.g. `192.168.1.100`)
2. Open `http://192.168.1.100:5000` on your phone, or connect via the [Android app](https://github.com/prolife86/WhiskyWise-app)
3. Add to home screen for an app-like experience

> Camera/barcode scanning requires HTTPS or localhost. For LAN HTTPS, consider a reverse proxy with a local SSL certificate, or use Tailscale.

---

## 📇 Tech Stack

- **Backend:** Python / Flask
- **Database:** SQLite (via SQLAlchemy)
- **Auth:** Flask-Login + Bearer tokens
- **Frontend:** Vanilla HTML/CSS/JS (no frameworks)
- **Container:** Docker + Gunicorn

---

## 🤝 Contributing

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 🤖 Development Notes

Parts of this project were developed with AI assistance to accelerate development. All code is reviewed and maintained manually.

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.
