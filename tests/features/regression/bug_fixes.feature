@regression @bug-fix
Feature: Tests de non-régression — Bugs corrigés
  En tant qu'équipe QA
  Je veux rejouer chaque bug corrigé

  Scenario: [BUG-001] KeyError sur offre sans "salary"
    Given l'API RemoteOK retourne une offre sans le champ "salary"
    When je lance le scraper
    Then aucune exception KeyError n'est levée
    And l'offre est insérée avec salary = ''

  Scenario: [BUG-002] Filtre acceptait "QA Director"
    Given une offre avec le titre "QA Director VP Engineering"
    When j'applique le filtre QA software
    Then l'offre est exclue

  Scenario: [BUG-003] Doublon avec casse différente
    Given la base a "https://remoteok.com/job/123"
    And une nouvelle offre arrive avec "https://RemoteOK.com/job/123"
    When le déduplicateur compare
    Then 0 doublon est inséré
