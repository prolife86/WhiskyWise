#!/usr/bin/with-contenv bashio

# ── Read options from HA Supervisor ──────────────────────────────────────────
SECRET_KEY=$(bashio::config 'secret_key')

# ── Data paths (HA maps /data to the add-on data folder) ─────────────────────
export DATABASE_PATH="/data/db/whiskywise.db"
export UPLOAD_FOLDER="/data/uploads"
export SECRET_KEY="${SECRET_KEY}"
export FLASK_APP="app.py"

# Ensure directories exist
mkdir -p /data/db /data/uploads

bashio::log.info "Starting WhiskyWise 1.2.0 on port 5000..."

exec gunicorn \
  --bind 0.0.0.0:5000 \
  --workers 1 \
  --threads 4 \
  --timeout 120 \
  app:app
