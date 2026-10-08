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


def test_les_quatre_cartes_de_stats_sont_presentes(reg_dashboard):
    reg_dashboard.open_ready()

    expect(reg_dashboard.hero_cards).to_have_count(4)
    expect(reg_dashboard.hero_cards.filter(has_text="Offres QA")).to_have_count(1)
    expect(reg_dashboard.hero_cards.filter(has_text="Cette semaine")).to_have_count(1)
    expect(reg_dashboard.hero_cards.filter(has_text="Marchés actifs")).to_have_count(1)
    expect(reg_dashboard.hero_cards.filter(has_text="Jobs clôturés")).to_have_count(1)


def test_les_offres_recentes_portent_le_badge_new(reg_dashboard, seeded):
    """Seules les offres publiées il y a moins de 7 jours sont badgées."""
    reg_dashboard.open_ready()

    attendu = len(seeded["info"]["recent_ids"])
    expect(reg_dashboard.new_badges).to_have_count(attendu)


def test_la_pagination_est_bornee_aux_deux_extremites(reg_dashboard, seeded):
    reg_dashboard.open_ready()
    total = seeded["info"]["total_display"]
    dernier = (total + PER_PAGE - 1) // PER_PAGE

    # Première page : on ne peut pas revenir en arrière.
    expect(reg_dashboard.page_button("‹")).to_be_disabled()
    expect(reg_dashboard.page_button("›")).to_be_enabled()

    reg_dashboard.page_button(str(dernier)).click()

    # Dernière page : on ne peut pas avancer davantage.
    expect(reg_dashboard.page_button("›")).to_be_disabled()
    expect(reg_dashboard.page_button("‹")).to_be_enabled()

    reg_dashboard.page_button("1").click()
    expect(reg_dashboard.page_button("‹")).to_be_disabled()
