"""Scénarios Playwright du dashboard JobHunt.

Ce fichier contient les scénarios historiques du dashboard (filtre budget, stats,
onglets pays, filtre remote, cartes, top matches, pagination, dismiss, Apply).

Deux façons de les exécuter :

  * sous pytest — la voie normale :
        JOBHUNT_BASE_URL=... python -m pytest tests/playwright/test_dashboard.py
    Ils utilisent le serveur E2E déterministe de la fixture `e2e_url` ;

  * hors pytest, via `run_scenario(nom)`, utilisé par le tableau de bord /qa :
    la fonction démarre son propre serveur en boucle locale sur une base
    temporaire ensemencée, puis renvoie {"passed", "error", "screenshot"}.
"""

import os
import socket
import sys
import tempfile
import threading

import pytest

# La racine du dépôt doit être importable : `app` et `tests.*` y vivent.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Ces scénarios appartiennent à l'étage de régression E2E (pas à la fumée).
pytestmark = pytest.mark.regression

SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)


@pytest.fixture
def e2e_url(seeded):
    """Serveur E2E déterministe (port libre de 127.0.0.1, base réamorcée).

    Remplace l'ancienne constante figée sur `localhost:5050`, qui faisait échouer
    ces scénarios par simple absence de serveur sur ce port.
    """
    return seeded["base_url"]


def _screenshot(page, name):
    path = os.path.join(SCREENSHOTS_DIR, f"{name}.png")
    page.screenshot(path=path)
    return path


def _serve_deterministic():
    """Démarre l'app en boucle locale sur une base temporaire ensemencée.

    Returns:
        (url, arret) — `arret` est la fonction à appeler pour éteindre le serveur.
    """
    import urllib.request

    import scraper

    # Neutralise le thread de scraping LinkedIn lancé à l'import de app.py :
    # il polluerait la base déterministe avec des offres réelles.
    scraper.fetch_linkedin_countries = lambda *a, **k: []

    import app as app_module
    from werkzeug.serving import make_server

    from tests.playwright.fixtures.e2e_data import seed_database

    db_path = os.path.join(tempfile.mkdtemp(prefix="qa_run_"), "e2e_jobs.db")
    seed_database(db_path)

    app_module.DB_PATH = db_path
    scraper.DB_PATH = db_path
    app_module.DB_POPULATED = True
    app_module._ensure_db_populated = lambda: None

    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()

    server = make_server("127.0.0.1", port, app_module.app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    url = f"http://127.0.0.1:{port}"
    deadline = 20
    while deadline > 0:
        try:
            urllib.request.urlopen(url + "/api/stats", timeout=1).read()
            break
        except Exception:
            deadline -= 1
    return url, server.shutdown


def _attendre_actif(page, element, timeout=10000):
    """Attend que l'élément cliqué porte la classe `active`.

    Remplace les attentes arbitraires (`wait_for_timeout`) par une condition
    observable : le filtre est appliqué quand son bouton devient actif.
    """
    page.wait_for_function(
        "el => (el.className || '').includes('active')", arg=element, timeout=timeout
    )


def _attendre_liste_changee(page, avant, timeout=10000):
    """Attend que la liste visible des offres change par rapport à `avant`.

    Condition observable : le nombre de cartes visibles diffère de l'état
    précédent. Utilisé quand le filtre ne marque pas de bouton actif.
    """
    page.wait_for_function(
        "n => [...document.querySelectorAll('.job-card')]"
        ".filter(e => e.offsetParent !== null).length !== n",
        arg=avant, timeout=timeout,
    )


def test_budget_filter(page, e2e_url):
    """Le filtre budget « ≥ 600 » ne laisse passer aucune offre sous le seuil.

    Vérifie trois choses observables depuis le navigateur :
      1. le groupe de filtres « budget » existe et porte la borne 600 ;
      2. après clic sur « ≥ 600 », aucune carte visible n'a un budget analysé < 600 ;
      3. les cartes sans budget analysé sont écartées (règle métier).
    """
    page.goto(e2e_url)
    page.wait_for_selector(".job-card", timeout=15000)

    groupe = page.query_selector('[data-type="budget"]')
    assert groupe is not None, "groupe de filtres « budget » absent du dashboard"
    libelles = [b.text_content().strip() for b in groupe.query_selector_all(".filter-btn")]
    assert any("600" in l for l in libelles), f"borne 600 absente : {libelles}"

    avant = [c for c in page.query_selector_all(".job-card") if c.is_visible()]
    assert avant, "aucune carte affichée avant filtrage"

    bouton = [b for b in groupe.query_selector_all(".filter-btn") if "600" in b.text_content()][0]
    bouton.click()
    _attendre_actif(page, bouton)

    visibles = [c for c in page.query_selector_all(".job-card") if c.is_visible()]
    assert len(visibles) <= len(avant), "le filtre a ajouté des cartes"

    hors_seuil = []
    sans_budget = []
    for carte in visibles:
        brut = carte.get_attribute("data-budget")
        if brut in (None, ""):
            sans_budget.append(carte.get_attribute("data-id"))
            continue
        if int(float(brut)) < 600:
            hors_seuil.append((carte.get_attribute("data-id"), brut))

    assert not hors_seuil, f"offres sous le seuil encore visibles : {hors_seuil}"
    assert not sans_budget, f"offres sans budget analysé encore visibles : {sans_budget[:5]}"


def test_page_title(page, e2e_url):
    """Le titre de la page identifie bien JobHunt."""
    page.goto(e2e_url)
    title = page.title()
    assert "JobHunt" in title or "Marché" in title or "QA" in title, f"titre inattendu : {title}"


def test_hero_stats(page, e2e_url):
    """Les cartes de statistiques du bandeau sont présentes et non vides."""
    page.goto(e2e_url)
    page.wait_for_selector(".hero-card", timeout=10000)
    cards = page.query_selector_all(".hero-card")
    assert len(cards) >= 3, f"3 cartes de stats attendues au minimum, {len(cards)} trouvées"
    textes = [c.text_content().strip() for c in cards]
    assert all(textes), "une carte de statistiques est vide"


def test_country_tabs(page, e2e_url):
    """Les onglets pays sont présents et un changement d'onglet est possible."""
    page.goto(e2e_url)
    page.wait_for_selector(".country-btn", timeout=10000)
    tabs = page.query_selector_all(".country-btn")
    assert len(tabs) >= 5, f"5 onglets pays attendus au minimum, {len(tabs)} trouvés"

    suisse = [t for t in tabs if "Suisse" in t.text_content() or "Switzerland" in t.text_content()]
    assert suisse, "onglet Suisse absent"
    suisse[0].click()
    _attendre_actif(page, suisse[0])
    assert suisse[0].is_visible(), "l'onglet Suisse a disparu après le clic"


def test_remote_filter(page, e2e_url):
    """Le filtre « Remote » existe et son clic ne casse pas la liste."""
    page.goto(e2e_url)
    page.wait_for_selector(".filter-btn", timeout=10000)
    filters = page.query_selector_all(".filter-btn")
    remote_btn = [f for f in filters if "Remote" in f.text_content()]
    assert remote_btn, "bouton de filtre « Remote » introuvable"

    remote_btn[0].click()
    _attendre_actif(page, remote_btn[0])
    assert page.query_selector_all(".job-card"), "le filtre Remote a vidé la liste d'offres"


def test_job_cards(page, e2e_url):
    """Au moins une offre est visible à l'écran."""
    page.goto(e2e_url)
    page.wait_for_selector(".job-card", timeout=15000)
    cards = page.query_selector_all(".job-card")
    visible = [c for c in cards if c.is_visible()]
    assert visible, "aucune carte d'offre visible"


def test_top_matches(page, e2e_url):
    """Les meilleures correspondances affichent un score de pertinence."""
    page.goto(e2e_url)
    page.wait_for_selector(".top-match-card", timeout=10000)
    cards = page.query_selector_all(".top-match-card")
    assert cards, "aucune carte de correspondance affichée"
    scores = [c.query_selector(".tm-score") for c in cards]
    scores = [s for s in scores if s]
    assert scores, "aucun score de correspondance affiché"
    assert all(s.text_content().strip() for s in scores), "un score de correspondance est vide"


def test_pagination(page, e2e_url):
    """La pagination est présente ; la page suivante est atteignable si elle existe."""
    page.goto(e2e_url)
    page.wait_for_selector(".page-btn", timeout=10000)
    btns = page.query_selector_all(".page-btn")
    assert btns, "aucun bouton de pagination"
    suivants = [b for b in btns if b.text_content().strip() == "›" and not b.is_disabled()]
    assert suivants, "aucun bouton de page suivante actif"
    page_active = page.query_selector(".page-btn.active")
    assert page_active is not None, "aucune page marquée active"
    numero_avant = page_active.text_content().strip()

    suivants[0].click()
    # Condition observable : la page marquée active n'est plus celle d'avant.
    page.wait_for_function(
        "n => { const a = document.querySelector('.page-btn.active');"
        " return a && a.textContent.trim() !== n; }",
        arg=numero_avant,
    )
    assert page.query_selector_all(".job-card"), "la page suivante n'affiche aucune offre"


def test_dismiss_button_does_not_navigate(page, e2e_url):
    """Cliquer sur la croix de rejet (✕) ne doit PAS quitter la page."""
    page.goto(e2e_url)
    page.wait_for_selector(".btn-dismiss", timeout=15000)
    dismiss_btn = page.query_selector(".btn-dismiss")
    assert dismiss_btn is not None, "aucun bouton de rejet trouvé alors que les cartes en portent"

    url_avant = page.url
    visibles_avant = len([c for c in page.query_selector_all(".job-card") if c.is_visible()])
    dismiss_btn.click()
    _attendre_liste_changee(page, visibles_avant)
    assert page.url == url_avant, f"la page a navigué ! {url_avant} → {page.url}"


def test_apply_button_is_only_clickable_link(page, e2e_url):
    """Le corps de la carte ne navigue pas ; seul le lien Apply est cliquable."""
    page.goto(e2e_url)
    page.wait_for_selector(".job-card", timeout=15000)
    card = page.query_selector(".job-card")
    assert card is not None, "aucune carte d'offre trouvée"

    url_avant = page.url
    card.click(position={"x": 50, "y": 50})
    page.wait_for_function("() => document.readyState === 'complete'")
    assert page.url == url_avant, "un clic sur le corps de la carte a navigué"

    apply_btn = card.query_selector(".btn-apply")
    assert apply_btn is not None, "la carte ne porte pas de lien Apply"
    href = apply_btn.get_attribute("href")
    assert href and href.startswith("http"), f"le lien Apply n'a pas d'URL valide : {href}"


SCENARIOS = {
    "test_page_title": test_page_title,
    "test_budget_filter": test_budget_filter,
    "test_hero_stats": test_hero_stats,
    "test_country_tabs": test_country_tabs,
    "test_remote_filter": test_remote_filter,
    "test_job_cards": test_job_cards,
    "test_top_matches": test_top_matches,
    "test_pagination": test_pagination,
    "test_dismiss_button_does_not_navigate": test_dismiss_button_does_not_navigate,
    "test_apply_button_is_only_clickable_link": test_apply_button_is_only_clickable_link,
}


def run_scenario(name: str) -> dict:
    """Exécute un scénario hors pytest (appelé par le tableau de bord /qa).

    Démarre son propre serveur en boucle locale sur une base temporaire
    ensemencée : le scénario est reproductible et n'exige aucun serveur externe.

    Returns:
        {"scenario", "passed", "error", "screenshot"}
    """
    from playwright.sync_api import sync_playwright

    if name not in SCENARIOS:
        return {"scenario": name, "passed": False, "error": f"Unknown scenario: {name}"}

    url, arret = _serve_deterministic()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()
            try:
                SCENARIOS[name](page, url)
                return {"scenario": name, "passed": True, "error": ""}
            except Exception as exc:  # noqa: BLE001 — on remonte le verdict, pas l'exception
                shot = _screenshot(page, f"fail_{name}")
                return {
                    "scenario": name,
                    "passed": False,
                    "error": str(exc)[:300],
                    "screenshot": shot,
                }
            finally:
                browser.close()
    finally:
        arret()
