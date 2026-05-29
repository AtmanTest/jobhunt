# 🧪 JOBHUNT — Stratégie de Tests & QA — Prompt Hermes Agent

## CONTEXTE
Tu es un expert QA ISTQB travaillant sur **JobHunt**, un dashboard de chasse aux missions QA Remote.

**Stack :**
- Backend : Flask (localhost:5050)
- Frontend statique : GitHub Pages → https://atmantest.github.io/jobhunt/
- BDD : SQLite (jobs.db)
- Sources scraping : RemoteOK, We Work Remotely, Wellfound, LinkedIn RSS, Otta
- Automatisations : cron jobs Hermes, enrichissement DeepSeek Flash, alertes WhatsApp

**Objectif de cette mission :**
Mettre en place une stratégie de tests complète, stable et maintenable pour couvrir tous les modules de JobHunt :
- Tests écrits en **Gherkin** (Given/When/Then)
- Approche **ISTQB** (tests fonctionnels, non-régression, edge cases, limites)
- Chaque bug trouvé → écriture immédiate d'un **test de non-régression** rejoué à chaque release
- Suite de tests automatisée et rejoua ble en une commande

---

## 📐 MISSION 1 — Structure du projet de tests

Crée la structure suivante dans le répertoire du projet :

```
tests/
├── features/                        # Fichiers Gherkin .feature
│   ├── scraping/
│   │   ├── remoteok_scraper.feature
│   │   ├── weworkremotely_scraper.feature
│   │   ├── linkedin_scraper.feature
│   │   ├── wellfound_scraper.feature
│   │   └── otta_scraper.feature
│   ├── filtering/
│   │   ├── qa_filter.feature
│   │   └── deduplication.feature
│   ├── enrichment/
│   │   └── ai_enrichment.feature
│   ├── api/
│   │   ├── jobs_endpoint.feature
│   │   ├── stats_endpoint.feature
│   │   └── saved_endpoint.feature
│   ├── frontend/
│   │   ├── dashboard_display.feature
│   │   ├── search_filters.feature
│   │   ├── job_cards.feature
│   │   ├── kanban_pipeline.feature
│   │   └── alerts_whatsapp.feature
│   ├── cron/
│   │   └── scheduled_jobs.feature
│   └── regression/
│       └── bug_fixes.feature        # Tests de non-régression bugs trouvés
│
├── step_definitions/                # Implémentations Python des steps Gherkin
│   ├── conftest.py
│   ├── scraping_steps.py
│   ├── filtering_steps.py
│   ├── enrichment_steps.py
│   ├── api_steps.py
│   ├── frontend_steps.py
│   ├── cron_steps.py
│   └── regression_steps.py
│
├── fixtures/
│   ├── sample_jobs.json             # Données de test statiques
│   ├── mock_remoteok_response.json
│   ├── mock_enrichment_response.json
│   └── test_db.sqlite               # BDD de test isolée
│
├── utils/
│   ├── db_helpers.py
│   ├── api_client.py
│   └── mock_server.py
│
├── reports/                         # Rapports générés après chaque run
│   └── .gitkeep
│
├── pytest.ini
├── requirements-test.txt
└── run_tests.sh                     # Script de lancement rapide
```

**Fichier `requirements-test.txt` :**
```
pytest==8.x
pytest-bdd==7.x
pytest-cov==5.x
pytest-html==4.x
requests==2.x
responses==0.25.x
freezegun==1.x
sqlite-utils==3.x
playwright==1.x        # Pour les tests E2E frontend
pytest-playwright==0.5.x
```

**Fichier `run_tests.sh` :**
```bash
#!/bin/bash
echo "🧪 JobHunt — Lancement de la suite de tests complète"
echo "=================================================="

# Tests unitaires + BDD
pytest tests/ -v --html=tests/reports/report.html --self-contained-html \
  --cov=app --cov-report=html:tests/reports/coverage \
  --tb=short

echo ""
echo "📊 Rapport : tests/reports/report.html"
echo "📈 Coverage : tests/reports/coverage/index.html"
```

---

## 📋 MISSION 2 — Fichiers Gherkin par module

### Module Scraping — `remoteok_scraper.feature`

```gherkin
# language: fr
@scraping @remoteok
Feature: Scraping RemoteOK
  En tant que système JobHunt
  Je veux récupérer les offres QA depuis RemoteOK
  Afin d'alimenter la base de données avec des missions fraîches

  Background:
    Given la base de données de test est vide
    And le scraper RemoteOK est initialisé

  Scenario: Scraping nominal avec résultats valides
    Given l'API RemoteOK retourne 15 offres dont 8 offres QA software
    When je lance le scraper RemoteOK
    Then 8 offres sont insérées en base
    And chaque offre contient les champs obligatoires : titre, url, entreprise, date_publication
    And le champ source vaut "remoteok"

  Scenario: Scraping avec réponse vide
    Given l'API RemoteOK retourne une liste vide
    When je lance le scraper RemoteOK
    Then 0 offres sont insérées en base
    And aucune erreur n'est levée

  Scenario: Scraping avec timeout réseau
    Given l'API RemoteOK met plus de 10 secondes à répondre
    When je lance le scraper RemoteOK
    Then une exception Timeout est capturée
    And le scraper se termine proprement sans crash
    And une entrée est écrite dans les logs avec le niveau ERROR

  Scenario: Scraping avec réponse HTTP 429 (rate limit)
    Given l'API RemoteOK retourne un code HTTP 429
    When je lance le scraper RemoteOK
    Then le scraper attend 60 secondes avant de réessayer
    And réessaie au maximum 3 fois
    And abandonne avec un log WARNING si toutes les tentatives échouent

  Scenario: Dédoublonnage lors d'un second scraping
    Given la base de données contient déjà 5 offres RemoteOK
    And l'API RemoteOK retourne les mêmes 5 offres plus 3 nouvelles offres
    When je lance le scraper RemoteOK
    Then seulement 3 nouvelles offres sont insérées en base
    And le total en base est 8 offres

  Scenario Outline: Exclusion des offres hors périmètre QA software
    Given l'API RemoteOK retourne une offre avec le titre "<titre>"
    When je lance le filtre QA
    Then l'offre est <résultat>

    Examples:
      | titre                              | résultat |
      | QA Automation Engineer             | conservée |
      | SDET Senior Playwright             | conservée |
      | Test Automation Lead               | conservée |
      | Game Tester — Mobile               | exclue   |
      | QA Manager non-technical           | exclue   |
      | Pharmaceutical Quality Assurance   | exclue   |
      | Manual QA Tester Junior            | conservée |
      | QA Director VP                     | exclue   |
```

---

### Module Filtrage — `qa_filter.feature`

```gherkin
@filtering
Feature: Filtrage des offres QA
  En tant que système JobHunt
  Je veux filtrer uniquement les offres de software QA pertinentes
  Afin de ne présenter que des missions adaptées à un profil SDET/QA Automation

  Scenario: Titre contenant "QA" et "Automation" est accepté
    Given une offre avec le titre "Senior QA Automation Engineer"
    When j'applique le filtre QA software
    Then l'offre est marquée comme valide

  Scenario: Titre contenant "Game Tester" est rejeté
    Given une offre avec le titre "Game Tester QA"
    When j'applique le filtre QA software
    Then l'offre est marquée comme invalide
    And la raison de rejet est "game_tester"

  Scenario: Description contenant des mots-clés pharma est rejetée
    Given une offre avec la description contenant "GMP pharmaceutical clinical trials validation"
    When j'applique le filtre QA software
    Then l'offre est marquée comme invalide
    And la raison de rejet est "pharma"

  Scenario: Offre avec stack tech reconnue est prioritaire
    Given une offre mentionnant "Cypress" ou "Playwright" ou "Selenium"
    When j'analyse la stack technique
    Then l'offre reçoit un score de pertinence >= 8/10

  Scenario: Offre sans indication de salaire
    Given une offre dont la description ne mentionne aucun chiffre monétaire
    When j'extrais le salaire
    Then le champ salary_min est null
    And le champ salary_max est null
    And le champ ai_enriched est false
```

---

### Module Enrichissement IA — `ai_enrichment.feature`

```gherkin
@enrichment @ai
Feature: Enrichissement IA des offres via DeepSeek Flash
  En tant que système JobHunt
  Je veux extraire automatiquement les données structurées de chaque offre
  Afin d'enrichir les filtres et améliorer la qualité des données

  Background:
    Given le client DeepSeek Flash est configuré avec une clé API valide
    And la base de données de test contient 5 offres sans enrichissement

  Scenario: Extraction réussie depuis une description complète
    Given une description d'offre mentionnant "100-150 EUR/day fully remote Cypress Playwright senior"
    When j'envoie la description à DeepSeek Flash pour enrichissement
    Then la réponse JSON est valide
    And salary_min vaut 100
    And salary_max vaut 150
    And currency vaut "EUR"
    And period vaut "daily"
    And remote_type vaut "fully_remote"
    And tech_stack contient "Cypress" et "Playwright"
    And seniority vaut "senior"
    And le champ ai_enriched est true

  Scenario: Description ambiguë — DeepSeek retourne des null
    Given une description vague sans mentions de salaire ni technos
    When j'envoie la description à DeepSeek Flash pour enrichissement
    Then salary_min est null
    And tech_stack est un tableau vide
    And ai_enriched est true
    And aucune exception n'est levée

  Scenario: Timeout API DeepSeek lors de l'enrichissement
    Given l'API DeepSeek met plus de 15 secondes à répondre
    When je tente l'enrichissement
    Then l'offre reste non enrichie (ai_enriched = false)
    And une entrée WARNING est écrite dans les logs
    And l'enrichissement des autres offres continue

  Scenario: Dépassement de quota tokens DeepSeek
    Given l'API DeepSeek retourne une erreur 429 quota dépassé
    When je tente l'enrichissement batch de 10 offres
    Then le processus s'arrête proprement
    And les offres déjà enrichies conservent leurs données
    And un log ERROR indique le nombre d'offres non enrichies

  Scenario: L'enrichissement ne réenrichit pas les offres déjà traitées
    Given la base contient 3 offres avec ai_enriched = true
    And 2 offres avec ai_enriched = false
    When je lance le processus d'enrichissement
    Then seules les 2 offres non enrichies sont envoyées à l'API
    And 0 requêtes supplémentaires sont faites pour les offres déjà enrichies
```

---

### Module API Flask — `jobs_endpoint.feature`

```gherkin
@api @backend
Feature: Endpoint API /api/jobs
  En tant que frontend JobHunt
  Je veux récupérer les offres depuis l'API Flask
  Afin de les afficher dans le dashboard

  Background:
    Given le serveur Flask tourne sur localhost:5050
    And la base de données contient 20 offres de test

  Scenario: GET /api/jobs retourne toutes les offres actives
    When j'envoie une requête GET sur /api/jobs
    Then le statut HTTP est 200
    And le Content-Type est "application/json"
    And la réponse contient un tableau de 20 offres
    And chaque offre contient les champs : id, title, company, url, date_posted, source

  Scenario: GET /api/jobs avec filtre stack tech
    Given 5 offres contiennent "Cypress" dans tech_stack
    When j'envoie une requête GET sur /api/jobs?tech=Cypress
    Then le statut HTTP est 200
    And la réponse contient exactement 5 offres
    And toutes les offres ont "Cypress" dans leur tech_stack

  Scenario: GET /api/jobs avec filtre salaire minimum
    Given 8 offres ont salary_min >= 600
    When j'envoie une requête GET sur /api/jobs?salary_min=600
    Then le statut HTTP est 200
    And la réponse contient exactement 8 offres

  Scenario: GET /api/jobs avec paramètre invalide
    When j'envoie une requête GET sur /api/jobs?salary_min=abc
    Then le statut HTTP est 400
    And le corps de la réponse contient un champ "error"

  Scenario: GET /api/stats retourne les agrégats corrects
    Given la base contient 20 offres dont 5 avec salary_min renseigné
    When j'envoie une requête GET sur /api/stats
    Then le statut HTTP est 200
    And la réponse contient total_jobs, jobs_this_week, jobs_this_month
    And avg_salary est calculé uniquement sur les offres avec salary_min renseigné

  Scenario: POST /api/jobs/:id/save sauvegarde une offre
    Given l'offre avec id=1 a saved = false
    When j'envoie une requête POST sur /api/jobs/1/save
    Then le statut HTTP est 200
    And l'offre avec id=1 a saved = true en base

  Scenario: POST /api/jobs/:id/apply enregistre une candidature
    Given l'offre avec id=2 a applied = false
    When j'envoie une requête POST sur /api/jobs/2/apply
    Then le statut HTTP est 200
    And l'offre avec id=2 a applied = true
    And applied_at est renseigné avec la date/heure actuelle
```

---

### Module Frontend E2E — `dashboard_display.feature`

```gherkin
@frontend @e2e
Feature: Affichage du dashboard JobHunt
  En tant qu'utilisateur QA freelance
  Je veux voir les offres de missions disponibles
  Afin de postuler rapidement aux meilleures opportunités

  Background:
    Given le frontend est accessible sur https://atmantest.github.io/jobhunt/
    And l'API Flask retourne 18 offres de test

  Scenario: Chargement initial du dashboard
    When j'ouvre la page principale
    Then les skeleton loaders apparaissent pendant le chargement
    And les 18 cartes d'offres s'affichent après chargement
    And le KPI "Total offres" affiche 18
    And aucune erreur n'apparaît dans la console navigateur

  Scenario: Badge NEW affiché pour les offres récentes
    Given 3 offres ont été publiées il y a moins de 7 jours
    When j'ouvre le dashboard
    Then ces 3 offres affichent le badge "NEW" en vert
    And les autres offres n'ont pas de badge NEW

  Scenario: Dark mode toggle fonctionne
    Given le dashboard est en mode clair
    When je clique sur le bouton de toggle dark/light
    Then le fond de la page devient sombre (#0d0f12 ou équivalent)
    And le texte reste lisible (contraste WCAG AA respecté)
    And le mode dark est conservé après rechargement de la page

  Scenario: Responsive mobile à 375px
    Given le viewport est réglé à 375px de largeur
    When j'ouvre le dashboard
    Then la sidebar se transforme en barre de navigation basse
    And les cartes s'affichent en colonne unique
    And aucun débordement horizontal n'est visible
    And les boutons ont une hauteur tactile d'au moins 44px

  Scenario: Recherche en temps réel filtre les offres
    Given le dashboard affiche 18 offres
    When je tape "Cypress" dans la barre de recherche
    Then seules les offres mentionnant "Cypress" s'affichent
    And le compteur affiche le nombre d'offres filtrées
    And les offres filtrées s'animent en apparition douce

  Scenario: Sauvegarder une offre
    Given je vois la carte de l'offre "Senior QA Automation Engineer"
    When je clique sur l'icône de bookmark
    Then l'icône devient pleine (offre sauvegardée)
    And l'offre apparaît dans l'onglet "Sauvegardées"
    And un feedback visuel de confirmation s'affiche

  Scenario: Postuler à une offre
    Given je vois la carte de l'offre "SDET Playwright"
    When je clique sur "Postuler"
    Then l'offre est marquée comme "Postulé"
    And l'offre apparaît dans le Kanban colonne "Postulé"
    And la date de candidature est enregistrée
```

---

### Module Cron — `scheduled_jobs.feature`

```gherkin
@cron @automation
Feature: Jobs cron automatisés
  En tant que système d'automatisation JobHunt
  Je veux que les jobs cron s'exécutent à l'heure prévue
  Afin de maintenir les données fraîches sans intervention manuelle

  Background:
    Given le service Hermes cron est démarré
    And la base de données est accessible

  Scenario: Job daily-refresh s'exécute à 08h00
    Given le cron "jobhunt-daily-refresh" est planifié à "0 8 * * *"
    When il est 08h00
    Then le scraping de toutes les sources est lancé
    And l'enrichissement IA est lancé sur les nouvelles offres
    And le fichier JSON est exporté
    And un git push est effectué vers GitHub Pages
    And un log INFO confirme la complétion

  Scenario: Job alert-check vérifie les nouvelles offres toutes les 2h
    Given le cron "jobhunt-alert-check" est planifié à "0 8-22/2 * * *"
    And 3 nouvelles offres ont été ajoutées depuis la dernière vérification
    When la vérification s'exécute
    Then les 3 nouvelles offres sont détectées
    And un message WhatsApp est envoyé pour chaque offre prioritaire
    And la date de dernière vérification est mise à jour

  Scenario: Job weekly-report s'exécute chaque lundi à 09h00
    Given le cron "jobhunt-weekly-report" est planifié à "0 9 * * 1"
    And la semaine a produit 15 nouvelles offres
    When le rapport hebdomadaire est généré
    Then un message WhatsApp contient le top 5 des offres
    And les stats de la semaine sont incluses (total, salaire moyen, top stack)

  Scenario: Échec d'un cron sans impact sur les suivants
    Given le cron "jobhunt-daily-refresh" échoue sur RemoteOK (timeout)
    When le job se termine
    Then les offres des autres sources sont quand même insérées
    And un log ERROR enregistre l'échec RemoteOK
    And le prochain cron est toujours planifié normalement
```

---

### Module Non-Régression — `bug_fixes.feature`

```gherkin
@regression @bug-fix
Feature: Tests de non-régression — Bugs corrigés
  En tant qu'équipe QA
  Je veux rejouer automatiquement chaque bug corrigé
  Afin de garantir qu'aucune régression ne réintroduit un bug résolu

  # ⚠️ TEMPLATE — Chaque fois qu'un bug est trouvé et corrigé,
  # ajouter un Scenario ici avec le numéro du bug et sa description.
  # Ce fichier est rejoué à chaque release sans exception.

  Scenario: [BUG-001] Le scraper RemoteOK crashait sur les offres sans champ "salary"
    # Bug trouvé le : à renseigner
    # Corrigé dans : commit à renseigner
    Given l'API RemoteOK retourne une offre sans le champ "salary"
    When je lance le scraper
    Then aucune exception KeyError n'est levée
    And l'offre est insérée avec salary_min = null

  Scenario: [BUG-002] Le filtre QA acceptait les offres "QA Director" non techniques
    # Bug trouvé le : à renseigner
    # Corrigé dans : commit à renseigner
    Given une offre avec le titre "QA Director VP Engineering"
    When j'applique le filtre QA software
    Then l'offre est exclue
    And la raison de rejet contient "management"

  Scenario: [BUG-003] Doublon inséré si même URL avec casse différente
    # Bug trouvé le : à renseigner
    Given la base contient une offre avec url "https://remoteok.com/job/123"
    And une nouvelle offre arrive avec url "https://RemoteOK.com/job/123"
    When le déduplicateur compare les URLs
    Then les deux URLs sont considérées comme identiques
    And 0 doublon est inséré en base

  # ---- AJOUTER ICI LES NOUVEAUX BUGS CORRIGÉS ----
  # Scenario: [BUG-XXX] Description courte du bug
  #   Given [contexte du bug]
  #   When [action qui déclenchait le bug]
  #   Then [comportement attendu après correction]
```

---

## 🔧 MISSION 3 — Implémentation des step definitions Python

Crée `tests/conftest.py` :

```python
import pytest
import sqlite3
import os
import json
from pathlib import Path

TEST_DB_PATH = "tests/fixtures/test_db.sqlite"
FIXTURES_DIR = Path("tests/fixtures")

@pytest.fixture(scope="function")
def test_db():
    """Base de données SQLite isolée pour chaque test."""
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    conn = sqlite3.connect(TEST_DB_PATH)
    conn.row_factory = sqlite3.Row
    # Créer le schéma identique à la production
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT,
            url TEXT UNIQUE NOT NULL,
            description TEXT,
            date_posted TEXT,
            source TEXT,
            salary_min INTEGER,
            salary_max INTEGER,
            currency TEXT,
            period TEXT,
            remote_type TEXT,
            tech_stack TEXT,
            seniority TEXT,
            contract_type TEXT,
            ai_enriched BOOLEAN DEFAULT 0,
            saved BOOLEAN DEFAULT 0,
            applied BOOLEAN DEFAULT 0,
            applied_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    yield conn
    conn.close()
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

@pytest.fixture
def flask_client():
    """Client de test Flask avec base de données isolée."""
    import sys
    sys.path.insert(0, os.getcwd())
    from app import app, init_db
    app.config["TESTING"] = True
    app.config["DATABASE"] = TEST_DB_PATH
    with app.test_client() as client:
        with app.app_context():
            init_db()
        yield client

@pytest.fixture
def sample_jobs():
    with open(FIXTURES_DIR / "sample_jobs.json") as f:
        return json.load(f)
```

---

## 📊 MISSION 4 — Configuration pytest et rapports

Crée `pytest.ini` :

```ini
[pytest]
testpaths = tests
python_files = test_*.py *_steps.py
python_classes = Test*
python_functions = test_*
addopts =
    -v
    --tb=short
    --strict-markers
    --html=tests/reports/report.html
    --self-contained-html

markers =
    scraping: Tests du module scraping
    filtering: Tests du module filtrage
    enrichment: Tests du module enrichissement IA
    api: Tests des endpoints API Flask
    frontend: Tests E2E Playwright
    cron: Tests des jobs cron
    regression: Tests de non-régression (rejouer après chaque bug fix)
    e2e: Tests end-to-end complets
    slow: Tests lents (> 5 secondes)
```

---

## 📏 MISSION 5 — Règles et conventions QA (obligatoires)

### Règle 1 — Bug trouvé = Test écrit immédiatement
Dès qu'un bug est découvert et corrigé :
1. Ouvrir `tests/features/regression/bug_fixes.feature`
2. Ajouter un `Scenario` avec le numéro BUG-XXX (incrémenter)
3. Écrire le Given/When/Then qui aurait détecté le bug
4. Implémenter le step si nécessaire dans `regression_steps.py`
5. Vérifier que le test ÉCHOUE avant le fix, PASSE après
6. Ne jamais merger un fix sans le test associé

### Règle 2 — Tests d'abord sur les chemins critiques
Les chemins critiques qui doivent avoir 100% de couverture :
- Scraping → Filtrage → Insertion BDD
- API GET /api/jobs → Réponse JSON valide
- Enrichissement IA → Stockage correct en BDD
- Cron daily-refresh → Complétion sans crash

### Règle 3 — Nomenclature des tests
- Fichiers `.feature` : `nom_module.feature` en snake_case
- Scenarios : commencer par l'action principale ("Scraping nominal", "Filtrage offres pharma")
- Tags : toujours tagger avec le module concerné + `@regression` si c'est un bug fix

### Règle 4 — Données de test isolées
- Jamais utiliser la base de production dans les tests
- Toujours utiliser la fixture `test_db` ou une BDD SQLite temporaire
- Les fixtures JSON dans `tests/fixtures/` sont la source de vérité des données de test
- Mocker toutes les API externes (RemoteOK, DeepSeek, WhatsApp)

### Règle 5 — Lancer les tests avant chaque push
```bash
# Avant chaque git push vers GitHub Pages :
bash tests/run_tests.sh

# Si des tests échouent, ne pas pusher.
# Corriger d'abord, écrire le test de non-régression, puis pusher.
```

---

## 🚀 ORDRE D'EXÉCUTION

1. Crée la structure de répertoires `tests/`
2. Installe les dépendances : `pip install -r requirements-test.txt`
3. Crée les fichiers `.feature` de chaque module (utilise exactement le Gherkin ci-dessus)
4. Implémente `conftest.py` et les fixtures
5. Implémente les step definitions module par module (commence par `scraping_steps.py`)
6. Crée `pytest.ini` et `run_tests.sh`
7. Lance `bash tests/run_tests.sh` et vérifie que tous les tests PASSENT
8. Montre-moi le rapport HTML généré

**Commence par la Mission 1 (structure) puis la Mission 2 (fichiers Gherkin). Confirme chaque étape avant de passer à la suivante.**
