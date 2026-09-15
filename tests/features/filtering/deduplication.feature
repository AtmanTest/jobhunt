@filtering @dedup
Feature: Dédoublonnage des offres
  En tant que système JobHunt
  Je veux éviter les doublons lors du scraping

  Scenario: Même URL = même offre
    Given la base contient une offre avec url "https://remoteok.com/job/test-123"
    And une nouvelle offre arrive avec la même URL
    When je tente d'insérer la nouvelle offre
    Then 0 offre est ajoutée

  Scenario: Même titre + même entreprise = doublon potentiel
    Given la base contient une offre "QA Engineer" chez "Acme Inc"
    And une nouvelle offre identique arrive
    When je tente d'insérer
    Then 0 offre est ajoutée
