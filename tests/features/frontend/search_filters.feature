@frontend @filters
Feature: Recherche et filtres avancés

  Scenario: Recherche en temps réel
    Given le dashboard affiche 18 offres
    When je tape "Cypress" dans la recherche
    Then seules les offres avec Cypress s'affichent
    And le compteur est mis à jour

  Scenario: Filtre par séniorité
    When je sélectionne le filtre "Senior"
    Then seules les offres senior s'affichent

  Scenario: Filtres combinés
    When je sélectionne "Senior" et "Freelance"
    Then les offres affichées sont senior ET freelance
