# Neuroliste - Annuaire des Neurologues Français

Application web moderne pour explorer et exporter les neurologues français depuis la base RPPS (Répertoire des Professionnels de Santé).

## 🚀 Démarrage rapide

### Installation avec Docker (recommandé)

```bash
# Cloner le projet
git clone https://github.com/OnoSendai13/neuroliste.git
cd neuroliste

# Démarrer les conteneurs
docker-compose up -d

# Services disponibles:
# - Frontend: http://127.0.0.1:5173
# - API: http://127.0.0.1:50000
```

### Installation locale (sans Docker)

```bash
# Cloner le projet
git clone https://github.com/OnoSendai13/neuroliste.git
cd neuroliste
```

#### Backend

```bash
cd backend
pip install -r requirements.txt

# Charger les données RPPS (10-15 min, ~2GB espace disque)
python ../scripts/load_rpps.py

# Démarrer l'API
uvicorn main:app --reload --port 50000
```

#### Frontend

```bash
cd frontend
npm install
npm run dev  # http://localhost:5173
```

## 📊 Données RPPS

Les données sont téléchargées directement depuis data.gouv.fr :

- **Personne activité** : `ps-libreacces-personne-activite.txt` (~803 MB)
- **Diplômes** : `ps-libreacces-dipl-autexerc.txt` (~271 MB) 
- **Savoir-faire** : `ps-libreacces-savoirfaire.txt` (~51 MB)

### Filtrage Neurologues

Les médecins sont identifiés comme neurologues si :

1. ✅ Diplôme avec code "CESM15", "DSM30", ou "DIP143" (Neurologie) dans dipl-autexerc
2. ✅ **ET** savoir-faire avec code **"SM32"** (Neurologie uniquement) dans savoirfaire

**Code SM exclus :**

- SM31 = Neuro-chirurgie (exclu)
- SM33 = Neuro-psychiatrie (exclu)

## 🎯 Fonctionnalités

- 🔍 **Filtres géographiques flexibles** : Région et Département sont indépendants
  - Filtrer par région uniquement
  - Filtrer par département uniquement
  - Combiner région + département si besoin
  - La sélection d'une région filtre les départements affichés
- 💼 **Mode exercice** : Cabinet (L), Salarié (S)
  - Mixte et Hospitalier retirés car ne débouchent sur aucun résultat
- 📊 **Statistiques interactives** : Camemberts et graphiques par région, département, mode d'exercice
  - Les graphiques se rafraîchissent automatiquement quand les filtres changent
  - Affichage du total filtré en temps réel
- 📅 **Date du dernier import** : Affichée dans le header
- 📥 **Export CSV** configuré avec filtres appliqués
- 🌙 **Dark mode** : Toggle Clair / Sombre / Système
- 🏥 **Numéro RPPS** : Affiché sous le nom dans le tableau
- 📱 **Interface responsive** React avec design moderne
- 🎨 **Design moderne** : Palette médicale teal, cartes, ombres, gradients subtils
- ✅ **Corrections d'adresses** : 524 adresses manquantes enrichies via recherche externe (duckduckgo)

## 🛠️ API Endpoints

```bash
# Liste des neurologues filtrés
GET /api/doctors?region=NAQ&departement=33

# Liste des départements (option: filtrer par région)
GET /api/locations?region=NAQ

# Statistiques pour graphiques (option: filtrer par région/département)
GET /api/stats?region=NAQ
# Réponse inclut: total, departements, modes, regions, types_etablissement, last_import

# Export CSV avec filtres
GET /api/export?region=NAQ&departement=33

# Charger les données RPPS depuis frontend
POST /api/load-data
```

## 🐳 Architecture Docker

```
neuroliste/
├── backend/
│   ├── main.py          # API FastAPI
│   ├── models.py        # Modèles SQLAlchemy
│   └── data/            # Base SQLite persistante
├── frontend/
│   ├── src/
│   │   ├── App.jsx      # Composant principal
│   │   ├── components/
│   │   │   ├── FilterPanel.jsx      # Filtres géographiques
│   │   │   ├── StatsDashboard.jsx   # Graphiques interactifs (Recharts)
│   │   │   ├── DoctorTable.jsx      # Tableau des neurologues
│   │   │   ├── Pagination.jsx       # Pagination
│   │   │   └── ThemeToggle.jsx      # Toggle dark mode
│   │   └── index.css    # Design system Tailwind
│   └── index.html
├── scripts/
│   └── load_rpps.py     # Script de chargement des données
└── docker-compose.yml
```

## 🖥️ Application autonome (Electron)

Voir [`STANDALONE_APP_PLAN.md`](./STANDALONE_APP_PLAN.md) pour le plan complet de transformation en application desktop autonome multiplateforme.

**Stack recommandée :** Electron + FastAPI embarqué + SQLite

**Effort estimé :** 5-7 jours

## 🌐 Déploiement web

### Avec Nginx (recommandé)

```bash
# Configuration nginx/nginx.conf
server {
    listen 80;
    server_name votre-domaine.fr;
    
    # Frontend static
    root /var/www/neuroliste/frontend/dist;
    index index.html;
    
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    # Proxy API
    location /api/ {
        proxy_pass http://127.0.0.1:50000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```yaml
# docker-compose.yml pour production
version: '3.8'
services:
  api:
    build: ./backend
    volumes:
      - ./backend/data:/app/data
    restart: unless-stopped
    expose:
      - "8000"  # Port interne uniquement
   
  frontend:
    build: ./frontend
    command: ["npm", "run", "build"]
    volumes:
      - ./frontend/dist:/var/www/neuroliste/frontend/dist
    restart: unless-stopped
```

### Avec Apache + mod_proxy

```apache
# .htaccess ou configuration virtuel host
<VirtualHost *:80>
    ServerName votre-domaine.fr
    
    # Frontend
    DocumentRoot /var/www/neuroliste/frontend/dist
    
    # Proxy API vers le backend
    ProxyPass /api/ http://127.0.0.1:50000/api/
    ProxyPassReverse /api/ http://127.0.0.1:50000/api/
    
    # SPA fallback
    FallbackResource /index.html
</VirtualHost>
```

### Notes production importantes

- **Base de données** : Remplacer SQLite par PostgreSQL/MySQL pour le multi-utilisateur
- **HTTPS** : Configurer SSL (Let's Encrypt) pour le déploiement public
- **Mise à jour données** : Créer un cron quotidien pour recharger les données RPPS
- **Variables** : Modifier les URLs dans le frontend via `.env.production` :

```bash
# frontend/.env.production
VITE_API_URL=https://votre-domaine.fr/api
```

## 📄 License

MIT - Usage libre pour projets de santé publique
