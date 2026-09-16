# Journal TDD — filtre budget minimum (TJM)

Sorties console réelles, capturées aux moments indiqués. Aucune n'a été réécrite.

## 1. Étape rouge — le test écrit avant le code

Commande : `python3 -m pytest tests/test_budget_filter.py -q`

```
ImportError: cannot import name 'filtrer_par_budget' from 'matcher'
ERROR tests/test_budget_filter.py
!!! Interrupted: 1 error during collection !!!
```

12 tests écrits, 0 ligne de code de production : la suite échoue à la collecte, exactement
comme attendu en TDD. La règle métier est figée avant l'implémentation (borne inclusive,
offre sans budget écartée, ordre d'entrée conservé).

## 2. Étape verte — le minimum de code qui satisfait les tests

Commande : `python3 -m pytest tests/test_budget_filter.py -q`

```
collected 12 items

tests/test_budget_filter.py ............                                 [100%]

============================== 12 passed in 0.02s ==============================
```

## 3. Passe d'intégration — le branchement révèle un défaut plus grave

Commandes : ajout du paramètre `budget_min` à `/api/jobs`, puis
`python3 -m pytest tests/test_budget_filter.py -q`

```
E   assert 404 == 200
E    +  where 404 = <WrapperTestResponse streamed [404 NOT FOUND]>.status_code
FAILED tests/test_budget_filter.py::TestFiltreBudget::test_api_accepte_le_parametre_budget
======================== 1 failed, 14 passed in 10.84s =========================
```

Le test d'intégration échoue : `/api/jobs` répond 404. La cause n'est pas la nouvelle
fonctionnalité — la fonction `api_jobs` existe mais son décorateur `@app.route` a disparu.
C'est l'anomalie **AN-101**.

## 4. Après correction du décorateur

Commandes : `@app.route("/api/jobs")` rétabli, puis
`python3 -m pytest tests/test_budget_filter.py tests/test_api_routes.py -q`

```
tests/test_budget_filter.py ...............                              [ 71%]
tests/test_api_routes.py ......                                          [100%]

============================= 21 passed in 11.72s ==============================
```

Effet mesuré sur la suite existante : les 5 scénarios BDD qui consomment cet endpoint
passent de nouveau.

## 5. End-to-end — navigateur réel (Playwright / Chromium)

Commande : serveur de test local `127.0.0.1:5099`, puis
`JOBHUNT_URL=http://127.0.0.1:5099 python3 -m pytest tests/playwright/test_dashboard.py -q`

```
======================= 10 passed, 10 warnings in 22.67s =======================
```

Les 9 scénarios historiques s'exécutent enfin (la dépendance `pytest-playwright` manquait
alors que les scénarios utilisaient la fixture `page` : anomalie **AN-102**), plus le
nouveau scénario du filtre budget. Le serveur de test est démarré et arrêté dans la même
commande : aucune exposition, aucun service laissé en marche.

## 6. Couverture mesurée

Commande : `python3 -m pytest tests -q --ignore=tests/playwright --cov=matcher
--cov=virtual_delivery --cov=app --cov-report=term`

```
Name                  Stmts   Miss  Cover
-----------------------------------------
app.py                 1276    812    36%
matcher.py              187     37    80%
virtual_delivery.py     126      8    94%
-----------------------------------------
TOTAL                  1589    857    46%
================== 26 failed, 153 passed, 6 skipped in 16.04s ===================
```

Lecture honnête : `matcher.py` et `virtual_delivery.py` sont bien couverts ; `app.py`
(1 276 instructions, application Flask monolithique) reste à 36 % — c'est le chantier
suivant, écrit noir sur blanc plutôt que masqué. Les 26 échecs restants appartiennent à
des scénarios BDD dont les définitions d'étapes ne sont pas enregistrées (dette de test
antérieure, aucun nouvel échec introduit).

## 7. Bilan de non-régression

Référence (avant intervention) : 34 échecs, 102 tests passants.
Après : 26 échecs, 153 tests passants, **0 nouvel échec**, 8 échecs résolus.
