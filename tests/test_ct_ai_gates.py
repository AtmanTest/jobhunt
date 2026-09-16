"""Portes ISTQB CT-AI appliquées au classifieur de pertinence du dashboard.

Ce module n'est pas une suite de tests « API » de plus : il applique le
processus en 8 portes du syllabus CT-AI (v1.0.1) au composant qui décide du
classement des offres (`matcher.match_job_to_cv`, utilisé par `app.index`).

  Porte 2 — données          : intégrité et absence de données personnelles
  Porte 3 — modèle/métriques : précision, rappel, F1 verrouillés sur un corpus étiqueté
  Porte 4 — niveaux de test  : fonction, composant, intégration
  Porte 5 — défis spécifiques : non-déterminisme, robustesse, entrées adverses
  Porte 6 — techniques       : relations métamorphiques, monotonie, bornage,
                               dos à dos avec une implémentation de référence
  Porte 7 — environnements   : corpus d'évaluation verrouillé par empreinte

Les seuils verrouillés (SEUIL_PERTINENCE, PRECISION_MIN, RAPPEL_MIN, F1_MIN)
sont des seuils de NON-RÉGRESSION : ils ont été mesurés sur ce corpus, ils ne
sont pas une garantie de performance en production. Toute hausse de ces seuils
exige un corpus plus large (voir docs/qa-ct-ai/03-metriques-seuils.md).
"""
import copy
import json
import os
import random
import re
import subprocess
import sys
import unicodedata
from hashlib import sha256

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from matcher import (  # noqa: E402
    CV_SKILLS,
    _kw,
    _norm,
    analyze_skills_gap,
    analyze_tjm,
    get_country_id,
    match_job_to_cv,
    source_stats,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "ct_ai")
CORPUS_PATH = os.path.join(FIXTURES_DIR, "matcher_gold.json")

# --- Seuils de non-régression (mesurés, voir doc porte 3) -------------------
SEUIL_PERTINENCE = 40
PRECISION_MIN = 0.95
RAPPEL_MIN = 0.85
F1_MIN = 0.90
EXACTITUDE_MIN = 0.90
MARGE_OFFRES_NON_PERTINENTES = 50  # aucune offre label=0 ne doit atteindre ce score

# --- Empreinte du corpus d'évaluation (porte 7) -----------------------------
CORPUS_SHA256 = "7ae1461cb19ae2eaffe5cade524d578ba44569412a5e38879041ec1548327cdb"

# --- Motifs de données personnelles interdites dans le dépôt (porte 2) ------
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Domaines de démonstration : présents dans la documentation et les collections d'API
DOMAINES_FACTICES = ("example.com", "example.org", "example.net", "test.com",
                     "test.local", "localhost", "mail.com", "domain.com")


def _emails_reels(contenu):
    """Adresses e-mail hors domaines de démonstration."""
    return [m for m in EMAIL_RE.findall(contenu)
            if not any(m.lower().endswith(d) for d in DOMAINES_FACTICES)]
TEL_FR_RE = re.compile(r"(?:\+33|0)\s?[1-9](?:[\s.\-]?\d{2}){4}")
TEL_INTL_RE = re.compile(r"\+\d{1,3}[\s.\-]?\d{2}[\s.\-]?\d{2}[\s.\-]?\d{2}[\s.\-]?\d{2}")

OFFRE_NEUTRE = {
    "title": "Chef de projet capital investissement",
    "company": "Societe Generale de Batiment",
    "tags": "",
    "description": "Suivi des dossiers, relation client, reporting mensuel.",
    "salary": "",
    "remote_type": "",
    "freelance_status": "",
    "location": "",
    "source": "fixture",
}

OFFRE_QA = {
    "title": "Senior QA Engineer - Playwright Automation",
    "company": "Atelier Test",
    "tags": "playwright, selenium, python",
    "description": ("QA engineer, automation, test strategy, regression. "
                    "Freelance mission, TJM 600 EUR/jour."),
    "salary": "600-700 €/jour",
    "remote_type": "remote",
    "freelance_status": "VALIDÉE",
    "location": "Paris",
    "source": "fixture",
}


def _charger_corpus():
    with open(CORPUS_PATH, encoding="utf-8") as fh:
        return json.load(fh)["offres"]


def _matrice_confusion(corpus, seuil=SEUIL_PERTINENCE):
    tp = fp = fn = tn = 0
    for offre in corpus:
        score, _ = match_job_to_cv(copy.deepcopy(offre))
        predit = score >= seuil
        reel = offre["label"] == 1
        if predit and reel:
            tp += 1
        elif predit and not reel:
            fp += 1
        elif not predit and reel:
            fn += 1
        else:
            tn += 1
    return tp, fp, fn, tn


# ===========================================================================
# PORTE 2 — Données : le corpus d'évaluation est un livrable testable
# ===========================================================================

class TestPorte2Donnees:
    def test_corpus_etiquete_structure_complete(self):
        corpus = _charger_corpus()
        assert len(corpus) >= 20, "corpus trop petit pour mesurer quoi que ce soit"
        champs = {"id", "label", "title", "company", "description", "salary",
                  "remote_type", "freelance_status", "location"}
        ids = set()
        for offre in corpus:
            assert champs <= set(offre), f"champs manquants sur {offre.get('id')}"
            assert offre["label"] in (0, 1), "étiquette hors domaine"
            assert offre["id"] not in ids, f"identifiant dupliqué : {offre['id']}"
            ids.add(offre["id"])

    def test_corpus_equilibre_entre_classes(self):
        corpus = _charger_corpus()
        positifs = sum(1 for o in corpus if o["label"] == 1)
        negatifs = len(corpus) - positifs
        ratio = min(positifs, negatifs) / max(positifs, negatifs)
        assert ratio >= 0.5, "déséquilibre des classes : la métrique serait trompeuse"

    def test_aucune_donnee_personnelle_dans_les_fixtures(self):
        for nom in ("matcher_gold.json",):
            chemin = os.path.join(FIXTURES_DIR, nom)
            contenu = open(chemin, encoding="utf-8").read()
            assert not _emails_reels(contenu), f"adresse e-mail dans {nom}"
            assert not TEL_FR_RE.search(contenu), f"téléphone français dans {nom}"
            assert not TEL_INTL_RE.search(contenu), f"téléphone international dans {nom}"

    def test_aucune_donnee_personnelle_dans_les_fichiers_suivis(self):
        """Garde-fou permanent : le dépôt ne doit exposer aucune coordonnée."""
        try:
            fichiers = subprocess.run(
                ["git", "ls-files"], cwd=os.path.join(os.path.dirname(__file__), ".."),
                capture_output=True, text=True, check=True).stdout.split()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("dépôt git indisponible")
        suspects = []
        for rel in fichiers:
            if rel.endswith((".png", ".jpg", ".jpeg", ".gif", ".db", ".pdf")):
                continue
            try:
                contenu = open(os.path.join(os.path.dirname(__file__), "..", rel),
                               encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            emails = _emails_reels(contenu)
            if emails:
                suspects.append(f"{rel} -> {emails[0]}")
            for motif in (TEL_FR_RE, TEL_INTL_RE):
                trouve = motif.search(contenu)
                if trouve:
                    suspects.append(f"{rel} -> {trouve.group(0)}")
        assert not suspects, "données personnelles détectées : " + "; ".join(suspects)


# ===========================================================================
# PORTE 3 — Métriques de performance fonctionnelle verrouillées
# ===========================================================================

class TestPorte3Metriques:
    def test_matrice_de_confusion_et_seuils(self):
        corpus = _charger_corpus()
        tp, fp, fn, tn = _matrice_confusion(corpus)
        precision = tp / (tp + fp) if tp + fp else 0.0
        rappel = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * rappel / (precision + rappel) if precision + rappel else 0.0
        exactitude = (tp + tn) / len(corpus)

        assert precision >= PRECISION_MIN, (
            f"précision {precision:.3f} < {PRECISION_MIN} (TP={tp} FP={fp})")
        assert rappel >= RAPPEL_MIN, (
            f"rappel {rappel:.3f} < {RAPPEL_MIN} (TP={tp} FN={fn})")
        assert f1 >= F1_MIN, f"F1 {f1:.3f} < {F1_MIN}"
        assert exactitude >= EXACTITUDE_MIN, f"exactitude {exactitude:.3f}"

    def test_aucune_offre_hors_sujet_ne_depasse_la_marge(self):
        corpus = _charger_corpus()
        for offre in corpus:
            if offre["label"] == 0:
                score, _ = match_job_to_cv(copy.deepcopy(offre))
                assert score < MARGE_OFFRES_NON_PERTINENTES, (
                    f"{offre['id']} ({offre['title']}) score={score} : "
                    "une offre hors sujet remonte au niveau des offres pertinentes")

    def test_toutes_les_offres_pertinentes_au_dessus_du_seuil_avec_marge(self):
        corpus = _charger_corpus()
        manquees = [o["id"] for o in corpus
                    if o["label"] == 1 and match_job_to_cv(copy.deepcopy(o))[0] < SEUIL_PERTINENCE - 10]
        assert not manquees, f"offres pertinentes très en dessous du seuil : {manquees}"


# ===========================================================================
# PORTE 4 — Spécification et niveaux de test
# ===========================================================================

class TestPorte4NiveauxDeTest:
    def test_niveau_fonction_score_borne_et_traçable(self):
        corpus = _charger_corpus()
        for offre in corpus:
            score, matched = match_job_to_cv(copy.deepcopy(offre))
            assert isinstance(score, int)
            assert 0 <= score <= 100, f"score hors bornes : {score}"
            assert isinstance(matched, list)
            assert set(matched) <= set(CV_SKILLS), "compétence renvoyée inconnue du profil"

    def test_niveau_composant_pipeline_complet(self, sample_jobs):
        """Reproduit la chaîne de l'index : score + TJM + fraîcheur sur chaque offre."""
        from scraper import compute_freshness_score
        for offre in sample_jobs:
            score, matched = match_job_to_cv(copy.deepcopy(offre))
            tjm = analyze_tjm(copy.deepcopy(offre))
            fraicheur = compute_freshness_score(offre.get("date"))
            assert 0 <= score <= 100
            assert set(tjm) == {"tjm", "currency", "unit", "range", "flag"}
            assert fraicheur in ("A", "B", "C", "D", None)

    def test_niveau_integration_page_accueil(self, flask_client):
        """La page d'accueil doit rester servie avec le moteur de classement actif."""
        reponse = flask_client.get("/")
        assert reponse.status_code == 200, "page d'accueil non servie"
        corps = reponse.get_data(as_text=True)
        assert "JobHunt" in corps or "offre" in corps.lower()


# ===========================================================================
# PORTE 5 — Défis spécifiques : non-déterminisme, autonomie, robustesse
# ===========================================================================

class TestPorte5DefisSpecifiques:
    def test_repetabilite_deterministe(self):
        """200 exécutions identiques : oracle de répétabilité (le composant n'apprend pas en ligne)."""
        scores = {match_job_to_cv(copy.deepcopy(OFFRE_QA))[0] for _ in range(200)}
        assert len(scores) == 1, f"résultats instables : {sorted(scores)}"

    @pytest.mark.parametrize("offre", [
        {},
        {"title": None, "description": None, "tags": None, "salary": None,
         "remote_type": None, "freelance_status": None},
        {"title": 42, "description": [], "tags": {"a": 1}, "salary": 3.14,
         "remote_type": ["remote"], "freelance_status": True},
        {"title": "", "description": "", "tags": "", "salary": "",
         "remote_type": "", "freelance_status": ""},
    ])
    def test_robustesse_aux_champs_absents_ou_invalides(self, offre):
        score, matched = match_job_to_cv(copy.deepcopy(offre))
        assert 0 <= score <= 100
        assert isinstance(matched, list)

    @pytest.mark.parametrize("hostile", [
        "🧪" * 500,
        "\u202e" + "QA Engineer" + "\u202c",
        "<script>alert(1)</script> QA Engineer",
        "QA " * 5000,
        "Новости QA тестирование" * 50,
    ])
    def test_entrees_adverses_ne_cassent_pas_le_classement(self, hostile):
        offre = {**OFFRE_QA, "description": hostile}
        score, _ = match_job_to_cv(offre)
        assert 0 <= score <= 100

    def test_bornage_du_bourrage_de_mots_cles(self):
        """Une offre farcie de mots-clés ne peut pas dépasser le plafond des blocs titre+compétences."""
        offre = {**OFFRE_QA, "title": "QA " * 50,
                 "description": "qa test automation " * 500,
                 "salary": "", "remote_type": "", "freelance_status": ""}
        score, matched = match_job_to_cv(offre)
        assert score <= 70, f"bourrage de mots-clés non borné : {score}"
        assert len(matched) <= 24, "le plafond de compétences n'est plus respecté"

    def test_perte_d_information_signalee_pas_masquee(self):
        """Un champ métier inconnu ne doit pas être interprété comme une valeur par défaut favorable."""
        offre = {**OFFRE_QA, "remote_type": "sur site", "freelance_status": "REJETÉE"}
        score_avec, _ = match_job_to_cv(offre)
        offre_remote = {**OFFRE_QA, "remote_type": "remote", "freelance_status": "VALIDÉE"}
        score_sans, _ = match_job_to_cv(offre_remote)
        assert score_avec < score_sans


# ===========================================================================
# PORTE 6 — Techniques : relations métamorphiques, monotonie, dos à dos
# ===========================================================================

class TestPorte6Techniques:
    @pytest.mark.parametrize("nom,mutation", [
        ("MR-01 casse minuscule", lambda j: {**j, "title": j["title"].lower(),
                                             "description": j["description"].lower()}),
        ("MR-02 casse majuscule", lambda j: {**j, "title": j["title"].upper(),
                                             "description": j["description"].upper()}),
        ("MR-03 accents retirés", lambda j: {
            **j, "description": unicodedata.normalize("NFKD", j["description"])
            .encode("ascii", "ignore").decode()}),
        ("MR-04 espaces multiples", lambda j: {**j, "title": "  " + j["title"].replace(" ", "   ") + "  "}),
        ("MR-05 ponctuation finale", lambda j: {**j, "title": j["title"] + " !!!"}),
        ("MR-06 espaces en bord de description", lambda j: {**j, "description": "   " + j["description"] + "  "}),
        ("MR-07 ordre des phrases inversé", lambda j: {
            **j, "description": " ".join(reversed(j["description"].split(". ")))}),
    ])
    def test_invariance_au_bruit_de_saisie(self, nom, mutation):
        """Une variation de forme ne doit jamais changer la décision (même score)."""
        attendu, _ = match_job_to_cv(copy.deepcopy(OFFRE_QA))
        obtenu, _ = match_job_to_cv(copy.deepcopy(mutation(OFFRE_QA)))
        assert obtenu == attendu, f"{nom} : {attendu} -> {obtenu}"

    @pytest.mark.parametrize("valeur", ["remote", "Remote", "REMOTE", "fully_remote",
                                        "Fully Remote", "100% remote", "remote work"])
    def test_invariance_des_champs_metier_equivalents_full_remote(self, valeur):
        attendu, _ = match_job_to_cv({**OFFRE_QA, "remote_type": "remote"})
        obtenu, _ = match_job_to_cv({**OFFRE_QA, "remote_type": valeur})
        assert obtenu == attendu, f"remote_type={valeur!r} : {attendu} -> {obtenu}"

    @pytest.mark.parametrize("valeur", ["VALIDÉE", "VALIDEE", "validée", "Validée", "validee"])
    def test_invariance_du_statut_freelance(self, valeur):
        attendu, _ = match_job_to_cv({**OFFRE_QA, "freelance_status": "VALIDÉE"})
        obtenu, _ = match_job_to_cv({**OFFRE_QA, "freelance_status": valeur})
        assert obtenu == attendu, f"freelance_status={valeur!r} : {attendu} -> {obtenu}"

    @pytest.mark.parametrize("valeur", ["hybrid", "Hybrid", "HYBRIDE", "hybride", "télétravail partiel"])
    def test_invariance_des_valeurs_hybrides(self, valeur):
        attendu, _ = match_job_to_cv({**OFFRE_QA, "remote_type": "hybrid"})
        obtenu, _ = match_job_to_cv({**OFFRE_QA, "remote_type": valeur})
        assert obtenu == attendu, f"remote_type={valeur!r} : {attendu} -> {obtenu}"

    def test_monotonie_ajouter_une_competence_du_profil_ne_baisse_jamais_le_score(self):
        base = {**OFFRE_QA, "title": "QA engineer", "description": "equipe de test",
                "tags": "", "salary": "", "remote_type": "", "freelance_status": ""}
        score_base, _ = match_job_to_cv(base)
        for competence in CV_SKILLS:
            enrichi = {**base, "description": base["description"] + f" {competence}"}
            score, _ = match_job_to_cv(enrichi)
            assert score >= score_base, f"+{competence} a fait baisser le score"

    @pytest.mark.parametrize("texte", [
        "Chef de projet capital investissement",
        "Latest news about testing industry",
        "Rapidité de traitement et satisfaction client",
        "Réunion de lancement du projet",
    ])
    def test_aucun_faux_positif_par_sous_chaine(self, texte):
        """« api » dans « capital », « test » dans « latest » : plus de compétence fantôme."""
        offre = {**OFFRE_NEUTRE, "title": texte}
        score, matched = match_job_to_cv(offre)
        assert score == 0, f"{texte!r} obtient {score} avec {matched}"

    def test_fonction_de_detection_mot_entier(self):
        assert _kw(_norm("capital investissement"), "api") is False
        assert _kw(_norm("latest release"), "test") is False
        assert _kw(_norm("tests d'api"), "api") is True
        assert _kw(_norm("TEST MANAGEMENT"), "test management") is True
        assert _kw(_norm("ci/cd pipeline"), "ci/cd") is True

    def test_dos_a_dos_avec_implementation_de_reference(self):
        """Test dos à dos : le classement doit rester cohérent avec un comptage indépendant."""
        corpus = _charger_corpus()
        termes_qa = ("qa", "test", "recette", "quality", "qualite", "testeur", "sdet")

        def reference(offre):
            texte = _norm(f"{offre.get('title', '')} {offre.get('description', '')} {offre.get('tags', '')}")
            return 10 if any(_kw(texte, t) for t in termes_qa) else 0

        classement_moteur = [o["id"] for o in sorted(
            corpus, key=lambda o: -match_job_to_cv(copy.deepcopy(o))[0])[:8]]
        classement_reference = [o["id"] for o in sorted(
            corpus, key=lambda o: (-reference(o), -int(o["label"])))[:8]]
        accord = len(set(classement_moteur) & set(classement_reference))
        assert accord >= 5, f"divergence avec l'implémentation de référence ({accord}/8)"

    def test_classification_de_marche_couvre_les_places_reelles(self):
        attendus = {"Paris": "france", "Lyon": "france", "Genève": "suisse",
                    "Zürich": "suisse", "Lausanne": "suisse", "Bâle": "suisse",
                    "Luxembourg": "luxembourg", "Dubai": "dubai", "Singapour": "singapour"}
        for localisation, marche in attendus.items():
            assert get_country_id(localisation) == marche, localisation

    def test_marche_inconnu_n_est_pas_compare_au_marche_francais(self):
        assert get_country_id("Berlin") == "inconnu"
        assert get_country_id("") == "inconnu"
        analyse = analyze_tjm({"salary": "700 €/jour", "location": "Berlin", "title": "", "description": ""})
        assert analyse["range"] == "", "un marché inconnu ne doit pas produire de référence"
        assert analyse["flag"] == ""

    def test_valeurs_limites_du_salaire(self):
        assert analyze_tjm({"salary": "600-700 €/jour"})["tjm"] == 650
        assert analyze_tjm({"salary": "600 à 700 EUR /jour"})["tjm"] == 650
        assert analyze_tjm({"salary": "TJM: 550"})["tjm"] == 550
        assert analyze_tjm({"salary": "aucune information"})["tjm"] is None
        assert analyze_tjm({"salary": ""})["tjm"] is None
        haut = analyze_tjm({"salary": "99999 €/jour", "location": "Paris"})
        assert haut["tjm"] == 99999 and haut["flag"] == "🔺 Très haut"
        # Sans marché identifié, aucune comparaison n'est produite (pas de faux signal)
        sans_marche = analyze_tjm({"salary": "99999 €/jour", "location": "Berlin"})
        assert sans_marche["tjm"] == 99999 and sans_marche["flag"] == ""
        assert sans_marche["range"] == ""

    def test_permutation_des_offres_ne_change_pas_le_classement(self):
        """Règle de classement documentée : score décroissant, puis identifiant croissant.

        Sans départage explicite, deux offres à score égal s'échangent à chaque
        rafraîchissement selon l'ordre d'insertion en base : c'est un
        non-déterminisme d'affichage (app.index applique la même règle).
        """
        corpus = _charger_corpus()

        def classement(offres):
            return [o["id"] for o in sorted(
                offres, key=lambda o: (-match_job_to_cv(copy.deepcopy(o))[0], str(o["id"])))]

        reference = classement(corpus)
        melange = copy.deepcopy(corpus)
        random.Random(1234).shuffle(melange)
        assert classement(melange) == reference, (
            "le classement dépend de l'ordre d'entrée des offres")


# ===========================================================================
# PORTE 7 — Environnement d'évaluation verrouillé
# ===========================================================================

class TestPorte7Environnement:
    def test_corpus_de_reference_verrouille_par_empreinte(self):
        empreinte = sha256(open(CORPUS_PATH, "rb").read()).hexdigest()
        assert empreinte == CORPUS_SHA256, (
            "le corpus d'évaluation a été modifié sans mise à jour du verrou : "
            "toute modification doit être revue (les métriques des portes 3 et 5 "
            "sont mesurées sur CETTE version du corpus)")

    def test_corpus_sous_controle_de_version(self):
        try:
            suivis = subprocess.run(
                ["git", "ls-files", "tests/fixtures/ct_ai"],
                cwd=os.path.join(os.path.dirname(__file__), ".."),
                capture_output=True, text=True, check=True).stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("dépôt git indisponible")
        assert "matcher_gold.json" in suivis, "corpus d'évaluation non versionné"


# ===========================================================================
# Non-régression métier : comportements historiques à ne pas casser
# ===========================================================================

class TestNonRegressionMetier:
    def test_offre_freelance_qa_reste_en_tete(self):
        score_qa, _ = match_job_to_cv(copy.deepcopy(OFFRE_QA))
        score_hors_sujet, _ = match_job_to_cv(copy.deepcopy(OFFRE_NEUTRE))
        assert score_qa >= 60, f"l'offre QA freelance ne remonte plus : {score_qa}"
        assert score_qa > score_hors_sujet

    def test_statut_rejete_ne_rapporte_aucun_point(self):
        rejete, _ = match_job_to_cv({**OFFRE_QA, "freelance_status": "REJETÉE"})
        valide, _ = match_job_to_cv({**OFFRE_QA, "freelance_status": "VALIDÉE"})
        ambigue, _ = match_job_to_cv({**OFFRE_QA, "freelance_status": "AMBIGUË"})
        assert valide == rejete + 10
        assert ambigue == rejete + 5

    def test_analyse_de_lacune_de_competences_reste_stable(self, sample_jobs):
        resultat = analyze_skills_gap(sample_jobs)
        assert set(resultat) == {"top_demanded", "missing", "match_rate"}
        assert 0 <= resultat["match_rate"] <= 100

    def test_stats_par_source_coherentes(self, sample_jobs):
        stats = source_stats(sample_jobs)
        total = sum(s["total"] for s in stats)
        assert total == len(sample_jobs)
        for source in stats:
            assert 0 <= source["freelance_pct"] <= 100
