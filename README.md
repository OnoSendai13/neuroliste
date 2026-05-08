# 🧠 Neuroliste - Annuaire des Neurologues Français

Application web pour explorer et exporter les neurologues français depuis la base RPPS (Répertoire des Professionnels de Santé).

## 🚀 Démarrage rapide

### Prerequisites
- Python 3.11+ 
- Node.js 18+ (pour développement frontend)
- SQLite

### Installation

```bash
# Cloner le projet
git clone https://github.com/OnoSendai13/neuroliste.git
cd neuroliste

# Backend
cd backend
pip install -r requirements.txt

# Charger les données RPPS (10-15 min, ~2GB espace disque)
python ../scripts/load_rpps.py

# Démarrer l'API
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## 📊 Données RPPS

Les données sont téléchargées directement depuis data.gouv.fr :

- **Personne activité** : `ps-libreacces-personne-activite.txt` (~803 MB)
- **Diplômes** : `ps-libreacces-dipl-autexerc.txt` (~271 MB)  
- **Savoir-faire** : `ps-libreacces-savoirfaire.txt` (~51 MB)

### Filtrage Neurologues

Les médecins sont identifiés comme neurologues si :
1. ✅ Diplôme avec code "CESM15", "DSM30", ou "DIP143" (Neurologie) dans dipl-autexerc
2. ✅ **ET** savoir-faire avec code "SM32" (Neurologie), "SM31" (Neuro-chirurgie) ou "SM33" (Neuro-psychiatrie)

## 🎯 Fonctionnalités

- 🔍 **Filtres géographiques** : Région → Département → Ville
- 💼 **Mode exercice** : Cabinet (libéral) ou Hôpital
- 📥 **Export CSV** configuré avec filtres appliqués
- 📱 **Interface responsive** React

## 🛠️ API Endpoints

```bash
# Liste des neurologues filtrés
GET /api/doctors?departement=69&mode_exercice=LIBERAL

# Autocomplete villes
GET /api/locations?departement=69

# Export CSV
GET /api/export?departement=69&mode_exercice=LIBERAL

# Trigger mise à jour des données
POST /api/update
```

## 📄 License

MIT - Usage libre pour projets de santé publique