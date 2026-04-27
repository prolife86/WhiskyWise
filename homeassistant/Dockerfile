ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install system dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    zbar \
    gcc \
    musl-dev \
    python3-dev \
    jpeg-dev \
    zlib-dev

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application source
COPY app.py .
COPY templates/ templates/

# Pre-create data dirs for non-volume local runs
RUN mkdir -p /data/uploads /data/db

# Copy HA entrypoint
COPY homeassistant/run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 5000

CMD ["/run.sh"]
