"""Vérifie que la démonstration de chaîne de livraison raconte bien l'histoire annoncée.

Cette suite protège la vitrine elle-même : si le code du produit simulé, un cas de test
ou les critères de sortie changent, la démonstration Web deviendrait mensongère
(afficher « 5 anomalies » alors qu'il n'y en a plus, par exemple). Ces tests
verrouillent donc le scénario : livraison v1 défectueuse, correctif v2 qui répare mais
casse ailleurs, correctif v3 conforme, verdict final GO.

Principe : les tests du produit simulé sont eux-mêmes testés.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import virtual_delivery as vd  # noqa: E402


# ---------------------------------------------------------------------------
# Cohérence de la base de test elle-même
# ---------------------------------------------------------------------------

class TestBaseDeTest:
    def test_chaque_cas_est_rattache_a_une_user_story_existante(self):
        ids_us = {us["id"] for us in vd.USER_STORIES}
        for cas in vd.CAS_DE_TEST:
            assert cas["us"] in ids_us, f"{cas['id']} rattaché à une US inexistante"

    def test_chaque_cas_reference_un_critere_d_acceptation(self):
        criteres = {ca["id"] for us in vd.USER_STORIES for ca in us["criteres"]}
        for cas in vd.CAS_DE_TEST:
            assert cas["ca"] in criteres, f"{cas['id']} référence un critère inexistant"

    def test_tracabilite_complete(self):
        """Aucun critère d'acceptation ne doit rester sans cas de test."""
        non_couverts = [ligne for ligne in vd.tracabilite() if not ligne["couvert"]]
        assert not non_couverts, f"critères non couverts : {[l['critere'] for l in non_couverts]}"

    def test_identifiants_de_cas_uniques(self):
        ids = [c["id"] for c in vd.CAS_DE_TEST]
        assert len(ids) == len(set(ids))

    def test_suite_contient_les_types_attendus(self):
        types = {c["type"] for c in vd.CAS_DE_TEST}
        for attendu in ("fonctionnel", "limite", "table de décision", "régression"):
            assert attendu in types, f"aucun cas de type {attendu}"


# ---------------------------------------------------------------------------
# Livraison v1 : la campagne doit trouver les défauts annoncés
# ---------------------------------------------------------------------------

class TestLivraisonV1:
    def test_campagne_v1_echoue_sur_les_defauts_injectes(self):
        synthese = vd.executer_campagne("v1")["synthese"]
        assert synthese["echecs"] == 5
        assert synthese["ids_en_echec"] == ["TC-03", "TC-04", "TC-06", "TC-08", "TC-12"]

    def test_v1_ne_permet_pas_le_go(self):
        rapport = vd.rapport_final("v1")
        assert rapport["criteres_sortie"]["go"] is False
        assert len(rapport["anomalies"]) == 5

    def test_chaque_anomalie_porte_les_informations_obligatoires(self):
        anomalies = vd.rapports_anomalie(vd.executer_campagne("v1")["resultats"])
        champs = {"id", "titre", "exigence", "severite", "priorite", "etapes", "attendu", "obtenu", "detecte_par"}
        for anomalie in anomalies:
            assert champs <= set(anomalie), f"rapport incomplet : {anomalie['id']}"
            assert anomalie["obtenu"] != anomalie["attendu"]

    def test_les_defauts_de_borne_et_de_tri_sont_bien_detectes(self):
        resultats = {r["cas"]: r for r in vd.executer_campagne("v1")["resultats"]}
        assert resultats["TC-04"]["statut"] == "en échec"  # borne inclusive du budget
        assert resultats["TC-06"]["statut"] == "en échec"  # sens du tri
        assert resultats["TC-08"]["statut"] == "en échec"  # index de pagination
        assert resultats["TC-03"]["statut"] == "en échec"  # casse du filtre


# ---------------------------------------------------------------------------
# Correctif v2 : répare une partie, casse ailleurs (c'est le cœur de la démo)
# ---------------------------------------------------------------------------

class TestCorrectifV2:
    def test_confirmation_v2_laisse_deux_anomalies_ouvertes(self):
        ids_v1 = vd.executer_campagne("v1")["synthese"]["ids_en_echec"]
        confirmation = vd.executer_campagne("v2", cas_ids=ids_v1)["synthese"]
        assert confirmation["reussis"] == 3
        assert confirmation["ids_en_echec"] == ["TC-03", "TC-12"]

    def test_regression_v2_casse_des_tests_qui_passaient(self):
        """Deux tests verts en v1 deviennent rouges en v2 : régression avérée."""
        verts_v1 = {r["cas"] for r in vd.executer_campagne("v1")["resultats"] if r["statut"] == "réussi"}
        rouges_v2 = set(vd.executer_campagne("v2")["synthese"]["ids_en_echec"])
        regressions = sorted(verts_v1 & rouges_v2)
        assert regressions == ["TC-01", "TC-10"], f"régressions attendues TC-01 et TC-10, obtenues {regressions}"

    def test_test_de_confirmation_ne_remplace_pas_le_test_de_regression(self):
        """La sélection des tests en échec ne suffit pas à voir la régression."""
        ids_v1 = vd.executer_campagne("v1")["synthese"]["ids_en_echec"]
        confirmation = set(vd.executer_campagne("v2", cas_ids=ids_v1)["synthese"]["ids_en_echec"])
        regression = set(vd.executer_campagne("v2")["synthese"]["ids_en_echec"])
        assert "TC-10" not in confirmation, "TC-10 ne fait pas partie des tests rejoués en confirmation"
        assert "TC-10" in regression, "TC-10 doit être détecté par la campagne de régression"

    def test_v2_ne_permet_pas_le_go(self):
        synthese = vd.executer_campagne("v2")["synthese"]
        anomalies = vd.rapports_anomalie(vd.executer_campagne("v2")["resultats"])
        assert vd.evaluer_criteres_sortie(synthese and vd.executer_campagne("v2")["resultats"], anomalies)["go"] is False


# ---------------------------------------------------------------------------
# Correctif v3 : conforme, le Go doit tomber
# ---------------------------------------------------------------------------

class TestCorrectifV3:
    def test_confirmation_v3_tout_vert(self):
        ids_v2 = vd.executer_campagne("v2")["synthese"]["ids_en_echec"]
        confirmation = vd.executer_campagne("v3", cas_ids=ids_v2)["synthese"]
        assert confirmation["echecs"] == 0

    def test_regression_v3_tout_vert(self):
        synthese = vd.executer_campagne("v3")["synthese"]
        assert synthese["reussis"] == synthese["executes"] == len(vd.CAS_DE_TEST)

    def test_verdict_final_go(self):
        rapport = vd.rapport_final("v3")
        assert rapport["criteres_sortie"]["go"] is True
        assert rapport["anomalies"] == []
        assert all(c["ok"] for c in rapport["criteres_sortie"]["criteres"])

    def test_scenario_complet_coherent(self):
        scenario = vd.scenario_complet()
        assert scenario["v1_campagne"]["synthese"]["echecs"] == 5
        assert scenario["v2_regression"]["synthese"]["echecs"] == 4
        assert scenario["v3_regression"]["synthese"]["echecs"] == 0
        assert scenario["v3_verdict"]["go"] is True


# ---------------------------------------------------------------------------
# Robustesse du moteur de démonstration
# ---------------------------------------------------------------------------

class TestMoteur:
    def test_version_inconnue_ne_plante_pas(self):
        resultats = vd.executer_campagne("v9")["resultats"]
        assert len(resultats) == len(vd.CAS_DE_TEST)

    def test_campagne_vide_est_geree(self):
        campagne = vd.executer_campagne("v1", cas_ids=["TC-INEXISTANT"])
        assert campagne["synthese"]["executes"] == 0
        assert campagne["synthese"]["taux_reussite"] == 0.0

    def test_un_cas_qui_plante_est_un_echec_pas_une_exception(self):
        cas_casse = {"id": "TC-X", "titre": "cas cassé", "us": "US-101", "ca": "CA-101-1",
                     "type": "fonctionnel", "priorite": "mineur", "technique": "test",
                     "etapes": "aucune", "attendu": "rien",
                     "fonction": lambda v: 1 / 0, "attendu_valeur": []}
        resultat = vd.executer_cas(cas_casse, "v1")
        assert resultat["statut"] == "en échec"
        assert "ZeroDivisionError" in resultat["obtenu"]

    def test_criteres_de_sortie_detectent_chaque_manquement(self):
        resultats = vd.executer_campagne("v1")["resultats"]
        evaluation = vd.evaluer_criteres_sortie(resultats, vd.rapports_anomalie(resultats))
        assert evaluation["go"] is False
        assert any(not c["ok"] and "critique" in c["critere"] for c in evaluation["criteres"])

    @pytest.mark.parametrize("version", ["v1", "v2", "v3"])
    def test_toutes_les_versions_repondent_les_12_cas(self, version):
        campagne = vd.executer_campagne(version)
        assert campagne["synthese"]["executes"] == len(vd.CAS_DE_TEST)
        assert all(r["statut"] in ("réussi", "en échec") for r in campagne["resultats"])
