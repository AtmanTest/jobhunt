# JobHunt — dashboard de veille d'offres QA

Dashboard Flask qui agrège des offres QA / test / SDET (CDI, freelance, remote), les score et
les présente par marché — France, Suisse, Luxembourg, Dubaï, Singapour — avec suivi de
candidature, statistiques, export statique et panneau QA.

**Ce dépôt ne contient aucune donnée personnelle.** L'identité utilisée dans les lettres de
motivation est fournie par variables d'environnement, la base locale et les exports JSON sont
ignorés par git, et les documents personnels ont été retirés.

## Fonctionnalités

- Scraping multi-sources : LinkedIn (API invitée), Google Jobs, Remotive, Arbeitnow, Adzuna, RSS
- Scoring des offres : matching compétences / titre / type de contrat, détection de doublons
- Clôture et rejet d'offres, suivi de candidature en kanban (À postuler → Entretien → Offre)
- Dashboard par pays, filtres remote / séniorité / contrat, recherche plein texte
- API JSON : `/api/jobs`, `/api/stats`, `/api/stats/advanced`, `/api/jobs/saved`
- Panneau QA : scénarios BDD (`tests/features/`), exécution des suites, résultats Playwright,
  déclenchement et lecture des workflows GitHub Actions
- Export statique dans `docs/` pour un hébergement statique

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Tout passe par l'environnement ; aucune valeur n'est stockée dans le dépôt.

| Variable | Rôle |
|---|---|
| `JOBHUNT_REPO` | dépôt GitHub utilisé pour la persistance des JSON (défaut : ce dépôt) |
| `JOBHUNT_BRANCH` | branche de persistance (défaut : `main`) |
| `JOBHUNT_APPLICANT_NAME` / `JOBHUNT_APPLICANT_TITLE` | signature des lettres de motivation |
| `JOBHUNT_INTRO_FR` / `JOBHUNT_INTRO_EN` / `JOBHUNT_AVAILABILITY_FR` | corps des lettres |
| `GITHUB_TOKEN` | écriture des JSON de persistance (patron `repo`) |
| `SUPABASE_URL` / `SUPABASE_KEY` | persistance optionnelle des offres rejetées |
| `DEEPSEEK_API_KEY` | enrichissement des offres par LLM |
| `FRANCE_TRAVAIL_CLIENT_ID` / `..._SECRET` / `..._ACCESS_TOKEN` | source France Travail |
| `PORT` | port d'écoute (défaut : 5050) |

## Lancement

```bash
python3 app.py            # http://localhost:5050
```

Scraping et export manuels :

```bash
python3 scraper.py                      # collecte les offres
python3 auto_update.py                  # collecte + export + commit des JSON
python3 -c "from scraper import export_static_json; export_static_json()"
```

## Tests

```bash
python3 -m pytest tests/ -q     # scénarios BDD + tests de régression
python3 pre_push_test.py        # garde-fou avant commit (lint + tests)
```

Les workflows `.github/workflows/ci.yml` et `qa-tests.yml` rejouent la suite en CI.

## Déploiement

`render.yaml` décrit un service web Python (build `pip install -r requirements.txt`,
start `gunicorn app:app`). Le dossier `docs/` peut être publié tel quel sur un hébergement
statique (GitHub Pages, Netlify…).

## Structure

```
app.py                routes Flask, API JSON, rendu des templates
scraper.py            sources d'offres, normalisation, filtrage, export
matcher.py            scoring offre ↔ profil (listes de compétences paramétrables)
auto_update.py        cycle collecte → export → persistance
supa.py               client Supabase optionnel
templates/            dashboard, stats, kanban, QA, monitoring, lettre de motivation
static/theme.css      feuille de style commune
tests/                scénarios BDD (features + step definitions) et tests de régression
docs/                 export statique
monitor-app/          mini-app de surveillance de disponibilité (séparée)
```
