---
title: RPPS Neuro — adresses manquantes
date: 2026-06-18
tags:
  - rpps
  - neuro
  - corrections
status: paused
---

# RPPS Neuro — adresses manquantes

## État du batch principal

Base cible :

- `/home/laurent/.local/share/rpps-neuro/data/neurologues.db`

Contrainte importante :

- **aucune modification directe de la DB**
- les corrections doivent rester dans des fichiers externes
- la DB doit rester en lecture seule

Fichier de candidats initial :

- `data/corrections/adresse_corrections_candidates.csv`

Batch DuckDuckGo final :

- `data/corrections/adresse_corrections_recherchees_duckduckgo.csv`
- `data/corrections/adresse_corrections_recherchees_duckduckgo_summary.json`

Résultat :

```text
rows : 678
unique_ids : 678
duplicates : 0
probable : 503
non_sure : 175
probable_with_address : 494
aucune modification DB effectuée
```

Lecture :

- `678` candidats d’adresses manquantes
- `503` lignes classées `probable`
- `494` ont une adresse suggérée exploitable
- `175` restent en `non_sure`

---

## Analyse des 175 `non_sure`

Fichiers produits :

- `data/corrections/non_sure_analysis_summary.json`
- `data/corrections/non_sure_to_review.csv`

Bilan :

```text
non_sure total : 175
avec adresse suggérée : 0
```

Répartition par catégorie d’audit :

```text
mode_vide_adresse_departement_vides : 106
liberal_sans_departement : 33
salarie_sans_departement : 35
salarie_adresse_vide_departement_present : 1
```

Par mode d’exercice :

```text
vide : 106
L : 33
S : 36
```

Scores observés :

```text
55 : 154
47 : 8
40 : 5
35 : 4
52 : 2
45 : 1
23 : 1
```

Principaux domaines sources dans les `non_sure` :

```text
www.mablouseblanche.fr : 49
www.medecinfrance.com : 17
supermedecin.fr : 15
monsuivimedical.fr : 11
www.doctoome.com : 10
www.doctolib.fr : 7
agenda.direct : 6
www.chu-montpellier.fr : 6
fr.linkedin.com : 4
www.aphp.fr : 4
```

Lecture utile :

- beaucoup de résultats sont des annuaires médicaux, mais le snippet ne contient pas l’adresse
- une partie pointe vers des sources étrangères ou hors France
- aucune des 175 n’a une adresse suffisamment fiable pour passer automatiquement en `probable`
- le CSV `non_sure_to_review.csv` contient une colonne `review_reasons` pour trier les motifs

---

## Piste Annuaire Santé / RPPS

Endpoint utilisé :

```text
POST https://annuaire.esante.gouv.fr/api/search/pp
```

Mécanisme :

- `POST` vide pour récupérer le token CSRF
- `POST` avec `numero_rpps` ou `id_ppss`

Test sur 12 praticiens `non_sure` :

```text
processed : 12
non_sure : 12
aucune adresse suggérée
aucune modification DB
```

Conclusion :

- l’Annuaire Santé confirme bien l’identité RPPS
- il permet de vérifier l’état d’exercice
- il ne fournit pas l’adresse dans les cas testés
- utile pour distinguer les vrais RPPS des faux positifs étrangers ou hors champ

---

## Piste `rpps + numéro RPPS` dans DuckDuckGo

Script modifié :

- `scripts/analysis/rechercher_adresses_manquantes.py`

Nouveau flag :

```text
--rpps-query
```

Effet :

- la requête passe de `Nom Prénom neurologue`
- à `RPPS 12345678901 Nom Prénom neurologue`

Résultat sur les 175 `non_sure` :

```text
processed : 175
probable : 29
non_sure : 146
aucune modification DB effectuée
```

Fichiers produits :

- `data/corrections/non_sure_rpps_duckduckgo.csv`
- `data/corrections/non_sure_rpps_duckduckgo_summary.json`
- `data/corrections/non_sure_rpps_probable_to_review.csv`
- `data/corrections/non_sure_rpps_remaining_non_sure.csv`

Lecture :

- `29` lignes ont maintenant une adresse extraite via recherche RPPS
- ces 29 doivent être revues manuellement
- `146` restent sans adresse exploitable
- plusieurs adresses peuvent exister pour un même médecin
- certaines adresses visibles sont anciennes
- certains résultats pointent vers des sources étrangères ou hors champ

---

## Décisions de conception

- ne pas modifier la DB directement
- garder les corrections en externe
- traiter les adresses extraites comme `probable`, jamais `certaine`
- ajouter une note explicite quand une adresse peut être ancienne ou multiple
- utiliser l’Annuaire Santé comme source de validation d’identité, pas comme source d’adresse
- utiliser DuckDuckGo comme source d’extraction d’adresse, avec revue humaine sur les cas ambigus

---

## Procédure d’application des corrections

État validé au 2026-06-19 :

- CSV de revue fusionné : `data/corrections/adresse_corrections_pending_review.csv`
- Résumé : `data/corrections/adresse_corrections_pending_review_summary.json`
- Rapport dry-run : `data/corrections/apply_adresse_corrections_pending_review_report.csv`
- Rapport de vérification DB : `data/corrections/adresse_corrections_pending_review_db_check.csv`

Résultat du dry-run :

```text
total corrections rows : 525
pending_review : 525
confirmed : 0
would_apply_if_confirmed : 525
would_apply : 0
rows_with_updates : 525
updated : 0
db_hash_unchanged : true
```

Lecture : les 525 lignes sont prêtes pour revue, mais aucune n’est applicable automatiquement tant que `status` reste `pending_review` et `apply_allowed=false`.

Commandes de revue :

```bash
python3 scripts/analysis/check_adresse_corrections.py \
  --db /home/laurent/.local/share/rpps-neuro/data/neurologues.db \
  --corrections data/corrections/adresse_corrections_pending_review.csv \
  --out data/corrections/adresse_corrections_pending_review_db_check.csv
```

Commande dry-run :

```bash
python3 scripts/apply_adresse_corrections.py \
  --db /home/laurent/.local/share/rpps-neuro/data/neurologues.db \
  --corrections data/corrections/adresse_corrections_pending_review.csv \
  --report data/corrections/apply_adresse_corrections_pending_review_report.csv \
  --dry-run --include-pending
```

Application uniquement après validation humaine :

1. Ouvrir `data/corrections/adresse_corrections_pending_review.csv`.
2. Mettre à `status=confirmed` et `apply_allowed=true` uniquement les lignes réellement validées.
3. Ne pas corriger `code_mode_exercice` ni `mode_exercice` depuis ce workflow.
4. Relancer le dry-run avec le CSV modifié.
5. Appliquer uniquement avec :

```bash
python3 scripts/apply_adresse_corrections.py \
  --db /home/laurent/.local/share/rpps-neuro/data/neurologues.db \
  --corrections data/corrections/adresse_corrections_pending_review.csv \
  --report data/corrections/apply_adresse_corrections_report.csv \
  --apply --yes-apply
```

---

## À reprendre plus tard

- [ ] revoir les `29` lignes `probable` issues de la recherche RPPS
- [ ] séparer :
  - adresses françaises plausibles
  - anciennes adresses
  - cas avec plusieurs adresses possibles
  - cas étrangers ou hors champ
- [ ] reprendre les `146` `non_sure` restants avec une stratégie plus ciblée
- [ ] envisager une passe manuelle ou semi-automatique sur les sources à forte valeur :
  - Doctolib
  - annuaires hospitaliers
  - pages professionnelles
  - pages institutionnelles
- [ ] vérifier que les corrections finales restent applicables même si la DB est reconstruite

---

## Fichiers importants

Fichiers actifs dans `data/corrections` :

- `data/corrections/adresse_corrections_pending_review.csv`
- `data/corrections/adresse_corrections_pending_review_summary.json`
- `data/corrections/apply_adresse_corrections_pending_review_report.csv`
- `data/corrections/adresse_corrections_pending_review_db_check.csv`
- `data/corrections/non_sure_rpps_probable_to_review.csv`
- `data/corrections/non_sure_rpps_remaining_non_sure.csv`

Intermédiaires archivés :

- `data/corrections/archive/2026-06-18-intermediate/`
