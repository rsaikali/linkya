#!/bin/bash
set -e

echo "Building frontend..."
cd /app

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

# Build the application
echo "Building React app..."
npm run build

# Copy build files to nginx directory
echo "Copying build files to nginx..."
cp -r build/* /usr/share/nginx/html/

echo "Frontend build complete!"
ls -la /usr/share/nginx/html/
