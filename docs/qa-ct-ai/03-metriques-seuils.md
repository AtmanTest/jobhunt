# Porte 3 — Métriques de performance fonctionnelle et seuils verrouillés

## Choix de la métrique (ch. 5)

Le composant rend une **décision binaire** (offre pertinente / non pertinente) à partir
d'un score continu. Les quatre situations de la matrice de confusion n'ont pas le même
coût :

| Situation | Effet réel | Coût |
|---|---|---|
| Faux négatif (offre pertinente sous le seuil) | la mission n'est jamais vue | **élevé** : perte d'opportunité silencieuse |
| Faux positif (offre hors sujet au-dessus du seuil) | quelques minutes perdues à lire | faible |

Conséquence : le **rappel** est la métrique directrice ; la précision est un garde-fou
(une précision qui s'effondre rend la liste inutilisable). La métrique composite retenue
est le **F1**, complétée par l'exactitude pour la vue d'ensemble. L'exactitude seule est
insuffisante : avec 50 % d'offres hors sujet, un classifieur qui dit « tout est pertinent »
afficherait 50 % d'exactitude.

Seuil de décision retenu : **score ≥ 40 / 100**.

## Résultat sur le corpus verrouillé (24 offres étiquetées, 12/12)

| Seuil | Précision | Rappel | F1 | Exactitude | TP | FP | FN | TN |
|---|---|---|---|---|---|---|---|---|
| 30 | 0,706 | 1,000 | 0,828 | 0,792 | 12 | 5 | 0 | 7 |
| **40** | **1,000** | **0,917** | **0,957** | **0,958** | **11** | **0** | **1** | **12** |
| 50 | 1,000 | 0,583 | 0,737 | 0,792 | 7 | 0 | 5 | 12 |
| 60 | 1,000 | 0,250 | 0,400 | 0,625 | 3 | 0 | 9 | 12 |
| 70 | 1,000 | 0,083 | 0,154 | 0,542 | 1 | 0 | 11 | 12 |

Détail des scores (offre = score / étiquette) :

```
g01=71/1  g08=68/1  g06=60/1  g02=59/1  g05=59/1  g03=51/1  g04=51/1  g10=49/1
g11=48/1  g09=47/1  g12=41/1  g07=39/1 | n10=36/0  n05=35/0  n02=34/0  n01=33/0
n04=31/0  n06=25/0  n09=25/0  n03=20/0  n07=20/0  n08=20/0  n11=20/0  n12=20/0
```

- Aucune offre hors sujet n'atteint 40 : la précision au seuil est parfaite sur ce corpus.
- 1 seul faux négatif : `g07` (Tester Mobile iOS/Android, 39) — manqué de 1 point.
- Séparation nette : la meilleure offre hors sujet plafonne à 36, la dernière offre
  pertinente est à 39. Marge très faible : c'est le point de fragilité à surveiller.

## Seuils verrouillés (non-régression)

| Constante du test | Valeur | Mesure de référence |
|---|---|---|
| `SEUIL_PERTINENCE` | 40 | optimum F1 sur le corpus |
| `PRECISION_MIN` | 0,95 | mesuré 1,000 |
| `RAPPEL_MIN` | 0,85 | mesuré 0,917 |
| `F1_MIN` | 0,90 | mesuré 0,957 |
| `EXACTITUDE_MIN` | 0,90 | mesuré 0,958 |
| `MARGE_OFFRES_NON_PERTINENTES` | 50 | max mesuré pour une offre hors sujet : 36 |

Ces valeurs sont des **verrous de non-régression**, pas des objectifs de performance. Une
baisse signale une régression ; une hausse ne doit pas être interprétée comme un progrès
sans nouveau corpus.

## Limites des métriques (à énoncer en revue, ch. 5)

1. **Taille du corpus** : 24 offres. Un point de rappel vaut 8 % ; l'intervalle de
   confiance est large. Toute conclusion fine est prématurée.
2. **Étiquetage** : binaire et synthétique. Les cas réels sont plus nuancés (mission QA
   noyée dans un poste de dev, intitulé local).
3. **Non-représentativité** : corpus français/francophone majoritaire, alors que le
   dashboard agrège aussi des sources internationales en anglais.
4. **Périmètre** : ces métriques mesurent le **classement**, pas la qualité de
   l'enrichissement amont ni la pertinence du sourcing des offres.
5. **Surajustement** : le seuil 40 a été choisi sur ce corpus. Aucun ajustement
   supplémentaire de lexique ne doit être fait en regardant ces scores — c'est
   précisément ce que le syllabus interdit (ch. 3). La dernière extension de lexique
   (intitulés français : « qualite », « testeur », « recette », « assurance qualite »,
   « plan de test », « cas de test », « non-régression », « anomalie ») répond à un
   manque constaté sur des intitulés réels du marché visé, et non à une optimisation de
   score : effet mesuré = rappel 0,833 → 0,917, précision inchangée.

## Suites de benchmark (ch. 5) — non applicables

Le syllabus cite les suites de référence MLCommons, DAWNBench, MLMark. Elles portent sur
les performances d'entraînement et d'inférence de modèles : hors sujet ici (aucun modèle
n'est entraîné ni servi par le dépôt).
