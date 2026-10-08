#!/usr/bin/env bash
# =============================================================================
# TNR JobHunt — tests de non-régression complets, en une seule commande.
#
# Étages :
#   1. Cœur       : unitaires + API + contrats + BDD backend  (hors ligne)
#   2. E2E        : parcours navigateur Playwright (@regression, serveur dédié)
#   3. BDD front  : scénarios Gherkin pilotant Chromium (@frontend)
#   4. Fumée      : uniquement avec --with-smoke (cible JOBHUNT_BASE_URL)
#
# Usage :
#   bash tests/run_tnr.sh
#   JOBHUNT_BASE_URL=http://127.0.0.1:5050 bash tests/run_tnr.sh --with-smoke
#
# S'arrête au premier étage en échec et affiche le récapitulatif des étages verts.
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

WITH_SMOKE=false
for arg in "$@"; do
  case "$arg" in
    --with-smoke) WITH_SMOKE=true ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    *) echo "option inconnue : $arg (voir --help)" >&2; exit 2 ;;
  esac
done

# Interpréteur : venv local, puis python3, puis python.
if [[ -x "$PROJECT_DIR/.venv/bin/python" ]]; then
  PY="$PROJECT_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  PY="$(command -v python)"
else
  echo "✖ Aucun interpréteur Python trouvé." >&2
  exit 127
fi

PASSED_STAGES=()

run_stage() {
  local label="$1"; shift
  echo ""
  echo "──────────────────────────────────────────────────────────────"
  echo "▶ $label"
  echo "──────────────────────────────────────────────────────────────"
  if "$@"; then
    PASSED_STAGES+=("$label")
  else
    local code=$?
    echo ""
    echo "✖ ÉCHEC : $label (code $code)"
    echo "  TNR interrompue — corrige, puis relance la commande complète."
    exit "$code"
  fi
}

echo "════════════════════════════════════════════════════════════════"
echo " TNR JobHunt — non-régression complète"
echo " Interpréteur : $PY"
echo "════════════════════════════════════════════════════════════════"

run_stage "Étage 1/4 — Cœur (unitaires · API · contrats · BDD backend)" \
  "$PY" -m pytest tests/ --ignore=tests/playwright -m "not frontend" -q

run_stage "Étage 2/4 — E2E navigateur (Playwright @regression)" \
  "$PY" -m pytest tests/playwright -m regression -q

run_stage "Étage 3/4 — BDD navigateur (Gherkin @frontend)" \
  "$PY" -m pytest tests/test_scenarios.py -m frontend -q

if $WITH_SMOKE; then
  if [[ -z "${JOBHUNT_BASE_URL:-}" ]]; then
    echo "✖ --with-smoke exige la variable JOBHUNT_BASE_URL" >&2
    exit 2
  fi
  run_stage "Étage 4/4 — Fumée (@smoke sur $JOBHUNT_BASE_URL)" \
    "$PY" -m pytest tests/playwright/specs/smoke -m smoke -q
else
  echo ""
  echo "──────────────────────────────────────────────────────────────"
  echo "⏭  Étage 4/4 — Fumée ignorée (ajoute --with-smoke + JOBHUNT_BASE_URL)"
  echo "──────────────────────────────────────────────────────────────"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo " ✅ TNR VERTE — ${#PASSED_STAGES[@]} étage(s) validé(s)"
for stage in ${PASSED_STAGES[@]+"${PASSED_STAGES[@]}"}; do
  echo "    · $stage"
done
echo "════════════════════════════════════════════════════════════════"
