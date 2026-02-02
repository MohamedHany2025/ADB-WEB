FROM python:3.9

WORKDIR /app

# Update and install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    android-tools-adb \
    android-tools-fastboot \
    scrcpy \
    git \
    wget \
    unzip \
    curl \
    openjdk-11-jdk \
    libusb1.0-0 \
    libusb-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Copy files
COPY requirements.txt .
COPY server.py .
COPY templates/ templates/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV PORT=8000
ENV DEBUG=False
ENV FLASK_ENV=production

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["python", "server.py"]

