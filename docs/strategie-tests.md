# Plan de stratégie de tests — JobHunt

| Élément | Valeur |
|---|---|
| Objet | Dashboard JobHunt (Flask + SQLite + scraping + enrichissement IA) |
| Référentiels | ISTQB CTFL 4.0 (processus, techniques, niveaux) · ISTQB CT-GenAI v1.1 (usage de l'IA en test) · Playwright Best Practices (POM, isolation, parallélisation) |
| Documents liés | [playwright-test-strategy.md](./playwright-test-strategy.md) (volet CT-GenAI) · [catalogue-cas-tests.md](./catalogue-cas-tests.md) · [tests/playwright/README.md](../tests/playwright/README.md) |
| Version | 1.0 |
| Statut | En vigueur |

---

## 1. Objet et objectifs

Ce plan définit **comment** JobHunt est testé : ce qu'on teste, à quel niveau, avec
quelle technique de conception, dans quel ordre de priorité, et **comment toute
nouvelle fonctionnalité ou correction de bug entre immédiatement dans une
non-régression complète (TNR)**.

Objectifs mesurables :

1. **Filet de sécurité** : toute régression fonctionnelle sur un parcours utilisateur
   ou un contrat d'API est détectée automatiquement avant merge.
2. **Une commande** : `bash tests/run_tnr.sh` exécute la TNR complète, hors ligne,
   sans service externe.
3. **Traçabilité** : chaque cas de test porte un identifiant relié à un module et à
   une priorité de risque ([catalogue-cas-tests.md](./catalogue-cas-tests.md)).
4. **Reproductibilité** : aucun test ne dépend de la base de production, d'un service
   tiers, d'un secret ou de l'ordre d'exécution.

---

## 2. Périmètre

### 2.1 Dans le périmètre

- Dashboard utilisateur : chargement, recherche, facettes, onglets pays, pagination,
  cartes d'offres, thème, responsive, Kanban des candidatures.
- Authentification et session (`/login`, `/api/auth/*`).
- Contrats d'API internes (`/api/jobs`, `/api/stats`, `/api/jobs/*`, `/api/profile`,
  `/api/monitor/*`, `/qa/api/*`).
- Chaîne de collecte et de filtrage : scrapers, filtre QA, déduplication, budget,
  fraîcheur, matching CV, enrichissement.
- Persistance des offres clôturées (`dismissed_jobs`, `/jobclotured`).
- Pages de contenu et vitrines (`/about`, `/changelog`, `/marche-qa`, `/poc-*`).

### 2.2 Hors périmètre

- Performance de charge et montée en charge (aucun test de stress dans cette version).
- Compatibilité multi-navigateurs (cible : Chromium ; Firefox/WebKit non couverts).
- Sécurité offensive (pentest) — seuls des contrôles de base sont prévus (§5.2).
- Tests sur données de production.
- Accessibilité avancée (RGAA/WCAG complet) — seuls des cheminements clavier de base.

### 2.3 Hypothèses et dépendances

- Le serveur E2E déterministe (`tests/playwright/conftest.py::live_server`) démarre
  l'application sur un port libre avec une base SQLite temporaire.
- Les fournisseurs externes (Supabase, DeepSeek, GitHub, WhatsApp, scrapers) sont
  **stubbés ou isolés** : jamais appelés réellement depuis la suite de tests.
- Python ≥ 3.11, Chromium installé (`python -m playwright install chromium`).

---

## 3. Cartographie des modules et criticité

Criticité = probabilité de défaillance × impact utilisateur (voir §7).

| # | Module | Point d'entrée | Comportement couvert | Criticité | Priorité |
|---|---|---|---|---|---|
| M1 | Authentification | `/login`, `/api/auth/{signup,login,logout,me}` | rendu, validation HTML5, bascule inscription, erreurs (401/500/réseau), redirection | Élevée | **P1** |
| M2 | Dashboard | `/` | stats hero, sections, état prêt, compteur | Élevée | **P1** |
| M3 | Recherche & facettes | JS client (`#jobSearch`, `.facet-group`) | filtrage temps réel, insensibilité casse, combinaisons, reset | Élevée | **P1** |
| M4 | Onglets pays | JS client (`.country-btn`) | activation d'un panneau unique, états vides, « Tous », LinkedIn | Moyenne | **P1** |
| M5 | Kanban candidatures | `#kanban-view`, `POST /api/job/<id>/stage` | colonnes par stade, déplacement, persistance serveur, fermeture clavier | Élevée | **P1** |
| M6 | Cartes d'offres & pagination | `.job-card`, `.pagination` | champs affichés, lien Apply sûr, 3 cartes/page | Moyenne | **P2** |
| M7 | Thème & responsive | `#theme-btn`, `#sidebar` | persistance clair/sombre, barre basse mobile, colonne unique | Faible | **P2** |
| M8 | API offres & stats | `/api/jobs`, `/api/stats`, `/api/stats/advanced` | filtres `qa/unapplied/search/source/budget_min`, agrégats | Élevée | **P1** |
| M9 | Actions sur une offre | `/api/jobs/<id>/{save,apply,notes,pipeline}`, `/api/job/<id>/{click,stage}` | transitions d'état, codes 404 | Moyenne | **P2** |
| M10 | Persistance « clôturés » | `/jobclotured`, `dismissed_jobs` | liste, dédoublonnage par utilisateur, filtre du dashboard | Moyenne | **P2** |
| M11 | Lettre de motivation | `/cover-letter/<id>`, `/api/generate-cover/<id>, /api/apply/<id>` | génération, 404 | Faible | **P2** |
| M12 | Enrichissement IA | `/api/jobs/enrich/<id>` | 403 si non autorisé, 400 description courte, 404 | Moyenne | **P2** |
| M13 | Scraping | `scraper.py`, `/refresh`, `/api/refresh`, `/api/linkedin/*` | parsing 5 sources, filtre QA, dédup, robustesse réseau | Élevée | **P1** |
| M14 | Filtrage & matching | `matcher.py` (`filtrer_par_budget`, `match_job_to_cv`, `analyze_tjm`, `detect_duplicates`, `analyze_skills_gap`) | règles métier, bornes, normalisation | Élevée | **P1** |
| M15 | Profil | `/api/profile`, `/api/profile/avatar`, `/settings` | 401 négatif, validation des champs | Moyenne | **P2** |
| M16 | Monitoring | `/monitoring`, `/api/monitor/*` | ajout/suppression de site, URL invalide, sondes | Faible | **P3** |
| M17 | Cockpit QA | `/qa`, `/qa/api/*`, `/api/github/*` | inventaire, déclenchement, absence de token | Faible | **P3** |
| M18 | Pages vitrines / POC | `/about`, `/changelog`, `/marche-qa`, `/cycle-de-vie`, `/poc-*` | rendu 200, contenu clé | Faible | **P3** |

---

## 4. Approche de test

### 4.1 Niveaux (pyramide)

| Niveau | Outil | Cible | Exemples |
|---|---|---|---|
| **Unitaire / composant** | pytest | fonctions métier pures (`matcher.py`, parsing scrapers, helpers) | filtre budget, dédup, parsing salaire |
| **Intégration / API** | pytest + client Flask | contrats HTTP et schémas JSON (`tests/api/schemas/`) | `/api/jobs` filtres, 401/404/422 |
| **E2E / UI** | Playwright (Chromium) | parcours utilisateur réels | login, recherche, Kanban |
| **BDD / acceptation** | pytest-bdd (Gherkin FR) | scénarios métier lisibles par le PO | `tests/features/**` |

Le niveau **E2E est volontairement mince** : peu de tests, critiques, isolés. Un
scénario E2E coûte cher à maintenir ; il n'est justifié que pour un parcours que
l'utilisateur traverse réellement.

### 4.2 Types de tests

| Type | Objectif | Où |
|---|---|---|
| Fonctionnel | le comportement attendu est observé | tous niveaux |
| Négatif | les entrées invalides sont refusées proprement | API + UI (401/404/422, erreurs formulaire) |
| Limites (BVA) | comportement aux bornes | budget (`>= 500`), `minlength=6`, pagination |
| Partition d'équivalence | une classe d'entrée = un comportement | recherche (casse), email (valide/invalide/vide) |
| Transition d'état | enchaînements légitimes/interdits | pipeline Kanban, applied/dismissed |
| Régression | rien n'a cassé | TNR (§8) |
| Contrat | le schéma de réponse ne change pas | `tests/api/contracts.py` |
| Accessibilité de base | cheminement clavier | Échap ferme le Kanban |
| Responsive | l'UI tient sur mobile | `test_mobile.py` |
| Sécurité de base | pas de fuite évidente | lien Apply `rel=noopener`, XPath interdit, pas de secret en dur |

### 4.3 Ce qui n'est pas un test

Un test qui n'assertionne rien, un test qui dort (`sleep`, `wait_for_timeout`), un
test qui dépend d'un autre test, ou un test désactivé en silence. Ces pratiques sont
proscrites par [tests/playwright/README.md](../tests/playwright/README.md).

---

## 5. Conception des tests (techniques ISTQB)

### 5.1 Technique par type de module

| Technique | Application JobHunt |
|---|---|
| **Partition d'équivalence** | Email : vide / mal formé / valide. Mot de passe : `< 6` / `>= 6`. Recherche : correspondance / aucune correspondance / casse différente. |
| **Analyse des valeurs limites** | Budget min `499 / 500 / 501`. Longueur mot de passe `5 / 6 / 7`. Pagination : 3 offres par page, borne `total = 3k`, `3k+1`. |
| **Table de décision** | Facettes : `séniorité ∈ {all, senior, mid, junior}` × `contrat ∈ {all, freelance, cdi}` → ensemble d'offres attendu. |
| **Transition d'état** | Kanban : `new → applied → interview → offer`, `→ rejected`. Dismissible uniquement sur `new`. |
| **Cas d'utilisation** | Parcours « trouver puis postuler » : recherche → facette → carte → Apply → retour. |
| **Invariants** | `/poc-ct-ai/api/score` : le score ne doit pas changer selon la casse, les accents ou les espaces (contrôle d'invariance). |

### 5.2 Règles de conception UI (Playwright)

1. **Page Objects obligatoires** (`tests/playwright/pages/`) : interactions et lectures
   seulement, **jamais** d'assertion.
2. **Locators** dans l'ordre : `get_by_role` > `get_by_label` > `get_by_placeholder` >
   texte > `data-testid` > CSS. **XPath interdit.**
3. **Zéro attente arbitraire** : on attend une condition observable
   (`expect` web-first, `wait_for_url`, `wait_for_function`).
4. **Isolation totale** : chaque test prépare son état ; la base est réamorcée par la
   fixture `seeded` ; aucun état partagé, aucun couplage d'ordre.
5. **Vert en `-n 1` et en `-n 4`** : la parallélisation ne doit jamais introduire de
   flakiness.

### 5.3 Cas de test — formalisme

Chaque cas du [catalogue](./catalogue-cas-tests.md) porte : `ID`, module, titre,
priorité, technique, préconditions, étapes, résultat attendu, spec Playwright cible,
statut (`✅ implémenté` / `⏳ à faire`).

Convention d'identifiant : `TC-<MODULE>-<NNN>` — ex. `TC-AUTH-004`.

---

## 6. Données de test

- **Source unique** : `tests/playwright/fixtures/e2e_data.py` (jeu canonique déterministe).
  Aucune donnée recopiée à la main dans les specs.
- **Factories** : `tests/data/factories.py` pour les tests Python.
- **Aucune donnée personnelle** dans `tests/fixtures/`.
- **Base** : SQLite `:memory:` (`test_db`) ou fichier temporaire (`test_db_path`).
  **Jamais** la base de production.
- **Isolation** : chaque test E2E réamorce la base ; chaque test unitaire nettoie
  ce qu'il crée.

Jeu E2E de référence (`e2e_data.py`) : 18 offres d'affichage (dont 3 « récentes »,
6 contenant « Cypress », 8 senior, 9 freelance, 5 senior ET freelance) + 5
candidatures hors périmètre pays, une par stade du Kanban.

---

## 7. Analyse de risque et priorisation

Priorité attribuée selon **probabilité de défaillance × impact** :

| Risque | Probabilité | Impact | Criticité | Tests dédiés |
|---|---|---|---|---|
| Régression sur un parcours d'entrée (login) | Moyenne | Élevé | **P1** | `test_login.py` |
| Filtrage/recherche renvoyant un mauvais lot | Moyenne | Élevé | **P1** | `test_search.py`, `test_facets.py` |
| Perte d'une candidature (Kanban non persisté) | Faible | Élevé | **P1** | `test_kanban.py` |
| Rupture de contrat d'API | Moyenne | Élevé | **P1** | `test_api_routes.py`, `test_contracts_schema.py` |
| Règle métier de filtrage QA/budget erronée | Moyenne | Moyen | **P1** | `test_budget_filter.py`, features `filtering/` |
| Scraper cassé par un changement de source | Élevée | Moyen | **P1** | features `scraping/`, tests scrapers |
| Onglet pays incohérent | Faible | Moyen | **P2** | `test_country_tabs.py` |
| Enrichissement IA indisponible | Moyenne | Faible | **P2** | `test_enrich_preserve.py` |
| Monitoring en erreur | Faible | Faible | **P3** | à compléter |

---

## 8. Critères d'entrée / sortie

| Jalon | Critère |
|---|---|
| **Entrée** | code compilable, `requirements*.txt` à jour, branche à jour sur `main`, CI verte |
| **Sortie (Definition of Done)** | TNR verte (`bash tests/run_tnr.sh`), un test de régression ajouté si bug, aucun secret, lien du commit dans le compte-rendu |
| **Suspension** | environnement E2E non démarrable (port, Chromium), ou flakiness > 5 % sur une suite |
| **Reprise** | cause identifiée, test concerné mis en quarantaine si instable, suite re-verte |

---

## 9. TNR — stratégie de non-régression

### 9.1 Définition

La **TNR** (tests de non-régression) est l'ensemble automatisé rejoué à chaque
changement pour garantir qu'une modification n'a rien cassé d'existant. Elle est
**complète par construction** : tout nouveau cas de test rejoint une suite existante
et est donc mécaniquement inclus dans les exécutions suivantes.

### 9.2 Composition

| Étage | Commande | Contenu | Durée cible |
|---|---|---|---|
| 1 — Cœur | `pytest tests/ --ignore=tests/playwright -m "not frontend"` | unitaires, API, contrats, BDD backend | < 30 s |
| 2 — E2E | `pytest tests/playwright -m regression` | parcours navigateur sur serveur déterministe | < 60 s |
| 3 — BDD navigateur | `pytest tests/test_scenarios.py -m frontend` | scénarios Gherkin pilotant Chromium | < 90 s |
| 4 — Fumée *(si `JOBHUNT_BASE_URL`)* | `pytest tests/playwright/specs/smoke -m smoke` | parcours minimal sur l'app cible | < 20 s |

### 9.3 Déclencheurs

- **À chaque commit/PR** (CI) : étages 1 à 3.
- **Avant une mise en production** : étages 1 à 4 (fumée sur l'environnement cible).
- **À la correction d'un bug** : ajout obligatoire d'un cas de test marqué `regression`
  **avant** la correction (le test doit échouer puis passer).

### 9.4 Sélection

Priorité à une **sélection basée sur le risque et l'impact** : un changement sur un
module critique (M1–M5, M8, M13, M14) déclenche la TNR complète ; un changement
purement cosmétique peut se limiter aux étages 1 et 2. En cas de doute : TNR complète.

### 9.5 Workflow « un bug = un test »

```
Bug détecté
   │
   ├─ Écrire un test qui reproduit le bug (marqueur "regression")
   │     → le test doit ÉCHOUER (preuve du bug)
   │
   ├─ Corriger le bug
   │     → le test doit PASSER
   │
   ├─ Nommer le test d'après le bug (ex. bug-D1, bug-S1) et l'ajouter à la TNR
   │
   └─ Lancer la TNR complète : bash tests/run_tnr.sh
```

### 9.6 Couverture de la TNR

- **P1 obligatoire** : intégralement couvert (modules M1–M5, M8, M13, M14).
- **P2** : intégralement couvert (M6–M12, M15).
- **P3** : couvert par des fumées de disponibilité et le contrat des API (M16–M18).

État détaillé, identifiants et défauts constatés : [catalogue-cas-tests.md](./catalogue-cas-tests.md).


---

## 10. Intégration continue

Pipeline `.github/workflows/ci.yml` :

| Job | Contenu |
|---|---|
| `test` | étage 1 + couverture, sur Python 3.11 et 3.12 |
| `ui-smoke` | étage 2 (Playwright `@regression`), étage 3 (BDD `@frontend`) et fumée `@smoke` contre l'app démarrée localement |

Évolutions prévues : ajouter un job `tnr` unique appelant `tests/run_tnr.sh` pour
garantir la parité entre le poste de développement et la CI.

---

## 11. Gestion des tests instables

- Un test instable part en **quarantaine** : entrée dans `tests/quarantine.json` avec
  un ticket et un propriétaire. Il est **ignoré par défaut** et **réactivé**
  uniquement avec `--run-quarantine`.
- **Jamais** de `skip` pour faire passer une suite.
- `--reruns` autorisé **en CI seulement**, jamais pour masquer un bug local.
- Seuil d'alerte : > 5 % d'exécutions instables sur une suite.

---

## 12. Rôles et responsabilités

| Rôle | Responsabilité |
|---|---|
| Développeur | écrit le test de non-régression du bug corrigé, garde la TNR verte |
| QA | conçoit les cas (ce catalogue), instrumente les suites, arbitre les priorités |
| DevOps | maintient la CI, l'hébergement des rapports, les environnements |
| PO | valide les scénarios BDD et les critères d'acceptation |

---

## 13. Métriques et reporting

| Métrique | Cible | Source |
|---|---|---|
| Taux de réussite TNR | 100 % avant merge | sortie pytest / CI |
| Couverture des exigences P1 | 100 % | matrice de traçabilité (§14) |
| Couverture de code | ≥ 70 % sur `app.py`, `matcher.py`, `scraper.py` | `pytest --cov` |
| Nombre de tests de régression ajoutés | ≥ 1 par bug corrigé | historique git |
| Flakiness | < 5 % | statut des relances CI |
| Durée TNR | < 3 min (étages 1–3) | CI |

---

## 14. Matrice de traçabilité (extrait)

| Module | Exigence | Cas de test | Spec Playwright |
|---|---|---|---|
| M1 | Se connecter avec des identifiants valides | TC-AUTH-001…014 | `specs/regression/test_login.py` |
| M2 | Afficher les offres au chargement | TC-DASH-001…003 | `specs/regression/test_dashboard_load.py` |
| M3 | Filtrer la liste en temps réel | TC-SEARCH-001…004 | `specs/regression/test_search.py` |
| M4 | Naviguer entre marchés | TC-TABS-001…004 | `specs/regression/test_country_tabs.py` |
| M5 | Déplacer une candidature et la conserver | TC-KB-001…003 | `specs/regression/test_kanban.py` |

La matrice complète figure dans [catalogue-cas-tests.md](./catalogue-cas-tests.md).

---

## 15. Une commande pour la TNR

```bash
bash tests/run_tnr.sh          # étages 1 à 3, hors ligne
JOBHUNT_BASE_URL=http://127.0.0.1:5050 bash tests/run_tnr.sh --with-smoke
```

Le script s'arrête au premier étage en échec et affiche le récapitulatif de chaque
étage : c'est le point d'entrée unique de la non-régression.
