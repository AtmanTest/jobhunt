# Économie de tokens de la chaîne d'agents

Un run traverse 7 appels LLM. Sans discipline, le coût vient du **contexte
renvoyé** à chaque étape, pas de la qualité des réponses. Règles appliquées.

## 1. Le prompt de rôle est en tête, et ne bouge pas

Le prompt de rôle (`prompts/*.md`) est le message `system`, toujours identique
d'un run à l'autre. Placé **en premier**, il forme un préfixe stable : c'est
exactement ce que le cache de contexte des fournisseurs facture au tarif
dégradé. Un préfixe qui change à chaque appel ne peut jamais être mis en cache.

## 2. Chaque étape ne reçoit que l'artefact précédent

`PO` reçoit le ticket. `Spec Review` reçoit la production du PO. `Architecte`
reçoit la production du PO. Jamais l'historique complet, jamais le ticket
redistribué à tout le monde. Un ticket renvoyé 6 fois se paie 6 fois.

## 3. Les artefacts passent par des fichiers, pas par le prompt

Les spécifications sont écrites dans `specs/<issue>/` **dans le dépôt**. Les
étapes suivantes les lisent à la demande au lieu de les traîner dans chaque
requête. Le dépôt est la mémoire de la chaîne.

## 4. `max_tokens` est plafonné par rôle

| Rôle | Plafond | Pourquoi |
|---|---|---|
| PO | 1 200 | des critères, pas un roman |
| Spec Review | 600 | un verdict et des bloquants |
| Architecte | 900 | des décisions |
| QA | 1 500 | les cas de test |
| Dev | 4 000 | du code |
| Fix | 2 000 | une correction ciblée |
| QA Review | 800 | un verdict motivé |

Un plafond haut laisse le modèle produire du remplissage facturé.

## 5. L'arborescence est transmise en noms seuls

L'agent Dev doit savoir **où** il écrit, pas connaître le code. On lui envoie la
liste des chemins (plafonnée à 400, avec mention de troncature), jamais le
contenu des fichiers.

## 6. Ce qui ne doit pas passer par un LLM n'y passe pas

Découpage des artefacts, nommage de branche, calcul d'empreinte, comptage des
tentatives, verdict de CI, étiquetage du ticket : **code déterministe**. Les
LLM ne sont appelés que là où il y a du jugement — rédiger, décider, corriger.

## 7. La boucle de correction est bornée

Trois tentatives, puis arrêt et remontée du blocage. Une boucle non bornée est
le poste de dépense qui s'emballe sans que personne ne le voie.

## 8. Le routage du modèle est explicite

`MODELE` dans `workflows/build_wf2.py` associe un modèle à chaque rôle. Les
étapes mécaniques peuvent basculer sur un modèle local (coût nul) sans toucher
au reste de la chaîne.

---

**Vérifier l'effet réel** : la table `runs` du projet Supabase journalise
`tokens_in`, `tokens_out` et `cost_usd` par étape. Comparer un run avant/après
un changement de prompt est le seul juge.
