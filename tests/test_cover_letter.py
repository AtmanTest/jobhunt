"""Lettre de motivation (M11) — affichage de la page et routes API.

Non-régression DE-001 : la route `/cover-letter/<id>` référençait un template
absent (`cover_letter.html`) et répondait 500 sur le bouton ✉️ de chaque carte.
Le template a été créé ; les cas ci-dessous verrouillent le comportement.
"""

from __future__ import annotations

import html
import sqlite3

import pytest

pytestmark = [pytest.mark.api, pytest.mark.backend]


def _job(db_path: str, job_id: int):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT title, company FROM jobs WHERE id = ?", (job_id,)).fetchone()
    finally:
        conn.close()


class TestAffichageDeLaLettre:
    @pytest.mark.regression
    def test_la_lettre_s_affiche_pour_une_offre(self, seeded_client, seeded_api, test_db_path):
        job_id = seeded_api["ids"][0]
        job = _job(test_db_path, job_id)

        reponse = seeded_client.get(f"/cover-letter/{job_id}")

        assert reponse.status_code == 200
        page = html.unescape(reponse.get_data(as_text=True))
        assert job["title"] in page
        assert job["company"] in page
        assert "Lettre de motivation" in page

    @pytest.mark.regression
    def test_une_offre_inconnue_renvoie_404(self, seeded_client):
        reponse = seeded_client.get("/cover-letter/999999")

        assert reponse.status_code == 404
        assert "Job non trouvé" in reponse.get_data(as_text=True)


class TestGeneration:
    def test_generate_cover_renvoie_une_lettre_json(self, seeded_client, seeded_api, test_db_path):
        job_id = seeded_api["ids"][0]
        job = _job(test_db_path, job_id)

        reponse = seeded_client.get(f"/api/generate-cover/{job_id}")

        assert reponse.status_code == 200
        lettre = reponse.get_json()["cover_letter"]
        assert job["title"] in lettre
        assert job["company"] in lettre

    def test_generate_cover_sur_offre_inconnue_ne_plante_pas(self, seeded_client):
        reponse = seeded_client.get("/api/generate-cover/999999")

        assert reponse.status_code == 200
        assert reponse.get_json()["error"] == "Job not found"


class TestCandidatureEnregistree:
    def test_appliquer_transmet_la_lettre_a_mark_applied(self, seeded_client, seeded_api, monkeypatch):
        import app as app_module

        appels = []
        monkeypatch.setattr(
            app_module, "mark_applied", lambda job_id, cover_letter="": appels.append((job_id, cover_letter))
        )
        job_id = seeded_api["ids"][1]

        reponse = seeded_client.post(f"/api/apply/{job_id}", json={"cover_letter": "Bonjour"})

        assert reponse.status_code == 200
        assert reponse.get_json() == {"status": "ok"}
        assert appels == [(job_id, "Bonjour")]
