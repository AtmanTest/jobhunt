# Porte 6 — IA au service du test : usage réel et limites

Le syllabus (ch. 11) traite l'IA **comme outil du testeur**, avec ses limites. Ce
document journalise l'usage effectif sur ce PoC, sans complaisance.

## Ce qui a été produit avec l'aide d'une IA

| Activité | Outil | Contrôle humain appliqué |
|---|---|---|
| Rédaction du premier jet de la suite `tests/test_ct_ai_gates.py` | agent IA | relecture ligne par ligne, exécution réelle, chaque assertion validée ou corrigée |
| Génération du corpus étiqueté (24 offres synthétiques) | agent IA | **règle d'étiquetage écrite avant** la génération, puis appliquée à la main offre par offre |
| Extraction du syllabe CT-AI en fichiers de référence | agent IA | comparaison automatique des objectifs d'apprentissage et des définitions au PDF d'origine ; zones non extraites déclarées |
| Détection des défauts (casse, sous-chaîne, marchés) | agent IA + exécution | chaque défaut reproduit par un test **avant** correction, puis revérifié après |

## Ce que l'IA a produit et qui a dû être corrigé

| Production IA | Défaut | Traitement |
|---|---|---|
| Assertions de valeurs limites sur le TJM | écrites d'après l'ancien comportement (marché français par défaut) | assertion corrigée **et** attente documentée : un marché inconnu ne produit plus de comparaison |
| Test de stabilité du classement | le test rejouait un tri naïf, pas la règle réelle de l'application | test réécrit sur la règle documentée (score décroissant, identifiant croissant) |
| Corpus étiqueté | risques de biais de génération (formulations trop typiques) | limite déclarée en porte 3 ; passage à un corpus réel échantillonné requis avant tout relèvement de seuil |

**Aucun test n'a été accepté sur la seule affirmation d'un modèle.** Les tests qui ont
révélé des défauts l'ont fait par **exécution réelle** ; les tests qui passaient pour de
mauvaises raisons ont été corrigés.

## Limites et risques assumés de l'aide IA

- **Biais du modèle** : les cas générés ressemblent au style des offres francophones
  déjà connues → le corpus sous-représente les offres anglophones et les intitulés
  locaux. Conséquence directe sur la mesure du rappel.
- **Dépendance aux données** : la qualité de la suite dépend de la qualité du corpus,
  laquelle dépend d'un jugement humain sur ce qu'est une offre « pertinente ».
- **Faux positifs** : la sur-génération de tests est un risque réel (tests redondants qui
  donnent une fausse impression de couverture). Critère appliqué : chaque test doit
  porter une propriété ou un risque identifié, sinon il est supprimé.
- **Oracle non vérifié** : une IA ne peut pas servir d'oracle de pertinence. Le seul
  oracle admis ici est l'étiquetage humain du corpus.

## Usage prévu (et non fait) dans l'application elle-même

Le projet utilise déjà un modèle de langue pour **enrichir** les offres (technologies,
séniorité, contrat, remote, fourchette). Conformément au ch. 11 :

- ces valeurs enrichies sont traitées comme une **source de variabilité à absorber**
  (parsing tolérant, alias), jamais comme une vérité ;
- aucune donnée produite par le modèle ne déclenche d'action automatique (pas de
  candidature, pas de rejet d'offre) : l'humain décide ;
- toute généralisation de l'usage du modèle (génération de lettre, tri automatique des
  offres) devra être accompagnée d'un taux d'erreur mesuré et d'une revue traçable.

## Traçabilité (ch. 11, exigence de revue)

Pour chaque usage d'IA dans la production de ce PoC : activité, outil, contrôle humain
appliqué, défaut constaté et correction. C'est le tableau ci-dessus. Un test produit par
IA est un **candidat**, jamais un résultat.
