# Porte 4 — Plan de test : spécification, niveaux, données, dérive, environnement

## Spécification du composant (ch. 7)

| Élément | Valeur |
|---|---|
| Composant | `matcher.match_job_to_cv(job, cv_skills=None) -> (score:int 0-100, matched:list[str])` |
| Entrées | dictionnaire d'offre : `title`, `description`, `tags`, `salary`, `remote_type`, `freelance_status` (+ `location` pour le TJM) |
| Sortie | score borné 0-100, liste des compétences reconnues (traçabilité) |
| Dépendances | lexique `CV_SKILLS` (34 entrées, dont 5 équivalents français), `TJM_RANGES` (5 marchés) |
| Version du modèle | pas de modèle : version du code = version du comportement. Toute évolution du lexique change les classements → à tracer dans `CHANGELOG.md` |
| Limites connues | détection lexicale, aucune compréhension sémantique ; sensible au vocabulaire employé par la source |

## Niveaux de test (ch. 7.2)

| Niveau | Objet | Où |
|---|---|---|
| Données d'entrée | forme et validité des offres transmises | porte 2 + `test_robustesse_aux_champs_absents_ou_invalides` |
| Modèle / algorithme | score, bornes, traçabilité des compétences | `test_niveau_fonction_score_borne_et_traçable` |
| Composant | chaîne score + TJM + fraîcheur telle qu'utilisée par l'index | `test_niveau_composant_pipeline_complet` |
| Intégration | page d'accueil servie avec le moteur actif | `test_niveau_integration_page_accueil` |
| Système | parcours complet scrapers → base → page | hors périmètre de ce jeu (tests BDD existants) |
| Acceptation | seuils de la porte 3 | `TestPorte3Metriques` |

## Données de test (ch. 7.3)

- **Corpus étiqueté** verrouillé par empreinte : sert aux décisions d'acceptation.
- **Fixtures techniques** (`sample_jobs.json`) : formes réelles, non utilisées pour mesurer.
- **Entrées adverses** : emoji massifs, texte bidirectionnel, injection HTML,
  répétition de mots-clés, alphabet non latin.
- **Valeurs limites du salaire** : plage avec tiret, « à », « EUR », TJM explicite,
  montant à un chiffre, montant démesuré, champ vide, champ absent.
- **Marchés** : les 5 marchés de référence + un marché non couvert (Berlin) + un champ vide.

## Défis spécifiques traités (ch. 8)

| Défi | Traitement |
|---|---|
| Non-déterminisme | le classement est **déterministe** (200 exécutions identiques) ; le non-déterminisme réel est en amont, dans l'enrichissement LLM → traité par la tolérance aux alias |
| Auto-apprentissage | nul en ligne ; risque reporté sur les données d'entrée et les versions de code |
| Systèmes autonomes | aucun : pas de décision automatique de candidature |
| Biais | biais d'échantillonnage du lexique (vocabulaire francophone/anglais technique) → mesuré par le rappel, pas masqué |
| Complexité | chaîne linéaire de 3 étapes, chaque étape testable séparément |
| Explicabilité | `matched_skills` + détail du TJM = justification offerte par offre |
| Oracle | oracle **expert humain** sur corpus étiqueté (pas d'oracle automatique possible : la « vérité » d'une pertinence est un jugement) |
| Sûreté | pas d'enjeu physique ; enjeu de perte d'opportunité, traité par le seuil de rappel |

## Dérive (ch. 7.6)

- **Dérive du concept** : le marché de la QA change (nouvelles technologies : IA,
  MLOps, tests de systèmes IA ; nouveaux intitulés). Le lexique doit être revu
  périodiquement — **déclencheur** : baisse du taux d'offres à score ≥ 40, ou apparition
  d'intitulés récurrents non reconnus.
- **Dérive de plateforme / de source** : une source peut changer son format de date,
  de salaire ou de champ remote → les contrôles de la porte 2 sont rejoués à chaque
  évolution de scraper.
- **Dérive du modèle amont** : le fournisseur d'enrichissement peut changer de version
  sans préavis → l'invariance aux alias de valeurs métier est la protection retenue.
- **Non couvert** : aucun suivi automatique de la performance en production. C'est la
  limite assumée de ce PoC (voir « sujets ouverts » ci-dessous).

## Environnement (ch. 10)

| Élément | Valeur |
|---|---|
| Environnement d'exécution des tests | Python 3.12, pytest 9.0.3, Flask 3.1.3, base SQLite en mémoire (`test_db`) |
| Isolation | aucune écriture en base de production ; le dépôt ne contient aucune donnée d'exploitation |
| Reproductibilité | corpus verrouillé par SHA-256, fixtures versionnées, aucun appel réseau dans les tests du moteur (l'API d'enrichissement est simulée par `responses`) |
| Environnement virtuel / jumeau numérique | non nécessaire ici : pas de système embarqué, pas d'interaction capteur. Le « simulateur » utilisé est la base en mémoire et les fixtures |
| Limite | les tests d'intégration de l'index s'appuient sur la base en mémoire : le comportement avec 1 000+ offres réelles n'est pas couvert par ces tests (couvert par les tests BDD existants) |

## Sujets ouverts (à traiter, explicitement non faits ici)

1. **Suivi de dérive en production** : enregistrer chaque semaine la distribution des
   scores et la part d'offres ≥ 40, alerter en cas de rupture. Nécessite un stockage
   d'historique (aujourd'hui absent).
2. **Corpus d'évaluation élargi** : passer de 24 à 100+ offres réelles étiquetées
   (échantillonnées sur plusieurs sources et plusieurs pays) avant de relever un seuil.
3. **Enrichissement versionné** : journaliser le modèle et la date de chaque appel
   d'enrichissement pour rendre une décision de classement rejouable.
4. **Test A/B** (ch. 9.4) : comparer deux versions de seuil sur un flux réel, avec
   indicateur de clics/candidatures. Non applicable aujourd'hui : aucun indicateur
   d'usage collecté côté utilisateur.
