#!/usr/bin/with-contenv bashio

# Read options from HA Supervisor
SECRET_KEY=$(bashio::config 'secret_key')

# Export env vars for the app
export SECRET_KEY="${SECRET_KEY}"
export DATABASE_PATH="/data/db/whiskywise.db"
export UPLOAD_FOLDER="/data/uploads"

# Ensure data dirs exist
mkdir -p /data/db /data/uploads

bashio::log.info "Starting WhiskyWise on port 5000..."

exec gunicorn \
  --bind 0.0.0.0:5000 \
  --workers 1 \
  --threads 4 \
  --timeout 120 \
  --chdir /app \
  app:app
