"""Régression — en-tête selon l'état de session : visiteur et utilisateur connecté.

Deux chemins bien distincts dans le dashboard :
  • anonyme   → le bouton utilisateur est remplacé par un lien « Connexion » ;
  • connecté  → le menu utilisateur reste et expose la déconnexion.

La session connectée est simulée par interception de `/api/auth/me` (voir la
fixture `connected_dashboard`) : on teste l'interface, pas le fournisseur.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.playwright, pytest.mark.regression]


def test_un_visiteur_anonyme_voit_le_lien_de_connexion(reg_dashboard):
    reg_dashboard.open_ready()

    expect(reg_dashboard.page.locator("a.user-login-btn")).to_be_visible()
    expect(reg_dashboard.page.locator("a.user-login-btn")).to_have_attribute("href", "/login")
    # Le bouton du menu connecté a bien été retiré.
    expect(reg_dashboard.user_menu_trigger).to_have_count(0)


def test_le_menu_utilisateur_est_affiche_pour_un_utilisateur_connecte(connected_dashboard):
    connected_dashboard.open_ready()

    expect(connected_dashboard.user_menu_trigger).to_be_visible()
    # Le prénom de l'utilisateur est repris dans le menu.
    expect(connected_dashboard.page.locator("#dd-name")).to_have_text("Atman")


def test_le_menu_utilisateur_s_ouvre_et_montre_la_deconnexion(connected_dashboard):
    connected_dashboard.open_ready()

    connected_dashboard.open_user_menu()

    expect(connected_dashboard.user_dropdown).to_have_class(re.compile(r"\bopen\b"))
    expect(connected_dashboard.logout_link).to_be_visible()


def test_la_deconnexion_appelle_l_api(connected_dashboard):
    connected_dashboard.open_ready()
    connected_dashboard.open_user_menu()

    with connected_dashboard.page.expect_request("**/api/auth/logout") as requete:
        connected_dashboard.logout()

    assert requete.value.method == "POST"
