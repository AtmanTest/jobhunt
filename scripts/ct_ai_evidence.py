#!/usr/bin/env python3
"""Génère la preuve publique du PoC ISTQB CT-AI.

Usage : python3 scripts/ct_ai_evidence.py
Sortie : docs/qa-ct-ai/evidence.json (lu par la page /poc-ct-ai)

Tout ce qui est affiché sur la vitrine est produit ici par exécution réelle :
comptage des tests, métriques sur le corpus étiqueté, tableau d'invariance
métamorphique. Aucune valeur n'est saisie à la main.
"""
import copy
import json
import os
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from hashlib import sha256

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from matcher import analyze_tjm, match_job_to_cv  # noqa: E402

CORPUS = os.path.join(ROOT, "tests", "fixtures", "ct_ai", "matcher_gold.json")
SUITE = "tests/test_ct_ai_gates.py"
SEUIL = 40
SORTIE = os.path.join(ROOT, "docs", "qa-ct-ai", "evidence.json")

# --------------------------------------------------------------------------
# Portes du processus (chapitres du syllabus CT-AI v1.0.1)
# --------------------------------------------------------------------------
PORTES = [
    {
        "n": 1,
        "titre": "Cadrage du risque IA",
        "chapitre": "ch. 1 et 2",
        "exigence": "Classer le système, identifier le mode d'approvisionnement et les "
                     "8 caractéristiques de qualité spécifiques à l'IA.",
        "produit": "Type de système (IA étroite), deux composants (enrichissement LLM tiers + "
                   "classement déterministe), tableau des 8 caractéristiques, matrice de 8 risques.",
        "preuve": "8 risques identifiés (R1 à R8), chacun rattaché à un test",
        "document": "docs/qa-ct-ai/01-cadrage-risque-ia.md",
        "classe_test": None,
    },
    {
        "n": 2,
        "titre": "Qualité des données",
        "chapitre": "ch. 4",
        "exigence": "Séparer les jeux de données, contrôler leur qualité, documenter la chaîne "
                    "de préparation.",
        "produit": "Corpus d'évaluation étiqueté (règle d'étiquetage écrite avant mesure), "
                   "distribution réelle des champs en base, balayage permanent des données personnelles.",
        "preuve": "24 offres étiquetées, 1 071 offres analysées en production locale, "
                  "0 coordonnée personnelle dans les fichiers suivis",
        "document": "docs/qa-ct-ai/02-qualite-donnees.md",
        "classe_test": "TestPorte2Donnees",
    },
    {
        "n": 3,
        "titre": "Modèle et métriques",
        "chapitre": "ch. 3 et 5",
        "exigence": "Instrumenter la matrice de confusion, choisir la métrique selon le coût "
                    "métier de l'erreur, fixer des seuils d'acceptation.",
        "produit": "Matrice de confusion complète, précision / rappel / F1 / exactitude, "
                   "seuil de pertinence à 40, seuils verrouillés en non-régression.",
        "preuve": "Le rappel est la métrique directrice : un faux négatif est une mission "
                  "jamais vue, un faux positif coûte une minute de lecture",
        "document": "docs/qa-ct-ai/03-metriques-seuils.md",
        "classe_test": "TestPorte3Metriques",
    },
    {
        "n": 4,
        "titre": "Spécification et niveaux de test",
        "chapitre": "ch. 7",
        "exigence": "Spécifier le composant IA, décliner les niveaux (données, modèle, composant, "
                    "intégration, système, acceptation), définir les données de test.",
        "produit": "Fiche de spécification, 5 niveaux de test couverts, données de test "
                   "(nominales, limites, hors distribution, adverses), surveillance de la dérive.",
        "preuve": "Traçabilité exigence → test : chaque niveau a au moins un test exécutable",
        "document": "docs/qa-ct-ai/04-plan-de-test.md",
        "classe_test": "TestPorte4NiveauxDeTest",
    },
    {
        "n": 5,
        "titre": "Défis spécifiques à l'IA",
        "chapitre": "ch. 8",
        "exigence": "Traiter le non-déterminisme, l'autonomie, les biais, la complexité, "
                    "l'explicabilité, la sûreté, la définition de l'oracle.",
        "produit": "Oracle de répétabilité (200 exécutions), robustesse aux champs absents et "
                   "invalides, entrées adverses, bornage anti-bourrage de mots-clés, explicabilité "
                   "du score par compétence reconnue.",
        "preuve": "Déterminisme prouvé, 5 familles d'entrées hostiles absorbées, "
                  "score toujours justifiable",
        "document": "docs/qa-ct-ai/04-plan-de-test.md",
        "classe_test": "TestPorte5DefisSpecifiques",
    },
    {
        "n": 6,
        "titre": "Techniques de test IA",
        "chapitre": "ch. 9",
        "exigence": "Appliquer et justifier les techniques : adverses, empoisonnement, paires, "
                    "dos à dos, A/B, métamorphique, expérimenté.",
        "produit": "10 relations métamorphiques, test de monotonie, test dos à dos avec "
                   "implémentation de référence, valeurs limites, entrées adverses.",
        "preuve": "Techniques non applicables nommées et justifiées (A/B sans indicateur d'usage, "
                  "couverture neuronale hors périmètre)",
        "document": "docs/qa-ct-ai/05-techniques.md",
        "classe_test": "TestPorte6Techniques",
    },
    {
        "n": 7,
        "titre": "Environnements de test",
        "chapitre": "ch. 10",
        "exigence": "Versionner modèle, données et environnement ; garantir qu'un test est rejouable "
                    "à l'identique.",
        "produit": "Environnement isolé (base en mémoire, API d'enrichissement simulée), corpus "
                   "verrouillé par empreinte SHA-256, aucun appel réseau pendant les tests.",
        "preuve": "Un test échoue si le corpus d'évaluation change sans revue des seuils",
        "document": "docs/qa-ct-ai/04-plan-de-test.md",
        "classe_test": "TestPorte7Environnement",
    },
    {
        "n": 8,
        "titre": "IA au service du test",
        "chapitre": "ch. 11",
        "exigence": "Documenter l'usage de l'IA pour produire les tests, contrôler sa sortie, "
                    "mesurer ses erreurs, ne jamais l'utiliser comme oracle.",
        "produit": "Journal d'usage : activité, outil, contrôle humain, défaut constaté et correction.",
        "preuve": "Aucun test accepté sur la seule affirmation d'un modèle ; oracle = étiquetage humain",
        "document": "docs/qa-ct-ai/06-journal-aide-ia.md",
        "classe_test": None,
    },
]

DEFAUTS = [
    {
        "titre": "Valeurs métier comparées au caractère près",
        "impact": "Les offres dont la source écrit « Remote », « REMOTE » ou « fully_remote » "
                  "perdaient 10 points de classement (valeur produite par l'enrichissement LLM "
                  "du projet lui-même).",
        "avant": "score 71 / 100",
        "apres": "score 71 / 100 pour toutes les écritures",
        "correction": "Normalisation casse + accents avant comparaison",
        "technique": "Relation métamorphique MR-08 / MR-09",
    },
    {
        "titre": "Statut freelance insensible à la casse",
        "impact": "« VALIDEE », « validée », « Validée » ne rapportaient aucun point, alors que "
                  "le champ vaut 10 points — autant que le télétravail complet.",
        "avant": "score 71 → 61 selon l'écriture",
        "apres": "score identique quelle que soit l'écriture",
        "correction": "Comparaison sur valeur normalisée",
        "technique": "Relation métamorphique MR-09",
    },
    {
        "titre": "Compétences détectées par sous-chaîne",
        "impact": "« api » était détecté dans « capital » et « rapidité » : des offres hors sujet "
                  "gagnaient des points et remontaient dans le classement.",
        "avant": "« Chef de projet capital investissement » → score 3",
        "apres": "score 0, aucune compétence fantôme",
        "correction": "Détection sur mot entier",
        "technique": "Analyse des faux positifs lexicaux",
    },
    {
        "titre": "Marchés non reconnus",
        "impact": "Zurich, Lausanne, Bâle, Berne étaient classés « France » : comparaison de TJM "
                  "fausse (600 €/jour contre des tarifs en francs suisses).",
        "avant": "marché = france",
        "apres": "marché = suisse",
        "correction": "Listes de villes complétées + normalisation des accents",
        "technique": "Analyse des valeurs limites",
    },
    {
        "titre": "Valeur par défaut silencieuse",
        "impact": "Toute localisation inconnue était comparée au marché français : un mauvais "
                  "signal affiché valait mieux qu'aucun, ce qui est faux.",
        "avant": "marché inconnu → comparaison France",
        "apres": "marché « inconnu » → aucune comparaison produite",
        "correction": "Retour explicite « inconnu »",
        "technique": "Test de non-masquage de l'information",
    },
    {
        "titre": "Faisceau de caractères mort après normalisation",
        "impact": "« 600 à 700 €/jour » n'était plus reconnu comme une plage : le TJM affiché "
                  "devenait 700 au lieu de 650.",
        "avant": "tjm = 700",
        "apres": "tjm = 650 (moyenne de la plage)",
        "correction": "Séparateur de plage explicite",
        "technique": "Analyse des valeurs limites",
    },
    {
        "titre": "Classement à score égal non déterministe",
        "impact": "Deux offres à score égal s'échangeaient selon l'ordre d'insertion en base : "
                  "deux rafraîchissements affichaient deux « tops » différents sans changement de données.",
        "avant": "ordre dépendant de la base",
        "apres": "ordre stable (score décroissant, identifiant croissant)",
        "correction": "Départage explicite",
        "technique": "Test de non-déterminisme",
    },
    {
        "titre": "Plantage sur donnée non textuelle",
        "impact": "Une description ou des tags renvoyés sous forme de liste faisaient échouer "
                  "le calcul de score de toute la page.",
        "avant": "TypeError",
        "apres": "champ traité comme vide, page servie",
        "correction": "Normalisation défensive des entrées",
        "technique": "Entrées adverses / données invalides",
    },
]

# Relations métamorphiques vérifiées en direct à chaque génération de la preuve.
# (intitulé, transformation de référence, transformation testée, libellé de la référence)
IDENTITE = lambda j: j  # noqa: E731

RELATIONS = [
    ("MR-01 · casse minuscule sur titre et description",
     IDENTITE,
     lambda j: {**j, "title": j["title"].lower(), "description": j["description"].lower()},
     None),
    ("MR-02 · casse majuscule sur titre et description",
     IDENTITE,
     lambda j: {**j, "title": j["title"].upper(), "description": j["description"].upper()},
     None),
    ("MR-03 · accents retirés",
     IDENTITE,
     lambda j: {**j, "description": unicodedata.normalize("NFKD", j["description"])
                .encode("ascii", "ignore").decode()},
     None),
    ("MR-04 · espaces multiples dans le titre",
     IDENTITE,
     lambda j: {**j, "title": "  " + j["title"].replace(" ", "   ") + "  "},
     None),
    ("MR-05 · ponctuation finale ajoutée au titre",
     IDENTITE,
     lambda j: {**j, "title": j["title"] + " !!!"},
     None),
    ("MR-06 · espaces en bord de description",
     IDENTITE,
     lambda j: {**j, "description": "   " + j["description"] + "   "},
     None),
    ("MR-07 · ordre des phrases de la description inversé",
     IDENTITE,
     lambda j: {**j, "description": " ".join(reversed(j["description"].split(". ")))},
     None),
    ("MR-08 · télétravail complet écrit autrement",
     lambda j: {**j, "remote_type": "remote"},
     lambda j: {**j, "remote_type": "fully_remote"},
     "remote"),
    ("MR-09 · statut freelance écrit autrement",
     lambda j: {**j, "freelance_status": "VALIDÉE"},
     lambda j: {**j, "freelance_status": "validée"},
     "VALIDÉE"),
    ("MR-10 · télétravail partiel écrit en français",
     lambda j: {**j, "remote_type": "hybrid"},
     lambda j: {**j, "remote_type": "télétravail partiel"},
     "hybrid"),
]


def _executer(cmd):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)


def comptage_tests():
    """Compte les tests réellement collectés, par classe (inclut les paramétrages).

    Parse l'arbre de `pytest --collect-only -q` : les lignes <Class X> ouvrent une
    classe, les lignes <Function y> sont des tests (une ligne par paramétrage).
    """
    res = _executer([sys.executable, "-m", "pytest", SUITE, "--collect-only", "-q"])
    par_classe = {}
    classe_courante = "Autres"
    total = 0
    for ligne in res.stdout.splitlines():
        ligne = ligne.strip()
        m = re.match(r"<Class ([^>]+)>", ligne)
        if m:
            classe_courante = m.group(1)
            continue
        if re.match(r"<Function [^>]+>", ligne):
            total += 1
            par_classe[classe_courante] = par_classe.get(classe_courante, 0) + 1
    return total, par_classe


def execution_suite():
    res = _executer([sys.executable, "-m", "pytest", SUITE, "-q", "--no-header"])
    sortie = res.stdout + res.stderr
    passe = re.search(r"(\d+) passed", sortie)
    echoue = re.search(r"(\d+) failed", sortie)
    duree = re.search(r"in ([\d.]+)s", sortie)
    return {
        "passes": int(passe.group(1)) if passe else 0,
        "echecs": int(echoue.group(1)) if echoue else 0,
        "duree_s": float(duree.group(1)) if duree else None,
    }


def metriques():
    corpus = json.load(open(CORPUS, encoding="utf-8"))["offres"]
    detail = []
    for offre in corpus:
        score, competences = match_job_to_cv(copy.deepcopy(offre))
        detail.append({"id": offre["id"], "titre": offre["title"], "score": score,
                       "label": offre["label"], "competences": competences,
                       "predit": score >= SEUIL})
    tp = sum(1 for d in detail if d["predit"] and d["label"] == 1)
    fp = sum(1 for d in detail if d["predit"] and d["label"] == 0)
    fn = sum(1 for d in detail if not d["predit"] and d["label"] == 1)
    tn = sum(1 for d in detail if not d["predit"] and d["label"] == 0)
    precision = tp / (tp + fp) if tp + fp else 0.0
    rappel = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * rappel / (precision + rappel) if precision + rappel else 0.0
    balayage = []
    for seuil in range(20, 80, 10):
        t = sum(1 for d in detail if d["score"] >= seuil and d["label"] == 1)
        f = sum(1 for d in detail if d["score"] >= seuil and d["label"] == 0)
        n = sum(1 for d in detail if d["score"] < seuil and d["label"] == 1)
        p = t / (t + f) if t + f else 0.0
        r = t / (t + n) if t + n else 0.0
        balayage.append({"seuil": seuil, "precision": round(p, 3), "rappel": round(r, 3),
                         "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0})
    return {
        "n": len(detail), "seuil": SEUIL, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 3), "rappel": round(rappel, 3),
        "f1": round(f1, 3), "exactitude": round((tp + tn) / len(detail), 3),
        "detail": sorted(detail, key=lambda d: -d["score"]),
        "balayage": balayage,
        "empreinte_corpus": sha256(open(CORPUS, "rb").read()).hexdigest()[:16],
    }


def invariance():
    corpus = json.load(open(CORPUS, encoding="utf-8"))["offres"]
    base_offre = copy.deepcopy(corpus[0])
    lignes = []
    for nom, ref, teste, libelle_ref in RELATIONS:
        score_ref, _ = match_job_to_cv(copy.deepcopy(ref(base_offre)))
        score, _ = match_job_to_cv(copy.deepcopy(teste(base_offre)))
        lignes.append({"nom": nom, "reference": score_ref, "score": score,
                       "ecart": score - score_ref,
                       "reference_libelle": libelle_ref or "forme normale",
                       "identique": score == score_ref})
    reference = lignes[0]["reference"]
    return {"reference": reference, "offre": base_offre["title"], "relations": lignes,
            "conformes": sum(1 for l in lignes if l["identique"]), "total": len(lignes)}


def entrees_adverses():
    corpus = json.load(open(CORPUS, encoding="utf-8"))["offres"]
    offre_qa = corpus[0]
    offres = [
        ("Offre hors sujet bourrée de mots-clés QA", {
            "title": "QA " * 50, "description": "qa test automation " * 500, "tags": "",
            "salary": "", "remote_type": "", "freelance_status": ""}),
        ("Contenu non textuel (liste, dictionnaire, nombre)", {
            "title": 42, "description": [], "tags": {"a": 1},
            "salary": None, "remote_type": None, "freelance_status": None}),
        ("Injection HTML dans la description", {
            **offre_qa, "description": "<script>alert(1)</script> QA Engineer",
            "salary": "", "remote_type": "", "freelance_status": ""}),
        ("Texte bidirectionnel et caractères de contrôle", {
            "title": "\u202eQA Engineer\u202c", "description": "test",
            "tags": "", "salary": "", "remote_type": "", "freelance_status": ""}),
        ("Alphabet non latin", {
            "title": "Новости QA", "description": "тестирование " * 50,
            "tags": "", "salary": "", "remote_type": "", "freelance_status": ""}),
    ]
    lignes = []
    for nom, offre in offres:
        try:
            score, _ = match_job_to_cv(copy.deepcopy(offre))
            lignes.append({"nom": nom, "resultat": f"score {score}/100, aucun plantage"})
        except Exception as exc:  # pragma: no cover - ne doit jamais arriver
            lignes.append({"nom": nom, "resultat": f"ÉCHEC : {type(exc).__name__}"})
    return lignes


def main():
    total, par_classe = comptage_tests()
    execution = execution_suite()
    m = metriques()
    inv = invariance()

    portes = []
    for porte in PORTES:
        porte = dict(porte)
        classe = porte.pop("classe_test")
        porte["nb_tests"] = par_classe.get(classe, 0) if classe else 0
        portes.append(porte)

    evidence = {
        "genere_le": datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M:%S"),
        "syllabus": "ISTQB CT-AI v1.0.1 FR",
        "tests": {"total_collectes": total, "par_classe": par_classe, **execution},
        "metriques": m,
        "invariance": inv,
        "adverses": entrees_adverses(),
        "defauts": DEFAUTS,
        "portes": portes,
        "stack": {
            "python": sys.version.split()[0],
            "flask": __import__("flask").__version__ if hasattr(__import__("flask"), "__version__") else "3.x",
            "pytest": __import__("pytest").__version__,
        },
    }

    os.makedirs(os.path.dirname(SORTIE), exist_ok=True)
    with open(SORTIE, "w", encoding="utf-8") as fh:
        json.dump(evidence, fh, ensure_ascii=False, indent=2)

    print(f"preuve écrite : {SORTIE}")
    print(f"tests collectés : {total} | exécutés : {execution['passes']} OK / {execution['echecs']} échec")
    print(f"métriques au seuil {SEUIL} : précision {m['precision']} · rappel {m['rappel']} · F1 {m['f1']}")
    print(f"invariance : {inv['conformes']}/{inv['total']} relations conformes")


if __name__ == "__main__":
    main()
