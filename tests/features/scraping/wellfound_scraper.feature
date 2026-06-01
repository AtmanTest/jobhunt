@scraping @wellfound
Feature: Scraping Wellfound (AngelList)
  En tant que système JobHunt
  Je veux récupérer les offres QA depuis Wellfound

  Scenario: Wellfound bloqué par Cloudflare
    Given l'URL Wellfound retourne HTTP 403
    When je lance le scraper Wellfound
    Then une erreur est loggée
    And le scraper retourne 0 offres sans crash
