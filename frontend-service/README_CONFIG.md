# Frontend Service Configuration

This React application is designed to work with Nginx as a reverse proxy.

## Environment Variables

### Development with Nginx (Recommended)

Leave the environment variables empty to use relative URLs:

```bash
# .env file - use relative URLs through Nginx
# REACT_APP_API_URL=
# REACT_APP_WS_URL=
```

The application will automatically:
- Use HTTP API calls to the same origin (proxied by Nginx to backend)
- Use WebSocket connections to the same origin (proxied by Nginx to backend)

### Development without Nginx (Direct Backend Access)

If you need to connect directly to the backend (not recommended):

```bash
# .env file - direct backend access
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000
```

## URLs Configuration

### With Nginx (Default)

- Frontend: `http://localhost:3000` (served by Nginx)
- API calls: `http://localhost:3000/api/*` (proxied to backend by Nginx)
- WebSocket: `ws://localhost:3000/ws/*` (proxied to backend by Nginx)

**Benefits:**
- Single port access
- Production-like setup
- No CORS issues
- Gzip compression
- Static files caching

### Without Nginx (Legacy)

- Frontend: `http://localhost:3000` (React dev server)
- API calls: `http://localhost:8000/api/*` (direct to backend)
- WebSocket: `ws://localhost:8000/ws/*` (direct to backend)

**Issues:**
- Potential CORS issues
- No compression
- No caching
- Multiple ports

## Building

```bash
# Build for production (used by Nginx)
npm run build

# Or via Docker
docker compose exec frontend-service npm run build

# Restart Nginx to serve new build
docker compose restart nginx
```

## Development

```bash
# Start all services (including Nginx)
docker compose up -d

# Build frontend
docker compose exec frontend-service npm run build

# Access application
open http://localhost:3000
```

## Troubleshooting

### WebSocket connection errors

If you see WebSocket errors like `WebSocket connection to 'ws://localhost:8000/ws/...' failed`:

1. Check that `REACT_APP_API_URL` and `REACT_APP_WS_URL` are **NOT** set in `.env`
2. Rebuild the frontend: `docker compose exec frontend-service npm run build`
3. Restart Nginx: `docker compose restart nginx`
4. Clear browser cache and reload

### API calls failing

If API calls fail with CORS or connection errors:

1. Verify Nginx is running: `docker compose ps nginx`
2. Check Nginx logs: `docker compose logs nginx`
3. Test API directly: `curl http://localhost:3000/api/consumption/latest`
4. Ensure you're accessing via `http://localhost:3000` (not `http://localhost:8000`)

## Production Deployment

For production, ensure:

1. Environment variables are empty (use relative URLs)
2. Frontend is built: `npm run build`
3. Nginx serves the build files
4. SSL/TLS is configured in Nginx (for wss:// WebSocket)

```nginx
# Example SSL configuration
server {
    listen 443 ssl http2;
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    # ... rest of config
}
```
