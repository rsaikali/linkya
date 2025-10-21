#!/bin/bash

echo "Initialisation automatique de pgAdmin..."

# Attendre que TimescaleDB soit prêt (test de connexion simple)
until nc -z timescaledb 5432; do
  echo "En attente de TimescaleDB..."
  sleep 2
done

echo "TimescaleDB est prêt, configuration de pgAdmin..."

# Copier le fichier pgpass avec les bonnes permissions
cp /pgadmin4/pgpass /var/lib/pgadmin/pgpass
chown pgadmin:pgadmin /var/lib/pgadmin/pgpass
chmod 600 /var/lib/pgadmin/pgpass

echo "Configuration pgAdmin terminée."

# Lancer pgAdmin normalement
exec /entrypoint.sh