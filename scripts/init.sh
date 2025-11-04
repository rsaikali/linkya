#!/bin/bash
# Script to build frontend on first run

set -e

echo "🚀 Initializing Nilmia services..."

# Start services
echo "📦 Starting services..."
docker compose up -d

# Wait for frontend-service to be ready
echo "⏳ Waiting for frontend-service to be ready..."
sleep 10

# Build frontend
echo "🔨 Building frontend..."
docker compose exec frontend-service npm run build

# Restart nginx to serve the new build
echo "🔄 Restarting Nginx..."
docker compose restart nginx

echo "✅ Nilmia is ready!"
echo ""
echo "📱 Access the application at: http://localhost:3000"
echo "🔧 API documentation at: http://localhost:8000/docs"
echo ""
echo "📊 Useful commands:"
echo "  make logs          - View all logs"
echo "  make nginx-logs    - View Nginx logs"
echo "  make frontend-build - Rebuild frontend"
echo "  make help          - Show all available commands"
