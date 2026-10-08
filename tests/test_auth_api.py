"""Contrats d'authentification et rafraîchissement (M1 côté API, M13).

Les réponses du fournisseur d'identité sont remplacées par des doublures : on
vérifie ce que JobHunt fait de chaque réponse (400/401/500), pas le fournisseur.
"""

from __future__ import annotations

import threading

import pytest

pytestmark = [pytest.mark.api, pytest.mark.backend]


class _AuthQuiRefuse:
    """Doublure de service d'auth : refuse systématiquement."""

    def sign_up(self, _payload):
        raise Exception("User already registered")

    def sign_in_with_password(self, _payload):
        raise Exception("Invalid login credentials")


class TestEtatDeSession:
    def test_me_sans_session_est_anonyme(self, flask_client):
        reponse = flask_client.get("/api/auth/me")

        assert reponse.status_code == 200
        assert reponse.get_json() == {"authenticated": False}

    def test_me_avec_session_renvoie_l_utilisateur(self, flask_client):
        with flask_client.session_transaction() as session:
            session["user_id"] = "u-1"
            session["email"] = "qa@example.com"

        corps = flask_client.get("/api/auth/me").get_json()

        assert corps["authenticated"] is True
        assert corps["user_id"] == "u-1"
        assert corps["email"] == "qa@example.com"

    def test_la_page_de_connexion_redirige_si_deja_connecte(self, flask_client):
        with flask_client.session_transaction() as session:
            session["user_id"] = "u-1"

        reponse = flask_client.get("/login")

        assert reponse.status_code == 302
        assert reponse.headers["Location"].endswith("/")

    def test_la_deconnexion_vide_la_session(self, flask_client):
        with flask_client.session_transaction() as session:
            session["user_id"] = "u-1"

        reponse = flask_client.post("/api/auth/logout")

        assert reponse.status_code == 200
        assert reponse.get_json() == {"ok": True}
        assert flask_client.get("/api/auth/me").get_json() == {"authenticated": False}


class TestRefusDuFournisseur:
    def test_sans_service_configure_l_inscription_renvoie_500(self, flask_client, monkeypatch):
        import app as app_module

        monkeypatch.setattr(app_module, "_supabase_auth", None)

        reponse = flask_client.post("/api/auth/signup", json={"email": "qa@example.com", "password": "secret1"})

        assert reponse.status_code == 500
        assert "not configured" in reponse.get_json()["error"]

    def test_un_mot_de_passe_trop_court_est_refuse_avant_le_service(self, flask_client, monkeypatch):
        import app as app_module

        monkeypatch.setattr(app_module, "_supabase_auth", _AuthQuiRefuse())

        reponse = flask_client.post("/api/auth/signup", json={"email": "qa@example.com", "password": "123"})

        assert reponse.status_code == 400
        assert "6 caractères" in reponse.get_json()["error"]

    def test_un_email_deja_utilise_renvoie_un_message_clair(self, flask_client, monkeypatch):
        import app as app_module

        monkeypatch.setattr(app_module, "_supabase_auth", _AuthQuiRefuse())

        reponse = flask_client.post("/api/auth/signup", json={"email": "qa@example.com", "password": "secret1"})

        assert reponse.status_code == 400
        assert "déjà utilisé" in reponse.get_json()["error"]

    def test_des_identifiants_invalides_renvoient_401(self, flask_client, monkeypatch):
        import app as app_module

        monkeypatch.setattr(app_module, "_supabase_auth", _AuthQuiRefuse())

        reponse = flask_client.post("/api/auth/login", json={"email": "qa@example.com", "password": "secret1"})

        assert reponse.status_code == 401
        assert reponse.get_json()["error"] == "Email ou mot de passe incorrect"


class TestFiltreApi:
    def test_le_filtre_unapplied_exclut_les_offres_postulees(self, seeded_client, seeded_api, test_db):
        test_db.execute("UPDATE jobs SET applied = 1 WHERE id = ?", (seeded_api["ids"][0],))
        test_db.commit()

        offres = seeded_client.get("/api/jobs?unapplied=1").get_json()

        assert offres, "le filtre ne doit pas vider la liste"
        assert all(offre["applied"] == 0 for offre in offres)


class TestRafraichissement:
    def test_refresh_declenche_le_scraping_en_tache_de_fond(self, flask_client, monkeypatch):
        import app as app_module

        appele = threading.Event()
        monkeypatch.setattr(app_module, "fetch_all", lambda: [])
        monkeypatch.setattr(app_module, "save_jobs", lambda offres: appele.set() or 0)

        reponse = flask_client.post("/api/refresh")

        assert reponse.status_code == 200
        assert reponse.get_json() == {"status": "started"}
        assert appele.wait(timeout=5), "le scraping n'a pas été déclenché"
