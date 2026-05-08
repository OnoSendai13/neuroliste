# 🧠 Neuroliste - Annuaire des Neurologues Français

Application web pour explorer et exporter les neurologues français depuis la base RPPS (Répertoire des Professionnels de Santé).

## 🚀 Démarrage rapide

### Prerequisites
- Docker & Docker Compose
- Node.js 18+ (pour développement local)
- Python 3.11+ (pour développement local)

### Lancement avec Docker (recommandé)

```bash
# Cloner le projet
git clone https://github.com/OnoSendai13/neuroliste.git
cd neuroliste

# Démarrer tous les services
docker-compose up --build

# Services disponibles :
# - Frontend : http://localhost:5173
# - Backend API : http://localhost:50000
# - API Docs : http://localhost:50000/docs
```

### Développement local (sans Docker)

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (dans un autre terminal)
cd frontend
npm install
npm run dev
```

### Remplir la base avec des données test

```bash
# Dans un autre terminal
python scripts/populate_sample.py
```

## 🏗️ Architecture

```
neuroliste/
├── backend/          # FastAPI + SQLite
│   ├── main.py       # API REST
│   ├── models.py     # Schéma DB
├── frontend/         # React + Vite
│   └── src/
├── scripts/          # Extraction RPPS
└── docker-compose.yml
```

## 🔌 Configuration MCP

Le backend se connecte à votre serveur MCP existant :

```bash
# Via variable d'environnement (dans docker-compose.yml)
MCP_URL=http://127.0.0.1:8007/mcp
```

L'endpoint `/api/update` déclenche la mise à jour via MCP.

## 📊 Données RPPS

### Sources
- **Personne activité** : `ps-libreacces-personne-activite.txt` (~803 MB)
- **Diplômes** : `ps-libreacces-dipl-autexerc.txt` (~271 MB)  
- **Savoir-faire** : `ps-libreacces-savoirfaire.txt` (~51 MB)

### Filtrage Neurologues
Les médecins sont identifiés comme neurologues si :
1. Présence d'un savoir-faire avec code "NEURO" ou "NEUROLOGIE"
2. **ET** diplôme "NEUROLOGIE" dans dipl-autexerc

## 🎯 Fonctionnalités

- 🔍 **Filtres géographiques** : Région → Département → Ville
- 💼 **Mode exercice** : Cabinet (libéral) ou Hôpital
- 📥 **Export CSV** configuré avec filtres appliqués
- 🔄 **Mise à jour** hebdo via MCP
- 📱 **Interface responsive** React

## 🛠️ API Endpoints

```bash
# Liste des neurologues filtrés
GET /api/doctors?departement=69&mode_exercice=LIBERAL

# Autocomplete villes
GET /api/locations?departement=69

# Export CSV
GET /api/export?departement=69&mode_exercice=LIBERAL

# Trigger mise à jour
POST /api/update
```

## 📄 License

MIT - Usage libre pour projets de santé publique