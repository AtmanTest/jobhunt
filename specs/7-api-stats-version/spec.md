<!-- Artefact de la chaîne d'agents — ticket #7 : [BUG] /api/stats n'expose pas la version du produit
     Rôle : PO (PSPO I & II) · Contrat : prompts/po.md
     Chaque étape ne reçoit que l'artefact de l'étape précédente. -->

## Objectif produit

Contribuer au Product Goal « rendre JobHunt observable et diagnostiquable en production par ses consommateurs » : toute réponse d'API doit permettre d'identifier sans ambiguïté la version du produit qui l'a produite, au même titre que la page /about.

## Valeur attendue

Un consommateur de `GET /api/stats` (supervision, support, intégration) peut identifier la version du produit en un seul appel, sans consulter /about ni le dépôt.

Mesure : sur `GET /api/stats`, la clé `version` est présente et sa valeur est une chaîne non vide strictement égale à celle exposée sur /about ; le taux de réponses conformes sur ce point est de 100 % sur l'ensemble des appels du test de non-régression.

## Hypothèses

- H1 : /about expose déjà une version du produit, et cette valeur est la source de vérité unique — la valeur renvoyée par `/api/stats` doit lui être identique (hypothèse assumée : il n'existe qu'une seule notion de « version du produit »).
- H2 : la version est connue du service au démarrage, sans dépendance à un appel réseau externe au moment de la requête.
- H3 : les consommateurs actuels de `/api/stats` tolèrent l'ajout d'une clé supplémentaire (ajout non cassant).
- H4 : la valeur de version est stable pendant toute la durée de vie d'une instance démarrée.

## Critères d'acceptation

- AC-01 — Étant donné le service démarré, quand j'appelle `GET /api/stats`, alors la réponse contient la clé `version`.
- AC-02 — Étant donné le service démarré, quand j'appelle `GET /api/stats`, alors la valeur associée à `version` est une chaîne de caractères non vide après suppression des espaces de début et de fin.
- AC-03 — Étant donné le service démarré, quand j'appelle `GET /api/stats` et que je lis la version exposée sur /about, alors les deux valeurs sont strictement égales.
- AC-04 — Étant donné le service démarré, quand j'appelle `GET /api/stats` deux fois de suite, alors la valeur de `version` est identique entre les deux réponses.
- AC-05 — Étant donné le service démarré, quand j'appelle `GET /api/stats`, alors l'ensemble des clés déjà présentes avant le correctif (by_contract_type, by_seniority, jobs_per_day, salary_avg, salary_min_val, salary_max_val, salary_median, top_locations, top_stacks) est toujours présent, et leurs valeurs sont inchangées par rapport à une réponse de référence obtenue avant correctif sur le même jeu de données.
- AC-06 — Étant donné le service démarré, quand j'appelle `GET /api/stats`, alors la réponse est un objet JSON valide (elle n'est ni rejetée ni tronquée par l'ajout de la clé).

## Hors périmètre

- Toute modification d'un autre champ de `/api/stats` (nom, type, valeur, format).
- Création d'un nouvel endpoint, y compris un endpoint dédié à la version.
- Modification de /about ou de sa source de version.
- Exposer d'autres métadonnées de build (commit, date de build, environnement).
- Évolution du format de réponse (enveloppe, pagination, versionnage d'API).

## Cas limites

- La version du produit est une chaîne vide ou composée uniquement d'espaces : la réponse ne satisfait pas AC-02 ; le test doit échouer, ce comportement est un défaut de la source de version et non un cas à tolérer.
- La version contient des caractères non ASCII ou des préfixes (par ex. `v1.2.3`, suffixe de pré-release) : la valeur est renvoyée telle quelle, sans normalisation, pour préserver l'égalité avec /about (AC-03).
- Le service tourne sans jeu de données métier (aucune offre) : `version` reste présente et non vide ; les autres clés peuvent être vides sans invalider AC-01, AC-02, AC-03.
- Appel de `GET /api/stats` sur une instance démarrée dans un environnement où la version n'est pas résolue : la réponse reste un JSON valide et l'absence ou le vide de `version` est traité comme un échec de test, jamais comme un succès silencieux.
- Appels concurrents répétés : la valeur de `version` reste identique (AC-04) et aucune réponse n'est malformée.

## Risques

- Risque de double source de vérité : si la version est calculée indépendamment pour /about et pour /api/stats, les deux valeurs peuvent diverger et AC-03 devient instable. Mitigation attendue au niveau conception (non prescrite ici).
- Risque de rupture de contrat pour des consommateurs validant strictement la liste des clés de `/api/stats` ; l'ajout est non cassant en JSON mais un validateur en liste blanche échouerait. AC-05 couvre la non-régression des clés existantes, pas la tolérance des consommateurs externes.
- Risque de valeur de version non déterministe en environnement de build (version dynamique, horodatage) : rendrait AC-04 instable entre deux instances ; AC-04 ne porte donc que sur une même instance démarrée.
- Risques propres à l'IA générative : sans objet ici — la demande ne touche à aucune sortie de modèle (pas d'hallucination, de biais ni de non-déterminisme de génération à couvrir).
- Risque de données personnelles : sans objet — aucune donnée personnelle n'est introduite par cette clé.

## Questions ouvertes

- Aucune question bloquante : les critères AC-01 à AC-06 sont testables en l'état.
- (non bloquante) Le nom exact de la clé est-il imposé comme `version` en minuscules, ou un autre libellé est-il acceptable ? Choix retenu : `version` en minuscules, tel que demandé dans le résultat attendu et dans le test de non-régression fournis.
- (non bloquante) La version doit-elle refléter la version applicative ou inclure le commit ? Choix retenu : uniquement la version du produit, la demande excluant explicitement les autres métadonnées de build.