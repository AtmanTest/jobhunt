# Tests Playwright — JobHunt

Parcours navigateur du dashboard, sur un **Chromium réel**.
**Peu de tests, critiques, isolés, parallélisables.**

## Lancer

```bash
python -m playwright install chromium

# fumée : parcours minimal, à chaque PR
python -m pytest tests/playwright -m smoke

# régression : parcours utilisateur complets
python -m pytest tests/playwright -m regression

# tout, en parallèle
python -m pytest tests/playwright -n auto
```

La régression démarre **son propre serveur** Flask sur un port libre de `127.0.0.1`,
adossé à une base SQLite temporaire ensemencée de façon déterministe : rien à lancer
à la main, aucun état partagé entre tests.

La fumée cible l'URL fournie par `JOBHUNT_BASE_URL` (ou `config/environments.py`).
Aucun chemin ni port n'est codé en dur.

## Organisation

| Chemin | Rôle |
|---|---|
| `specs/smoke/` | `@smoke` — parcours minimal, à chaque PR |
| `specs/regression/` | `@regression` — chargement, recherche, facettes, thème, mobile, Kanban, carte, état vide |
| `test_dashboard.py` | 10 scénarios historiques du dashboard (filtre budget, stats, onglets pays, pagination, rejet, Apply) — étage `@regression` |
| `pages/` | Page Objects (interactions seules, **jamais d'assertion**) |
| `fixtures/` | jeu de données E2E déterministe (`e2e_data.py`) |
| `scenarios/` | **traçabilité** : le Gherkin français de `test_dashboard.py`, chaque scénario portant l'étiquette `@cas:<fonction de test>` |
| `run_all.py` | lanceur historique (utilise `run_scenario`) — équivalent de pytest, conservé pour la démo |

`run_scenario(nom)` exécute un scénario **hors pytest** en démarrant son propre
serveur : c'est ce qu'appelle le tableau de bord interne `/qa`.

## Règles

1. Locators centralisés dans les Page Objects : `get_by_role` > `get_by_label` >
   texte > `data-testid` > CSS. **XPath interdit.**
2. Aucune attente arbitraire : **jamais `wait_for_timeout`, jamais `sleep`**. On attend
   une condition observable (`expect`, `wait_for_selector`, `wait_for_function`).
3. Un test prépare son état par la fixture, jamais par un autre test.
4. Un test doit être vert en `-n 1` **et** en `-n 4`.
5. Test instable → `tests/quarantine.json` avec un ticket et un propriétaire.
   **Jamais de `skip` pour faire passer la suite.**
