"""Fumée — le dashboard répond et affiche sa structure.

Marqueur @smoke : c'est cette suite qui tourne à chaque pull request.
Aucune donnée n'est créée ni modifiée ici : un fumée doit être rejouable à l'infini
et ne jamais dépendre de l'ordre d'exécution.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.smoke


def test_dashboard_charge_et_porte_son_titre(dashboard):
    dashboard.open().wait_ready()
    expect(dashboard.page).to_have_title(re.compile("JobHunt", re.IGNORECASE))


def test_bloc_hero_visible(dashboard):
    dashboard.open().wait_ready()
    expect(dashboard.hero.first).to_be_visible()


def test_barre_de_filtres_presente(dashboard):
    dashboard.open().wait_ready()
    expect(dashboard.filter_bar.first).to_be_attached()


def test_liste_d_offres_presente(dashboard):
    """La liste existe et se compte sans erreur (0 offre est un état valide)."""
    dashboard.open().wait_ready()
    assert dashboard.job_cards_count() >= 0
    expect(dashboard.job_list.first).to_be_attached()


def test_aucune_erreur_console_bloquante(dashboard):
    """Une erreur JS au chargement rend le dashboard inutilisable : on la détecte ici."""
    erreurs: list[str] = []
    dashboard.page.on("pageerror", lambda exc: erreurs.append(str(exc)))
    dashboard.open().wait_ready()
    assert erreurs == [], f"erreur(s) JavaScript au chargement : {erreurs}"
