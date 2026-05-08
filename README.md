# 🧠 Neuroliste - Annuaire des Neurologues Français

Application web pour explorer et exporter les neurologues français depuis la base RPPS (Répertoire des Professionnels de Santé).

## 🚀 Démarrage rapide

### Prerequisites
- Docker & Docker Compose
- Node.js 18+ (pour développement local)
- Python 3.11+ (pour développement local)

### Lancement avec Docker

```bash
# Cloner le projet
git clone https://github.com/OnoSendai13/neuroliste.git
cd neuroliste

# Démarrer tous les services
docker-compose up --build

# Services disponibles :
# - Frontend : http://localhost:5173
# - Backend API : http://localhost:50000
# - MCP Server : http://127.0.0.1:8007/mcp
```

### Développement local

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

## 🏗️ Architecture

```
neuroliste/
├── backend/          # FastAPI + SQLite
│   ├── main.py       # API REST
│   ├── models.py     # Schéma DB
│   └── mcp_server.py # Integration MCP
├── frontend/         # React + Vite
│   └── src/
├── scripts/          # Extraction RPPS
└── docker-compose.yml
```

## 🔌 Configuration MCP

### Option 1 : Docker (recommandé)

Le serveur MCP tourne dans Docker sur `127.0.0.1:8007`.

Ajoutez à votre configuration Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`) :

```json
{
  "mcpServers": {
    "rpps-neuro": {
      "command": "docker",
      "args": ["exec", "-i", "rpps-mcp-server", "python", "mcp_server.py"]
    }
  }
}
```

### Option 2 : Accès direct

Si votre serveur MCP est déjà en cours d'exécution sur `127.0.0.1:8007` :

```bash
# Le backend utilisera automatiquement ce MCP
export MCP_URL=http://127.0.0.1:8007/mcp
```

## 📊 Données RPPS

### Sources
- **Personne activité** : `ps-libreacces-personne-activite.txt` (~803 MB)
- **Diplômes** : `ps-libreacces-dipl-autexerc.txt` (~271 MB)  
- **Savoir-faire** : `ps-libreacces-savoirfaire.txt` (~51 MB)

### Filtrage Neurologues
Les médecins sont identifiés comme neurologues si :
1. ✅ Présence d'un savoir-faire avec code "NEURO" ou "NEUROLOGIE"
2. ✅ **ET** diplôme "NEUROLOGIE" dans dipl-autexerc

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

## 📦 Déploiement

### Variables d'environnement

```bash
# Backend
DATABASE_URL=sqlite:////app/data/neurologues.db
MCP_URL=http://127.0.0.1:8007/mcp

# Frontend
VITE_API_URL=http://localhost:50000
```

## 🗺️ Roadmap

- [ ] Intégration complète avec vrai MCP
- [ ] Cache des résultats autocomplete
- [ ] Carte interactive des neurologues
- [ ] Alertes disponibilité par région

## 📄 License

MIT - Usage libre pour projets de santé publique