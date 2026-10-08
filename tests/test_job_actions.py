"""Actions sur une offre (M9) et persistance « offre clôturée » (M10).

Périmètre : sauvegarde, candidature, note, pipeline, clic, enrichissement, et
l'enregistrement d'une offre masquée. Chaque cas vérifie le **contrat** de la
route (statut HTTP + effet en base), jamais l'implémentation interne.

Isolation : toutes les écritures vont dans la base SQLite temporaire du test ;
`scraper.DB_PATH` est aligné par la fixture `api_env`. Aucun appel réseau :
les synchronisations Supabase/GitHub sont neutralisées par `monkeypatch`.
"""

from __future__ import annotations

import html
import sqlite3

import pytest

pytestmark = [pytest.mark.api, pytest.mark.backend]


def _row(db_path: str, sql: str, params: tuple = ()):
    """Lit une ligne avec une connexion NEUVE (évite les instantanés périmés)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def _count(db_path: str, sql: str, params: tuple = ()) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, params).fetchone()[0]
    finally:
        conn.close()


class TestSauvegarde:
    def test_sauvegarder_puis_desauvegarder_bascule_le_drapeau(self, seeded_client, seeded_api, test_db_path):
        job_id = seeded_api["ids"][0]

        reponse = seeded_client.post(f"/api/jobs/{job_id}/save")
        assert reponse.status_code == 200
        assert reponse.get_json() == {"status": "ok", "saved": True}
        assert _row(test_db_path, "SELECT saved FROM jobs WHERE id = ?", (job_id,))["saved"] == 1

        reponse = seeded_client.post(f"/api/jobs/{job_id}/save")
        assert reponse.get_json()["saved"] is False
        assert _row(test_db_path, "SELECT saved FROM jobs WHERE id = ?", (job_id,))["saved"] == 0

    def test_sauvegarder_une_offre_inconnue_renvoie_404(self, seeded_client):
        reponse = seeded_client.post("/api/jobs/999999/save")
        assert reponse.status_code == 404
        assert reponse.get_json()["error"] == "Job not found"


class TestCandidature:
    def test_postuler_marque_l_offre_et_cree_la_candidature(self, seeded_client, seeded_api, test_db_path):
        job_id = seeded_api["ids"][0]

        reponse = seeded_client.post(
            f"/api/jobs/{job_id}/apply",
            json={"status": "postulé", "cover_letter": "Bonjour", "notes": "Relance lundi"},
        )

        assert reponse.status_code == 200
        assert reponse.get_json()["pipeline_status"] == "postulé"
        job = _row(test_db_path, "SELECT applied, cover_letter FROM jobs WHERE id = ?", (job_id,))
        assert job["applied"] == 1
        assert job["cover_letter"] == "Bonjour"
        candidature = _row(test_db_path, "SELECT status, notes FROM applications WHERE job_id = ?", (job_id,))
        assert candidature["status"] == "postulé"
        assert candidature["notes"] == "Relance lundi"

    def test_postuler_deux_fois_ne_cree_qu_une_candidature(self, seeded_client, seeded_api, test_db_path):
        job_id = seeded_api["ids"][1]

        seeded_client.post(f"/api/jobs/{job_id}/apply", json={"status": "postulé"})
        seeded_client.post(f"/api/jobs/{job_id}/apply", json={"status": "entretien"})

        assert _count(test_db_path, "SELECT COUNT(*) FROM applications WHERE job_id = ?", (job_id,)) == 1
        assert (
            _row(test_db_path, "SELECT status FROM applications WHERE job_id = ?", (job_id,))["status"]
            == "entretien"
        )

    def test_postuler_une_offre_inconnue_renvoie_404(self, seeded_client):
        reponse = seeded_client.post("/api/jobs/999999/apply", json={})
        assert reponse.status_code == 404


class TestSuivi:
    def test_une_note_est_persistee(self, seeded_client, seeded_api, test_db_path):
        job_id = seeded_api["ids"][2]

        reponse = seeded_client.post(f"/api/jobs/{job_id}/notes", json={"notes": "À relancer vendredi"})

        assert reponse.status_code == 200
        assert _row(test_db_path, "SELECT notes FROM jobs WHERE id = ?", (job_id,))["notes"] == "À relancer vendredi"

    def test_le_pipeline_est_mis_a_jour(self, seeded_client, seeded_api, test_db_path):
        job_id = seeded_api["ids"][3]

        reponse = seeded_client.post(f"/api/jobs/{job_id}/pipeline", json={"status": "entretien"})

        assert reponse.get_json()["pipeline_status"] == "entretien"
        assert (
            _row(test_db_path, "SELECT status FROM applications WHERE job_id = ?", (job_id,))["status"]
            == "entretien"
        )

    def test_un_clic_marque_l_offre_comme_vue(self, seeded_client, seeded_api, test_db_path):
        job_id = seeded_api["ids"][4]

        reponse = seeded_client.get(f"/api/job/{job_id}/click")

        assert reponse.status_code == 200
        assert _row(test_db_path, "SELECT viewed FROM jobs WHERE id = ?", (job_id,))["viewed"] == 1


class TestOffreMasquee:
    def test_masquer_deux_fois_n_enregistre_qu_une_entree(self, seeded_client, seeded_api, test_db_path, monkeypatch):
        import app as app_module

        # Aucune synchronisation externe pendant le test : on isole le contrat HTTP.
        monkeypatch.setattr(app_module, "_sync_dismissed_to_supabase", lambda uid: None)
        monkeypatch.setattr(app_module, "_push_closed_jobs_to_github", lambda: None)
        job_id = seeded_api["ids"][5]
        job = _row(test_db_path, "SELECT title, company FROM jobs WHERE id = ?", (job_id,))

        seeded_client.post(f"/api/job/{job_id}/stage", json={"stage": "dismissed"})
        seeded_client.post(f"/api/job/{job_id}/stage", json={"stage": "dismissed"})

        assert (
            _count(
                test_db_path,
                "SELECT COUNT(*) FROM dismissed_jobs WHERE LOWER(TRIM(title)) = LOWER(TRIM(?))",
                (job["title"],),
            )
            == 1
        )

    def test_la_page_des_offres_cloturees_liste_le_restant(self, seeded_client, seeded_api, test_db_path, monkeypatch):
        import app as app_module

        monkeypatch.setattr(app_module, "_sync_dismissed_to_supabase", lambda uid: None)
        monkeypatch.setattr(app_module, "_push_closed_jobs_to_github", lambda: None)
        job_id = seeded_api["ids"][6]
        titre = _row(test_db_path, "SELECT title FROM jobs WHERE id = ?", (job_id,))["title"]

        seeded_client.post(f"/api/job/{job_id}/stage", json={"stage": "dismissed"})
        reponse = seeded_client.get("/jobclotured")

        assert reponse.status_code == 200
        page = html.unescape(reponse.get_data(as_text=True))
        # La route normalise le titre en minuscules avant enregistrement.
        assert titre.lower() in page.lower()
        assert _count(test_db_path, "SELECT COUNT(*) FROM dismissed_jobs") == 1


class TestEnrichissement:
    def test_refuse_derriere_un_proxy_public(self, seeded_client, seeded_api):
        reponse = seeded_client.get(
            f"/api/jobs/enrich/{seeded_api['ids'][0]}",
            headers={"X-Forwarded-For": "203.0.113.7"},
        )
        assert reponse.status_code == 403

    def test_une_offre_inconnue_renvoie_404(self, seeded_client):
        reponse = seeded_client.get("/api/jobs/enrich/999999")
        assert reponse.status_code == 404

    def test_une_description_trop_courte_renvoie_400(self, seeded_client, test_db):
        test_db.execute(
            "INSERT INTO jobs (title, company, url, description) VALUES (?, ?, ?, ?)",
            ("QA", "Acme", "https://exemple.test/qa", "Trop court"),
        )
        test_db.commit()
        job_id = test_db.execute("SELECT MAX(id) FROM jobs").fetchone()[0]

        reponse = seeded_client.get(f"/api/jobs/enrich/{job_id}")

        assert reponse.status_code == 400
        assert reponse.get_json()["error"] == "Description too short or empty"
