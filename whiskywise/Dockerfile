# WhiskyWise Home Assistant Add-on
# Base image supports aarch64 and amd64
FROM ghcr.io/home-assistant/base-python:3.11

# Install system dependencies
RUN apk add --no-cache \
    gcc \
    musl-dev \
    python3-dev \
    jpeg-dev \
    zlib-dev

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
