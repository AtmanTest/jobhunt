@scraping @linkedin
Feature: Scraping LinkedIn Jobs
  En tant que système JobHunt
  Je veux récupérer les offres QA depuis LinkedIn

  Scenario: LinkedIn RSS bloqué
    Given l'URL LinkedIn retourne HTTP 404
    When je lance le scraper LinkedIn
    Then une erreur est loggée
    And le scraper retourne 0 offres sans crash
