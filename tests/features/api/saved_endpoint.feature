@api @saved
Feature: Endpoint save/unsave des offres
  En tant qu'utilisateur
  Je veux sauvegarder des offres

  Scenario: Sauvegarder une offre
    Given l'offre avec id=1 a saved = 0
    When j'envoie POST /api/jobs/1/save
    Then le statut HTTP est 200
    And l'offre avec id=1 a saved = 1

  Scenario: Liste des sauvegardées
    Given 3 offres sont sauvegardées
    When j'envoie GET /api/jobs/saved
    Then la réponse contient 3 offres
