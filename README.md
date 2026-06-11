# Neuroliste - Annuaire des Neurologues Français

Application web pour explorer et exporter les neurologues français depuis la base RPPS (Répertoire des Professionnels de Santé).

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

- 🔍 **Filtres géographiques hiérarchisés** : Région → Département → Ville
  - La sélection d'une région filtre automatiquement les départements affichés
  - Le dropdown département ne montre que les départements de la région sélectionnée
- 💼 **Mode exercice** : Cabinet (L), Salarié (S), Mixte (B), Hospitalier (H)
- 📊 **Statistiques interactives** : Camemberts et graphiques par région, département, mode d'exercice
  - Les graphiques se rafraîchissent automatiquement quand les filtres changent
  - Affichage du total filtré en temps réel
- 📥 **Export CSV** configuré avec filtres appliqués
- 📱 **Interface responsive** React avec filtres intuitifs
- 🔘 **Bouton "Load RPPS Data"** : Charge les données depuis l'interface admin (10-15 min)

## 🛠️ API Endpoints

```bash
# Liste des neurologues filtrés
GET /api/doctors?region=NAQ&departement=33

# Liste des départements (option: filtrer par région)
GET /api/locations?region=NAQ

# Statistiques pour graphiques (option: filtrer par région/département)
GET /api/stats?region=NAQ

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
│   │   │   ├── Filters.jsx      # Filtres géographiques
│   │   │   ├── StatsPanel.jsx   # Graphiques interactifs
│   │   │   └── DoctorList.jsx   # Tableau des neurologues
│   │   └── App.css
│   └── index.html
├── scripts/
│   └── load_rpps.py     # Script de chargement des données
└── docker-compose.yml
```

## 📄 License

MIT - Usage libre pour projets de santé publique