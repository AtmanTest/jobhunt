@filtering
Feature: Filtrage des offres QA
  En tant que système JobHunt
  Je veux filtrer uniquement les offres de software QA pertinentes

  Scenario: Titre contenant "QA Automation" est accepté
    Given une offre avec le titre "Senior QA Automation Engineer"
    When j'applique le filtre QA software
    Then l'offre est marquée comme valide

  Scenario: Titre contenant "Game Tester" est rejeté
    Given une offre avec le titre "Game Tester QA"
    When j'applique le filtre QA software
    Then l'offre est marquée comme invalide

  Scenario: Description pharma est rejetée
    Given une offre avec la description contenant "GMP pharmaceutical clinical trials"
    When j'applique le filtre QA software
    Then l'offre est marquée comme invalide

  Scenario: Offre avec stack tech reconnue
    Given une offre mentionnant "Cypress" ou "Playwright" ou "Selenium"
    When j'analyse la stack technique
    Then l'offre reçoit un score de pertinence >= 8/10
