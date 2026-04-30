FROM python:3.13-slim
WORKDIR /app
RUN apt-get update && apt-get install -y \
    libzbar0 \
    libzbar-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Data dirs are created at runtime from the volume mount,
# but we pre-create them so local (non-volume) runs work too
RUN mkdir -p /data/uploads /data/db
ENV FLASK_APP=app.py
ENV DATABASE_PATH=/data/db/whiskywise.db
ENV UPLOAD_FOLDER=/data/uploads
# SECRET_KEY must be set at runtime via docker-compose.yml or the HA Supervisor.
# Do NOT set it here — baking secrets into image layers exposes them via
# 'docker inspect' and 'docker history'.

# Version is injected at build time by CI via --build-arg.
# Falls back to 'dev' for local builds without the arg.
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION}

# Run as non-root
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser /app /data
USER appuser
EXPOSE 5000
# Single worker avoids concurrent DB-init races on first boot;
# 4 threads handle concurrent requests efficiently.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "120", "app:app"]
