"""Profil utilisateur (M15).

Priorité aux cas négatifs — c'est là que se trouvent les risques (fuite de
données d'autrui, écriture non validée). Les appels Supabase sont interceptés :
aucun service externe, aucun secret, aucune donnée réelle.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.api, pytest.mark.backend]

CHAMPS_AUTORISES = ("full_name", "headline", "location", "phone", "bio", "preferences")


def _connecter(client, uid: str = "u-test") -> None:
    with client.session_transaction() as session:
        session["user_id"] = uid
        session["email"] = "qa@example.com"


class _ReponseFactice:
    status_code = 200
    text = ""

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class TestAccesRefuse:
    def test_lire_le_profil_sans_session_renvoie_401(self, flask_client):
        reponse = flask_client.get("/api/profile")
        assert reponse.status_code == 401
        assert reponse.get_json()["error"] == "Non authentifié"

    def test_modifier_le_profil_sans_session_renvoie_401(self, flask_client):
        reponse = flask_client.put("/api/profile", json={"full_name": "Intrus"})
        assert reponse.status_code == 401

    def test_envoyer_un_avatar_sans_session_renvoie_401(self, flask_client):
        reponse = flask_client.post("/api/profile/avatar", json={"avatar": "AAAA"})
        assert reponse.status_code == 401


class TestValidation:
    def test_modifier_sans_donnee_valide_renvoie_400(self, flask_client):
        _connecter(flask_client)

        reponse = flask_client.put("/api/profile", json={})

        assert reponse.status_code == 400
        assert reponse.get_json()["error"] == "Aucune donnée valide"

    def test_les_champs_non_autorises_sont_ignores(self, flask_client):
        _connecter(flask_client)

        # `role` n'est pas dans la liste blanche : la requête est refusée faute
        # de champ valide, ce qui prouve que le champ n'a pas été transmis.
        reponse = flask_client.put("/api/profile", json={"role": "admin"})

        assert reponse.status_code == 400

    def test_seuls_les_champs_autorises_partent_vers_le_profil(self, flask_client, monkeypatch):
        import app as app_module

        _connecter(flask_client)
        envoyes = []

        def faux_post(url, headers=None, json=None, timeout=None):
            envoyes.append(json)
            return _ReponseFactice({"id": "u-test", "full_name": "Atman"})

        monkeypatch.setattr(app_module.requests, "post", faux_post)

        reponse = flask_client.put(
            "/api/profile",
            json={"full_name": "Atman", "role": "admin", "email": "pirate@example.com"},
        )

        assert reponse.status_code == 200
        assert envoyes, "aucun envoi vers le profil"
        assert set(envoyes[0]) <= set(CHAMPS_AUTORISES) | {"id", "email"}
        assert "role" not in envoyes[0]

    def test_envoyer_un_avatar_sans_image_renvoie_400(self, flask_client):
        _connecter(flask_client)

        reponse = flask_client.post("/api/profile/avatar", json={})

        assert reponse.status_code == 400
        assert reponse.get_json()["error"] == "Image requise"


class TestPageParametres:
    def test_la_page_parametres_est_servie(self, flask_client):
        reponse = flask_client.get("/settings")
        assert reponse.status_code == 200
