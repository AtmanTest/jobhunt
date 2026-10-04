# Tests Playwright — JobHunt

Parcours UI du dashboard. **Peu de tests, critiques, isolés, parallélisables.**

## Lancer

```bash
python -m playwright install chromium

pytest tests/playwright/specs/smoke -m smoke            # fumée (PR)
pytest tests/playwright -n auto                          # tout, en parallèle
JOBHUNT_ENV=preview pytest tests/playwright               # autre environnement
JOBHUNT_BASE_URL=http://127.0.0.1:5050 pytest tests/playwright
```

L'URL de base vient de `config/environments.py` (surchargeable par `JOBHUNT_BASE_URL`).
Aucun chemin d'exécution n'est codé en dur.

## Organisation

| Dossier | Rôle |
|---|---|
| `specs/smoke/` | `@smoke` — parcours minimal, à chaque PR |
| `specs/dashboard/` | affichage, statistiques, top matches |
| `specs/filters/` | filtres, recherche, pays |
| `specs/kanban/` | pipeline |
| `pages/` | Page Objects (interactions, jamais d'assertion) |
| `fixtures/` | données de test (via `tests/data/factories.py`) |
| `auth/` | `storageState` par rôle — généré, **jamais commité** |

## Règles

1. Locators : `get_by_role` > `get_by_label` > texte > `data-testid` > CSS. **XPath interdit.**
2. Assertions : web-first (`expect(loc).to_be_visible()`). **Jamais `wait_for_timeout`.**
3. Un test crée ses données, les nettoie, et porte un identifiant unique.
4. Un test doit être vert en `--workers=1` **et** en `--workers=4`.
5. Test instable → `tests/quarantine.json` avec un ticket et un propriétaire.

`run_all.py` (ancien lanceur avec `PW_PYTHON` codé en dur) est **déprécié** : ne plus l'utiliser.
