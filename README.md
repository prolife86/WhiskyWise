# 🥃 Whisky Wise
Your Personal Spirits Guide
>
**Whisky Wise** is a lightweight, containerized personal assistant for spirits enthusiasts. Whether you're tracking a growing collection or cataloging the nuance of a rare Islay peat, Whisky Wise provides a clean, distraction-free interface to manage your journey through the world of whisky.
## ✨ Key Features
 * **Tasting Journal:** Log detailed notes on Nose, Palate, and Finish.
 * **Scoring** — 10-point scale
 * **Flavor Profiles** — 13 preset profiles
 * **Collection Management:** Track "Stashed," "Open," and "Finished" bottles.
 * **Photos** — ie. Front label, back label, cask/bottle, barcode
 * **Purchase Info** — Price, store, retired status
 * **Data Portability:** Your data stays in your container; export to CSV anytime.
 * **Barcode Scanning** — Camera-based scanning for logging and tracking
 * **Wishlist** — Note-style wishlist with price and store
 * **Top 10 Chart** — Animated rating chart on the home page
 * **Search & Filter** — By name, distillery, barcode, flavor, score, price, status
 * **CSV Export** — Download your entire collection
 * **User Authentication** — Login required, password changeable

## 🚀 Getting Started
The most reliable way to run Whisky Wise is via Docker. This ensures all dependencies (database, environment, and server) are perfectly configured out of the box.

### Prerequisites
- Docker & Docker Compose installed
  
### Setup Guide
```bash
# 1. Clone / download this folder
cd whiskywise

# 2. (Recommended) Change the SECRET_KEY in docker-compose.yml

# 3. Build and run
docker-compose up -d

# 4. Open in your browser
http://localhost:5000
```

## Configuration (docker-compose.yml)

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | `change-this-...` | Flask session secret — **must be changed** |
| `DATABASE_PATH` | `/data/db/whiskywise.db` | SQLite DB path |
| `UPLOAD_FOLDER` | `/data/uploads` | Photo upload directory |

## Data Persistence

All data is stored in a named Docker volume (`whiskywise_data`):
- Database: `/data/db/whiskywise.db` (SQLite)
- Photos: `/data/uploads/`

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

## 🛠 Advanced Configuration
### Docker Compose Example
If you prefer to integrate Whisky Wise into an existing stack, use this docker-compose.yml snippet:
```yaml
services:
  whiskywise:
    image: ghcr.io/prolife86/whiskywise:main
    ports:
      - "5000:5000"
    volumes:
      - /mnt/user/appdata/WhiskyWise:/data
    environment:
      - SECRET_KEY=7335bd4e2f8105c2d1f6e6ab0020d2c0908136f026dda30f43eebf4fa4084f40
      - DATABASE_PATH=/data/db/whiskywise.db
      - UPLOAD_FOLDER=/data/uploads
    restart: unless-stopped
```

### Volume Persistence
> **Critical:** Always map the /app/data directory to a local volume.
> If you delete the container without a volume mapping, you will lose your tasting history and collection data.

### Default login
- **Username:** `admin`
- **Password:** `whiskywise`
> ⚠️ Change this immediately via **⚙️ Settings → Change Password**

## Barcode Scanning

Barcode scanning uses the browser's **BarcodeDetector API** (available in Chrome 83+ and Safari 17+). Works best on:
- Android Chrome
- iOS Safari 17+

If the API is unavailable, you can type the barcode manually.

## Accessing on Mobile (LAN)

To use WhiskyWise on your phone while connected to your home network:

1. Find your server's local IP (e.g. `192.168.1.100`)
2. Open `http://192.168.1.100:5000` on your phone
3. Add to home screen for an app-like experience

> Note: Camera/barcode scanning requires HTTPS or localhost. For LAN HTTPS, consider putting WhiskyWise behind a reverse proxy like Nginx with a local SSL certificate or use Tailscale.

## Tech Stack
- **Backend:** Python / Flask
- **Database:** SQLite (via SQLAlchemy)
- **Auth:** Flask-Login
- **Frontend:** Pure HTML/CSS/JS (no frameworks, mobile-first)
- **Container:** Docker + Gunicorn

## 🤝 Contributing
Found a bug or want to suggest a feature like "Distillery Maps"?
 1. Fork the Project.
 2. Create your Feature Branch (git checkout -b feature/AmazingFeature).
 3. Commit your Changes (git commit -m 'Add some AmazingFeature').
 4. Push to the Branch (git push origin feature/AmazingFeature).
 5. Open a Pull Request.

## 🤖 Built with AI
Portions of this application, were developed with the assistance of **Claude Sonnet 4.6**.
This allows for a more rapid development cycle and optimized container orchestration.

## 📜 License
Distributed under the MIT License. See LICENSE for more information.
