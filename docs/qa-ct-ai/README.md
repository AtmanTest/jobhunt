# Portes ISTQB CT-AI appliquées au dashboard QA

Ce dossier contient la trace du processus **ISTQB CT-AI (syllabus v1.0.1 FR)** appliqué
au moteur de classement des offres de JobHunt (`matcher.py` + l'enrichissement appelé
par `app.index`).

L'objet testé n'est pas « un site web » : c'est un **système à base d'IA faible** qui
prend une offre d'emploi brute et produit une **décision** (pertinente / non pertinente)
et un **classement**. C'est donc exactement le périmètre du référentiel.

| Porte | Fichier | Contenu |
|---|---|---|
| 1 | `01-cadrage-risque-ia.md` | type de système, caractéristiques de qualité, risques |
| 2 | `02-qualite-donnees.md` | corpus d'évaluation, qualité des données, données interdites |
| 3 | `03-metriques-seuils.md` | métriques, seuils verrouillés, matrice de confusion |
| 4 | `04-plan-de-test.md` | niveaux de test, données de test, dérive, environnement |
| 5 | `05-techniques.md` | relations métamorphiques, dos à dos, entrées adverses |
| 6 | `06-journal-aide-ia.md` | usage de l'IA pour produire les tests + revue humaine |

Code de test associé : `tests/test_ct_ai_gates.py` (62 tests) et corpus étiqueté
`tests/fixtures/ct_ai/matcher_gold.json`.

## Ce que le processus a changé concrètement

Sept défauts ont été trouvés par les tests eux-mêmes puis corrigés (voir `05-techniques.md`
pour la méthode et le détail) :

1. `remote_type` comparé à l'identique → « Remote », « REMOTE », `fully_remote` (valeur
   réellement produite par l'enrichissement, cf. `tests/conftest.py`) ne rapportaient
   aucun point : les offres full remote perdaient 10 points de classement.
2. `freelance_status` comparé à l'identique → « VALIDEE », « validée » perdus.
3. Détection de compétences par sous-chaîne → « api » détecté dans « capital »,
   « test » dans « latest » : des offres hors sujet gagnaient des points.
4. Trois marchés (Zurich, Lausanne, Bâle…) tombaient dans le marché français.
5. Toute localisation inconnue était comparée au marché français → comparaison de TJM fausse.
6. Faisceau de caractères par plage `[-àà]` inefficace après normalisation (« 600 à 700 »
   n'était plus lu comme une plage).
7. Classement des offres à score égal dépendant de l'ordre d'insertion en base
   (deux rafraîchissements pouvaient afficher deux tops différents).

Plus un défaut de robustesse : une description ou des tags non textuels faisaient
planter le calcul de score (`TypeError`).

## Comment rejouer

```bash
python3 -m pytest tests/test_ct_ai_gates.py -q
```

Les seuils sont des seuils de **non-régression** mesurés sur le corpus verrouillé :
ils ne sont pas une garantie de performance en production (voir porte 3).
