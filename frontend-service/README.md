# Frontend Service - Interface React Material-UI

Interface utilisateur moderne pour visualiser et interagir avec les données Linky et NILM.

## Technologies

- **React 18**: Framework UI moderne
- **Material-UI (MUI)**: Composants UI avec design system
- **Chart.js**: Graphiques interactifs de consommation
- **Axios**: Client HTTP pour communiquer avec le backend

## Fonctionnalités

### Dashboard temps réel
- **Dernière consommation**: Affichage en temps réel de la puissance, température, index HP/HC
- **Rafraîchissement automatique**: Mise à jour toutes les 5 secondes

### Graphique de consommation
- **Historique**: Graphique Chart.js avec données agrégées
- **Périodes configurables**: 1h, 6h, 12h, 24h, 48h, 7 jours
- **Détections NILM**: Overlay des appareils détectés sur le graphique
- **Rafraîchissement automatique**: Mise à jour toutes les 30 secondes

## Palette de couleurs Nilmia

Le thème Material-UI utilise la palette personnalisée :

- **Primary** (#BD2A2E): Rouge Big-Machine-1 pour les éléments principaux
- **Secondary** (#486966): Vert foncé Big-Machine-5 pour les accents
- **Background** (#B2BEBF): Gris clair Big-Machine-3 pour le fond
- **Text** (#3B3936): Gris foncé Big-Machine-2 pour le texte principal

## Composants React

- **`App.js`**: Composant principal avec AppBar et layout
- **`LatestConsumption.js`**: Carte affichant la dernière consommation
- **`ConsumptionChart.js`**: Graphique interactif avec détections NILM
- **`theme.js`**: Thème Material-UI personnalisé
- **`services/api.js`**: Service de communication avec le backend

## Configuration

Variables d'environnement dans `.env` :

```bash
REACT_APP_API_URL=http://localhost:8000
```

## Développement

```bash
# Démarrer le frontend
docker-compose up frontend

# Installer les dépendances (si besoin)
npm install

# Ouvrir dans le navigateur
make frontend
# ou
open http://localhost:3000
```

## Structure

```
frontend-service/
├── Dockerfile          # Image Docker Node.js 20
├── package.json        # Dépendances Node.js
├── public/
│   └── index.html      # Page HTML principale
└── src/
    ├── index.js        # Point d'entrée React
    ├── App.js          # Composant principal
    ├── theme.js        # Thème Material-UI
    ├── components/     # Composants React
    │   ├── LatestConsumption.js
    │   └── ConsumptionChart.js
    └── services/
        └── api.js      # Service API
```

## Design responsive

L'interface est entièrement responsive et s'adapte aux différentes tailles d'écran (desktop, tablette, mobile).

## Accès

- **URL**: http://localhost:3000
- **Backend API**: http://localhost:8000
