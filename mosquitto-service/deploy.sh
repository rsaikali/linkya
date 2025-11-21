#!/bin/bash
# ============================================
# Mosquitto Quick Deploy Script
# ============================================
# Deployment script for Raspberry Pi (ARM 32-bit)

set -e

echo "=== Mosquitto MQTT Broker - Quick Deploy ==="
echo ""

# Check if running on ARM
ARCH=$(uname -m)
echo "Detected architecture: $ARCH"

if [[ "$ARCH" != "armv7l" && "$ARCH" != "armv6l" && "$ARCH" != "aarch64" ]]; then
    echo "WARNING: This script is designed for ARM architecture (Raspberry Pi)"
    read -p "Continue anyway? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed"
    echo "Install Docker: curl -fsSL https://get.docker.com | sh"
    exit 1
fi

# Check if Docker Compose is installed
if ! docker compose version &> /dev/null; then
    echo "Error: Docker Compose is not installed"
    exit 1
fi

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    
    echo ""
    echo "IMPORTANT: Please edit .env file and set secure passwords!"
    echo "Edit with: nano .env"
    echo ""
    read -p "Press Enter to edit .env now, or Ctrl+C to exit and edit manually..."
    nano .env
fi

# Validate .env
echo "Validating configuration..."
source .env

if [ "$MQTT_ADMIN_PASSWORD" = "change_me_admin_password" ] || \
   [ "$MQTT_BACKEND_PASSWORD" = "change_me_backend_password" ]; then
    echo "ERROR: Please change default passwords in .env file!"
    exit 1
fi

# Build image
echo ""
echo "Building Mosquitto image..."
docker compose build

# Start service
echo ""
echo "Starting Mosquitto service..."
docker compose up -d

# Wait for service to be healthy
echo ""
echo "Waiting for service to be ready..."
sleep 5

# Check status
echo ""
echo "Checking service status..."
docker compose ps

# Display logs
echo ""
echo "Recent logs:"
docker compose logs --tail=20

# Test connection
echo ""
echo "Testing MQTT connection..."
if docker compose exec -T mosquitto mosquitto_pub -h localhost -p 1883 \
    -t "test/deploy" -m "Deploy successful" \
    -u admin -P "$MQTT_ADMIN_PASSWORD" 2>/dev/null; then
    echo "✓ Connection test successful!"
else
    echo "✗ Connection test failed"
fi

# Display next steps
echo ""
echo "=== Deployment Summary ==="
echo "Service: mosquitto"
echo "Status: Running"
echo "Ports:"
echo "  - 1883 (MQTT)"
echo "  - 8883 (MQTT over TLS)"
echo "  - 9001 (WebSocket)"
echo "  - 9002 (WebSocket over TLS)"
echo ""
echo "Next steps:"
echo "  1. Export CA certificate: make certs-export"
echo "  2. Copy ca.crt to your MQTT clients"
echo "  3. Configure clients to connect to this broker"
echo "  4. Monitor logs: make logs"
echo ""
echo "Useful commands:"
echo "  make help        - Show all available commands"
echo "  make logs        - View logs"
echo "  make status      - Check status"
echo "  make test        - Test connection"
echo "  make backup      - Backup data and certificates"
echo ""
