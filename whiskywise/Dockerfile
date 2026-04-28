# WhiskyWise Home Assistant Add-on
FROM ghcr.io/home-assistant/base-python:3.13-alpine3.21

# Install system dependencies
RUN apk add --no-cache \
    gcc \
    musl-dev \
    python3-dev \
    jpeg-dev \
    zlib-dev \
    zbar

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Copy application source (synced into this folder by CI)
COPY app.py .
COPY templates/ templates/

# Copy HA entrypoint
COPY run.sh /run.sh
RUN chmod a+x /run.sh

EXPOSE 5000

CMD ["/run.sh"]
