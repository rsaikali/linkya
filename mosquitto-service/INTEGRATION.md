# Configuration MQTT pour linkya-client

Ce document explique comment configurer le client MQTT pour se connecter au broker Mosquitto de Linkya.

## Configuration du watcher MQTT dans linkya-client

Dans le fichier `config/watchers.yml` de linkya-client, ajoutez :

```yaml
watchers:
  mqtt_publisher:
    enabled: true
    broker: ${MQTT_BROKER_HOST}
    port: 8883  # Port TLS
    # Username automatically set to PRM from TéléInfo frame
    password: ${MQTT_CLIENT_PASSWORD}
    tls:
      enabled: true
      ca_cert: ${MQTT_CA_CERT_PATH}
      insecure: false  # Set to true for self-signed certificates
    connection:
      keepalive: 60
      reconnect_delay: 5
      connect_timeout: 10
```

## Variables d'environnement pour linkya-client

Dans le fichier `.env` de linkya-client :

```bash
# MQTT Broker Configuration
MQTT_BROKER_HOST=localhost  # ou IP du serveur Linkya
# Username automatically extracted from PRM in TéléInfo frame
MQTT_CLIENT_PASSWORD=your_prm_password_here
MQTT_CA_CERT_PATH=/path/to/ca.crt  # Certificat CA si TLS activé
```

## Obtenir le certificat CA

Si TLS est activé, récupérez le certificat CA depuis le serveur Linkya :

```bash
# Copier le certificat depuis le container
docker cp mosquitto:/mosquitto/certs/ca.crt ./ca.crt

# Ou via volume mount
docker run --rm -v linkya_mosquitto_certs:/certs alpine cat /certs/ca.crt > ca.crt
```

## Topics MQTT utilisés

Le client publiera automatiquement sur ces topics :

- `linky/{PRM}/data` : Données TéléInfo temps réel
- `linky/{PRM}/status` : Status de connexion du client

Format des données :
```json
{
  "timestamp": "2025-11-11 14:30:00",
  "tic_mode": "standard",
  "data": {
    "PRM": "12345678901234",
    "EAST": "000123456",
    "PAPP": "00350",
    // ... autres données TéléInfo
  }
}
```