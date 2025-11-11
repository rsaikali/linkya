# Mosquitto MQTT Broker Service

Service MQTT Mosquitto pour la plateforme IoT Linkya avec support TLS et authentification.

## Fonctionnalités

- **Authentication**: Authentification par nom d'utilisateur/mot de passe
- **TLS/SSL**: Support complet du chiffrement TLS avec certificats auto-signés
- **ACL**: Contrôle d'accès granulaire par topic et utilisateur
- **WebSockets**: Support MQTT over WebSockets pour applications web
- **Persistence**: Persistance des messages et abonnements
- **Monitoring**: Topics système `$SYS/` pour surveillance

## Ports exposés

| Port | Protocol | Description |
|------|----------|-------------|
| 1883 | MQTT | MQTT standard (non-chiffré) |
| 8883 | MQTT+TLS | MQTT avec chiffrement TLS |
| 9001 | WebSocket | MQTT over WebSockets (non-chiffré) |
| 9002 | WebSocket+TLS | MQTT over WebSockets avec TLS |

## Configuration

### Variables d'environnement

Configurées dans le fichier `.env` principal du projet :

#### TLS Configuration
- `MQTT_TLS_ENABLED`: Active/désactive TLS (true/false)
- `MQTT_SERVER_NAME`: Nom du serveur pour les certificats (défaut: localhost)
- `MQTT_MUTUAL_TLS`: Active l'authentification mutuelle TLS (true/false)

#### Authentication
- `MQTT_ADMIN_PASSWORD`: Mot de passe administrateur
- `MQTT_BACKEND_PASSWORD`: Mot de passe service backend
- `MQTT_MONITOR_PASSWORD`: Mot de passe service monitoring
- `MQTT_GUEST_PASSWORD`: Mot de passe utilisateur invité
- `MQTT_PRM_PASSWORDS`: Mots de passe PRM (format: PRM1:pass1,PRM2:pass2)

### Utilisateurs par défaut

| Utilisateur | Permissions | Description |
|-------------|-------------|-------------|
| `admin` | Lecture/écriture sur tous les topics | Administrateur système |
| `linkya-backend` | Lecture données Linky, écriture commandes | Service backend |
| `linkya-monitor` | Lecture seule données + stats système | Service monitoring |
| `guest` | Lecture topics publics uniquement | Utilisateur invité |
| `{PRM}` | Lecture/écriture namespace propre | Compteurs Linky (par PRM) |

### Topics MQTT

```
linky/{PRM}/data         # Données TéléInfo temps réel
linky/{PRM}/status       # Status connexion compteur
linky/{PRM}/commands     # Commandes vers compteur
backend/commands/+       # Commandes vers backend
backend/responses/+      # Réponses du backend
$SYS/broker/+           # Statistiques système
```

## Sécurité

### TLS/SSL
- Certificats auto-signés générés automatiquement
- Support TLS 1.2+
- Validation des certificats côté client
- Authentification mutuelle TLS optionnelle

### Contrôle d'accès
- ACL basées sur les topics et utilisateurs
- Authentification obligatoire (pas d'accès anonyme)
- Permissions granulaires par utilisateur
- Support des patterns dynamiques (PRM)

## Intégration avec linkya-client

Le client `mqtt_publisher.py` se connecte avec les paramètres suivants :

```yaml
# Configuration dans watchers.yml
mqtt_publisher:
  enabled: true
  broker: ${MQTT_BROKER_HOST}
  port: 8883  # TLS
  username: ${MQTT_CLIENT_USERNAME}
  password: ${MQTT_CLIENT_PASSWORD}
  tls:
    enabled: true
    ca_cert: ${MQTT_CA_CERT_PATH}
    insecure: false
```

## Dépannage

### Vérification de l'état
```bash
# Status du service
docker compose ps mosquitto

# Logs du service
docker compose logs -f mosquitto

# Test de connexion
mosquitto_pub -h localhost -p 1883 -t test -m "hello" -u admin -P <password>
```

### Certificats TLS
```bash
# Régénérer les certificats
docker compose exec mosquitto /mosquitto/scripts/generate-certs.sh

# Vérifier la validité
openssl x509 -in /path/to/certs/server.crt -text -noout
```

### Utilisateurs
```bash
# Régénérer le fichier de mots de passe
docker compose exec mosquitto /mosquitto/scripts/generate-passwords.sh

# Lister les utilisateurs
docker compose exec mosquitto cat /mosquitto/config/passwd
```