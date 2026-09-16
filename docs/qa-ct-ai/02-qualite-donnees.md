# Porte 2 — Qualité des données

## Principe

Les données sont un livrable testable au même titre que le code : ce qui entre dans le
classement doit être contrôlé avant d'être utilisé comme vérité.

## Trois jeux distincts

| Jeu | Contenu | Rôle |
|---|---|---|
| Corpus de référence étiqueté | `tests/fixtures/ct_ai/matcher_gold.json` — 24 offres synthétiques, 12 pertinentes / 12 hors sujet, étiquetées manuellement | mesure (précision, rappel, F1) : c'est **l'unique** jeu de mesure |
| Corpus technique | `tests/fixtures/sample_jobs.json` | tests fonctionnels et d'intégration, non utilisés pour mesurer |
| Données de production | `jobs.db` (jamais versionnée) | exploitation ; **jamais** utilisée comme jeu d'évaluation, sous peine de mesurer la mémorisation |

Aucune offre du jeu de mesure ne provient de la production : pas de fuite
apprentissage / évaluation.

## Règle d'étiquetage (écrite avant la mesure)

`label = 1` si le **cœur** du poste est le test ou la qualité logicielle (manuel,
automatisation, QA lead, test manager, recette, assurance qualité) ou une mission
freelance de test.
`label = 0` sinon, **même si** l'offre mentionne « test », « QA » ou « quality » en
passant (développeur qui écrit des tests unitaires, product owner, SRE, marketing qui
mène des A/B tests).

Cette règle est appliquée avant toute mesure : sur un corpus de cette taille, ajuster la
règle après avoir vu les scores serait du surajustement (ch. 3).

## Contrôles automatisés (extraits de `tests/test_ct_ai_gates.py`)

1. **Complétude** : tout enregistrement porte `id`, `label`, `title`, `company`,
   `description`, `salary`, `remote_type`, `freelance_status`, `location`.
2. **Domaine des étiquettes** : `label ∈ {0, 1}`, aucun identifiant dupliqué.
3. **Équilibre des classes** : ratio ≥ 0,5 entre les deux classes — un corpus déséquilibré
   rendrait l'exactitude trompeuse (ch. 4, qualité des jeux de données).
4. **Données personnelles** : balayage systématique des fixtures et **de tous les fichiers
   suivis** par git (adresses e-mail, téléphones français et internationaux). Les domaines
   de démonstration (`example.com`, `test.com`) sont explicitement tolérés : ce sont des
   placeholders de documentation, pas des données personnelles.
5. **Versionnage** : le corpus d'évaluation est suivi par git et son empreinte SHA-256 est
   verrouillée par un test (porte 7).

## Qualité des données d'entrée en production : ce qui est mesuré sur la base locale

Distribution réelle des champs métier sur 1 071 offres (base locale, aucun contenu
personnel) :

| Champ | Valeurs observées | Conséquence |
|---|---|---|
| `remote_type` | vide 448, null 437, `remote` 119, `hybrid` 59, `onsite` 8 | 83 % des offres n'ont pas d'information de télétravail : le bloc « remote » (10 points) est donc **majoritairement nul**, il ne discrimine qu'une minorité |
| `freelance_status` | `VALIDÉE` 666, `AMBIGUË` 329, `REJETÉE` 20, `non-freelance` 12, null 44 | le classement repose sur un champ majoritairement favorable ; un faux `VALIDÉE` vaut 10 points, soit autant que le télétravail complet |

Lecture : le score s'appuie sur des champs **partiellement renseignés**, ce qui est une
limite documentée de l'oracle (voir porte 3, « limites des métriques »).

## Défauts de données constatés et traitement

| Constat | Traitement |
|---|---|
| L'enrichissement LLM produit `fully_remote` (voir le mock d'API dans `tests/conftest.py`) alors que le classement n'attendait que `remote` | alias de valeurs métier acceptés, test d'invariance dédié |
| Des offres sans localisation du tout | plus de comparaison de TJM au marché français : marché `inconnu` |
| Champs `description` / `tags` non textuels (liste, dictionnaire) | traités comme vides, plus de plantage |
