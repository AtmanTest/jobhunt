# CHANGELOG

## [1.5.0] - 2026-09-16
### Ajouté
- 🧪 Cadre ISTQB CT-AI appliqué au moteur de classement : 62 tests (portes 2 à 7) dans `tests/test_ct_ai_gates.py`
- 📊 Corpus d'évaluation étiqueté et verrouillé par empreinte SHA-256 (`tests/fixtures/ct_ai/matcher_gold.json`)
- 📁 `docs/qa-ct-ai/` : cadrage du risque IA, qualité des données, métriques et seuils, plan de test, techniques, journal d'aide IA
- 🛡️ Contrôle permanent : aucune adresse e-mail ni téléphone dans les fichiers suivis

### Corrigé
- Comparaison des valeurs métier insensible à la casse et aux accents (`remote_type`, `freelance_status`)
- Détection des compétences sur mot entier : fin des compétences fantômes (« api » dans « capital », « test » dans « latest »)
- Valeurs de télétravail reconnues étendues (`fully_remote`, `Fully Remote`, `100% remote`, `télétravail partiel`)
- Marchés complétés (Zurich, Genève, Lausanne, Bâle, Berne, Lucerne, Lugano…) et marché inconnu plus comparé au marché français
- Plage de salaire « 600 à 700 » de nouveau interprétée comme une plage après normalisation des accents
- Classement déterministe à score égal (départage par identifiant) : plus de top qui change entre deux rafraîchissements
- Robustesse : plus de plantage quand `description` ou `tags` ne sont pas du texte
- Énumération Playwright : référence morte supprimée (bloquait la collecte de toute la suite pytest)

### Technique
- 3 scénarios de filtrage qui échouaient passent désormais (titre « game tester » rejeté, « QA automation » accepté, description pharma rejetée)

## [1.0.0] - 2026-05-28
### Ajouté
- 🆕 Badge "Nouveau" sur les jobs non cliqués avec tracking de vue
- 🏷️ Classifieur freelance : VALIDÉE / AMBIGUË / REJETÉE avec score /10
- 🏠 Détection remote/hybrid/onsite pour chaque offre
- 💶 Extraction TJM/budget et durée de mission
- 🇫🇷 17 plateformes freelance France dans le dashboard
- 🇫🇷 Nouveaux scrapers : LesJeudis, Optioncarriere
- 🔄 Cron-job.org toutes les 6h pour refresh automatique
- 📋 Versionnage de l'app + changelog + rollback git
- 🗄️ Migration automatique du schéma DB

### Modifié
- 🔍 Filtrage strict freelance : CDI/CDD/stage exclus
- 📊 Dashboard enrichi : statut, score, remote, TJM, durée
- ⬇️ Ordre : VALIDÉE en premier, date décroissante

### Technique
- 🏗️ Architecture version.py + git tags + DB schema version
- 🧪 Classifieur avec scoring multi-critères
- ⚡ Optimisation requêtes SQL
