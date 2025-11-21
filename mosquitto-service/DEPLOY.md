# Mosquitto MQTT Broker - Standalone Deployment

Déploiement autonome du broker MQTT Mosquitto sur Raspberry Pi (ARM 32-bit).

## Prérequis

- **Matériel** : Raspberry Pi (ARM 32-bit compatible)
- **OS** : Raspberry Pi OS / Raspbian
- **Docker** : Version 20.10+ avec support ARM
- **Docker Compose** : Version 2.0+

## Installation rapide

### 1. Préparer l'environnement

```bash
# Cloner uniquement le service mosquitto
git clone <repository-url>
cd mosquitto-service

# Copier le fichier de configuration
cp .env.example .env

# Éditer les mots de passe
nano .env
```

### 2. Configuration

Modifier le fichier `.env` :

```bash
# Serveur TLS (adapter selon votre réseau)
MQTT_SERVER_NAME=raspberrypi.local

# Mots de passe (OBLIGATOIRE - changer les valeurs par défaut)
MQTT_ADMIN_PASSWORD=votre_mot_de_passe_admin_securise
MQTT_BACKEND_PASSWORD=votre_mot_de_passe_backend_securise
MQTT_MONITOR_PASSWORD=votre_mot_de_passe_monitor_securise
MQTT_GUEST_PASSWORD=votre_mot_de_passe_guest_securise

# Configuration PRM (ajouter vos compteurs Linky)
MQTT_PRM_PASSWORDS=09714037613599:pAssw0rd
```

### 3. Démarrage

```bash
# Construire l'image (ARM 32-bit)
docker compose build

# Démarrer le service
docker compose up -d

# Vérifier les logs
docker compose logs -f
```

## Vérification du fonctionnement

### Test de connexion locale

```bash
# Test sans authentification (devrait échouer)
mosquitto_pub -h localhost -p 1883 -t test -m "hello"

# Test avec authentification admin
docker compose exec mosquitto mosquitto_pub \
  -h localhost -p 1883 \
  -t "test/connection" -m "Hello from Mosquitto" \
  -u admin -P "${MQTT_ADMIN_PASSWORD}"
```

### Test de connexion réseau

Depuis un autre appareil sur le réseau :

```bash
# Installer mosquitto-clients
sudo apt-get install mosquitto-clients

# Test de connexion
mosquitto_pub -h raspberrypi.local -p 1883 \
  -t "test/remote" -m "Hello from remote" \
  -u admin -P "votre_mot_de_passe_admin"
```

## Gestion des certificats TLS

### Certificats auto-signés (par défaut)

Les certificats sont générés automatiquement au premier démarrage.

```bash
# Régénérer les certificats
docker compose exec mosquitto /mosquitto/scripts/generate-certs.sh

# Exporter le certificat CA
docker compose cp mosquitto:/mosquitto/certs/ca.crt ./ca.crt

# Copier vers les clients
scp ca.crt client@machine:/path/to/certs/
```

### Certificats personnalisés

Pour utiliser vos propres certificats :

```bash
# Copier vos certificats
docker compose cp ca.crt mosquitto:/mosquitto/certs/ca.crt
docker compose cp server.crt mosquitto:/mosquitto/certs/server.crt
docker compose cp server.key mosquitto:/mosquitto/certs/server.key

# Redémarrer Mosquitto
docker compose restart
```

## Gestion des utilisateurs

### Ajouter un nouveau compteur Linky

Modifier `.env` :

```bash
MQTT_PRM_PASSWORDS=09714037613599:pAssw0rd,98765432109876:nouveau_password
```

Régénérer le fichier de mots de passe :

```bash
docker compose exec mosquitto /mosquitto/scripts/generate-passwords.sh
```

### Lister les utilisateurs configurés

```bash
docker compose exec mosquitto cat /mosquitto/config/passwd
```

## Monitoring

### Logs en temps réel

```bash
docker compose logs -f mosquitto
```

### Statistiques du broker

```bash
# Via topics système $SYS
mosquitto_sub -h raspberrypi.local -p 1883 \
  -t '$SYS/broker/#' \
  -u admin -P "votre_mot_de_passe_admin"
```

### Santé du service

```bash
# Status Docker
docker compose ps

# Health check
docker inspect mosquitto | grep -A 5 Health
```

## Sauvegarde et restauration

### Sauvegarde

```bash
# Sauvegarder les données persistantes
docker compose exec mosquitto tar czf /tmp/mosquitto-backup.tar.gz \
  /mosquitto/data /mosquitto/certs

docker compose cp mosquitto:/tmp/mosquitto-backup.tar.gz \
  ./mosquitto-backup-$(date +%Y%m%d).tar.gz
```

### Restauration

```bash
# Restaurer depuis une sauvegarde
docker compose cp mosquitto-backup-20251113.tar.gz mosquitto:/tmp/backup.tar.gz

docker compose exec mosquitto tar xzf /tmp/backup.tar.gz -C /
docker compose restart
```

## Mise à jour

```bash
# Arrêter le service
docker compose down

# Mettre à jour le code
git pull

# Reconstruire et redémarrer
docker compose build
docker compose up -d
```

## Dépannage

### Le service ne démarre pas

```bash
# Vérifier les logs
docker compose logs mosquitto

# Vérifier la configuration
docker compose exec mosquitto mosquitto -c /mosquitto/config/mosquitto.conf -t
```

### Connexions refusées

```bash
# Vérifier que les ports sont ouverts
sudo netstat -tuln | grep -E '(1883|8883|9001|9002)'

# Vérifier le firewall
sudo ufw status
sudo ufw allow 1883/tcp
sudo ufw allow 8883/tcp
```

### Problèmes de certificats TLS

```bash
# Vérifier la validité des certificats
docker compose exec mosquitto openssl x509 -in /mosquitto/certs/server.crt -text -noout

# Forcer la régénération
docker compose exec mosquitto rm /mosquitto/certs/*.crt /mosquitto/certs/*.key
docker compose restart
```

## Performance et optimisation

### Raspberry Pi (ARM 32-bit)

Recommandations pour optimiser les performances :

```bash
# Limiter les logs (éditer config/mosquitto.conf)
log_type error
log_type warning
# log_type notice   # Commenter
# log_type information  # Commenter

# Ajuster la persistance
autosave_interval 600  # Augmenter l'intervalle
```

### Monitoring des ressources

```bash
# CPU et mémoire
docker stats mosquitto

# Espace disque
docker system df
```

## Sécurité

### Bonnes pratiques

1. **Changer TOUS les mots de passe par défaut** dans `.env`
2. **Activer TLS** : `MQTT_TLS_ENABLED=true`
3. **Firewall** : Limiter l'accès aux ports MQTT
4. **Certificats** : Utiliser des certificats signés en production
5. **Backup régulier** : Sauvegarder `/mosquitto/data` et `/mosquitto/certs`

### Firewall (UFW)

```bash
# Autoriser uniquement depuis le réseau local
sudo ufw allow from 192.168.1.0/24 to any port 1883
sudo ufw allow from 192.168.1.0/24 to any port 8883
```

## Support

Pour plus d'informations, consultez :
- `README.md` - Documentation complète du service
- `INTEGRATION.md` - Guide d'intégration avec linkya-client
- Logs : `docker compose logs -f mosquitto`
