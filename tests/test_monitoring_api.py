"""Monitoring de disponibilité (M16).

Le fichier de données est redirigé vers `tmp_path` : aucun état partagé, aucun
fichier de développement modifié, aucun appel réseau (les sondes ne sont pas
déclenchées — seul `check-one` sur un site inconnu est exercé).
"""

from __future__ import annotations

import json

import pytest

pytestmark = [pytest.mark.api, pytest.mark.backend]


@pytest.fixture
def monitor_client(flask_client, tmp_path, monkeypatch):
    """Client Flask dont le stockage monitoring pointe dans `tmp_path`."""
    import app as app_module

    fichier = tmp_path / "monitor.json"
    monkeypatch.setattr(app_module, "MONITOR_FILE", str(fichier))
    return flask_client


class TestLecture:
    def test_la_liste_des_sites_est_structuree(self, monitor_client):
        reponse = monitor_client.get("/api/monitor/sites")

        assert reponse.status_code == 200
        corps = reponse.get_json()
        assert corps == {"sites": [], "alerts": []}


class TestAjout:
    def test_une_url_vide_est_refusee(self, monitor_client):
        reponse = monitor_client.post("/api/monitor/sites", json={"url": ""})

        assert reponse.status_code == 400
        assert reponse.get_json()["error"] == "URL invalide"

    def test_ajouter_deux_fois_le_meme_site_est_idempotent(self, monitor_client):
        for _ in range(2):
            reponse = monitor_client.post(
                "/api/monitor/sites", json={"url": "https://exemple.test", "name": "Exemple"}
            )
            assert reponse.status_code == 200

        sites = monitor_client.get("/api/monitor/sites").get_json()["sites"]
        assert len(sites) == 1
        assert sites[0]["name"] == "Exemple"


class TestSuppression:
    def test_supprimer_un_site_le_retire(self, monitor_client):
        monitor_client.post("/api/monitor/sites", json={"url": "https://exemple.test"})

        reponse = monitor_client.delete("/api/monitor/sites", json={"url": "https://exemple.test"})

        assert reponse.status_code == 200
        assert monitor_client.get("/api/monitor/sites").get_json()["sites"] == []


class TestSondeIsolee:
    def test_verifier_un_site_inconnu_ne_plante_pas(self, monitor_client):
        reponse = monitor_client.post("/api/monitor/check-one", json={"url": "https://inconnu.test"})

        assert reponse.status_code == 200
        assert monitor_client.get("/api/monitor/sites").get_json()["sites"] == []

    def test_le_stockage_est_bien_du_json(self, monitor_client, tmp_path):
        monitor_client.post("/api/monitor/sites", json={"url": "https://exemple.test"})

        contenu = json.loads((tmp_path / "monitor.json").read_text())
        assert "https://exemple.test" in contenu["sites"]
