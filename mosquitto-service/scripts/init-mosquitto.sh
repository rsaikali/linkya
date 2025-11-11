#!/bin/bash
# ============================================
# Mosquitto Initialization Script
# ============================================
# This script initializes Mosquitto with TLS certificates and password file

set -e

echo "=== Mosquitto Initialization ==="
echo "Starting Mosquitto initialization process..."

# Check if running as root (required for certificate generation)
if [ "$(id -u)" != "0" ]; then
    echo "Warning: Not running as root. Some operations may fail."
fi

# Generate TLS certificates if enabled and not present
if [ "$MQTT_TLS_ENABLED" = "true" ]; then
    echo "TLS is enabled. Checking certificates..."
    /mosquitto/scripts/generate-certs.sh
else
    echo "TLS is disabled. Skipping certificate generation."
fi

# Generate password file
echo "Generating password file..."
/mosquitto/scripts/generate-passwords.sh

# Validate configuration file
echo "Validating Mosquitto configuration..."
if mosquitto -c /mosquitto/config/mosquitto.conf -t; then
    echo "Configuration is valid."
else
    echo "Error: Configuration validation failed!"
    exit 1
fi

# Create data directory if it doesn't exist
mkdir -p /mosquitto/data
chmod 755 /mosquitto/data

# Set proper ownership for mosquitto user
if id mosquitto >/dev/null 2>&1; then
    echo "Setting ownership for mosquitto user..."
    chown -R mosquitto:mosquitto /mosquitto/data
    chown -R mosquitto:mosquitto /mosquitto/config
    chown -R mosquitto:mosquitto /mosquitto/certs 2>/dev/null || true
    chown -R mosquitto:mosquitto /mosquitto/log 2>/dev/null || true
fi

echo "Initialization completed successfully!"
echo ""
echo "Starting Mosquitto MQTT broker..."
echo "Configuration: /mosquitto/config/mosquitto.conf"
echo "Data directory: /mosquitto/data"
echo "Log destination: stdout"

# Start Mosquitto
exec mosquitto -c /mosquitto/config/mosquitto.conf