# Porte 5 — Techniques de test appliquées

Ce document liste **ce qui a réellement été exécuté**, avec les défauts trouvés. Les
techniques non applicables sont nommées comme telles : le syllabus demande de justifier
la sélection, pas d'appliquer tout le catalogue.

## 1. Relations métamorphiques (ch. 9.5) — technique principale

Aucun oracle exact n'existe (« ce score devrait valoir 57 ») : l'oracle retenu est une
**relation entre deux exécutions**. Sept relations implémentées et vérifiées :

| Réf. | Relation | Résultat |
|---|---|---|
| MR-01 | mettre le titre et la description en minuscules ne change pas la décision | identique |
| MR-02 | les mettre en majuscules ne change pas la décision | identique |
| MR-03 | retirer les accents ne change pas la décision | identique |
| MR-04 | espaces multiples en tête et entre les mots | identique |
| MR-05 | ajouter une ponctuation finale au titre | identique |
| MR-06 | espaces en bord de description | identique |
| MR-07 | inverser l'ordre des phrases de la description | identique |
| MR-08 | `remote` ↔ `Remote` ↔ `REMOTE` ↔ `fully_remote` ↔ `100% remote` ↔ `remote work` | identique |
| MR-09 | `VALIDÉE` ↔ `VALIDEE` ↔ `validée` ↔ `Validée` | identique |
| MR-10 | `hybrid` ↔ `Hybride` ↔ `HYBRIDE` ↔ `télétravail partiel` | identique |

**Défauts trouvés** : MR-08 et MR-09 échouaient avant correction (perte de 10 points par
variante de casse). Le cas `fully_remote` n'était pas théorique : c'est la valeur produite
par l'enrichissement LLM du projet, visible dans le mock d'API de `tests/conftest.py`.

## 2. Test par sous-chaîne (faux positifs lexicaux)

Détection des compétences par recherche de sous-chaîne : « api » apparaissait dans
« capital » et « rapidité », « test » dans « latest ».

| Entrée | Avant | Après |
|---|---|---|
| « Chef de projet capital investissement » | score 3, compétence fantôme `api` | score 0, aucune compétence |
| « Latest news about testing industry » | score 10 | score 0 |
| « Rapidité de traitement et satisfaction client » | score 3, `api` | score 0 |
| « Applications mobiles iOS » | score 6 (`mobile`, `ios`) | inchangé (détections réelles) |

Correction : correspondance sur **mot entier** avec frontières alphanumériques,
sauf mots-clés à séparateur technique (`ci/cd`, `/jour`) qui restent en sous-chaîne.

## 3. Test de monotonie (propriété)

Ajouter une compétence du profil dans la description d'une offre **ne doit jamais faire
baisser** le score. Vérifié sur les 34 compétences du lexique : aucune violation.
Cette propriété borne l'effet d'un enrichissement partiel de l'offre.

## 4. Valeurs limites (ch. 9.7 et ch. 3)

Salaire / TJM : une plage « 600-700 €/jour » et « 600 à 700 EUR /jour » doivent donner le
même résultat (moyenne 650). Le second cas échouait après la normalisation des accents :
le faisceau `[-àà]` ne reconnaissait plus le « à » devenu « a ». Corrigé par un séparateur
de plage explicite (`-`, `–`, `a`, `à`, `to`, `jusqu'à`).

Marchés : « Zürich », « Lausanne », « Bâle » tombaient dans le marché **français**
(comparaison de TJM fausse de 5 à 6 fois l'écart réel). Toute localisation non reconnue
retourne désormais `inconnu`, et un marché inconnu ne produit **aucune** comparaison.

## 5. Test dos à dos (ch. 9.3)

Comparaison du classement produit par le moteur avec une **implémentation de référence
indépendante** (comptage de termes QA, écrite pour le test et non dérivée du code testé).
Critère : au moins 5 offres communes sur les 8 premières. La divergence mesurée est
documentée comme limite (le moteur pondère la fraîcheur et le freelance, pas la référence).

## 6. Entrées adverses (ch. 9.1)

| Attaque | Attendu | Résultat |
|---|---|---|
| 500 emoji dans la description | pas de plantage, score borné | respecté |
| Caractères de contrôle bidirectionnels (U+202E) | pas d'inversion de décision | respecté |
| Injection HTML `<script>` | traité comme du texte | respecté |
| 25 000 répétitions de « QA » (bourrage de mots-clés) | plafonds respectés (titre 20, compétences 30, bonus 20) | score ≤ 70, plafond de compétences respecté |
| Alphabet non latin (cyrillique) | pas de faux positifs | respecté |

Le bornage est la protection anti-« piratage de récompense » (ch. 2, effets secondaires) :
une offre ne peut pas dominer le classement par accumulation lexicale.

## 7. Empoisonnement des données (ch. 9.1)

Applicable au sens « donnée d'entrée malveillante ou erronée » : une offre dont un champ
métier contredit les autres (télétravail déclaré « sur site » mais décrit comme full
remote) ne doit pas obtenir le bonus télétravail. Vérifié : le score avec un champ métier
défavorable est strictement inférieur au score avec le champ favorable.

## 8. Non-déterminisme (ch. 8.4)

200 exécutions sur la même entrée → un seul score possible : le composant est déterministe.
Le non-déterminisme de la chaîne est situé **en amont** (modèle de langue) et absorbé par
les alias de valeurs.

Un second non-déterminisme, celui du **classement à score égal** (dépendant de l'ordre
d'insertion en base), a été trouvé et corrigé : départage explicite par identifiant dans
`app.index` (top, jobs du jour, hot picks). Sans cela, deux rafraîchissements pouvaient
afficher deux « tops » différents sans qu'aucune donnée n'ait changé.

## 9. Techniques explicitement non retenues

| Technique | Pourquoi non |
|---|---|
| Test A/B (9.4) | aucun indicateur d'usage réel (clics, candidatures) n'est collecté ; comparer sans indicateur ne prouve rien |
| Couverture des neurones / DeepXplore (6.2) | le composant testé n'est pas un réseau de neurones ; les mesures de couverture neuronale s'appliquent à l'enrichissement, inaccessible (API tierce) |
| Test par paires (9.2) | combinaisons de paramètres trop peu nombreuses (3 champs métier à 3-3-4 valeurs) : la couverture exhaustive reste inférieure à 40 cas |
| Test exploratoire / EDA (9.6) | partiellement appliqué : analyse manuelle des valeurs réelles des champs en base (voir porte 2) |
