"""Régression — thème sombre : bascule puis PERSISTANCE après rechargement.

On ne se contente pas de tester une classe : on lit l'état réellement calculé
(couleur de fond du <body>) avant et après rechargement, ainsi que la préférence
stockée. Le mode par défaut de l'app étant sombre, le test prouve la persistance
d'un choix explicite (clair) puis du retour au sombre.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.playwright, pytest.mark.regression]

# Bornes observables de la somme R+G+B du fond du <body>.
DARK_THRESHOLD = 80
LIGHT_THRESHOLD = 500


def test_bascule_en_sombre_persiste_apres_rechargement(reg_dashboard):
    reg_dashboard.open_ready()

    # Pré-condition : état clair explicite (préférence stockée + rechargée à froid).
    reg_dashboard.set_stored_theme("light")
    reg_dashboard.wait_background_light()
    expect(reg_dashboard.page.locator("html")).to_have_attribute("data-theme", "light")
    light_sum = reg_dashboard.background_channel_sum()
    assert light_sum > LIGHT_THRESHOLD, f"fond clair attendu, somme={light_sum}"

    # Bascule vers le sombre.
    reg_dashboard.toggle_theme()
    reg_dashboard.wait_background_dark()
    expect(reg_dashboard.page.locator("html")).not_to_have_attribute("data-theme", "light")
    dark_sum = reg_dashboard.background_channel_sum()
    assert dark_sum < DARK_THRESHOLD, f"fond sombre attendu, somme={dark_sum}"
    assert dark_sum < light_sum, f"le fond ne s'est pas assombri : {light_sum} -> {dark_sum}"

    # Rechargement : le mode sombre est réellement conservé.
    reg_dashboard.reload_loaded()
    reg_dashboard.wait_background_dark()
    expect(reg_dashboard.page.locator("html")).not_to_have_attribute("data-theme", "light")
    assert reg_dashboard.background_channel_sum() < DARK_THRESHOLD, (
        "le fond n'est pas resté sombre après rechargement"
    )


def test_choix_clair_persiste_apres_rechargement(reg_dashboard):
    """La préférence claire (choix non-défaut) doit survivre à un rechargement."""
    reg_dashboard.open_ready()
    # Par défaut, l'app est sombre.
    reg_dashboard.wait_background_dark()

    reg_dashboard.toggle_theme()
    reg_dashboard.wait_background_light()
    expect(reg_dashboard.page.locator("html")).to_have_attribute("data-theme", "light")
    assert reg_dashboard.stored_theme() == "light"

    reg_dashboard.reload_loaded()
    reg_dashboard.wait_background_light()
    expect(reg_dashboard.page.locator("html")).to_have_attribute("data-theme", "light")
    assert reg_dashboard.background_channel_sum() > LIGHT_THRESHOLD, (
        "le fond n'est pas resté clair après rechargement"
    )
