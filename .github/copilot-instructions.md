# JobHunt — instructions d'ingénierie

S'applique à **tout agent ou humain** qui écrit du code dans ce dépôt.

## Langage & conventions
- Python 3.11+ uniquement. Pas de dépendance nouvelle sans justification dans la PR.
- Une fonction = une responsabilité. Docstring courte sur les fonctions publiques.
- Libellés métier en français, code en anglais.

## Tests — non négociable
- **TNR avant CHAQUE commit** : `bash tests/run_tests.sh`
- **Un bug corrigé = un test de non-régression** (marqueur `regression`).
- Jamais de code non testé poussé.
- Un scénario = une assertion conceptuelle.

## Isolation
- Fixture `test_db` (SQLite `:memory:`) ou `test_db_path` (`tmp_path`) — **jamais** la base de prod.
- Chaque test nettoie ce qu'il crée. Aucun état partagé entre tests.

## Données de test
- Passer par `tests/data/factories.py`. Pas de JSON recopié à la main dans les tests.
- Aucune donnée personnelle dans `tests/fixtures/`.

## Locators (UI)
- Ordre de préférence : `get_by_role` > `get_by_label` > `data-testid` > CSS. **XPath interdit** si évitable.
- Page Objects obligatoires dans `tests/playwright/pages/`.

## API
- Valider le **statut ET le schéma** (`tests/api/schemas/`).
- Toujours couvrir le cas négatif (401 / 404 / 422).

## Anti-flaky
- Un test instable part en **quarantaine** (`tests/quarantine.json`) — jamais désactivé en silence.
- `--reruns` autorisé en CI seulement, jamais pour masquer un bug.

## Definition of Done
TNR vert · test de régression si bug · aucun secret · lien du commit (ou lien live) dans le compte-rendu.
