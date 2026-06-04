# Frontend React avec Node.js
FROM node:20-alpine

# Création du répertoire de travail
WORKDIR /app

# Copie des fichiers de dépendances
COPY package*.json ./

# Installation des dépendances
RUN npm install

# Copie du code source
COPY . .

# Exposition du port React
EXPOSE 3000

# Commande de démarrage (mode développement)
CMD ["npm", "start"]
