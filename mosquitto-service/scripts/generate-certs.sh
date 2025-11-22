#!/bin/bash
# ============================================
# TLS Certificate Generator for Mosquitto
# ============================================
# This script generates self-signed certificates for Mosquitto TLS
# For production, replace with certificates from a trusted CA

set -e

CERT_DIR="/mosquitto/certs"
DAYS=36500
COUNTRY="FR"
STATE="France"
CITY="Paris"
ORG="Linkya"
OU="IoT"
CN="${MQTT_SERVER_NAME:-localhost}"

echo "=== Mosquitto TLS Certificate Generator ==="
echo "Certificate directory: $CERT_DIR"
echo "Server name: $CN"
echo "Validity: $DAYS days"

# Create certificate directory if it doesn't exist
mkdir -p "$CERT_DIR"
cd "$CERT_DIR"

# Check if certificates already exist
if [ -f "ca.crt" ] && [ -f "server.crt" ] && [ -f "server.key" ]; then
    echo "Certificates already exist. Checking validity..."
    
    # Check if certificates are still valid (not expired)
    if openssl x509 -checkend 86400 -noout -in server.crt >/dev/null 2>&1; then
        echo "Existing certificates are still valid. Skipping generation."
        echo "To force regeneration, delete the certificates and run this script again."
        exit 0
    else
        echo "Existing certificates are expired or invalid. Regenerating..."
        rm -f *.crt *.key *.csr *.srl
    fi
fi

# Generate CA private key
echo "Generating CA private key..."
openssl genrsa -out ca.key 4096

# Generate CA certificate
echo "Generating CA certificate..."
openssl req -new -x509 -days $((DAYS + 30)) -key ca.key -out ca.crt -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/OU=$OU/CN=$ORG-CA"

# Generate server private key
echo "Generating server private key..."
openssl genrsa -out server.key 4096

# Generate server certificate signing request
echo "Generating server certificate signing request..."
openssl req -new -key server.key -out server.csr -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/OU=$OU/CN=$CN"

# Create server certificate extensions
cat > server.ext << EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = $CN
DNS.2 = localhost
DNS.3 = mosquitto
DNS.4 = *.linkya.local
IP.1 = 127.0.0.1
IP.2 = ::1
EOF

# Generate server certificate signed by CA
echo "Generating server certificate..."
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt -days $DAYS -sha256 -extfile server.ext

# Generate client certificate (optional, for mutual TLS)
if [ "$MQTT_MUTUAL_TLS" = "true" ]; then
    echo "Generating client certificate for mutual TLS..."
    
    # Generate client private key
    openssl genrsa -out client.key 4096
    
    # Generate client certificate signing request
    openssl req -new -key client.key -out client.csr -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/OU=$OU/CN=linkya-client"
    
    # Generate client certificate signed by CA
    openssl x509 -req -in client.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out client.crt -days $DAYS
    
    echo "Client certificate generated: client.crt, client.key"
fi

# Set appropriate permissions
chmod 644 *.crt
chmod 600 *.key
chmod 644 *.csr 2>/dev/null || true

# Clean up temporary files
rm -f server.csr server.ext client.csr 2>/dev/null || true

echo "Certificate generation completed!"
echo "Files generated:"
echo "  - CA Certificate: ca.crt"
echo "  - Server Certificate: server.crt"
echo "  - Server Private Key: server.key"

if [ "$MQTT_MUTUAL_TLS" = "true" ]; then
    echo "  - Client Certificate: client.crt"
    echo "  - Client Private Key: client.key"
fi

echo ""
echo "Certificate information:"
echo "CA Certificate:"
openssl x509 -in ca.crt -text -noout | grep -E "(Subject|Validity|DNS|IP)"
echo ""
echo "Server Certificate:"
openssl x509 -in server.crt -text -noout | grep -E "(Subject|Validity|DNS|IP)"