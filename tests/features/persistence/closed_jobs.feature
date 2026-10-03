@regression @closed-jobs @persistence
Feature: Persistance des jobs clôturés
  En tant qu'utilisateur
  Je veux que les jobs clôturés ne réapparaissent jamais

  Scenario: Dismiss un job et vérifie qu'il est dans dismissed_jobs
    Given une offre avec ID 42 existe
    When je dismiss l'offre 42
    Then l'offre 42 apparaît dans la table dismissed_jobs
    And l'offre 42 n'apparaît plus dans les résultats du dashboard

  Scenario: Restauration des dismissed_jobs depuis closed_jobs.json
    Given le fichier docs/closed_jobs.json contient 2 entrées
    When l'application démarre et charge closed_jobs.json
    Then la table dismissed_jobs contient 2 entrées
    And ces offres sont filtrées du dashboard
