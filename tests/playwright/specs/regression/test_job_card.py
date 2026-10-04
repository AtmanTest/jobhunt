"""Régression — carte d'offre : champs affichés et lien de candidature sûr.

Vérifie que titre, entreprise, salaire et tags sont visibles, et que le lien
« Apply » ouvre un nouvel onglet avec `rel` protégé (noopener/noreferrer).
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.playwright, pytest.mark.regression]


def test_la_carte_offre_affiche_titre_entreprise_salaire_et_tags(reg_dashboard):
    reg_dashboard.open_ready()
    card = reg_dashboard.first_visible_card()

    title = card.locator(".jc-title-link")
    expect(title).to_be_visible()
    expect(title).not_to_have_text("")

    company = card.locator(".jc-company")
    expect(company).to_be_visible()
    expect(company).not_to_have_text("")

    # Salaire présent (toute offre du jeu de données en porte un).
    expect(card.locator(".jc-meta")).to_contain_text("💰")

    # Tags affichés (skill-tags issus du matching ou tags de l'offre).
    expect(card.locator(".jc-tags span").first).to_be_visible()


def test_le_lien_apply_ouvre_un_nouvel_onglet_protege(reg_dashboard):
    reg_dashboard.open_ready()
    link = reg_dashboard.first_visible_card().locator(".btn-apply")

    expect(link).to_be_visible()
    expect(link).to_have_attribute("target", "_blank")
    expect(link).to_have_attribute("rel", re.compile(r"\bnoopener\b"))
    expect(link).to_have_attribute("href", re.compile(r"^https?://"))
