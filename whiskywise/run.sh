#!/usr/bin/with-contenv bashio

# Read options from HA Supervisor
SECRET_KEY=$(bashio::config 'secret_key')

# Export env vars for the app
export SECRET_KEY="${SECRET_KEY}"
export DATABASE_PATH="/data/db/whiskywise.db"
export UPLOAD_FOLDER="/data/uploads"

# Derive APP_VERSION from config.yaml, which is copied into the image at build
# time and always reflects the exact version the Supervisor installed.
# This is more reliable than bashio::addon.version (which can fail in some HA
# configurations) and doesn't depend on build-args being passed through.
export APP_VERSION
APP_VERSION=$(grep '^version:' /app/config.yaml | sed 's/version:[[:space:]]*"\?\([^"]*\)"\?/\1/')

# Ensure data dirs exist
mkdir -p /data/db /data/uploads

bashio::log.info "Starting WhiskyWise v${APP_VERSION} on port 5000..."

exec gunicorn \
  --bind 0.0.0.0:5000 \
  --workers 1 \
  --threads 4 \
  --timeout 120 \
  --chdir /app \
  app:app
