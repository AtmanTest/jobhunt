"""Pages publiques et vitrines (M18).

Fumée de disponibilité : chaque page répond et ne lève pas d'exception. Le
calcul de score du POC est vérifié sur son **invariant** : la décision ne doit
pas dépendre de la forme de la saisie (casse, espaces, ponctuation).
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.api, pytest.mark.backend]

PAGES = (
    "/",
    "/about",
    "/changelog",
    "/marche-qa",
    "/cycle-de-vie",
    "/stats",
    "/jobclotured",
    "/monitoring",
    "/qa",
    "/poc-ct-ai",
    "/poc-delivery",
    "/settings",
)

OFFRE = {
    "title": "QA Automation Engineer Playwright",
    "description": (
        "Mission freelance QA : automatisation des tests end-to-end avec Playwright, "
        "Cypress et Python, intégration continue, stratégie de test et API testing."
    ),
    "tags": "QA, Playwright, Cypress, Python",
    "salary": "600 EUR",
    "location": "Paris, France",
    "remote_type": "remote",
    "freelance_status": "VALIDÉE",
}


class TestDisponibilite:
    @pytest.mark.parametrize("page", PAGES)
    def test_la_page_repond(self, api_env, page):
        with api_env.test_client() as client:
            reponse = client.get(page)
        assert reponse.status_code in (200, 302), f"{page} a répondu {reponse.status_code}"


class TestPreuvesCtAi:
    def test_les_preuves_sont_servies_ou_signalees(self, api_env):
        with api_env.test_client() as client:
            reponse = client.get("/poc-ct-ai/api/evidence")

        # 200 si les preuves ont été générées, 503 sinon : jamais 500.
        assert reponse.status_code in (200, 503)


class TestScoreInvariant:
    def test_le_score_ne_depend_pas_de_la_forme_de_la_saisie(self, api_env):
        with api_env.test_client() as client:
            reponse = client.post("/poc-ct-ai/api/score", json=OFFRE)

        assert reponse.status_code == 200
        corps = reponse.get_json()
        assert corps["invariance_ok"] is True
        assert all(variante["identique"] for variante in corps["controle"])
        # Le score de référence doit être présent et borné.
        assert 0 <= corps["score"] <= 100


class TestScenariosDelivery:
    def test_le_scenario_de_livraison_est_servi(self, api_env):
        with api_env.test_client() as client:
            reponse = client.get("/poc-delivery/api/scenario")

        assert reponse.status_code == 200
        assert reponse.get_json() is not None
