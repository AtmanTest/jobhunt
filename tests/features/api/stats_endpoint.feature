@api @stats
Feature: Endpoint API /api/stats/advanced
  En tant que frontend JobHunt
  Je veux obtenir des analytics avancées

  Scenario: GET /api/stats/advanced
    Given la base contient 10 offres avec seniority variés
    When j'envoie GET /api/stats/advanced
    Then le statut HTTP est 200
    And la réponse contient "by_seniority"
    And "by_contract_type" est présent
    And "top_stacks" est un tableau
