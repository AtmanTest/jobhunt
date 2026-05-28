# CHANGELOG

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
