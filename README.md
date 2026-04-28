# 🥃 Whisky Wise - *Your Personal Spirits Guide*

Track your whisky collection, log tasting notes, and analyze flavor profiles — all in a self-hosted web app.

## ✨ Features

* 📝 Tasting journal (Nose, Palate, Finish)
* ⭐ 10-point rating system
* 🧠 Flavor profiles (13 presets + radar chart visualization)
* 🗂 Collection tracking (Stashed, Open, Finished)
* 📸 Photo storage (labels, bottle, barcode)
* 💰 Purchase tracking (price, store, retired)
* 🔍 Search & filtering (name, distillery, barcode, flavor, score)
* 📊 Top 10 animated chart
* 📦 CSV export (full data ownership)
* 📷 Barcode scanning (camera-based)
* 👥 Multi-user support
* 📝 Wishlist tracking

## ❓ Why Whisky Wise?

* No cloud lock-in — your data stays local
* Built for whisky (not generic note apps)
* Fast, lightweight, and self-hosted

## 🚀 Getting Started

WhiskyWise can be installed in several ways depending on your setup. Pick the one that fits your environment.

---

### 🏠 Home Assistant Add-on *(New in v1.2.1)*

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

The most reliable way to run WhiskyWise outside of Home Assistant. All dependencies are perfectly configured out of the box.

**Prerequisites:** Docker & Docker Compose installed.

```bash
# 1. Clone / download this folder
cd whiskywise

# 2. (Recommended) Change the SECRET_KEY in docker-compose.yml

# 3. Build and run
docker-compose up -d

# 4. Open in your browser
http://localhost:5000
```

---

### 📦 UnRaid

Download the `my-WhiskyWise.xml` and adjust the following lines:

* \#6 (Network)
* \#7 (IP Address)
* \#31 (Secret Key)

Upload the adjusted `my-WhiskyWise.xml` to your flash drive via: **Main → browse icon in front of the Flash drive → config → plugins → dockerMan → templates-user**, then upload and reboot.
You can also enter this information manually into UnRaid without rebooting.
*(The icon can be added via the advanced options.)*

---

## 🖥️ Configuration (docker-compose.yml)

| Variable | Default | Description |
| --- | --- | --- |
| `SECRET_KEY` | `change-this-...` | Flask session secret — **must be changed** |
| `DATABASE_PATH` | `/data/db/whiskywise.db` | SQLite DB path |
| `UPLOAD_FOLDER` | `/data/uploads` | Photo upload directory |

For Home Assistant users, these are configured via the add-on **Configuration** tab in the HA UI.

## 💿 Data Persistence

All data is stored in a named Docker volume (`whiskywise_data`):

* Database: `/data/db/whiskywise.db` (SQLite)
* Photos: `/data/uploads/`

To back up your data:

```bash
docker run --rm -v whiskywise_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/whiskywise-backup.tar.gz /data
```

To restore:

```bash
docker run --rm -v whiskywise_data:/data -v $(pwd):/backup alpine \
  tar xzf /backup/whiskywise-backup.tar.gz -C /
```

> Home Assistant users: your data lives in the add-on's `/data` folder, which HA maps to a persistent volume automatically. Back up via the standard HA backup system.

## 🛠 Advanced Configuration

### Docker Compose Example

If you prefer to integrate WhiskyWise into an existing stack, use this `docker-compose.yml` snippet:

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

### Volume Persistence

> **Critical:** Always map the data directory to a local volume.
> If you delete the container without a volume mapping, you will lose your tasting history and collection data.

## 🔐 Security Notes

* Change the default admin password immediately
* Use a strong `SECRET_KEY`
* For external access, run behind a reverse proxy (Nginx, Traefik, etc.)
* HTTPS is recommended for camera features and security
* Do not expose directly to the internet without a reverse proxy and HTTPS

### Default login

* **Username:** `admin`
* **Password:** `whiskywise`

> ⚠️ Change this immediately via **⚙️ Settings → Change Password**

For use of the admin panel, navigate to `http://[IP]:[Port]/admin`

## 🫆 Barcode Scanning

Barcode scanning uses the browser's BarcodeDetector API (available in Chrome 83+ and Safari 17+). Works best on:

* Android Chrome
* iOS Safari 17+

If the API is unavailable, you can type the barcode manually.

## 📱 Accessing on Mobile (LAN)

To use WhiskyWise on your phone while connected to your home network:

1. Find your server's local IP (e.g. `192.168.1.100`)
2. Open `http://192.168.1.100:5000` on your phone
3. Add to home screen for an app-like experience

> Note: Camera/barcode scanning requires HTTPS or localhost. For LAN HTTPS, consider putting WhiskyWise behind a reverse proxy like Nginx with a local SSL certificate, or use Tailscale.

## 📇 Tech Stack

* **Backend:** Python / Flask
* **Database:** SQLite (via SQLAlchemy)
* **Auth:** Flask-Login
* **Frontend:** Vanilla HTML/CSS/JS (no frameworks, fast and lightweight)
* **Container:** Docker + Gunicorn

## 🤝 Contributing

Found a bug or want to suggest a feature like "Distillery Maps"?

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 🤖 Development Notes

Parts of this project were developed with AI assistance to accelerate development. All code is reviewed and maintained manually.

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.
