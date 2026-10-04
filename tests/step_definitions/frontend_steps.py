"""Step definitions Playwright des scénarios frontend E2E.

Ces steps pilotent un vrai navigateur (Chromium via pytest-playwright) contre
l'application Flask servie en boucle locale. Le serveur E2E est démarré une
seule fois par session, sur un port libre de 127.0.0.1, adossé à une base
SQLite temporaire amorcée par ``tests/playwright/fixtures/e2e_data.py``
(18 offres d'affichage + 5 candidatures Kanban).

Aucune attente arbitraire : chaque attente porte sur une condition observable
(``wait_for_selector``, ``wait_for_function``, événement navigateur).
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import urllib.request

import pytest
from pytest_bdd import given, then, when

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tests.playwright.fixtures.e2e_data import seed_database  # noqa: E402
from tests.playwright.pages import DashboardPage  # noqa: E402

# Fragments de messages de console considérés comme du bruit réseau (chargement
# de ressource, requête bloquée) et non comme des erreurs applicatives.
_BENIGN_CONSOLE = ("Failed to load resource", "net::", "ERR_")


# ---------------------------------------------------------------------------
# Fixtures — serveur E2E + données (isolées par scénario)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def e2e_server(tmp_path_factory):
    """Démarre l'app Flask sur un port local libre, adossée à une base de test."""
    import scraper

    # Neutralise le thread de scraping LinkedIn lancé à l'import de app.py :
    # il polluerait la base E2E avec des offres réelles non déterministes.
    scraper.fetch_linkedin_countries = lambda *a, **k: []

    import app as app_module

    db_path = str(tmp_path_factory.mktemp("e2e") / "e2e_jobs.db")
    seed_database(db_path)

    originals = {
        "fetch_linkedin_countries": scraper.fetch_linkedin_countries,
        "scraper_db_path": scraper.DB_PATH,
        "app_db_path": app_module.DB_PATH,
        "app_populated": app_module.DB_POPULATED,
        "app_ensure": app_module._ensure_db_populated,
    }

    app_module.DB_PATH = db_path
    scraper.DB_PATH = db_path
    app_module.DB_POPULATED = True
    app_module._ensure_db_populated = lambda: None

    from werkzeug.serving import make_server

    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()

    server = make_server("127.0.0.1", port, app_module.app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 20
    ready = False
    while time.time() < deadline:
        try:
            urllib.request.urlopen(base_url + "/api/stats", timeout=1).read()
            ready = True
            break
        except Exception:
            time.sleep(0.05)
    if not ready:
        server.shutdown()
        raise RuntimeError("le serveur E2E n'a pas démarré")

    yield {"base_url": base_url, "db_path": db_path}

    server.shutdown()
    scraper.fetch_linkedin_countries = originals["fetch_linkedin_countries"]
    scraper.DB_PATH = originals["scraper_db_path"]
    app_module.DB_PATH = originals["app_db_path"]
    app_module.DB_POPULATED = originals["app_populated"]
    app_module._ensure_db_populated = originals["app_ensure"]


@pytest.fixture
def fh(e2e_server, page):
    """Harnais frontend : page Playwright + base réamorcée + état partagé.

    La base est réamorcée avant chaque scénario : isolation totale, aucun
    couplage d'ordre (un déplacement Kanban ne fuit pas sur le test suivant).
    """
    info = seed_database(e2e_server["db_path"])
    return {
        "page": page,
        "base_url": e2e_server["base_url"],
        "db_path": e2e_server["db_path"],
        "info": info,
        "state": {},
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _open(fh, capture_console=False):
    page = fh["page"]
    if capture_console:
        fh["state"]["console_errors"] = []
        fh["state"]["page_errors"] = []
        page.on(
            "console",
            lambda m: fh["state"]["console_errors"].append(m.text) if m.type == "error" else None,
        )
        page.on("pageerror", lambda e: fh["state"]["page_errors"].append(str(e)))
    DashboardPage(page, base_url=fh["base_url"]).open().wait_ready()
    fh["state"]["page"] = page
    return page


def _ensure_open(fh):
    """Ouvre le dashboard si aucun scénario ne l'a déjà fait."""
    page = fh["page"]
    if not (page.url or "").startswith("http"):
        _open(fh)
    return page


def _wait_cards(page):
    page.wait_for_selector(".job-card[data-id]", state="visible", timeout=15000)


def _visible_card_ids(page):
    """Ids distincts des cartes NON filtrées (indépendant de la pagination)."""
    return page.evaluate(
        "Array.from(new Set([...document.querySelectorAll('.job-card[data-id]')]"
        ".filter(c=>!c.classList.contains('filtered-out'))"
        ".map(c=>c.getAttribute('data-id'))))"
    )


def _bg_sum(page):
    return page.evaluate(
        "(() => { const c=getComputedStyle(document.body).backgroundColor;"
        " const n=(c.match(/\\d+/g)||[0,0,0]).map(Number); return n[0]+n[1]+n[2]; })()"
    )


def _wait_bg(page, dark=True):
    """Attend que le fond du body atteigne l'état sombre/clair (transition CSS 0.25s)."""
    threshold = 80 if dark else 500
    cmp_op = "<" if dark else ">"
    page.wait_for_function(
        "() => { const c=getComputedStyle(document.body).backgroundColor;"
        f" const n=(c.match(/\\d+/g)||[0,0,0]).map(Number); return n[0]+n[1]+n[2] {cmp_op} {threshold}; }}",
        timeout=5000,
    )


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given("3 offres ont été publiées il y a moins de 7 jours")
def three_recent_offers(fh):
    ids = fh["info"]["recent_ids"]
    assert len(ids) == 3, f"attendu 3 offres récentes, trouvé {len(ids)}"
    fh["state"]["recent_ids"] = ids


@given("le dashboard est en mode clair")
def dashboard_in_light_mode(fh):
    page = _open(fh)
    page.evaluate("localStorage.setItem('jh-theme', 'light')")
    page.reload(wait_until="domcontentloaded")
    _wait_cards(page)
    assert page.evaluate("document.documentElement.getAttribute('data-theme')") == "light"
    _wait_bg(page, dark=False)
    fh["state"]["bg_before"] = _bg_sum(page)


@given("le viewport est à 375px")
def viewport_375(fh):
    fh["page"].set_viewport_size({"width": 375, "height": 800})


@given("une offre avec titre, entreprise, salaire, tags")
def offer_with_fields(fh):
    page = _open(fh)
    _wait_cards(page)
    assert page.locator(".job-card .jc-title-link").first.is_visible()
    assert page.locator(".job-card .jc-company").first.is_visible()


@given("une carte d'offre avec URL")
def offer_card_with_url(fh):
    page = _open(fh)
    _wait_cards(page)
    href = page.get_attribute(".job-card .btn-apply", "href")
    assert href and href.startswith("http"), f"URL d'offre absente: {href!r}"
    fh["state"]["apply_href"] = href


@given("le dashboard affiche 18 offres")
def dashboard_shows_18(fh):
    page = _open(fh)
    _wait_cards(page)
    ids = page.evaluate(
        "new Set([...document.querySelectorAll('.job-card[data-id]')].map(c=>c.getAttribute('data-id'))).size"
    )
    assert ids == 18, f"attendu 18 offres distinctes, trouvé {ids}"
    counter = page.text_content("#jobCounter")
    assert "18" in counter, f"compteur initial inattendu: {counter!r}"


@given("j'ai 5 candidatures à différents stades")
def five_applications(fh):
    page = _open(fh)
    stages = page.evaluate(
        "fetch('/api/jobs').then(r=>r.json()).then(js=>js"
        ".filter(j=>(j.pipeline_stage&&j.pipeline_stage!=='new')||j.applied_at)"
        ".map(j=>j.pipeline_stage))"
    )
    assert len(stages) == 5, f"attendu 5 candidatures, trouvé {len(stages)}"


@given('une offre est dans "À postuler"')
def offer_in_a_postuler(fh):
    page = _ensure_open(fh)
    if not page.locator("#kanban-board .kanban-card").count():
        page.click("#kanban-tab")
    page.wait_for_selector('#kanban-board .kanban-col[data-stage="new"] .kanban-card', timeout=10000)
    jid = page.get_attribute(
        '#kanban-board .kanban-col[data-stage="new"] .kanban-card', "data-id"
    )
    assert jid, "aucune offre dans la colonne « À postuler »"
    fh["state"]["kanban_id"] = jid


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when("j'ouvre la page principale")
def open_main_page(fh):
    _open(fh, capture_console=True)


@when("j'ouvre le dashboard")
def open_dashboard(fh):
    _open(fh)


@when("la carte est rendue")
def card_rendered(fh):
    _wait_cards(fh["page"])


@when("je clique sur le toggle dark/light")
def click_theme_toggle(fh):
    page = fh["page"]
    page.click("#theme-btn")
    page.wait_for_function(
        "() => document.documentElement.getAttribute('data-theme') !== 'light'", timeout=5000
    )


@when('je tape "Cypress" dans la recherche')
def type_search(fh):
    page = fh["page"]
    page.fill("#jobSearch", "Cypress")
    page.wait_for_function(
        "() => (document.getElementById('jobCounter').textContent||'').indexOf('18') === -1",
        timeout=5000,
    )


@when('je sélectionne le filtre "Senior"')
def select_senior(fh):
    page = _ensure_open(fh)
    page.click('.facet-group[data-type="seniority"] .facet-btn[data-val="senior"]')
    page.wait_for_function(
        "() => document.querySelector('.facet-group[data-type=\"seniority\"] .facet-btn.active').dataset.val === 'senior'",
        timeout=5000,
    )


@when('je sélectionne "Senior" et "Freelance"')
def select_senior_and_freelance(fh):
    page = _ensure_open(fh)
    page.click('.facet-group[data-type="seniority"] .facet-btn[data-val="senior"]')
    page.click('.facet-group[data-type="contract"] .facet-btn[data-val="freelance"]')
    page.wait_for_function(
        "() => { const s=document.querySelector('.facet-group[data-type=\"seniority\"] .facet-btn.active');"
        " const c=document.querySelector('.facet-group[data-type=\"contract\"] .facet-btn.active');"
        " return s && c && s.dataset.val==='senior' && c.dataset.val==='freelance'; }",
        timeout=5000,
    )


@when("j'ouvre l'onglet Candidatures")
def open_kanban_tab(fh):
    page = fh["page"]
    page.click("#kanban-tab")
    page.wait_for_selector("#kanban-board .kanban-card", timeout=10000)


@when('je clique "Postulé"')
def click_postule(fh):
    page = fh["page"]
    jid = fh["state"]["kanban_id"]
    page.click(
        f'#kanban-board .kanban-col[data-stage="new"] .kanban-card[data-id="{jid}"] '
        f'.kanban-move-btn[data-move="applied"]'
    )
    page.wait_for_function(
        f"() => !!document.querySelector('#kanban-board .kanban-col[data-stage=\"applied\"] "
        f".kanban-card[data-id=\"{jid}\"]')",
        timeout=10000,
    )


@when("je clique sur le titre ou le bouton Apply")
def click_apply(fh):
    page = fh["page"]
    link = page.locator(".job-card .btn-apply").first
    fh["state"]["apply_target"] = link.get_attribute("target")
    fh["state"]["apply_rel"] = link.get_attribute("rel")
    fh["state"]["title_rel"] = page.get_attribute(".job-card .jc-title-link", "rel")
    fh["state"]["title_target"] = page.get_attribute(".job-card .jc-title-link", "target")
    with page.context.expect_page(timeout=8000) as popup:
        link.click()
    fh["state"]["popup"] = popup.value


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then("les skeleton loaders apparaissent pendant le chargement")
def skeleton_visible(fh):
    page = fh["page"]
    count = page.evaluate("window.__skeletonCount")
    assert count and count > 0, "aucun skeleton loader enregistré pendant le chargement"


@then("les cartes d'offres s'affichent après chargement")
def cards_after_load(fh):
    page = fh["page"]
    _wait_cards(page)
    assert page.locator(".job-card").count() > 0


@then("aucune erreur n'apparaît dans la console")
def no_console_errors(fh):
    page_errors = fh["state"].get("page_errors", [])
    console_errors = [
        m for m in fh["state"].get("console_errors", [])
        if not any(p in m for p in _BENIGN_CONSOLE)
    ]
    assert page_errors == [], f"erreur(s) JavaScript: {page_errors}"
    assert console_errors == [], f"erreur(s) console: {console_errors}"


@then('ces 3 offres affichent le badge "NEW" en vert')
def new_badges_green(fh):
    page = fh["page"]
    _wait_cards(page)
    result = page.evaluate(
        """(() => {
          const badges=[...document.querySelectorAll('.badge-new-green')];
          const ids=[...new Set(badges.map(b=>b.closest('.job-card').getAttribute('data-id')))].sort();
          const colors=[...new Set(badges.map(b=>getComputedStyle(b).color))];
          return {ids, text: badges.length?badges[0].textContent:null, colors};
        })()"""
    )
    expected = sorted(str(i) for i in fh["state"]["recent_ids"])
    assert result["ids"] == expected, f"badges NEW inattendus: {result['ids']} != {expected}"
    assert result["text"] == "NEW", f"libellé du badge: {result['text']!r}"
    for color in result["colors"]:
        nums = [int(n) for n in color.replace("rgb(", "").replace(")", "").split(",")[:3]]
        assert nums[1] > nums[0] and nums[1] > nums[2], f"couleur non verte: {color}"


@then("le fond devient sombre")
def background_dark(fh):
    page = fh["page"]
    before = fh["state"]["bg_before"]
    _wait_bg(page, dark=True)
    after = _bg_sum(page)
    fh["state"]["bg_after"] = after
    assert after < before, f"fond non assombri: {before} -> {after}"
    assert after < 200, f"fond pas sombre: {after}"


@then("le mode est conservé après rechargement")
def theme_persists(fh):
    page = fh["page"]
    page.reload(wait_until="domcontentloaded")
    _wait_cards(page)
    assert page.evaluate("document.documentElement.getAttribute('data-theme')") != "light"
    _wait_bg(page, dark=True)
    assert _bg_sum(page) < 200, "fond non sombre après rechargement"


@then("la sidebar devient une barre basse")
def sidebar_bottom_bar(fh):
    page = fh["page"]
    info = page.evaluate(
        "(() => { const r=document.getElementById('sidebar').getBoundingClientRect();"
        " return {pos:getComputedStyle(document.getElementById('sidebar')).position,"
        " top:r.top, bottom:r.bottom, h:window.innerHeight}; })()"
    )
    assert info["pos"] == "fixed", f"sidebar non fixe: {info}"
    assert info["bottom"] >= info["h"] - 4, f"barre basse attendue, bottom={info['bottom']} h={info['h']}"
    assert info["top"] > info["h"] / 2, f"sidebar pas en bas: top={info['top']}"


@then("les cartes sont en colonne unique")
def cards_single_column(fh):
    page = fh["page"]
    info = page.evaluate(
        """(() => {
          const list=document.querySelector('.job-list');
          const lw=list.getBoundingClientRect().width;
          const cards=[...document.querySelectorAll('.job-card')].filter(c=>c.offsetParent!==null).slice(0,4);
          return {lw, widths:cards.map(c=>c.getBoundingClientRect().width),
                  tops:cards.map(c=>c.getBoundingClientRect().top)};
        })()"""
    )
    assert info["widths"], "aucune carte visible"
    for w in info["widths"]:
        assert w >= info["lw"] - 8, f"carte non pleine largeur ({w} < {info['lw']})"
    assert info["tops"] == sorted(info["tops"]), "les cartes ne sont pas empilées verticalement"


@then("le titre est visible")
def title_visible(fh):
    page = fh["page"]
    loc = page.locator(".job-card .jc-title-link").first
    assert loc.is_visible() and (loc.text_content() or "").strip()


@then("l'entreprise est visible")
def company_visible(fh):
    page = fh["page"]
    loc = page.locator(".job-card .jc-company").first
    assert loc.is_visible() and (loc.text_content() or "").strip()


@then("le salaire est visible si présent")
def salary_visible(fh):
    page = fh["page"]
    assert page.locator(".job-card .jc-meta", has_text="💰").count() > 0, "aucun salaire affiché"


@then("les tags sont affichés en pills")
def tags_pills(fh):
    page = fh["page"]
    n = page.locator(".job-card .jc-tags span").count()
    assert n > 0, "aucun tag affiché"
    radius = page.evaluate(
        "getComputedStyle(document.querySelector('.job-card .jc-tags span')).borderTopLeftRadius"
    )
    assert radius not in ("0px", ""), f"tags non arrondis (pills): radius={radius}"


@then("le lien s'ouvre dans un nouvel onglet")
def link_new_tab(fh):
    assert fh["state"].get("apply_target") == "_blank"
    assert fh["state"].get("title_target") == "_blank"
    assert fh["state"].get("popup") is not None, "aucun nouvel onglet ouvert"


@then('l\'attribut rel="noopener noreferrer" est présent')
def rel_noopener(fh):
    for rel in (fh["state"].get("apply_rel"), fh["state"].get("title_rel")):
        assert rel and "noopener" in rel and "noreferrer" in rel, f"rel invalide: {rel!r}"


@then("seules les offres avec Cypress s'affichent")
def only_cypress(fh):
    page = fh["page"]
    bad = page.evaluate(
        "([...document.querySelectorAll('.job-card[data-id]')]"
        ".filter(c=>!c.classList.contains('filtered-out'))"
        ".filter(c=>!(c.textContent||'').toLowerCase().includes('cypress')).length)"
    )
    assert bad == 0, f"{bad} carte(s) sans « Cypress » encore affichée(s)"
    assert len(_visible_card_ids(page)) > 0, "aucune offre Cypress affichée"


@then("le compteur est mis à jour")
def counter_updated(fh):
    page = fh["page"]
    text = page.text_content("#jobCounter")
    assert "18" not in text, f"compteur non mis à jour: {text!r}"
    n = int("".join(ch for ch in text if ch.isdigit()) or 0)
    assert n == len(fh["info"]["cypress_ids"]), f"compteur {n} != {len(fh['info']['cypress_ids'])}"


@then("seules les offres senior s'affichent")
def only_senior(fh):
    page = fh["page"]
    bad = page.evaluate(
        "([...document.querySelectorAll('.job-card[data-id]')]"
        ".filter(c=>!c.classList.contains('filtered-out'))"
        ".filter(c=>c.getAttribute('data-seniority')!=='senior').length)"
    )
    assert bad == 0, f"{bad} carte(s) non senior affichée(s)"
    assert len(_visible_card_ids(page)) == len(fh["info"]["senior_ids"])


@then("les offres affichées sont senior ET freelance")
def senior_and_freelance(fh):
    page = fh["page"]
    bad = page.evaluate(
        "([...document.querySelectorAll('.job-card[data-id]')]"
        ".filter(c=>!c.classList.contains('filtered-out'))"
        ".filter(c=>!(c.getAttribute('data-seniority')==='senior' && c.getAttribute('data-contract')==='freelance')).length)"
    )
    assert bad == 0, f"{bad} carte(s) ne respectant pas Senior ET Freelance"
    assert len(_visible_card_ids(page)) == len(fh["info"]["senior_freelance_ids"])


@then("je vois 5 colonnes : À postuler, Postulé, Entretien, Offre, Refusé")
def five_columns(fh):
    titles = fh["page"].evaluate(
        "[...document.querySelectorAll('#kanban-board .kanban-col-title')].map(h=>h.textContent)"
    )
    assert titles == ["À postuler", "Postulé", "Entretien", "Offre", "Refusé"], titles


@then("chaque colonne contient le bon nombre d'offres")
def column_counts(fh):
    counts = fh["page"].evaluate(
        "(() => { const o={}; document.querySelectorAll('#kanban-board .kanban-col')"
        ".forEach(c=>{o[c.dataset.stage]=c.querySelectorAll('.kanban-card').length}); return o; })()"
    )
    assert counts == {"new": 1, "applied": 1, "interview": 1, "offer": 1, "rejected": 1}, counts


@then('l\'offre apparaît dans la colonne "Postulé"')
def offer_in_postule(fh):
    page = fh["page"]
    jid = fh["state"]["kanban_id"]
    assert page.evaluate(
        f"!!document.querySelector('#kanban-board .kanban-col[data-stage=\"applied\"] "
        f".kanban-card[data-id=\"{jid}\"]')"
    ), "l'offre n'est pas dans la colonne Postulé"
    stage = page.evaluate(
        f"fetch('/api/jobs').then(r=>r.json()).then(js=>{{const j=js.find(x=>String(x.id)==='{jid}');"
        f"return j?j.pipeline_stage:null;}})"
    )
    assert stage == "applied", f"le déplacement n'a pas persisté (stage={stage})"
