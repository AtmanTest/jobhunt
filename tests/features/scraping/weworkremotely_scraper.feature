@scraping @wwr
Feature: Scraping We Work Remotely
  En tant que système JobHunt
  Je veux récupérer les offres QA depuis We Work Remotely
  Afin d'alimenter la base de données

  Scenario: Scraping nominal via RSS
    Given le flux RSS WWR retourne 10 offres dont 3 QA
    When je lance le scraper WWR
    Then 3 offres QA sont insérées en base
    And le champ source vaut "WWR"

  Scenario: Flux RSS indisponible
    Given le flux RSS WWR retourne une erreur HTTP 500
    When je lance le scraper WWR
    Then une erreur est loggée
    And le scraper continue sans crash
