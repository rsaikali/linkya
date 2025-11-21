# ============================================
# Mosquitto MQTT Broker - Docker Image
# ============================================
# Official Mosquitto image with TLS and authentication support
# Includes custom configuration and initialization scripts

FROM eclipse-mosquitto:2.0.18

# Maintainer information
LABEL maintainer="Linkya Team"
LABEL description="Mosquitto MQTT Broker for Linkya IoT platform"
LABEL version="2.0.18"

# Switch to root for setup
USER root

# Install additional packages for certificate generation and debugging
RUN apk update && \
    apk add --no-cache \
        openssl \
        bash \
        curl \
        netcat-openbsd && \
    rm -rf /var/cache/apk/*

# Create necessary directories
RUN mkdir -p /mosquitto/config \
             /mosquitto/data \
             /mosquitto/log \
             /mosquitto/certs \
             /mosquitto/scripts && \
    chmod 755 /mosquitto/config \
              /mosquitto/data \
              /mosquitto/log \
              /mosquitto/certs \
              /mosquitto/scripts

# Copy configuration files
COPY config/mosquitto.conf /mosquitto/config/
COPY config/acl.conf /mosquitto/config/

# Remove default mosquitto configuration to avoid conflicts
RUN rm -f /mosquitto/config/mosquitto.conf.example \
          /mosquitto/config/mosquitto.conf.default \
          /etc/mosquitto/mosquitto.conf 2>/dev/null || true

# Copy and make scripts executable
COPY scripts/*.sh /mosquitto/scripts/
RUN chmod +x /mosquitto/scripts/*.sh

# Create mosquitto user if it doesn't exist
RUN if ! id mosquitto >/dev/null 2>&1; then \
        addgroup -g 1883 mosquitto && \
        adduser -D -u 1883 -G mosquitto -s /bin/sh mosquitto; \
    fi

# Set ownership
RUN chown -R mosquitto:mosquitto /mosquitto

# Health check on TLS port
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD mosquitto_pub -h localhost -p 8883 -t '\$SYS/broker/ping' -m "healthcheck" -u admin -P "\${MQTT_ADMIN_PASSWORD}" --cafile /mosquitto/certs/ca.crt --insecure || exit 1

# Expose ports (TLS ONLY for security)
# 8883: MQTT over TLS
# 9002: MQTT over WebSockets with TLS
EXPOSE 8883 9002

# Set working directory
WORKDIR /mosquitto

# Use custom initialization script as entrypoint
ENTRYPOINT ["/mosquitto/scripts/init-mosquitto.sh"]