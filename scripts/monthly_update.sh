#!/usr/bin/env bash
#
# Mise a jour mensuelle de la base RPPS Neurologues.
#
# Les donnees RPPS sont publiees par data.gouv.fr vers le 5 de chaque mois ;
# ce script recharge la base depuis les fichiers les plus recents, verifie
# le resultat, et ne remet l'application en service que si la base est
# conforme.
#
# Le point critique : load_rpps.py commence par un DELETE global de la table
# neurologues. L'executer avec l'API en ligne exposerait une base a moitie
# vide. L'API est donc arretee pendant le chargement, et le chargement
# s'execute dans un conteneur jetable qui monte les memes volumes que le
# service (base de donnees + cache des fichiers telecharges).
#
# Usage :
#   bash scripts/monthly_update.sh              # mise a jour
#   bash scripts/monthly_update.sh --verify     # verifie la base, ne touche a rien
#   bash scripts/monthly_update.sh --force      # ignore le verrou de concurrence
#
# Cron (le 6 de chaque mois a 2h, voir scripts/cron_monthly) :
#   0 2 6 * * cd /chemin/vers/rpps-neuro-app && bash scripts/monthly_update.sh >> logs/monthly_update.log 2>&1
#
set -Eeuo pipefail

cd "$(dirname "$0")/.."
PROJECT_DIR="$(pwd)"
COMPOSE="${COMPOSE:-docker compose}"
DATA_DIR="${RPPS_DATA_DIR:-C:\\Users\\neuro\\AppData\\Local\\rpps-neuro\\data}"
LOCK_FILE="${TMPDIR:-/tmp}/rpps-monthly-update.lock"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/monthly_update.log"
MIN_ROWS="${MIN_ROWS:-3000}"
MAX_ROWS="${MAX_ROWS:-5000}"

FORCE=0
VERIFY_ONLY=0
for arg in "$@"; do
    case "$arg" in
        --verify)  VERIFY_ONLY=1 ;;
        --force)   FORCE=1 ;;
        -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
        *) echo "Option inconnue: $arg" >&2; exit 2 ;;
    esac
done

log()  { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
fail() { log "ECHEC: $*" >&2; exit 1; }

mkdir -p "$LOG_DIR"
exec >>"$LOG_FILE" 2>&1
log "=============================================================="
log "Mise a jour mensuelle RPPS - debut"

# ---------------------------------------------------------------- garde-fou
# Un seul run a la fois : deux chargements concurrents sur la meme base
# SQLite donneraient un resultat indetermine.
if [ "$FORCE" -eq 0 ]; then
    if ! mkdir "$LOCK_FILE" 2>/dev/null; then
        fail "une mise a jour est deja en cours (verrou: $LOCK_FILE). Utiliser --force pour passer outre."
    fi
    trap 'rmdir "$LOCK_FILE" 2>/dev/null || true' EXIT
fi

command -v docker >/dev/null 2>&1 || fail "docker introuvable"
docker info >/dev/null 2>&1 || fail "le demon Docker ne repond pas"

# L'image doit correspondre au code du depot : sinon le chargement utilise
# un load_rpps.py / verify_load.py obsolete (le script de verification n'a
# pas existe dans les images construites avant le 15/11/2026).
log "Construction de l'image API..."
$COMPOSE build api >/dev/null || fail "construction de l'image API impossible"

# Le chemin de donnees doit etre visible du daemon : un bind-mount sur un
# disque non partage par Docker Desktop remonte un volume VIDE (perte de
# donnees au 15/11/2026). On verifie avant de toucher a quoi que ce soit.
log "Verification du montage des donnees (marqueur)..."
MARKER_NAME=".mount_check_$$"
MARKER="$DATA_DIR/$MARKER_NAME"
if ! mkdir -p "$DATA_DIR" 2>/dev/null; then
    fail "repertoire de donnees inaccessible: $DATA_DIR"
fi
echo "probe" > "$MARKER" 2>/dev/null || fail "ecriture impossible dans $DATA_DIR"
# Le nom du marqueur passe par l'environnement : un $$ developpe dans le
# sh du conteneur donnerait le PID du conteneur, pas celui de l'hote.
if ! $COMPOSE run --rm --no-deps -T -e MARKER_NAME="$MARKER_NAME" api sh -c \
        'test -f "/app/data/$MARKER_NAME" && echo OK' 2>/dev/null | grep -q OK; then
    rm -f "$MARKER"
    fail "le montage /app/data ne voit pas l'hote ($DATA_DIR). Docker Desktop partage-t-il ce disque ?"
fi
rm -f "$MARKER"
log "Montage des donnees : OK"

# --------------------------------------------------------------- verif seule
if [ "$VERIFY_ONLY" -eq 1 ]; then
    log "Mode verification seule."
    $COMPOSE run --rm --no-deps -T api python scripts/verify_load.py \
        --db /app/data/neurologues.db --min-rows "$MIN_ROWS" --max-rows "$MAX_ROWS"
    log "Base conforme."
    exit 0
fi

# --------------------------------------------------------------- sauvegarde
BACKUP="/app/data/neurologues.db.bak-$(date +%Y%m%d-%H%M%S)"
log "Sauvegarde de la base courante -> $(basename "$BACKUP")"
$COMPOSE run --rm --no-deps -T -e BACKUP="$BACKUP" api sh -c '
    set -e
    if [ -f /app/data/neurologues.db ]; then
        cp /app/data/neurologues.db "$BACKUP"
        echo "Sauvegarde creee: $BACKUP ($(stat -c %s "$BACKUP") octets)"
    else
        echo "Pas de base existante, aucun backup (premier chargement ?)"
    fi
' || fail "sauvegarde impossible"

# --------------------------------------------------- arret de l'API + load
# L'API est arretee : elle ne doit pas servir une base en cours de recharge.
log "Arret de l'API..."
$COMPOSE stop api >/dev/null 2>&1 || true

restore_on_error() {
    log "Echec du chargement : restauration de la sauvegarde."
    $COMPOSE run --rm --no-deps -T api sh -c "
        set -e
        ls -t /app/data/neurologues.db.bak-* 2>/dev/null | head -1 | while read b; do
            cp \"\$b\" /app/data/neurologues.db
            echo \"Base restauree depuis \$b\"
            break
        done
    " || log "AVERTISSEMENT: restauration impossible, intervention manuelle requise."
    $COMPOSE up -d api >/dev/null 2>&1 || true
}

log "Chargement des donnees RPPS (conteneur jetable, cache persistant)..."
if ! $COMPOSE run --rm --no-deps -T api python scripts/load_rpps.py; then
    restore_on_error
    fail "le chargement RPPS a echoue"
fi

# ------------------------------------------------------------ verification
log "Verification de la base chargee..."
if ! $COMPOSE run --rm --no-deps -T api python scripts/verify_load.py \
        --db /app/data/neurologues.db --min-rows "$MIN_ROWS" --max-rows "$MAX_ROWS"; then
    restore_on_error
    fail "la base chargee ne passe pas la verification, sauvegarde restauree"
fi

# ------------------------------------------------- remise en service + purge
log "Correction eventuelle des regions (mapping officiel)..."
$COMPOSE run --rm --no-deps -T api python scripts/fix_regions.py \
    --db /app/data/neurologues.db || log "AVERTISSEMENT: fix_regions.py a echoue"

log "Redemarrage de l'application..."
$COMPOSE up -d >/dev/null 2>&1 || fail "redemarrage de l'application impossible"

# Le conteneur API doit repondre avant de consideraer la mise a jour finie.
log "Attente de la reponse de l'API..."
for i in $(seq 1 30); do
    if curl -fsS -m 5 http://127.0.0.1:50000/api/stats >/dev/null 2>&1; then
        log "API repondante apres ${i}s."
        break
    fi
    sleep 1
done
curl -fsS -m 5 http://127.0.0.1:50000/api/stats >/dev/null 2>&1 \
    || fail "l'API ne repond pas apres le redemarrage"

# Purge des sauvegardes anciennes (on en garde 3).
log "Purge des sauvegardes anciennes (3 conserves)..."
$COMPOSE run --rm --no-deps -T api sh -c "
    ls -t /app/data/neurologues.db.bak-* 2>/dev/null | tail -n +4 | while read f; do
        rm -f \"\$f\" && echo \"Supprime: \$f\"
    done
" || true

log "Mise a jour mensuelle terminee avec succes."
log "=============================================================="
