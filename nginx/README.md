# Nginx Configuration

This directory contains the Nginx configuration for serving the frontend application and proxying API requests to the backend.

## Architecture

```
User Browser (port 3000)
    ↓
Nginx (port 80 inside container)
    ├─→ /api/* → Backend (port 8000)
    ├─→ /ws/* → Backend WebSocket (port 8000)
    └─→ /* → Frontend static files
```

## Features

- **Reverse Proxy**: Routes `/api/*` and `/ws/*` to the FastAPI backend
- **WebSocket Support**: Full WebSocket support for real-time features
- **Static File Serving**: Serves React build files with optimal caching
- **SPA Routing**: All routes redirect to index.html for client-side routing
- **Compression**: Gzip compression for text-based resources
- **Security Headers**: X-Frame-Options, X-Content-Type-Options, X-XSS-Protection
- **Health Check**: `/health` endpoint for monitoring

## Development Mode

In development mode:
1. The React dev server runs on `frontend-service:3000` with hot reload
2. Build the frontend: `docker compose exec frontend-service npm run build`
3. Nginx serves the built files from `./frontend-service/build`
4. Access the application at `http://localhost:3000`

## Building Frontend

To rebuild the frontend:

```bash
# From host
docker compose exec frontend-service npm run build

# Or rebuild the entire service
docker compose up -d --build nginx
```

## Configuration Files

- `nginx.conf`: Main Nginx configuration
- `Dockerfile`: Nginx container configuration

## Caching Strategy

- **Static assets** (js, css, images, fonts): 1 year cache with immutable flag
- **index.html**: No cache (always fresh)
- **API responses**: No cache (dynamic content)

## Logs

View Nginx logs:

```bash
# Access logs
docker compose logs -f nginx

# Error logs
docker compose exec nginx cat /var/log/nginx/error.log
```

## Health Check

Check if Nginx is healthy:

```bash
curl http://localhost:3000/health
```

Should return: `healthy`
