"""Régression — écran de connexion `/login`.

Couvre le socle d'authentification : rendu du formulaire, validation HTML5
(blocage côté navigateur, donc sans requête réseau), bascule connexion/inscription,
et les quatre issues de la soumission — identifiants refusés, erreur serveur,
erreur réseau, succès avec redirection vers le tableau de bord.

Les réponses d'authentification sont STUBBÉES (`page.route`) : la suite ne dépend
d'aucun service Supabase, d'aucun secret et reste déterministe. On vérifie le
CONTRAT d'interface (ce que l'UI fait de chaque réponse), pas le fournisseur.

Aucune attente arbitraire : chaque attente porte sur une condition observable
(message affiché, URL changée, évènement `invalid` du navigateur).
"""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.playwright, pytest.mark.regression]

EMAIL = "qa@example.com"
PASSWORD = "motdepasse"


def _stub_auth(login_page, endpoint: str, status: int, payload: dict) -> None:
    """Intercepte un endpoint d'auth et renvoie une réponse JSON figée."""
    login_page.page.route(
        f"**{endpoint}",
        lambda route: route.fulfill(
            status=status,
            content_type="application/json",
            body=json.dumps(payload),
        ),
    )


# ── Rendu et structure ────────────────────────────────────────────────────
def test_la_page_de_connexion_s_affiche(login):
    login.open()

    expect(login.auth_box).to_be_visible()
    expect(login.email_input).to_be_visible()
    expect(login.password_input).to_be_visible()
    expect(login.submit_button).to_be_visible()
    expect(login.submit_button).to_have_text("Se connecter")


def test_le_titre_identifie_l_application(login):
    login.open()
    assert "JobHunt" in login.title()


def test_le_mot_de_passe_est_masque(login):
    login.open()
    # La saisie ne doit jamais être lisible en clair.
    assert login.password_type() == "password"


def test_le_message_d_erreur_est_masque_au_depart(login):
    login.open()
    expect(login.error_message).to_be_hidden()


# ── Validation HTML5 (aucun appel réseau) ─────────────────────────────────
def test_un_email_vide_bloque_la_soumission(login):
    login.open()
    login.page.evaluate(
        "() => { window.__invalidFired = false;"
        " document.getElementById('email')"
        "   .addEventListener('invalid', () => { window.__invalidFired = true; }); }"
    )

    login.submit()

    # Le navigateur refuse la soumission : l'évènement `invalid` part, pas de fetch.
    login.page.wait_for_function("() => window.__invalidFired === true")
    expect(login.error_message).to_be_hidden()


def test_un_email_mal_forme_est_invalide(login):
    login.open()
    login.fill("pas-un-email", PASSWORD)
    assert login.email_is_valid() is False

    login.fill(EMAIL, PASSWORD)
    assert login.email_is_valid() is True


def test_un_mot_de_passe_de_moins_de_six_caracteres_est_invalide(login):
    login.open()
    login.fill(EMAIL, "123")
    assert login.password_is_valid() is False

    login.fill(EMAIL, "123456")
    assert login.password_is_valid() is True


# ── Bascule connexion / inscription ───────────────────────────────────────
def test_basculer_vers_l_inscription_change_les_libelles(login):
    login.open()

    login.toggle_mode()

    expect(login.submit_button).to_have_text("Créer un compte")
    expect(login.subtitle).to_have_text("Crée ton compte pour commencer")
    expect(login.toggle_link).to_have_text("Se connecter")
    expect(login.toggle_text).to_have_text("Déjà un compte ? ")


def test_rebasculer_restaure_le_mode_connexion(login):
    login.open()
    login.toggle_mode()
    login.toggle_mode()

    expect(login.submit_button).to_have_text("Se connecter")
    expect(login.subtitle).to_have_text("Connecte-toi pour accéder à tes offres")


# ── Issues de la soumission ───────────────────────────────────────────────
def test_des_identifiants_invalides_affichent_le_message_du_serveur(login):
    _stub_auth(login, "/api/auth/login", 401, {"error": "Email ou mot de passe incorrect"})
    login.open()

    login.sign_in(EMAIL, PASSWORD)

    expect(login.error_message).to_be_visible()
    expect(login.error_message).to_have_text("Email ou mot de passe incorrect")
    # On reste sur la page de connexion.
    assert login.url().endswith("/login")


def test_une_erreur_serveur_est_affichee(login):
    _stub_auth(login, "/api/auth/login", 500, {"error": "Supabase auth not configured"})
    login.open()

    login.sign_in(EMAIL, PASSWORD)

    expect(login.error_message).to_have_text("Supabase auth not configured")


def test_une_erreur_reseau_est_affichee(login):
    login.page.route("**/api/auth/login", lambda route: route.abort())
    login.open()

    login.sign_in(EMAIL, PASSWORD)

    expect(login.error_message).to_have_text("Erreur réseau")


def test_une_inscription_refusee_affiche_le_message_du_serveur(login):
    _stub_auth(
        login,
        "/api/auth/signup",
        400,
        {"error": "Cet email est déjà utilisé. Connecte-toi."},
    )
    login.open()
    login.toggle_mode()

    login.sign_in(EMAIL, PASSWORD)

    expect(login.error_message).to_be_visible()
    expect(login.error_message).to_have_text("Cet email est déjà utilisé. Connecte-toi.")


def test_une_connexion_reussie_redirige_vers_le_dashboard(login, seeded):
    _stub_auth(login, "/api/auth/login", 200, {"ok": True, "user_id": "u-test"})
    login.open()

    login.sign_in(EMAIL, PASSWORD)

    login.page.wait_for_url(f"{seeded['base_url']}/", timeout=10_000)
    expect(login.page.locator(".hero").first).to_be_visible()
