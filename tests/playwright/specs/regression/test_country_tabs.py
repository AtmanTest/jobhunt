"""Régression — onglets pays du tableau de bord.

Chaque onglet active son panneau (et un seul) ; un marché sans offre montre son
état vide ; l'onglet « Tous » regroupe l'intégralité des offres servies.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.playwright, pytest.mark.regression]


def test_le_dashboard_ouvre_par_defaut_sur_la_france(reg_dashboard):
    reg_dashboard.open_ready()

    expect(reg_dashboard.active_country_tab).to_have_attribute("data-tab", "france")
    assert reg_dashboard.active_panel_id() == "panel-france"


def test_un_onglet_sans_offre_affiche_son_etat_vide(reg_dashboard):
    reg_dashboard.open_ready()

    reg_dashboard.click_country("suisse")

    expect(reg_dashboard.active_country_tab).to_have_attribute("data-tab", "suisse")
    assert reg_dashboard.active_panel_id() == "panel-suisse"
    expect(reg_dashboard.panel("suisse")).to_be_visible()
    # Le jeu de données ne contient aucune offre suisse : l'état vide est attendu.
    expect(reg_dashboard.panel("suisse").locator(".empty-state")).to_be_visible()


def test_l_onglet_tous_regroupe_toutes_les_offres(reg_dashboard, seeded):
    reg_dashboard.open_ready()
    total = seeded["info"]["total_display"]

    reg_dashboard.click_country("tous")

    expect(reg_dashboard.active_country_tab).to_have_attribute("data-tab", "tous")
    expect(reg_dashboard.panel("tous").locator(".job-card[data-id]")).to_have_count(total)


def test_l_onglet_linkedin_active_son_panneau(reg_dashboard):
    reg_dashboard.open_ready()

    reg_dashboard.click_country("linkedin")

    assert reg_dashboard.active_panel_id() == "panel-linkedin"
    expect(reg_dashboard.panel("linkedin")).to_be_visible()
    expect(reg_dashboard.panel("linkedin").locator("#linkedin-jobs-container")).to_be_attached()
