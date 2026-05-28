@scraping @remoteok
Feature: Scraping RemoteOK
  En tant que système JobHunt
  Je veux récupérer les offres QA depuis RemoteOK
  Afin d'alimenter la base de données avec des missions fraîches

  Background:
    Given la base de données de test est vide
    And le scraper RemoteOK est initialisé

  Scenario: Scraping nominal avec résultats valides
    Given l'API RemoteOK retourne 15 offres dont 8 offres QA software
    When je lance le scraper RemoteOK
    Then 8 offres sont insérées en base
    And chaque offre contient les champs obligatoires : titre, url, entreprise, date_publication
    And le champ source vaut "remoteok"

  Scenario: Scraping avec réponse vide
    Given l'API RemoteOK retourne une liste vide
    When je lance le scraper RemoteOK
    Then 0 offres sont insérées en base
    And aucune erreur n'est levée

  Scenario: Dédoublonnage lors d'un second scraping
    Given la base de données contient déjà 5 offres RemoteOK
    And l'API RemoteOK retourne les mêmes 5 offres plus 3 nouvelles offres
    When je lance le scraper RemoteOK
    Then seulement 3 nouvelles offres sont insérées en base
    And le total en base est 8 offres

  Scenario Outline: Exclusion des offres hors périmètre QA software
    Given l'API RemoteOK retourne une offre avec le titre "<titre>"
    When je lance le filtre QA
    Then l'offre est <résultat>

    Examples:
      | titre                              | résultat |
      | QA Automation Engineer             | conservée |
      | SDET Senior Playwright             | conservée |
      | Test Automation Lead               | conservée |
      | Game Tester — Mobile               | exclue   |
      | QA Manager non-technical           | exclue   |
      | Senior QA Consultant               | conservée |
      | Manual QA Tester Junior            | conservée |
