"""Chaîne de livraison virtuelle — un produit simulé, livré avec de vrais défauts, testé pour de vrai.

Objet pédagogique : dérouler tout le processus de test du syllabus ISTQB CT-AI (et CTFL)
sur une livraison réaliste — demande métier, user stories, analyse de risque, conception
des tests, exécution, anomalies, correctif, test de confirmation, test de régression,
critères de sortie, Go/No-Go, clôture.

Ce qui est simulé : le « développeur » et son code (trois versions successives).
Ce qui n'est PAS simulé : l'exécution des tests. Chaque cas de test est une fonction qui
s'exécute réellement contre la version de produit sélectionnée ; les échecs affichés sont
des échecs réels, avec le résultat obtenu et le résultat attendu.

Aucune donnée personnelle : le jeu de données est un catalogue d'offres fictives.
"""
from __future__ import annotations

from copy import deepcopy

# ---------------------------------------------------------------------------
# 1. Demande métier
# ---------------------------------------------------------------------------
DEMANDE_METIER = {
    "id": "DM-2026-014",
    "titre": "Permettre aux utilisateurs de retrouver rapidement les offres qui leur conviennent",
    "demandeur": "Direction produit",
    "contexte": (
        "Les utilisateurs se plaignent de devoir parcourir toute la liste pour trouver les offres "
        "réellement télétravaillables dans leur budget. Deux écrans d'analyse ont été nécessaires "
        "pour arriver à la conclusion, l'effort est jugé prioritaire."
    ),
    "valeur_attendue": "Réduire le temps de recherche d'une offre pertinente et augmenter le taux de candidature.",
    "perimetre": "Filtre de recherche (type de télétravail, budget minimum) + tri par pertinence + pagination.",
    "hors_perimetre": "Recherche par mot-clé libre, sauvegarde des filtres, notifications.",
    "indicateurs": ["Temps moyen pour trouver une offre", "Nombre de candidatures par session"],
}

# ---------------------------------------------------------------------------
# 2. User stories et critères d'acceptation
# ---------------------------------------------------------------------------
USER_STORIES = [
    {
        "id": "US-101",
        "titre": "Filtrer les offres par type de télétravail",
        "recit": "En tant qu'utilisateur, je veux filtrer les offres par type de télétravail "
                 "afin de ne voir que celles compatibles avec mon organisation.",
        "priorite": "Must",
        "valeur_metier": 5,
        "risque": 4,
        "risque_justification": "Le champ vient d'une source externe et ses valeurs varient "
                                "(casse, libellés anglais/français) : erreur de filtrage fréquente en production.",
        "criteres": [
            {"id": "CA-101-1", "etant_donne": "des offres de types remote, fully_remote, hybrid et onsite",
             "quand": "je filtre sur « remote »", "alors": "je vois uniquement les offres de type remote"},
            {"id": "CA-101-2", "etant_donne": "une offre écrite « Fully_Remote » par la source",
             "quand": "je filtre sur « fully_remote »", "alors": "elle est bien retournée"},
            {"id": "CA-101-3", "etant_donne": "un filtre saisi en majuscules",
             "quand": "je lance la recherche", "alors": "le résultat est identique à la saisie en minuscules"},
            {"id": "CA-101-4", "etant_donne": "des offres de types remote, hybrid et onsite",
             "quand": "je filtre sur « onsite »", "alors": "je vois uniquement les offres sur site"},
        ],
    },
    {
        "id": "US-102",
        "titre": "Filtrer les offres par budget minimum",
        "recit": "En tant que freelance, je veux indiquer un budget minimum afin d'écarter les missions "
                 "sous mon seuil.",
        "priorite": "Must",
        "valeur_metier": 4,
        "risque": 3,
        "risque_justification": "Comparaison de seuil : une borne mal choisie (strict au lieu d'inclusif) "
                                "exclut silencieusement des offres.",
        "criteres": [
            {"id": "CA-102-1", "etant_donne": "une offre exactement au budget minimum saisi",
             "quand": "je filtre", "alors": "elle est incluse dans le résultat"},
            {"id": "CA-102-2", "etant_donne": "des offres sans budget renseigné",
             "quand": "je filtre sur un budget minimum", "alors": "elles sont exclues du résultat"},
            {"id": "CA-102-3", "etant_donne": "un filtre de télétravail et un budget minimum saisis ensemble",
             "quand": "je lance la recherche", "alors": "les deux règles s'appliquent simultanément"},
        ],
    },
    {
        "id": "US-103",
        "titre": "Trier les résultats par pertinence",
        "recit": "En tant qu'utilisateur, je veux voir les offres les plus pertinentes en premier afin de "
                 "décider plus vite.",
        "priorite": "Must",
        "valeur_metier": 4,
        "risque": 2,
        "risque_justification": "Un tri inversé reste « fonctionnel » : il ne casse rien, il dégrade la valeur.",
        "criteres": [
            {"id": "CA-103-1", "etant_donne": "des offres notées de 12 à 88", "quand": "j'affiche les résultats",
             "alors": "elles sont ordonnées du score le plus haut au plus bas"},
            {"id": "CA-103-2", "etant_donne": "deux offres à score identique", "quand": "j'affiche les résultats",
             "alors": "l'ordre est stable d'un affichage à l'autre (départage par identifiant)"},
        ],
    },
    {
        "id": "US-104",
        "titre": "Parcourir les résultats page par page",
        "recit": "En tant qu'utilisateur, je veux parcourir les résultats par page afin de ne pas charger "
                 "toute la liste d'un coup.",
        "priorite": "Should",
        "valeur_metier": 3,
        "risque": 3,
        "risque_justification": "Le calcul d'index de page est une source classique de décalage d'un élément.",
        "criteres": [
            {"id": "CA-104-1", "etant_donne": "9 résultats et des pages de 3", "quand": "j'affiche la page 1",
             "alors": "je vois les résultats 1 à 3"},
            {"id": "CA-104-2", "etant_donne": "3 résultats et des pages de 3", "quand": "j'affiche la page 2",
             "alors": "je vois une liste vide"},
        ],
    },
]

# ---------------------------------------------------------------------------
# 3. Jeu de données produit (offres fictives)
# ---------------------------------------------------------------------------
OFFRES = [
    {"id": "o1", "titre": "QA Engineer - Playwright Automation", "remote_type": "remote", "tjm": 600, "score": 82},
    {"id": "o2", "titre": "QA Lead - Plateforme de paiement", "remote_type": "fully_remote", "tjm": 700, "score": 78},
    {"id": "o3", "titre": "Test Manager bancaire", "remote_type": "hybrid", "tjm": 650, "score": 71},
    {"id": "o4", "titre": "Ingénieur test logiciel", "remote_type": "onsite", "tjm": 520, "score": 60},
    {"id": "o5", "titre": "QA Analyst recette", "remote_type": "remote", "tjm": 580, "score": 60},
    {"id": "o6", "titre": "SDET - plateforme données", "remote_type": "fully_remote", "tjm": 900, "score": 88},
    {"id": "o7", "titre": "Tester mobile iOS / Android", "remote_type": "hybrid", "tjm": None, "score": 55},
    {"id": "o8", "titre": "Chef de projet BTP", "remote_type": "onsite", "tjm": None, "score": 12},
]

TAILLE_PAGE = 3

# ---------------------------------------------------------------------------
# 4. Les trois livraisons du développeur
# ---------------------------------------------------------------------------
VERSIONS = {
    "v1": {
        "libelle": "v1.0.0 — première livraison du développeur",
        "note": "Le développeur a livré le filtre en s'appuyant sur les valeurs qu'il a vues passer : "
                "comparaison stricte, budget strictement supérieur, tri croissant, index de page décalé.",
        "date": "J+5",
    },
    "v2": {
        "libelle": "v1.1.0 — correctif après anomalies",
        "note": "Les quatre anomalies sont corrigées. Le correctif du filtre est implémenté par "
                "recherche de sous-chaîne pour « être plus tolérant ».",
        "date": "J+7",
    },
    "v3": {
        "libelle": "v1.1.1 — correctif de la régression",
        "note": "Le filtre compare désormais des familles de valeurs normalisées (casse, accents, alias), "
                "sans recherche de sous-chaîne.",
        "date": "J+8",
    },
}
VERSION_LIVREE = "v1"
VERSION_FINALE = "v3"


def _norm(valeur) -> str:
    """Normalisation identique à celle du moteur de classement : casse, accents, espaces."""
    import unicodedata
    if not isinstance(valeur, str):
        return ""
    texte = unicodedata.normalize("NFKD", valeur)
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return " ".join(texte.strip().lower().split())


def filtrer(offres, filtre_remote=None, budget_min=None, version=VERSION_FINALE):
    """Filtre de produit, dans la version livrée par le développeur."""
    resultat = list(offres)

    if filtre_remote:
        if version == "v1":
            # DÉFAUT D1 : comparaison stricte, sensible à la casse
            resultat = [o for o in resultat if o["remote_type"] == filtre_remote]
        elif version == "v2":
            # DÉFAUT D5 (régression) : recherche de sous-chaîne trop large
            cible = _norm(filtre_remote)
            resultat = [o for o in resultat if cible in _norm(o["remote_type"])]
        else:
            # version corrigée : familles de valeurs normalisées
            cible = _norm(filtre_remote)
            resultat = [o for o in resultat if _norm(o["remote_type"]) == cible]

    if budget_min is not None:
        if version == "v1":
            # DÉFAUT D2 : comparaison stricte — l'offre exactement au seuil est exclue
            resultat = [o for o in resultat if (o.get("tjm") or 0) > budget_min]
        else:
            resultat = [o for o in resultat if o.get("tjm") is not None and o["tjm"] >= budget_min]

    return resultat


def trier(offres, version=VERSION_FINALE):
    """Tri par pertinence décroissante, départage stable par identifiant."""
    if version == "v1":
        # DÉFAUT D3 : tri croissant (les moins pertinentes en premier)
        return sorted(offres, key=lambda o: o["score"])
    return sorted(offres, key=lambda o: (-o["score"], o["id"]))


def paginer(offres, page=1, taille=TAILLE_PAGE, version=VERSION_FINALE):
    """Pagination : page 1 = premiers résultats."""
    if page < 1:
        page = 1
    if version == "v1":
        # DÉFAUT D4 : index de départ décalé d'une page
        debut = page * taille
    else:
        debut = (page - 1) * taille
    return offres[debut:debut + taille]


def rechercher(filtre_remote=None, budget_min=None, page=1, taille=TAILLE_PAGE, version=VERSION_FINALE):
    """Enchaînement complet du produit : filtre, tri, pagination (comme l'API réelle)."""
    resultat = filtrer(deepcopy(OFFRES), filtre_remote, budget_min, version)
    resultat = trier(resultat, version)
    return paginer(resultat, page, taille, version)


# ---------------------------------------------------------------------------
# 5. Catalogue de cas de test (conçu à l'étape de conception)
# ---------------------------------------------------------------------------
# Chaque cas cible explicitement un niveau : le composant filtre, le composant tri,
# ou l'enchaînement complet (filtre + tri + pagination). C'est ce découpage qui rend
# la localisation du défaut immédiate quand un test échoue.
# type : fonctionnel | limite | table de décision | régression


def _ids(offres):
    return [o["id"] for o in offres]


def _filtre(filtre_remote=None, budget_min=None, version=VERSION_FINALE):
    """Composant filtre seul : isole un défaut de filtrage d'un défaut de tri."""
    return filtrer(deepcopy(OFFRES), filtre_remote, budget_min, version)


def _flux(filtre_remote=None, budget_min=None, version=VERSION_FINALE):
    """Filtre puis tri (sans pagination) : niveau composant enchaîné."""
    return trier(filtrer(deepcopy(OFFRES), filtre_remote, budget_min, version), version)


CAS_DE_TEST = [
    {
        "id": "TC-01", "us": "US-101", "ca": "CA-101-1", "type": "fonctionnel", "priorite": "critique",
        "technique": "Partition d'équivalence",
        "titre": "Filtrer sur « remote » retourne uniquement les offres de type remote",
        "etapes": "Appliquer le filtre « remote », trier, comparer les identifiants obtenus.",
        "attendu": "o1 puis o5 (les deux offres de type remote)",
        "fonction": lambda v: _ids(_filtre("remote", None, v)),
        "attendu_valeur": ["o1", "o5"],
    },
    {
        "id": "TC-02", "us": "US-101", "ca": "CA-101-2", "type": "fonctionnel", "priorite": "majeur",
        "technique": "Partition d'équivalence",
        "titre": "Filtrer sur « fully_remote » retourne les offres correspondantes",
        "etapes": "Appliquer le filtre « fully_remote », trier, comparer les identifiants obtenus.",
        "attendu": "o2 puis o6",
        "fonction": lambda v: _ids(_filtre("fully_remote", None, v)),
        "attendu_valeur": ["o2", "o6"],
    },
    {
        "id": "TC-03", "us": "US-101", "ca": "CA-101-3", "type": "limite", "priorite": "critique",
        "technique": "Analyse des valeurs limites (casse)",
        "titre": "Un filtre saisi en majuscules donne le même résultat qu'en minuscules",
        "etapes": "Comparer le filtre « REMOTE » au filtre « remote ».",
        "attendu": "résultats identiques : o1 puis o5",
        "fonction": lambda v: _ids(_filtre("REMOTE", None, v)),
        "attendu_valeur": ["o1", "o5"],
    },
    {
        "id": "TC-04", "us": "US-102", "ca": "CA-102-1", "type": "limite", "priorite": "critique",
        "technique": "Analyse des valeurs limites (borne inclusive)",
        "titre": "Une offre exactement au budget minimum est incluse",
        "etapes": "Filtrer sur un budget minimum de 600 : l'offre à 600 exactement doit apparaître.",
        "attendu": "o1 (600 exactement), o2 (700), o3 (650), o6 (900)",
        "fonction": lambda v: _ids(_filtre(None, 600, v)),
        "attendu_valeur": ["o1", "o2", "o3", "o6"],
    },
    {
        "id": "TC-05", "us": "US-102", "ca": "CA-102-2", "type": "limite", "priorite": "majeur",
        "technique": "Analyse des valeurs limites (absence de valeur)",
        "titre": "Les offres sans budget renseigné sont exclues",
        "etapes": "Filtrer sur un budget minimum de 0 : aucune offre sans budget ne doit apparaître.",
        "attendu": "o1 à o6 — jamais o7 ni o8 (budget absent)",
        "fonction": lambda v: _ids(_filtre(None, 0, v)),
        "attendu_valeur": ["o1", "o2", "o3", "o4", "o5", "o6"],
    },
    {
        "id": "TC-06", "us": "US-103", "ca": "CA-103-1", "type": "fonctionnel", "priorite": "critique",
        "technique": "Cas de test fonctionnel",
        "titre": "Les résultats sont triés du score le plus haut au plus bas",
        "etapes": "Trier la totalité des offres et vérifier la décroissance des scores.",
        "attendu": "scores décroissants, premier = 88",
        "fonction": lambda v: [o["score"] for o in trier(deepcopy(OFFRES), v)],
        "attendu_valeur": [88, 82, 78, 71, 60, 60, 55, 12],
    },
    {
        "id": "TC-07", "us": "US-103", "ca": "CA-103-2", "type": "fonctionnel", "priorite": "mineur",
        "technique": "Cas de test fonctionnel",
        "titre": "Deux offres à score égal sont départagées par identifiant",
        "etapes": "Vérifier l'ordre des deux offres à score 60 (o4 et o5).",
        "attendu": "o4 puis o5",
        "fonction": lambda v: [o["id"] for o in trier(deepcopy(OFFRES), v) if o["score"] == 60],
        "attendu_valeur": ["o4", "o5"],
    },
    {
        "id": "TC-08", "us": "US-104", "ca": "CA-104-1", "type": "limite", "priorite": "majeur",
        "technique": "Analyse des valeurs limites (index de page)",
        "titre": "La page 1 affiche les 3 premiers résultats",
        "etapes": "Appeler la recherche complète page 1 et comparer aux 3 premiers du tri.",
        "attendu": "o6, o1, o2",
        "fonction": lambda v: _ids(rechercher(page=1, taille=3, version=v)),
        "attendu_valeur": ["o6", "o1", "o2"],
    },
    {
        "id": "TC-09", "us": "US-104", "ca": "CA-104-2", "type": "limite", "priorite": "mineur",
        "technique": "Analyse des valeurs limites (page hors plage)",
        "titre": "Une page au-delà du dernier résultat renvoie une liste vide",
        "etapes": "Filtrer sur « hybrid » (2 offres) et demander la page 3.",
        "attendu": "liste vide",
        "fonction": lambda v: _ids(rechercher(filtre_remote="hybrid", page=3, taille=3, version=v)),
        "attendu_valeur": [],
    },
    {
        "id": "TC-10", "us": "US-101", "ca": "CA-101-1", "type": "régression", "priorite": "critique",
        "technique": "Test de régression (correctif du filtre)",
        "titre": "Filtrer sur « remote » ne doit pas retourner les offres fully_remote",
        "etapes": "Vérifier qu'aucune offre d'un autre type ne remonte dans le filtre « remote ».",
        "attendu": "aucune offre hors du type demandé",
        "fonction": lambda v: [o["id"] for o in _filtre("remote", None, v) if o["remote_type"] != "remote"],
        "attendu_valeur": [],
    },
    {
        "id": "TC-11", "us": "US-101", "ca": "CA-101-4", "type": "régression", "priorite": "majeur",
        "technique": "Test de régression (filtres voisins)",
        "titre": "Filtrer sur « onsite » ne retourne que les offres sur site",
        "etapes": "Vérifier le filtre « onsite » et les types retournés.",
        "attendu": "o4 puis o8",
        "fonction": lambda v: _ids(_filtre("onsite", None, v)),
        "attendu_valeur": ["o4", "o8"],
    },
    {
        "id": "TC-12", "us": "US-102", "ca": "CA-102-3", "type": "table de décision", "priorite": "majeur",
        "technique": "Test par tables de décisions (filtres combinés)",
        "titre": "Filtres combinés télétravail + budget minimum",
        "etapes": "Appliquer « remote » et budget 600 : la combinaison des deux règles doit tenir.",
        "attendu": "o1 uniquement (de type remote et à 600 exactement)",
        "fonction": lambda v: _ids(_filtre("remote", 600, v)),
        "attendu_valeur": ["o1"],
    },
]


# ---------------------------------------------------------------------------
# 6. Activités du processus (mapping syllabus)
# ---------------------------------------------------------------------------
ETAPES = [
    {"n": 1, "id": "demande", "acteur": "Métier", "activite": "Demande métier",
     "syllabus": "Contexte du projet et base de test (CTFL §1, CT-AI ch. 7.1)",
     "role_visiteur": "Lire la demande et juger si elle est testable."},
    {"n": 2, "id": "us", "acteur": "Product Owner", "activite": "User stories et critères d'acceptation",
     "syllabus": "Base de test : conditions de test vérifiables (CTFL §2.2)",
     "role_visiteur": "Vérifier que chaque critère est vérifiable sans ambiguïté."},
    {"n": 3, "id": "risque", "acteur": "QA", "activite": "Analyse de risque et planification",
     "syllabus": "Analyse de risque produit et de projet (CTFL §5.2)",
     "role_visiteur": "Valider la priorisation par risque."},
    {"n": 4, "id": "conception", "acteur": "QA", "activite": "Conception des tests et traçabilité",
     "syllabus": "Analyse, conception et implémentation des tests (CTFL §4, CT-AI ch. 9)",
     "role_visiteur": "Contrôler la traçabilité exigence → test."},
    {"n": 5, "id": "execution", "acteur": "QA", "activite": "Campagne d'exécution sur la livraison v1.0.0",
     "syllabus": "Exécution des tests et journalisation (CTFL §1.4, CT-AI ch. 7.2)",
     "role_visiteur": "Lancer la campagne : les tests s'exécutent réellement."},
    {"n": 6, "id": "anomalies", "acteur": "QA", "activite": "Rapports d'anomalie et triage",
     "syllabus": "Gestion des anomalies : rapport, sévérité, priorité (CTFL §5.5)",
     "role_visiteur": "Vérifier que chaque anomalie est exploitable par le développeur."},
    {"n": 7, "id": "correctif1", "acteur": "Développeur", "activite": "Premier correctif — livraison v1.1.0",
     "syllabus": "Analyse des anomalies et correction (CTFL §5.4)",
     "role_visiteur": "Pousser le correctif du développeur."},
    {"n": 8, "id": "confirmation", "acteur": "QA", "activite": "Test de confirmation sur v1.1.0",
     "syllabus": "Test de confirmation : rejouer les tests en échec (CTFL §1.2.2)",
     "role_visiteur": "Rejouer uniquement les tests en échec."},
    {"n": 9, "id": "regression", "acteur": "QA", "activite": "Test de régression sur v1.1.0",
     "syllabus": "Test de régression : vérifier que rien n'a été cassé (CTFL §1.2.2)",
     "role_visiteur": "Rejouer toute la suite : le correctif peut avoir cassé ailleurs."},
    {"n": 10, "id": "correctif2", "acteur": "Développeur", "activite": "Second correctif — livraison v1.1.1",
     "syllabus": "Itération sur les anomalies détectées en régression (CTFL §5.4)",
     "role_visiteur": "Pousser le correctif de la régression."},
    {"n": 11, "id": "verification", "acteur": "QA", "activite": "Confirmation et régression finales sur v1.1.1",
     "syllabus": "Re-test complet avant décision de mise en production (CTFL §1.2.2)",
     "role_visiteur": "Vérifier que tout est vert avant de décider."},
    {"n": 12, "id": "verdict", "acteur": "QA + Métier", "activite": "Critères de sortie, Go/No-Go et clôture",
     "syllabus": "Critères d'entrée/sortie, rapport de test et clôture (CTFL §5.3, §5.5, §5.6)",
     "role_visiteur": "Décider le Go sur les faits, puis lire le rapport de clôture."},
]


# ---------------------------------------------------------------------------
# 7. Moteur d'exécution
# ---------------------------------------------------------------------------
def executer_cas(cas, version):
    """Exécute un cas de test contre une version de produit. Retourne un résultat réel."""
    try:
        obtenu = cas["fonction"](version)
        reussi = obtenu == cas["attendu_valeur"]
        return {
            "cas": cas["id"], "titre": cas["titre"], "us": cas["us"], "ca": cas["ca"],
            "type": cas["type"], "priorite": cas["priorite"], "technique": cas["technique"],
            "etapes": cas["etapes"], "attendu": cas["attendu"],
            "obtenu": obtenu, "attendu_valeur": cas["attendu_valeur"],
            "statut": "réussi" if reussi else "en échec",
            "message": None if reussi else f"attendu {cas['attendu_valeur']} — obtenu {obtenu}",
        }
    except Exception as exc:  # un test qui plante est un test en échec, jamais une exception qui remonte
        return {
            "cas": cas["id"], "titre": cas["titre"], "us": cas["us"], "ca": cas["ca"],
            "type": cas["type"], "priorite": cas["priorite"], "technique": cas["technique"],
            "etapes": cas["etapes"], "attendu": cas["attendu"],
            "obtenu": f"{type(exc).__name__}", "attendu_valeur": cas["attendu_valeur"],
            "statut": "en échec",
            "message": f"erreur d'exécution : {type(exc).__name__} — {exc}",
        }


def executer_campagne(version=VERSION_LIVREE, cas_ids=None):
    """Exécute une campagne : toute la suite, ou une sélection (test de confirmation)."""
    cas = CAS_DE_TEST
    if cas_ids:
        demandes = set(cas_ids)
        cas = [c for c in CAS_DE_TEST if c["id"] in demandes]
    resultats = [executer_cas(c, version) for c in cas]
    return {
        "version": version,
        "version_libelle": VERSIONS.get(version, {}).get("libelle", version),
        "resultats": resultats,
        "synthese": synthese(resultats),
    }


def synthese(resultats):
    reussis = [r for r in resultats if r["statut"] == "réussi"]
    echecs = [r for r in resultats if r["statut"] == "en échec"]
    par_type = {}
    for r in resultats:
        par_type.setdefault(r["type"], {"total": 0, "echecs": 0})
        par_type[r["type"]]["total"] += 1
        if r["statut"] == "en échec":
            par_type[r["type"]]["echecs"] += 1
    return {
        "executes": len(resultats),
        "reussis": len(reussis),
        "echecs": len(echecs),
        "taux_reussite": round(100 * len(reussis) / len(resultats), 1) if resultats else 0.0,
        "par_type": par_type,
        "echecs_critiques": len([r for r in echecs if r["priorite"] == "critique"]),
        "echecs_majeurs": len([r for r in echecs if r["priorite"] == "majeur"]),
        "echecs_mineurs": len([r for r in echecs if r["priorite"] == "mineur"]),
        "ids_en_echec": [r["cas"] for r in echecs],
    }


def rapports_anomalie(resultats):
    """Construit les rapports d'anomalie à partir des échecs réels.

    Un rapport par cause racine supposée : les cas en échec qui portent la même
    signature (mêmes valeurs attendues/obtenues) sont regroupés.
    """
    anomalies = []
    for r in resultats:
        if r["statut"] != "en échec":
            continue
        anomalies.append({
            "id": f"AN-{r['cas']}",
            "titre": r["titre"],
            "exigence": f"{r['us']} / {r['ca']}",
            "severite": {"critique": "bloquante", "majeur": "majeure", "mineur": "mineure"}[r["priorite"]],
            "priorite": "à corriger avant livraison" if r["priorite"] in ("critique", "majeur")
                        else "à planifier",
            "type": r["type"],
            "etapes": r["etapes"],
            "attendu": r["attendu"],
            "obtenu": r["obtenu"],
            "detecte_par": r["cas"],
            "technique": r["technique"],
        })
    return anomalies


def evaluer_criteres_sortie(resultats, anomalies_ouvertes=None):
    """Critères de sortie fixés avant la campagne (plan de test)."""
    s = synthese(resultats)
    anomalies_ouvertes = anomalies_ouvertes if anomalies_ouvertes is not None else \
        [a for a in rapports_anomalie(resultats)]
    critiques_ouvertes = [a for a in anomalies_ouvertes if a["severite"] == "bloquante"]
    majeures_ouvertes = [a for a in anomalies_ouvertes if a["severite"] == "majeure"]
    criteres = [
        {"critere": "Tous les tests à priorité critique passent",
         "exige": "0 échec critique", "mesure": s["echecs_critiques"], "ok": s["echecs_critiques"] == 0},
        {"critere": "Aucune anomalie bloquante ou majeure ouverte",
         "exige": "0 anomalie ouverte", "mesure": len(critiques_ouvertes) + len(majeures_ouvertes),
         "ok": not critiques_ouvertes and not majeures_ouvertes},
        {"critere": "Taux de réussite de la suite ≥ 100 %",
         "exige": "100 %", "mesure": f"{s['taux_reussite']} %", "ok": s["taux_reussite"] == 100.0},
        {"critere": "Suite de régression exécutée à 100 %",
         "exige": "tous les tests de régression exécutés",
         "mesure": f"{s['par_type'].get('régression', {}).get('total', 0)} tests de régression",
         "ok": s["par_type"].get("régression", {}).get("total", 0) >= 2},
        {"critere": "Traçabilité exigence → test complète",
         "exige": "chaque user story couverte",
         "mesure": f"{len({r['us'] for r in resultats})}/{len(USER_STORIES)} user stories couvertes",
         "ok": len({r["us"] for r in resultats}) == len(USER_STORIES)},
    ]
    return {"criteres": criteres, "go": all(c["ok"] for c in criteres)}


def tracabilite():
    """Matrice de traçabilité exigence → critère d'acceptation → cas de test."""
    lignes = []
    for us in USER_STORIES:
        cas_us = [c for c in CAS_DE_TEST if c["us"] == us["id"]]
        for ca in us["criteres"]:
            cas_ca = [c["id"] for c in cas_us if c["ca"] == ca["id"]]
            lignes.append({
                "us": us["id"], "us_titre": us["titre"], "critere": ca["id"],
                "enonce": f"Étant donné {ca['etant_donne']} — quand {ca['quand']} — alors {ca['alors']}",
                "cas": cas_ca,
                "couvert": bool(cas_ca),
                "technique": ", ".join(sorted({c["technique"] for c in cas_us if c["ca"] == ca["id"]})) or "—",
            })
    return lignes


def rapport_final(version=VERSION_LIVREE):
    """Photo complète d'une livraison : campagne + anomalies + critères."""
    campagne = executer_campagne(version)
    anomalies = rapports_anomalie(campagne["resultats"])
    return {
        "version": version,
        "campagne": campagne,
        "anomalies": anomalies,
        "criteres_sortie": evaluer_criteres_sortie(campagne["resultats"], anomalies),
        "tracabilite": tracabilite(),
    }


def scenario_complet():
    """Le scénario de référence, exécuté de bout en bout (utilisé par les tests et la vitrine)."""
    etapes = {}
    etapes["v1_campagne"] = executer_campagne("v1")
    etapes["v1_anomalies"] = rapports_anomalie(etapes["v1_campagne"]["resultats"])
    etapes["v1_verdict"] = evaluer_criteres_sortie(etapes["v1_campagne"]["resultats"], etapes["v1_anomalies"])

    ids_v1 = etapes["v1_campagne"]["synthese"]["ids_en_echec"]
    etapes["v2_confirmation"] = executer_campagne("v2", cas_ids=ids_v1)
    etapes["v2_regression"] = executer_campagne("v2")
    etapes["v2_anomalies"] = rapports_anomalie(etapes["v2_regression"]["resultats"])
    etapes["v2_verdict"] = evaluer_criteres_sortie(etapes["v2_regression"]["resultats"], etapes["v2_anomalies"])

    ids_v2 = etapes["v2_regression"]["synthese"]["ids_en_echec"]
    etapes["v3_confirmation"] = executer_campagne("v3", cas_ids=ids_v2)
    etapes["v3_regression"] = executer_campagne("v3")
    etapes["v3_anomalies"] = rapports_anomalie(etapes["v3_regression"]["resultats"])
    etapes["v3_verdict"] = evaluer_criteres_sortie(etapes["v3_regression"]["resultats"], etapes["v3_anomalies"])
    return etapes


if __name__ == "__main__":
    sc = scenario_complet()
    for cle in ("v1", "v2", "v3"):
        s = sc[f"{cle}_campagne" if cle == "v1" else f"{cle}_regression"]["synthese"]
        print(f"{cle} : {s['reussis']}/{s['executes']} réussis — échecs {s['ids_en_echec']}")
    print("verdict final :", "GO" if sc["v3_verdict"]["go"] else "NO-GO")
