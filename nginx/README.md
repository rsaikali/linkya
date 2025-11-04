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

## Troubleshooting

### WebSocket Connection Refused Errors

**Symptom**: Logs show `connect() failed (111: Connection refused) while connecting to upstream`

**Cause**: Docker was trying to use IPv6 to connect to backend

**Solution**: IPv6 is now disabled on the Docker network. If you still see this error:

1. Recreate the network:
```bash
docker compose down
docker compose up -d
```

2. Check backend is accessible:
```bash
docker compose exec nginx ping -c 2 backend
```

3. Verify network configuration:
```bash
docker network inspect nilmia_nilmia-network | grep IPv6
# Should show: "EnableIPv6": false
```

### Domain Access Issues

**Symptom**: Application works on `localhost:3000` but not on `dev.saikali.fr`

**Solution**: The `server_name` directive accepts multiple domains. Check Nginx logs:

```bash
docker compose logs nginx --tail=50
```

If you see errors, ensure your reverse proxy (if any) is correctly forwarding requests.

### WebSocket Connections Failing

**Symptom**: Browser console shows `WebSocket connection to 'ws://...' failed`

**Solution**:

1. Verify Nginx is proxying WebSocket correctly:
```bash
# Test from inside container
docker compose exec nginx curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  http://backend:8000/ws/consumption
```

2. Check for status 101 in logs (Switching Protocols):
```bash
docker compose logs nginx | grep "101"
```

3. Ensure firewall allows WebSocket connections

