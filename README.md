# JobHunt — veille d'offres QA et chaîne d'agents pilotée par les tickets

[![CI](https://github.com/AtmanTest/jobhunt/actions/workflows/ci.yml/badge.svg)](https://github.com/AtmanTest/jobhunt/actions/workflows/ci.yml)

Dashboard Flask qui agrège des offres QA / test / SDET (CDI, freelance, remote), les score et les
présente par marché — France, Suisse, Luxembourg, Dubaï, Singapour — avec suivi de candidature,
statistiques, export statique et panneau QA.

Le dépôt porte aussi une **chaîne d'agents** qui transforme un ticket GitHub en pull request
testée : spécification écrite, plan, cas de test, code, CI, revue. Tout est versionné et
consultable — aucune boîte noire.

**Ce dépôt ne contient aucune donnée personnelle ni aucun secret.** L'identité utilisée dans les
lettres de motivation vient de variables d'environnement, la base locale et les exports JSON sont
ignorés par git, et le code lit ses clés depuis l'environnement.

## La chaîne d'agents — d'un ticket à une pull request

L'entrée est **toujours un ticket GitHub** rédigé avec un formulaire (bug, user story, tâche
technique). Jamais un prompt jetable : le ticket porte la demande, la pull request porte la preuve.

| Étape | Rôle | Lit | Écrit |
|---|---|---|---|
| 1 | **PO** (PSPO I & II) | le ticket | `specs/<n>/spec.md` — critères d'acceptation |
| 2 | **Spec Review** | la spec | un verdict GO / NO-GO — garde-fou avant d'engager du travail |
| 3 | **Architecte** | la spec | `specs/<n>/plan.md` — découpage et approche |
| 4 | **QA** (CTFL v4.0 + CT-GenAI) | spec + plan | les cas de test |
| 5 | **Dev** | plan, cas de test et **la liste des chemins** du dépôt | les fichiers de code |
| 6 | **CI** | le code poussé | un statut de vérification |
| 7 | **QA Review** | le résultat de la CI | un verdict et le rapport de livraison |

**Les agents ne se parlent pas : ils s'écrivent.** Chaque étape ne reçoit que l'artefact de
l'étape précédente — jamais l'historique complet. C'est ce qui maintient le coût d'un cycle à
quelques milliers de jetons au lieu de dizaines de milliers.

Le canal est le dépôt lui-même : artefacts versionnés dans `specs/`, étiquettes sur le ticket
(`agent:go` pour lancer, `agent:no-go` pour arrêter), rapport final en commentaire de pull request.

### Où voir ce que fait chaque agent

| Endroit | Ce qu'on y voit |
|---|---|
| **n8n → Executions** | le texte exact reçu et produit par chaque nœud : entrées et sorties |
| **`specs/<n>/`** | les artefacts, versionnés et comparables d'une version à l'autre |
| **La pull request** | le diff, le statut de la CI et le rapport de livraison |
| **LiteLLM → Logs / Usage** | jetons et coût par appel, séparés par clé (chaîne d'agents / agent en direct) |

## Tests — quatre étages, tous exécutés

| Étage | Volume | Où |
|---|---|---|
| Unitaires, API, contrats | inclus dans le job `test` | `tests/` |
| BDD métier (Gherkin) | scénarios de bout en bout sur base isolée | `tests/features/`, `tests/step_definitions/` |
| Parcours navigateur | Playwright, sans attente arbitraire | `tests/playwright/specs/` |
| Panneau QA intégré | inventaire réel : BDD + pytest + Playwright | `http://localhost:5050/qa` |

```bash
python3 -m pytest tests/ -q --ignore=tests/playwright
python3 -m playwright install chromium
python3 -m pytest tests/playwright -n 4
```

Règles tenues par la suite : **pas d'attente fixe** (`wait_for_timeout` interdit — on attend une
condition observable), **pas de base en mémoire** partagée entre le test et l'application, et
**chaque correction de bug arrive avec le test qui la couvre**.

### Ce que la CI vérifie, et qui ne se contourne pas

Trois contrôles sont **obligatoires** sur `main` :

- `Unitaires · API · contrats · BDD (3.11)` et `(3.12)`
- `Navigateur (Playwright · @smoke + BDD @frontend)`

Une pull request dont la CI est rouge **ne peut pas être fusionnée** — la règle est technique, pas
déclarative. C'est la réponse au vrai risque d'un projet de test : que la suite existe sur le
papier mais ne soit jamais exécutée avant la fusion.

## Économie de jetons — mesurée, pas estimée

Chaque appel passe par une passerelle auto-hébergée (LiteLLM) qui journalise les jetons et le coût
**par clé**, avec un plafond :

| Consommateur | Entrée | Sortie | Coût |
|---|---|---|---|
| Chaîne d'agents (clé plafonnée 5 $ / 30 j) | ~3 400 | ~2 700 | ~0,002 $ par cycle |
| Agent en direct (clé plafonnée 20 $ / 30 j) | 31 011 mesurés, ~24 000 après consolidation du contexte | quelques | ~0,005 $ par échange |

L'écart est instructif : un cycle complet de la chaîne coûte **moins** qu'un seul échange en
conversation, parce que la chaîne ne transporte que l'artefact utile là où un agent de dialogue
réinjecte son contexte, sa mémoire et ses outils à chaque tour. Détail de l'installation et
requêtes de contrôle : `docs/llm-gateway.md`.

## Référentiels

- **ISTQB CTFL v4.0** (techniques : analyse des valeurs limites, tables de décisions, transitions
  d'état) et **ISTQB CT-GenAI** pour la partie IA
- **PSPO I & II** pour le rôle de Product Owner
- Nommage des artefacts aligné sur les pratiques de spécification (`spec` / `plan` / `tasks`)
- Contrats de rôle dans `prompts/`, standard détaillé dans `docs/standard-multi-agents.md`,
  architecture visible dans `docs/architecture-agents.html`

## Installation et lancement

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py            # http://localhost:5050
```

## Configuration

Tout passe par l'environnement ; aucune valeur n'est stockée dans le dépôt.

| Variable | Rôle |
|---|---|
| `JOBHUNT_REPO` | dépôt GitHub utilisé pour la persistance des JSON (défaut : ce dépôt) |
| `JOBHUNT_BRANCH` | branche de persistance (défaut : `main`) |
| `JOBHUNT_APPLICANT_NAME` / `JOBHUNT_APPLICANT_TITLE` | signature des lettres de motivation |
| `JOBHUNT_INTRO_FR` / `JOBHUNT_INTRO_EN` / `JOBHUNT_AVAILABILITY_FR` | corps des lettres |
| `GITHUB_TOKEN` | écriture des JSON de persistance |
| `SUPABASE_URL` / `SUPABASE_KEY` | persistance optionnelle des offres rejetées |
| `DEEPSEEK_API_KEY` | enrichissement des offres par LLM |
| `FRANCE_TRAVAIL_CLIENT_ID` / `..._SECRET` / `..._ACCESS_TOKEN` | source France Travail |
| `PORT` | port d'écoute (défaut : 5050) |

## Fonctionnalités du dashboard

- Scraping multi-sources : LinkedIn, Google Jobs, Remotive, Arbeitnow, Adzuna, France Travail, RSS
- Scoring des offres : compétences, titre, type de contrat ; détection de doublons
- Suivi de candidature en kanban (À postuler → Entretien → Offre), clôture et rejet
- Dashboard par pays, filtres remote / séniorité / contrat, recherche plein texte
- API JSON : `/api/jobs`, `/api/stats`, `/api/stats/advanced`, `/api/jobs/saved`
- Panneau QA : scénarios BDD, exécution des suites, résultats Playwright, lecture des workflows

## Structure

```
app.py                  routes Flask, API JSON, rendu des templates
scraper.py              sources d'offres, normalisation, filtrage, export
matcher.py              scoring offre ↔ profil
auto_update.py          cycle collecte → export → persistance
supa.py                 client Supabase optionnel
prompts/                contrats de rôle des agents (PO, Spec Review, Architecte, QA, Dev, QA Review, Fix)
workflows/              chaîne d'agents n8n, générée depuis le code (build_wf2.py → wf2_agents.json)
.github/ISSUE_TEMPLATE/ formulaires de tickets (bug, user story, tâche technique)
templates/              dashboard, stats, kanban, QA, monitoring, lettre de motivation
static/theme.css        feuille de style commune
tests/                  BDD (features + step definitions), régression, navigateur (Playwright)
docs/                   export statique, standard multi-agents, architecture, passerelle LLM
monitor-app/            mini-app de surveillance de disponibilité (séparée)
```

## Documentation

| Document | Contenu |
|---|---|
| `docs/standard-multi-agents.md` | rôles, garde-fous, référentiels, cycle de vie d'un ticket |
| `docs/architecture-agents.html` | architecture en une page, lisible dans un navigateur |
| `docs/llm-gateway.md` | passerelle de modèles : installation, clés plafonnées, contrôle des coûts |
| `docs/token-economy.md` | ce qui fait varier le coût d'une chaîne d'agents |
