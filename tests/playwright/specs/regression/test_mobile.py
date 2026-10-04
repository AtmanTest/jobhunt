"""Régression — viewport mobile 375x800 : barre basse et colonne unique.

Vérifie le repli responsive réel (position calculée de la sidebar, largeurs et
empilement effectifs des cartes), pas seulement la présence des éléments.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.playwright, pytest.mark.regression]

VIEWPORT = {"width": 375, "height": 800}


def test_navigation_mobile_devient_une_barre_basse(reg_dashboard, page):
    page.set_viewport_size(VIEWPORT)
    reg_dashboard.open_ready()
    reg_dashboard.wait_sidebar_bottom_bar()

    expect(reg_dashboard.sidebar).to_be_visible()
    geo = reg_dashboard.sidebar_geometry()
    assert geo["position"] == "fixed", f"sidebar non fixe : {geo}"
    assert geo["top"] > geo["height"] / 2, f"sidebar pas en bas : {geo}"
    assert geo["bottom"] >= geo["height"] - 4, f"sidebar pas collée au bas : {geo}"


def test_cartes_en_colonne_unique_sur_mobile(reg_dashboard, page):
    page.set_viewport_size(VIEWPORT)
    reg_dashboard.open_ready()

    expect(reg_dashboard.active_visible_cards.first).to_be_visible()
    layout = reg_dashboard.active_panel_layout()

    assert layout["widths"], "aucune carte visible pour mesurer la mise en page"
    for width in layout["widths"]:
        assert width >= layout["list_width"] - 8, (
            f"carte non pleine largeur ({width} < {layout['list_width']})"
        )
    assert layout["tops"] == sorted(layout["tops"]), (
        f"les cartes ne sont pas empilées verticalement : {layout['tops']}"
    )
