     1|# CHANGELOG
     2|
     3|## [1.0.0] - 2026-05-28
     4|### Ajouté
     5|- 🆕 Badge "Nouveau" sur les jobs non cliqués avec tracking de vue
     6|- 🏷️ Classifieur freelance : VALIDÉE / AMBIGUË / REJETÉE avec score /10
     7|- 🏠 Détection remote/hybrid/onsite pour chaque offre
     8|- 💶 Extraction TJM/budget et durée de mission
     9|- 🇫🇷 17 plateformes freelance France dans le dashboard
    10|- 🇫🇷 Nouveaux scrapers : LesJeudis, Optioncarriere
    11|- 🔄 Cron-job.org toutes les 6h pour refresh automatique
    12|- 📋 Versionnage de l'app + changelog + rollback git
    13|- 🗄️ Migration automatique du schéma DB
    14|
    15|### Modifié
    16|- 🔍 Filtrage strict freelance : CDI/CDD/stage exclus
    17|- 📊 Dashboard enrichi : statut, score, remote, TJM, durée
    18|- ⬇️ Ordre : VALIDÉE en premier, date décroissante
    19|
    20|### Technique
    21|- 🏗️ Architecture version.py + git tags + DB schema version
    22|- 🧪 Classifieur avec scoring multi-critères
    23|- ⚡ Optimisation requêtes SQL
    24|