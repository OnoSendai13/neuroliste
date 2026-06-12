# Plan de transformation en application autonome

Ce document décrit la stratégie pour transformer Neuroliste d'une application Docker en application desktop autonome multiplateforme.

## État actuel

Architecture actuelle :

```
docker-compose
├── backend FastAPI (Python)
├── frontend React/Vite
└── SQLite local
```

L'application fonctionne mais dépend de Docker. Pour un utilisateur non technique, il faut :
1. Installer Docker Desktop
2. Lancer `docker-compose up -d`
3. Ouvrir le navigateur sur `http://localhost:5173`

## Objectif

Créer une application desktop autonome :
- Un exécutable par plateforme (Windows, Mac, Linux)
- Pas de Docker requis
- SQLite embarqué
- Données RPPS incluses ou téléchargeables au premier lancement
- Interface moderne conservée

## Option recommandée : Electron

### Pourquoi Electron

1. **Conservation du code existant** — React, Tailwind, Recharts restent utilisables
2. **FastAPI embarqué** — le backend Python tourne en processus background
3. **SQLite embarqué** — les données voyagent avec l'application
4. **Multiplateforme** — un seul codebase pour Windows, Mac, Linux
5. **Écosystème mature** — documentation abondante, tooling éprouvé

### Architecture cible

```
neuroliste-desktop/
├── electron/
│   ├── main.js          # Processus principal Electron
│   ├── preload.js       # Bridge sécurisé frontend ↔ backend
│   └── package.json     # Config Electron
├── backend/             # FastAPI existant (inchangé)
├── frontend/            # React existant (inchangé)
└── scripts/             # Scripts de build
```

### Flux d'exécution

```
1. L'utilisateur lance l'application (.exe/.app/.AppImage)
2. Electron démarre
3. Electron lance FastAPI en background (processus Python embarqué)
4. Electron ouvre une fenêtre Chromium avec le frontend React
5. Le frontend appelle l'API via localhost (port interne)
6. SQLite est embarqué dans le paquet ou généré au premier lancement
7. À la fermeture, Electron arrête proprement FastAPI
```

## Alternatives évaluées

### Tauri

Plus léger qu'Electron (~10-20 MB vs ~150-200 MB), mais :
- Plus complexe à configurer avec FastAPI
- Nécessite un sidecar Python
- Moins de flexibilité si on veut tout garder en JS

**Verdict :** Intéressant pour une v2, mais Electron est plus pragmatique pour une v1.

### PWA

Moins de travail, mais :
- Le backend doit quand même tourner quelque part
- Pas vraiment autonome hors ligne
- Moins de contrôle sur le système de fichiers

**Verdict :** Pas adapté à l'objectif "application autonome".

### React Native / Expo

Pour du mobile pur :
- Nécessite de réécrire presque tout le frontend
- Le backend reste à part
- Effort beaucoup plus important

**Verdict :** À envisager seulement si le besoin mobile devient prioritaire.

## Plan de travail

### Phase 1 — Préparation du fork (1 jour)

- [ ] Créer un fork propre `neuroliste-desktop`
- [ ] Nettoyer l'architecture actuelle (déjà partiellement fait)
- [ ] Vérifier que tout fonctionne sans Docker
- [ ] Documenter les chemins de fichiers par OS

### Phase 2 — Wrapper Electron (2-3 jours)

- [ ] Initialiser Electron avec Vite
- [ ] Créer le processus principal (`main.js`)
- [ ] Lancer FastAPI en background au démarrage
- [ ] Gérer l'arrêt propre des processus
- [ ] Configurer `preload.js` pour le bridge sécurisé
- [ ] Tester la communication frontend ↔ backend

### Phase 3 — Données embarquées (1-2 jours)

- [ ] Décider : DB incluse dans le paquet vs téléchargement au premier lancement
- [ ] Gérer les chemins SQLite par OS (`appData`, `userData`, etc.)
- [ ] Script de migration/update des données
- [ ] Gestion des erreurs si la DB est corrompue

### Phase 4 — Build multiplateforme (1-2 jours)

- [ ] Configuration `electron-builder`
- [ ] Build Windows (.exe + installer)
- [ ] Build Mac (.dmg)
- [ ] Build Linux (.AppImage)
- [ ] Tests sur les 3 plateformes

### Phase 5 — Polish (1-2 jours)

- [ ] Icône et métadonnées de l'application
- [ ] Écran de chargement
- [ ] Gestion des erreurs utilisateur
- [ ] Auto-updater optionnel
- [ ] Documentation utilisateur

## Estimation totale

| Phase | Effort |
|-------|--------|
| Préparation | 1 jour |
| Wrapper Electron | 2-3 jours |
| Données embarquées | 1-2 jours |
| Build multiplateforme | 1-2 jours |
| Polish | 1-2 jours |
| **Total** | **5-7 jours** |

## Points de vigilance

### 1. Embarquer Python + FastAPI

Le plus délicat. Options :
- **PyInstaller** pour packager FastAPI en exécutable
- **Nuitka** pour compiler Python en binaire
- **Sidecar Python** inclus dans le paquet Electron

Recommandation : **PyInstaller** pour FastAPI, lancé comme sidecar par Electron.

### 2. Chemins de fichiers

Chaque OS a ses conventions :
- Windows : `C:\Users\<user>\AppData\Roaming\Neuroliste`
- Mac : `~/Library/Application Support/Neuroliste`
- Linux : `~/.config/neuroliste`

À gérer via `electron.app.getPath('userData')`.

### 3. Taille du paquet

Avec Python + FastAPI + SQLite + données RPPS :
- Application vide : ~150-200 MB (Electron)
- Python + deps : ~50-100 MB
- Données RPPS : ~2 GB si incluses

Option recommandée : **données téléchargeables au premier lancement** pour garder le paquet léger.

### 4. Auto-update

Optionnel mais recommandé pour les utilisateurs non techniques.
- `electron-updater` pour les mises à jour automatiques
- Releases GitHub avec assets par plateforme

## Conclusion

Electron est le choix le plus pragmatique pour une v1 :
- Maximum de code réutilisé
- Écosystème mature
- Build multiplateforme éprouvé
- Effort raisonnable (5-7 jours)

Tauri peut être envisagé pour une v2 si la taille du paquet devient un problème.
