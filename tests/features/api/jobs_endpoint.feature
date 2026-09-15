@api @backend
Feature: Endpoint API /api/jobs
  En tant que frontend JobHunt
  Je veux récupérer les offres depuis l'API Flask

  Background:
    Given le serveur Flask tourne sur localhost:5050
    And la base de données contient 20 offres de test

  Scenario: GET /api/jobs retourne les offres
    When j'envoie une requête GET sur /api/jobs
    Then le statut HTTP est 200
    And le Content-Type est "application/json"
    And la réponse contient 20 offres

  Scenario: GET /api/jobs avec filtre stack tech
    Given 5 offres contiennent "Cypress" dans tech_stack
    When j'envoie GET /api/jobs?tech=Cypress
    Then le statut HTTP est 200
    And la réponse contient 5 offres

  Scenario: GET /api/stats retourne les agrégats
    When j'envoie une requête GET sur /api/stats
    Then le statut HTTP est 200
    And la réponse contient total_jobs, jobs_this_week, avg_salary
