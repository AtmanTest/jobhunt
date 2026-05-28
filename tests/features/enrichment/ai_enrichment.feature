@enrichment @ai
Feature: Enrichissement IA des offres via DeepSeek Flash
  En tant que système JobHunt
  Je veux extraire automatiquement les données structurées de chaque offre

  Scenario: Extraction réussie depuis une description complète
    Given une description d'offre mentionnant "100-150 USD/day fully remote Cypress Playwright senior"
    When j'envoie la description à DeepSeek Flash pour enrichissement
    Then salary_min vaut 100
    And salary_max vaut 150
    And currency vaut "USD"
    And remote_type vaut "fully_remote"
    And tech_stack contient "Cypress" et "Playwright"
    And seniority vaut "senior"
    And le champ ai_enriched est true

  Scenario: Description vague
    Given une description vague sans mentions de salaire
    When j'envoie la description à DeepSeek Flash
    Then salary_min est null
    And tech_stack est un tableau vide
    And ai_enriched est true

  Scenario: Pas de ré-enrichissement
    Given la base contient 3 offres avec ai_enriched = true
    And 2 offres avec ai_enriched = false
    When je lance l'enrichissement
    Then seules les 2 offres non enrichies sont envoyées
