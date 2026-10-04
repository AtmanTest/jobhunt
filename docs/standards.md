# Standards d'ingénierie — JobHunt

## Pyramide
1. **Contrats** (`tests/test_contracts_schema.py`) — forme des données, rapides, zéro dépendance
2. **API** (`tests/test_api_*.py`, `features/api/`) — statut + schéma + cas négatifs
3. **BDD métier** (`features/`) — règles de filtrage, déduplication, enrichissement
4. **UI** (`tests/playwright/`) — parcours critiques uniquement, jamais les micro-détails de style

## Règles
- Isolation : `test_db` / `test_db_path`, aucun état partagé, aucun accès à la prod
- Données : uniquement via `tests/data/factories.py`
- Locators : `get_by_role` > `get_by_label` > `data-testid` > CSS ; XPath proscrit
- Un bug corrigé = un test de non-régression (marqueur `regression`)
- Un test instable = quarantaine tracée (`tests/quarantine.json`), jamais supprimé en silence

## Exécution
| Objectif | Commande |
|---|---|
| TNR complet | `bash tests/run_tests.sh` |
| Rapide (sans UI ni intégration) | `pytest -m "not frontend and not e2e and not integration"` |
| Parallèle | `pytest -n auto` (groupes `xdist_group` par famille) |
| Contrats seuls | `pytest -m contract` |
| Réactiver la quarantaine | `pytest --run-quarantine` |

## Sécurité (non négociable)

- **Aucun service de développement sur `0.0.0.0`.** `app.run` écoute `127.0.0.1` ; l'exposition
  volontaire passe par `JOBHUNT_DEV_HOST` (jamais par défaut).
- **`debug=True` interdit par défaut** (le debugger Werkzeug permet l'exécution de code).
  Activation explicite seulement : `JOBHUNT_DEV_DEBUG=1`.
- Secrets hors dépôt, fichiers en `600`. Aucune clé dans un test, un prompt ou un log.
- Le `--bind 0.0.0.0` de `Procfile` / `render.yaml` est le **port du conteneur** chez l'hébergeur
  (le proxy de la plateforme route vers lui) : il ne s'agit pas d'une exposition réseau locale.

## Propriété
- Toute PR : `CODEOWNERS` → revue obligatoire
- Une règle de test modifiée = une ligne dans le CHANGELOG
