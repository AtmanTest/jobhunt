"""Régression — état vide : une recherche sans résultat.

Comportement d'entrée « invalide » observable : un terme qui ne correspond à
aucune offre vide la liste, affiche « 0 offres », puis l'effacement restaure tout.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.playwright, pytest.mark.regression]

NO_MATCH = "zzz-offre-inexistante-zzz"


def test_recherche_sans_resultat_affiche_un_etat_vide(reg_dashboard, seeded):
    reg_dashboard.open_ready()
    total = seeded["info"]["total_display"]

    reg_dashboard.search(NO_MATCH)

    expect(reg_dashboard.counter).to_have_text("0 offres")
    expect(reg_dashboard.active_matching_cards).to_have_count(0)
    expect(reg_dashboard.active_visible_cards).to_have_count(0)

    # L'effacement ramène l'état complet.
    reg_dashboard.clear_search()
    expect(reg_dashboard.counter).to_have_text(f"{total} offres")
    expect(reg_dashboard.active_matching_cards).to_have_count(total)
