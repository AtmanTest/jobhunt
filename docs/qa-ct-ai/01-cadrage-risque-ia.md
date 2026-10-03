# Porte 1 — Cadrage du risque IA

## Système concerné

`matcher.py` + l'enrichissement (`auto_enrich.py`, API LLM) appelés par `app.index`.

Chaîne : offre brute (scrapers) → enrichissement LLM (technologies, séniorité, type de
contrat, remote, fourchette) → **`match_job_to_cv`** → score 0-100 → `analyze_tjm` →
classement affiché (`top_matches`, `jobs_of_day`, `hot_picks`, priorité).

## Classification (syllabus ch. 1)

- **IA faible et étroite** : une seule tâche, à savoir décider si une offre est pertinente
  pour un profil de test logiciel freelance et à quel point. Aucune IA générale, aucune
  autonomie de décision : le score ordonne, l'humain postule.
- Deux composants distincts dans la chaîne, avec deux natures de risque différentes :
  - **enrichissement** = modèle de langue appelé par API (non déterministe, non versionné
    côté fournisseur, données inconnues) ;
  - **classement (`matcher.py`)** = algorithme déterministe à base de règles et de mots-clés.
    C'est le composant dont la sortie est **opposable** : c'est lui qui décide ce qui
    remonte à l'écran.
- Mode d'approvisionnement : **modèle pré-entraîné tiers (AIaaS)** pour l'enrichissement,
  développement propre pour le classement → risques de dépendance fournisseur, de
  changement de version silencieux et de données d'entraînement inconnues.

## Les 8 caractéristiques de qualité spécifiques à l'IA (ch. 2) appliquées ici

| Caractéristique | Traduction dans ce système | Où c'est testé |
|---|---|---|
| Flexibilité / adaptabilité | le score doit rester stable quand la **forme** de l'offre change (casse, accents, espaces, ponctuation, ordre des phrases) | porte 6, MR-01 à MR-07 |
| Autonomie | nulle : aucune décision automatique de candidature. L'humain reste dans la boucle | porte 1 (conception) |
| Évolution (auto-apprentissage) | le classement n'apprend pas en ligne : il est figé par version de code. Le risque d'évolution est donc dans les **données d'entrée** (nouveaux formats de sources) | porte 4 |
| Biais | biais d'échantillonnage : le lexique du profil est calé sur un marché (France, freelance, anglais technique) et peut manquer des intitulés locaux | porte 3 (rappel par classe) |
| Éthique | les offres sont des données publiques ; aucune donnée personnelle du candidat ne doit entrer dans le dépôt | porte 2 (balayage e-mail/téléphone) |
| Effets secondaires / piratage de récompense | une offre qui empile les mots-clés (« QA, test, automation, TJM ») pourrait dominer le classement sans être réellement pertinente | porte 5, bornage du bourrage |
| Transparence / interprétabilité / explicabilité | le score est explicable : `matched_skills` liste les compétences reconnues, et le TJM affiche le détail du calcul. **Exigence** : toute remontée de classement doit être justifiable offre par offre | porte 4, traçabilité du score |
| Sûreté | pas d'enjeu de sécurité physique ; l'enjeu est la **perte d'opportunité** (une offre pertinente non remontée) et l'erreur d'affichage | porte 3 (rappel) |

## Risques identifiés et atténuations

| # | Risque | Effet | Atténuation retenue |
|---|---|---|---|
| R1 | Une offre pertinente n'est jamais remontée | perte d'opportunité invisible | seuil de pertinence verrouillé + test « aucune offre pertinente à plus de 10 points sous le seuil » |
| R2 | Une offre hors sujet remonte en tête | perte de temps, perte de confiance | marge de score maximale pour les offres hors sujet |
| R3 | Le classement dépend de la source (casse, format) | classement instable d'un cycle à l'autre | normalisation, relations métamorphiques |
| R4 | Le classement dépend de l'ordre en base | deux affichages différents sans changement de données | départage déterministe par identifiant |
| R5 | L'enrichissement LLM change de version | valeurs métier inattendues (`fully_remote`) | tolérance aux alias de valeurs + test dédié |
| R6 | Comparaison de TJM contre le mauvais marché | décision financière faussée | marché inconnu → aucune comparaison plutôt qu'une comparaison fausse |
| R7 | Fuite de données personnelles via le dépôt ou le site | préjudice direct | test permanent de balayage (e-mail, téléphones), corpus synthétique |
| R8 | Le corpus d'évaluation est modifié sans que les métriques soient revues | faux sentiment de qualité | empreinte SHA-256 du corpus verrouillée par un test |

## Périmètre exclu (assumé)

- La qualité intrinsèque du modèle d'enrichissement tiers : non testable (fournisseur
  fermé, version non épinglée). Traité comme une **source de variabilité** à absorber,
  pas comme un composant dont on prouve la justesse.
- Les tests d'interface visuelle (Playwright) : hors de cette porte.
