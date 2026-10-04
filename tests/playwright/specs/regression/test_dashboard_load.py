"""Régression — chargement du dashboard.

Vérifie que le tableau de bord sert bien les offres, que le compteur est cohérent
avec le DOM et la base, et qu'aucune erreur console/JS n'est émise au chargement.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.playwright, pytest.mark.regression]

# Taille de page du composant de pagination du dashboard.
PER_PAGE = 3


def test_le_dashboard_affiche_les_offres_et_un_compteur_coherent(reg_dashboard, seeded):
    reg_dashboard.open_ready()
    total = seeded["info"]["total_display"]

    # La liste est réellement rendue...
    expect(reg_dashboard.job_list.first).to_be_visible()
    # ...le panneau actif contient une carte par offre servie...
    expect(reg_dashboard.active_panel_cards).to_have_count(total)
    # ...et le compteur annoncé correspond au nombre d'offres.
    expect(reg_dashboard.counter).to_have_text(f"{total} offres")

    # Le compteur est cohérent avec la source serveur (data-total) et le DOM.
    assert reg_dashboard.counter_number() == total
    assert reg_dashboard.total_attribute() == total


def test_la_pagination_n_expose_qu_une_page_de_cartes(reg_dashboard):
    reg_dashboard.open_ready()
    # Seules les cartes de la première page sont réellement à l'écran.
    expect(reg_dashboard.active_visible_cards).to_have_count(PER_PAGE)


def test_aucune_erreur_console_au_chargement(reg_dashboard, console_errors):
    reg_dashboard.open_ready()
    expect(reg_dashboard.job_list.first).to_be_visible()
    expect(reg_dashboard.active_panel_cards.first).to_be_visible()
    assert console_errors == [], f"erreur(s) console/JS au chargement : {console_errors}"
