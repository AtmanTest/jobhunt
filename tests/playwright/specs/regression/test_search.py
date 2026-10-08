"""Régression — recherche temps réel.

La saisie filtre les cartes instantanément et met à jour le compteur ; l'effacement
restaure l'état complet. Aucune attente arbitraire : on attend la condition observable
(compteur mis à jour, cartes non conformes disparues).
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.playwright, pytest.mark.regression]

QUERY = "Cypress"


def test_la_recherche_temps_reel_ne_laisse_que_les_offres_correspondantes(reg_dashboard, seeded):
    reg_dashboard.open_ready()
    expected = len(seeded["info"]["cypress_ids"])

    reg_dashboard.search(QUERY)

    # Le compteur est mis à jour...
    expect(reg_dashboard.counter).to_have_text(f"{expected} offres")
    # ...et seules les offres correspondantes restent actives.
    expect(reg_dashboard.active_matching_cards).to_have_count(expected)
    # Aucune carte restante ne contredit le terme recherché.
    expect(reg_dashboard.active_matching_cards.filter(has_not_text=QUERY)).to_have_count(0)


def test_effacer_la_recherche_restaure_l_etat_complet(reg_dashboard, seeded):
    reg_dashboard.open_ready()
    total = seeded["info"]["total_display"]

    reg_dashboard.search(QUERY)
    expect(reg_dashboard.counter).to_have_text(f"{len(seeded['info']['cypress_ids'])} offres")

    reg_dashboard.clear_search()

    expect(reg_dashboard.counter).to_have_text(f"{total} offres")
    expect(reg_dashboard.active_matching_cards).to_have_count(total)


def test_la_recherche_ignore_la_casse(reg_dashboard, seeded):
    """Partition d'équivalence : « cypress » et « Cypress » sélectionnent le même lot."""
    reg_dashboard.open_ready()
    expected = len(seeded["info"]["cypress_ids"])

    reg_dashboard.search(QUERY.lower())

    expect(reg_dashboard.counter).to_have_text(f"{expected} offres")
    expect(reg_dashboard.active_matching_cards).to_have_count(expected)


def test_la_recherche_porte_aussi_sur_l_entreprise(reg_dashboard):
    """Le terme est cherché dans toute la carte (titre, entreprise, tags)."""
    reg_dashboard.open_ready()

    reg_dashboard.search("Globex")

    expect(reg_dashboard.counter).to_have_text("1 offres")
    expect(reg_dashboard.active_matching_cards).to_have_count(1)
    expect(reg_dashboard.active_matching_cards.first).to_contain_text("Globex")
