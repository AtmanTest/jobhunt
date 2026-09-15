@frontend @e2e
Feature: Affichage du dashboard JobHunt
  En tant qu'utilisateur QA freelance
  Je veux voir les offres disponibles

  Scenario: Chargement initial du dashboard
    When j'ouvre la page principale
    Then les skeleton loaders apparaissent pendant le chargement
    And les cartes d'offres s'affichent après chargement
    And aucune erreur n'apparaît dans la console

  Scenario: Badge NEW pour les offres < 7 jours
    Given 3 offres ont été publiées il y a moins de 7 jours
    When j'ouvre le dashboard
    Then ces 3 offres affichent le badge "NEW" en vert

  Scenario: Dark mode toggle
    Given le dashboard est en mode clair
    When je clique sur le toggle dark/light
    Then le fond devient sombre
    And le mode est conservé après rechargement

  Scenario: Responsive mobile à 375px
    Given le viewport est à 375px
    When j'ouvre le dashboard
    Then la sidebar devient une barre basse
    And les cartes sont en colonne unique
