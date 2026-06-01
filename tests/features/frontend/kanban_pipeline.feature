@frontend @kanban
Feature: Pipeline Kanban des candidatures

  Scenario: Voir les colonnes Kanban
    Given j'ai 5 candidatures à différents stades
    When j'ouvre l'onglet Candidatures
    Then je vois 5 colonnes : À postuler, Postulé, Entretien, Offre, Refusé
    And chaque colonne contient le bon nombre d'offres

  Scenario: Déplacer une offre dans le pipeline
    Given une offre est dans "À postuler"
    When je clique "Postulé"
    Then l'offre apparaît dans la colonne "Postulé"
