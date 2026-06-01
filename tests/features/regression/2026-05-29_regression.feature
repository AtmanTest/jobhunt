@regression @bugs
Feature: Tests de régression — Session 2026-05-29
  En tant que QA de JobHunt
  Je veux vérifier que les bugs corrigés restent fermés

  Background:
    Given le serveur Flask tourne sur localhost:5050

  # ─── BUG 1: Doublons dans JOBS DU JOUR ──────────────────
  @bug-D1 @critical
  Scenario: JOBS DU JOUR ne contient pas de doublons
    When je charge la page d'accueil
    Then les 3 premiers éléments de JOBS DU JOUR sont uniques
    And aucun titre d'offre ne se répète dans JOBS DU JOUR

  # ─── BUG 2: Doublons dans TOP MATCHES CV ───────────────
  @bug-D2 @critical
  Scenario: TOP MATCHES CV ne contient pas de doublons
    Given la base a des offres de sources multiples
    When je charge la page d'accueil
    Then chaque offre dans TOP MATCHES CV apparaît une seule fois
    And aucun score de match identique avec le même titre+entreprise ne se répète

  # ─── BUG 3: Doublons dans save_jobs (title+company) ─────
  @bug-D3 @critical
  Scenario: Deux offres même titre + même boîte mais URL différente = doublon
    Given la DB contient {"title": "QA Engineer", "company": "Acme", "url": "https://a.com/1"}
    When on insère {"title": "QA Engineer", "company": "Acme", "url": "https://b.com/2"}
    Then 0 nouvelle ligne est insérée (dédoublonnée par titre+entreprise)

  # ─── BUG 4: Stats page 404 ──────────────────────────────
  @bug-S1 @medium
  Scenario: Page Stats accessible
    When je navigue vers /stats
    Then le code HTTP est 200
    And la page affiche des statistiques d'offres

  # ─── BUG 5: LinkedIn scraper navigation ──────────────────
  @bug-L1 @medium
  Scenario: LinkedIn scraper navigue via URL directe (pas JS eval)
    Given Chrome est ouvert sur une page quelconque
    When le scraper appelle chrome_navigate("https://linkedin.com/jobs/...")
    Then l'onglet actif de Chrome est sur linkedin.com
    And le titre contient "Offres d'emploi pour"

  # ─── BUG 6: LinkedIn scraper dédup par titre+boîte ──────
  @bug-L2 @medium
  Scenario: LinkedIn scraper ignore les doublons entre recherches
    Given la recherche "QA test" et "test automation" renvoient le même job
    When le scraper LinkedIn s'exécute
    Then linkedin_jobs.json contient 1 occurrence de ce job (pas 2)
    And le count total < somme des counts de chaque recherche

  # ─── BUG 7: LinkedIn scraper keywords trop stricts ───────
  @bug-L3 @medium
  Scenario: Les keywords LinkedIn couvrent les titres français
    Given le scraper LinkedIn a les nouveaux keywords
    When une recherche est effectuée avec "testeur logiciel"
    Then les résultats incluent des offres intitulées "Testeur ..."
    And les résultats incluent "Chef tests QA"

  # ─── BUG 8: Vision NVIDIA 401 ───────────────────────────
  @bug-V1 @high
  Scenario: Vision auxiliaire NVIDIA authentifiée
    Given le config.yaml a auxiliary.vision.api_key
    When Hermes appelle vision_analyze
    Then le status n'est pas 401
    And l'image est analysée avec succès

  # ─── FONCTIONNEL: Onglets pays ───────────────────────────
  @functional @medium
  Scenario: Filtre France affiche les offres françaises
    Given le dashboard affiche 500 offres "Tous"
    When je clique sur "🇫🇷 France"
    Then seules les offres localisées en France sont affichées
    And le compteur passe à 100

  @functional @medium
  Scenario: Filtre LinkedIn affiche les offres LinkedIn
    Given le dashboard a un compteur LinkedIn à 36
    When je clique sur "🔗 LinkedIn"
    Then seules les offres de source LinkedIn sont affichées

  @functional @medium
  Scenario: Pagination fonctionne
    Given j'ai 500 offres chargées
    When je clique sur page 2
    Then les offres de la page 2 s'affichent
    And le bouton page 1 devient accessible

  # ─── FONCTIONNEL: Postuler / Sauvegarder ──────────────────
  @functional @medium
  Scenario: Apply ↗ ouvre le lien externe
    Given une carte d'offre avec un lien Apply ↗
    When je clique sur Apply ↗
    Then un nouvel onglet s'ouvre vers l'URL de l'offre

  # ─── FONCTIONNEL: Pages accessibles ──────────────────────
  @navigation @low
  Scenario Outline: Toutes les pages sont accessibles
    When je navigue vers <page>
    Then le code HTTP est 200
    Examples:
      | page          |
      | /             |
      | /cv           |
      | /qa           |
      | /marche-qa    |
      | /about        |
      | /changelog    |

  # ─── FONCTIONNEL: API endpoints ──────────────────────────
  @api @medium
  Scenario Outline: Les API retournent du JSON valide
    When je requête <endpoint>
    Then le status est 200
    And la réponse est du JSON valide
    Examples:
      | endpoint                     |
      | /api/jobs                    |
      | /api/stats                   |
      | /api/linkedin/jobs           |
      | /api/jobs/saved              |
      | /api/jobs/applied            |
