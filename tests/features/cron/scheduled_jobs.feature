@cron @automation
Feature: Jobs cron automatisés

  Scenario: Job daily-refresh à 08h00
    Given le cron "jobhunt-daily-refresh" est planifié à "0 8 * * *"
    When il est 08h00
    Then le scraping et l'export sont lancés
    And un git push est effectué

  Scenario: Job alert-check toutes les 2h
    Given 3 nouvelles offres ajoutées
    When la vérification s'exécute
    Then les 3 offres sont détectées
    And un message WhatsApp est envoyé

  Scenario: Job weekly-report le lundi 9h
    Given la semaine a produit 15 offres
    When le rapport est généré
    Then le top 5 des offres est inclus
    And les stats sont envoyées
