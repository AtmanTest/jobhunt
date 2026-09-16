# language: fr
@niveau:bout-en-bout @outil:playwright @navigateur:chromium
Fonctionnalité: Tableau de bord des offres, vérifié dans un navigateur réel
  Chaque scénario de ce fichier décrit un comportement observable du tableau de bord.
  Il est exécuté par Playwright sur un Chromium réel : les mêmes scénarios tournent
  en local (serveur de test) et dans la chaîne d'intégration.
  Le lien entre le scénario et le code est explicite : l'étiquette @cas porte le nom
  de la fonction de test correspondante dans tests/playwright/test_dashboard.py.

  Contexte:
    Étant donné que le tableau de bord est ouvert dans le navigateur
    Et que l'adresse de test est fournie par la variable d'environnement JOBHUNT_URL

  @cas:test_page_title
  Scénario: Le titre de l'onglet identifie le produit
    Alors le titre du document contient « JobHunt », « Marché » ou « QA »
    Et le titre relevé est journalisé dans le résultat du scénario

  @cas:test_hero_stats
  Scénario: Les indicateurs principaux sont affichés
    Quand j'attends l'affichage du bandeau d'indicateurs
    Alors au moins 3 cartes d'indicateurs sont présentes
    Et le contenu de chaque carte est relevé

  @cas:test_country_tabs
  Scénario: Les onglets de marché permettent de changer de pays
    Quand j'attends l'affichage des onglets de marché
    Alors au moins 5 onglets sont présents
    Et le passage sur le marché suisse s'effectue sans erreur

  @cas:test_remote_filter
  Scénario: Le filtre télétravail est disponible et activable
    Quand j'attends l'affichage de la barre de filtres
    Alors un bouton de filtre « Remote » existe
    Et son activation ne provoque aucune erreur d'exécution

  @cas:test_job_cards
  Scénario: Les offres sont affichées sous forme de cartes
    Quand j'attends le chargement des cartes d'offres
    Alors au moins une carte est visible à l'écran
    Et le nombre de cartes visibles est relevé

  @cas:test_top_matches
  Scénario: Les meilleures correspondances affichent un score
    Quand j'attends l'affichage des meilleures correspondances
    Alors chaque carte de correspondance expose un score
    Et les premiers scores sont relevés dans le résultat

  @cas:test_pagination
  Scénario: La pagination permet d'atteindre la page suivante
    Quand j'attends l'affichage des boutons de page
    Alors si un bouton « › » actif existe, je l'active sans erreur
    Et s'il n'y a qu'une seule page, le scénario réussit sans action

  @cas:test_budget_filter
  Scénario: Le filtre budget minimum écarte les offres sous le seuil
    Étant donné que la barre de filtres contient un bouton « ≥ 600 € »
    Quand j'active ce bouton et que j'attends la fin du filtrage
    Alors aucune carte visible dont le budget est renseigné n'affiche un TJM inférieur à 600
    Et au moins une carte dont le budget est renseigné reste affichée
    Et toutes les cartes portant un budget connu sont cohérentes avec le seuil retenu

  @cas:test_dismiss_button_does_not_navigate
  Scénario: Le bouton de rejet masque une offre sans quitter la page
    Quand j'attends l'affichage d'un bouton de rejet ✕
    Et que je relève l'adresse courante
    Alors après activation, l'adresse de la page ne change pas
    Et si aucun bouton de rejet n'existe, le scénario réussit sans action

  @cas:test_apply_button_is_only_clickable_link
  Scénario: Seul le lien de candidature ouvre la page de l'offre
    Quand je clique sur le corps d'une carte d'offre
    Alors l'adresse courante ne change pas
    Et seul l'élément de candidature est un lien cliquable vers l'offre
