"""Régression — facettes séniorité puis combinaison séniorité + contrat.

Vérifie que le filtre par facette ne laisse que les offres conformes, que le
bouton actif reflète le choix, et que le compteur reste cohérent.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.playwright, pytest.mark.regression]


def test_facette_senior_ne_laisse_que_les_offres_senior(reg_dashboard, seeded):
    reg_dashboard.open_ready()
    expected = len(seeded["info"]["senior_ids"])

    reg_dashboard.click_seniority("senior")

    expect(reg_dashboard.active_seniority).to_have_attribute("data-val", "senior")
    expect(reg_dashboard.counter).to_have_text(f"{expected} offres")
    expect(reg_dashboard.active_matching_cards).to_have_count(expected)
    # Aucune carte restante n'est non-senior.
    expect(
        reg_dashboard.page.locator(
            '.tab-panel.active .job-card[data-id]:not(.filtered-out):not([data-seniority="senior"])'
        )
    ).to_have_count(0)


def test_filtres_combines_senior_et_freelance(reg_dashboard, seeded):
    reg_dashboard.open_ready()
    expected = len(seeded["info"]["senior_freelance_ids"])

    reg_dashboard.click_seniority("senior")
    reg_dashboard.click_contract("freelance")

    expect(reg_dashboard.active_seniority).to_have_attribute("data-val", "senior")
    expect(reg_dashboard.active_contract).to_have_attribute("data-val", "freelance")
    expect(reg_dashboard.counter).to_have_text(f"{expected} offres")

    matching = reg_dashboard.active_matching_cards
    expect(matching).to_have_count(expected)
    # Toutes les cartes restantes sont senior ET freelance (l'intersection compte
    # autant d'éléments que l'ensemble des cartes actives).
    expect(
        reg_dashboard.page.locator(
            '.tab-panel.active .job-card[data-id]:not(.filtered-out)'
            '[data-seniority="senior"][data-contract="freelance"]'
        )
    ).to_have_count(expected)


def test_reinitialiser_la_facette_restaure_tout(reg_dashboard, seeded):
    reg_dashboard.open_ready()
    total = seeded["info"]["total_display"]

    reg_dashboard.click_seniority("senior")
    expect(reg_dashboard.active_matching_cards).to_have_count(len(seeded["info"]["senior_ids"]))

    reg_dashboard.click_seniority("all")

    expect(reg_dashboard.active_seniority).to_have_attribute("data-val", "all")
    expect(reg_dashboard.counter).to_have_text(f"{total} offres")
    expect(reg_dashboard.active_matching_cards).to_have_count(total)
