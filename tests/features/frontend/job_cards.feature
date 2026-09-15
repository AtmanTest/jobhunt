@frontend @cards
Feature: Cartes d'offres

  Scenario: Carte affiche toutes les infos
    Given une offre avec titre, entreprise, salaire, tags
    When la carte est rendue
    Then le titre est visible
    And l'entreprise est visible
    And le salaire est visible si présent
    And les tags sont affichés en pills

  Scenario: Lien externe s'ouvre dans un nouvel onglet
    Given une carte d'offre avec URL
    When je clique sur le titre ou le bouton Apply
    Then le lien s'ouvre dans un nouvel onglet
    And l'attribut rel="noopener noreferrer" est présent
