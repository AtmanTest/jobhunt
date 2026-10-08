"""Cockpit QA (M17) — inventaire et déclenchement CI.

Aucun déclenchement réel de workflow GitHub : l'absence de jeton doit produire
une erreur explicite (400) plutôt qu'un appel sortant.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.api, pytest.mark.backend]


class TestInventaire:
    def test_l_inventaire_des_cas_est_servi(self, flask_client):
        reponse = flask_client.get("/qa/api/test-cases")

        assert reponse.status_code == 200
        assert isinstance(reponse.get_json(), dict)


class TestExecutions:
    def test_la_liste_des_executions_est_servie(self, flask_client):
        reponse = flask_client.get("/qa/api/runs")

        assert reponse.status_code == 200
        assert "runs" in reponse.get_json()

    def test_une_execution_inconnue_reste_en_attente(self, flask_client):
        reponse = flask_client.get("/qa/api/runs/identifiant-inexistant")

        assert reponse.status_code == 200
        corps = reponse.get_json()
        assert corps["run_id"] == "identifiant-inexistant"
        assert corps["status"] == "pending"


class TestDeclenchement:
    def test_sans_jeton_github_le_declenchement_est_refuse(self, flask_client, monkeypatch):
        import app as app_module

        monkeypatch.setattr(app_module, "GITHUB_TOKEN", "")

        reponse = flask_client.post("/qa/api/github/trigger", json={"suites": "playwright"})

        assert reponse.status_code == 400
        assert "GITHUB_TOKEN" in reponse.get_json()["error"]
