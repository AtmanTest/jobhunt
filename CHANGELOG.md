# CHANGELOG

## [1.6.0] - 2026-09-16
### Ajouté
- 🎯 Filtre par budget minimum (TJM) : règle métier unique (`matcher.filtrer_par_budget`), branchée sur l'API des offres et sur la barre de filtres du tableau de bord
- 🧪 12 tests unitaires + 3 tests d'intégration + 1 scénario navigateur pour ce filtre (développement piloté par les tests)
- 📄 Page « Cycle de vie complet » (`/cycle-de-vie`) : demande métier, user stories, stratégie de test, TDD, campagnes exécutées, anomalies, correctifs extraits de Git, non-régression, couverture, intégration continue, amélioration continue, rattachement CTFL / CT-AI / CT-GenAI
- 🧾 `scripts/build_lifecycle.py` : produit la preuve par exécution réelle (suites + couverture + lecture du code et de l'historique)
- 🧾 `scripts/build_pages.py` : publie les démonstrations sur GitHub Pages avec contrôle automatique de non-fuite

### Corrigé
- 🐛 **AN-101** : `/api/jobs` répondait 404 — le décorateur de route avait disparu (5 scénarios BDD en échec réparés)
- 🐛 **AN-102** : la suite navigateur ne pouvait pas s'exécuter (`pytest-playwright` absent des dépendances) → 10 scénarios tournent désormais dans un vrai Chromium

### Technique
- 📉 Suite historique : 34 → 26 échecs, 102 → 153 tests passants, aucun nouvel échec
- 📊 Couverture mesurée : matcher.py 80 %, virtual_delivery.py 94 %, app.py 36 % (chantier identifié)

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
