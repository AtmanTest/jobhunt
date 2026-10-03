@scraping @otta
Feature: Scraping Otta.com
  En tant que système JobHunt
  Je veux récupérer les offres QA depuis Otta

  Scenario: Otta nécessite JavaScript
    Given l'URL Otta retourne du HTML statique sans les offres
    When je lance le scraper Otta
    Then une erreur est loggée
    And le scraper retourne 0 offres sans crash
