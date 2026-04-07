# WhiskyWise
Because after a few drams (and this app), you'll be the smartest person in the room.

# 🥃 Whisky Wise
**Whisky Wise** is a lightweight, containerized personal assistant for spirits enthusiasts. Whether you're tracking a growing collection or cataloging the nuance of a rare Islay peat, Whisky Wise provides a clean, distraction-free interface to manage your journey through the world of whisky.
## ✨ Key Features
 * **Tasting Journal:** Log detailed notes on Nose, Palate, and Finish.
 * **Collection Management:** Track "Stashed," "Open," and "Finished" bottles.
 * **Flavor Profiles:** Visual mapping of smoke, fruit, medicinal, and floral notes.
 * **Data Portability:** Your data stays in your container; export to CSV anytime.
 * **Mobile-Ready:** Responsive design for logging bottles while at the store or a tasting.
## 🚀 Getting Started
The most reliable way to run Whisky Wise is via Docker. This ensures all dependencies (database, environment, and server) are perfectly configured out of the box.
### Prerequisites
 * Docker installed on your machine.
 * Docker Compose (included with Docker Desktop).
### Setup Guide
## 🛠 Advanced Configuration
### Docker Compose Example
If you prefer to integrate Whisky Wise into an existing stack, use this docker-compose.yml snippet:
```yaml
services:
  whisky-wise:
    image: ghcr.io/yourusername/whisky-wise:latest
    container_name: whisky_wise
    restart: unless-stopped
    ports:
      - "8080:80"
    volumes:
      - ./whisky_data:/app/data
    environment:
      - NODE_ENV=production
      - DB_TYPE=sqlite

```
### Volume Persistence
> **Critical:** Always map the /app/data directory to a local volume. If you delete the container without a volume mapping, you will lose your tasting history and collection data.
> 
## 🤝 Contributing
Found a bug or want to suggest a feature like "Distillery Maps"?
 1. Fork the Project.
 2. Create your Feature Branch (git checkout -b feature/AmazingFeature).
 3. Commit your Changes (git commit -m 'Add some AmazingFeature').
 4. Push to the Branch (git push origin feature/AmazingFeature).

 5. ## 🤖 Built with AI
Portions of this application, were developed with the assistance of **Claude Sonnet 4.6**.
This allows for a more rapid development cycle and optimized container orchestration.
 6. Open a Pull Request.
## 📜 License
Distributed under the MIT License. See LICENSE for more information.
