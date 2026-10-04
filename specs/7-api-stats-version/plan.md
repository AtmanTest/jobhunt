<!-- Artefact de la chaîne d'agents — ticket #7 : [BUG] /api/stats n'expose pas la version du produit
     Rôle : Architecte · Contrat : prompts/architecte.md
     Chaque étape ne reçoit que l'artefact de l'étape précédente. -->

## Décisions

- **D1 — Source unique de la version, exposée par `/about` et réutilisée par `/api/stats`.**
  *Raison* : AC-03 impose une égalité stricte ; H1 fait de `/about` la source de vérité. Deux calculs indépendants créeraient une divergence structurelle.
  *Alternative écartée* : dupliquer la logique de résolution de version dans le handler `/api/stats` (rejetée : double source de vérité, risque explicitement identifié).

- **D2 — Résolution de la version au démarrage, stockée en mémoire pour la durée de vie de l'instance.**
  *Raison* : H2 (pas d'appel réseau à la requête) et H4 (stabilité sur une instance). Satisfait AC-04 sans dépendance externe.
  *Alternative écartée* : lire la version à chaque requête depuis le système de fichiers / variable d'environnement (rejetée : coût inutile, risque de dérive si la source change en cours de vie).

- **D3 — Ajout additif de la clé `version` dans l'objet JSON existant, sans enveloppe ni renommage.**
  *Raison* : H3 (ajout non cassant) et AC-05/AC-06 (aucune modification des clés existantes, JSON toujours valide).
  *Alternative écartée* : introduire une enveloppe `{ data, meta }` (rejetée : hors périmètre explicite — « pas d'évolution du format de réponse »).

- **D4 — Valeur renvoyée telle quelle, sans normalisation (trim, préfixe, casse).**
  *Raison* : AC-03 impose l'égalité stricte avec `/about` ; les cas limites interdisent toute transformation. Le `trim` d'AC-02 n'est qu'un critère de validation du test, pas une transformation appliquée à la réponse.
  *Alternative écartée* : normaliser en sortie (rejetée : casserait AC-03 en cas de valeur atypique et masquerait un défaut de la source).

- **D5 — Une valeur vide ou blanche constitue un échec explicite, jamais un succès silencieux.**
  *Raison* : cas limite documenté ; AC-02 exige explicitement qu'un tel cas fasse échouer le test.
  *Alternative écartée* : renvoyer `null` ou omettre la clé (rejetée : contredit AC-01 et masque le défaut).

- **D6 — Aucune dépendance nouvelle.**
  *Raison* : l'ajout d'une clé à une réponse existante ne le justifie aucune. Contrainte de dépôt respectée.
  *Alternative écartée* : bibliothèque de gestion de version de build (rejetée : hors périmètre, nouvelle dépendance non justifiée).

## Impact données

- Aucune modification de schéma, aucune colonne, aucune contrainte, aucune migration.
- La version n'est pas une donnée métier : elle n'est ni stockée ni requêtée.
- Invariants respectés : migrations versionnées (sans objet ici), aucune donnée personnelle introduite.

## Impact interfaces

- **Route** : `GET /api/stats` — signature, méthode, chemin inchangés.
- **Contrat de réponse** : ajout d'une clé `version` au premier niveau de l'objet.
  - type : `string`
  - non nulle, non vide après trim (validation)
  - strictement égale à la valeur exposée par `/about`
  - autres clés (`by_contract_type`, `by_seniority`, `jobs_per_day`, `salary_avg`, `salary_min_val`, `salary_max_val`, `salary_median`, `top_locations`, `top_stacks`) : présentes, nom et type inchangés, valeurs inchangées sur un jeu de données identique.
- **Cas d'erreur** : aucun nouveau code d'erreur. Le comportement en l'absence de données métier reste inchangé ; `version` reste présente et non vide (cas limite documenté).
- **`/about`** : aucun changement d'interface ni de source.
- **Contrat de version de `/about`** : la consommation par `/api/stats` impose que `/about` expose sa version via un mécanisme **importable** par le reste du service (injection au démarrage), et non uniquement par rendu HTML. C'est une contrainte de conception dérivée de D1, à vérifier par l'implémentation.

## Testabilité

- **AC-01** : test d'assertion de présence de la clé `version` dans l'objet JSON de `GET /api/stats`. Observable directement dans la réponse HTTP.
- **AC-02** : assertion que `response.version` est de type `string` et que `response.version.trim().length > 0`. Le cas limite « chaîne vide ou blanche » devient un test négatif explicite : ce test **doit échouer** si la source renvoie une telle valeur.
- **AC-03** : test qui récupère la version exposée par `/about` (via la même source que la résolution au démarrage) et vérifie l'égalité stricte (`===`, pas d'égalité insensible à la casse ni de trim). Doit être exécuté sur la même instance que l'appel `/api/stats`.
- **AC-04** : deux appels séquentiels sur la même instance, assertion d'égalité des valeurs. Test sur une même instance uniquement (cf. risque de non-déterminisme inter-instances).
- **AC-05** : capture d'une **réponse de référence** avant correctif sur un jeu de données figé ; après correctif, sur le même jeu de données, assertion que l'ensemble des clés historiques est identique et que leurs valeurs sont profondément égales (égalité structurelle, pas seulement de clés).
- **AC-06** : test que la réponse est un JSON valide (parsing complet sans erreur, pas de troncature) — observable via désérialisation stricte par le client de test.
- **Mesure du Product Goal** : test de non-régression qui, sur l'ensemble des appels à `/api/stats`, vérifie la conjonction AC-01 et AC-02 et calcule un taux de conformité (cible : 100 %).
- Contraintes de test respectées : jeu de données de test sans donnée personnelle, secret de version hors dépôt (variable d'environnement injectée en CI), pas de dépendance réseau externe.

## Risques

- **Double source de version** — mitigation : D1 (export unique consommé par `/about` et au démarrage du service). Test AC-03 en garde-fou.
- **Validation stricte côté consommateur externe (liste blanche de clés)** — mitigation : aucune au niveau produit ; l'ajout est non cassant en JSON. Documenter l'ajout dans le contrat d'API. AC-05 ne couvre que la non-régression, pas la tolérance externe (risque résiduel accepté).
- **Valeur de version non déterministe en build** — mitigation : AC-04 restreint à une même instance ; H4 assumée. Aucune garantie inter-instances, conformément au périmètre.
- **Version non résolue dans un environnement donné** — mitigation : D5 (échec explicite en test), AC-02 fait échouer le test au lieu de produire un faux positif.
- **Source de `/about` non importable par le service** — mitigation : contrainte de conception exposée dans « Impact interfaces » ; l'implémentation doit factoriser la résolution.
- **Risques IA génératives et données personnelles** : sans objet (cf. analyse fournie).

## Hors périmètre technique

- Modification de tout autre champ de `/api/stats` (nom, type, valeur, format).
- Création d'un endpoint dédié à la version ou de tout nouvel endpoint.
- Modification de `/about`, de son rendu ou de sa source de version.
- Exposition d'autres métadonnées de build (commit, date, environnement).
- Évolution du format de réponse (enveloppe, pagination, versionnage d'API).
- Modification de schéma, migration de base de données.
- Ajout de dépendance.
- Gestion du non-déterminisme inter-instances de la version.
- Adaptation des validateurs de consommateurs externes en liste blanche.