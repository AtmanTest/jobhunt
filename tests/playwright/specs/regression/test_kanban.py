"""Régression — Kanban des candidatures.

Ouverture de l'écran, colonnes par stade, comptes par colonne, déplacement d'une
carte PUIS vérification de la PERSISTANCE côté serveur en relisant `/api/jobs`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from tests.playwright.pages import STAGE_LABELS, STAGES

pytestmark = [pytest.mark.playwright, pytest.mark.regression]


def test_le_kanban_ouvre_les_cinq_colonnes_par_stade(reg_dashboard, kanban):
    reg_dashboard.open_ready()
    kanban.open()

    expect(kanban.view).to_be_visible()
    expect(kanban.columns).to_have_count(len(STAGES))
    expect(kanban.column_titles).to_have_text(list(STAGE_LABELS))

    # Le jeu de données place exactement une candidature par stade.
    for stage in STAGES:
        expect(kanban.cards_in(stage)).to_have_count(1)


def test_deplacer_une_carte_persiste_cote_serveur(reg_dashboard, kanban, seeded, page):
    reg_dashboard.open_ready()
    kanban.open()

    job_id = seeded["info"]["kanban_ids"]["new"]
    expect(kanban.cards_in("new")).to_have_count(1)

    kanban.move_card(job_id, "new", "applied")

    # La carte a changé de colonne dans l'UI...
    expect(kanban.card("applied", job_id)).to_be_visible()
    expect(kanban.cards_in("new")).to_have_count(0)
    expect(kanban.cards_in("applied")).to_have_count(2)

    # ...et le déplacement est bien persisté côté serveur : on relit /api/jobs.
    page.wait_for_function(
        "([id, stage]) => fetch('/api/jobs').then(r => r.json()).then(js => {"
        " const j = js.find(x => String(x.id) === String(id));"
        " return !!j && j.pipeline_stage === stage; })",
        arg=[job_id, "applied"],
        timeout=10_000,
    )
    response = page.request.get(f"{seeded['base_url']}/api/jobs")
    assert response.ok, f"/api/jobs a répondu {response.status}"
    jobs = response.json()
    persisted = next(j for j in jobs if str(j["id"]) == str(job_id))
    assert persisted["pipeline_stage"] == "applied"
