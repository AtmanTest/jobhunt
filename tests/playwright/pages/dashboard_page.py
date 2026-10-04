"""Page Object du tableau de bord JobHunt.

Règles (playwright.dev/docs/best-practices) :
  • un Page Object décrit des INTERACTIONS et des LECTURES, il n'assertionne pas
    (les assertions restent dans les specs) ;
  • les locators sont centralisés ici : une refonte de l'UI ne casse qu'un fichier ;
  • ordre de préférence : role > label > text > testid > CSS. Jamais de XPath ;
  • aucune attente arbitraire (sleep) : uniquement des attentes sur condition
    observable (web-first `expect` côté spec, `wait_for_function` pour le style calculé).
"""

from __future__ import annotations

from typing import Any

from playwright.sync_api import Locator, Page


class DashboardPage:
    """Page `/` — tableau de bord des offres QA."""

    PATH = "/"
    READY_TIMEOUT_MS = 10_000

    def __init__(self, page: Page, base_url: str = "") -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")

        # ── Structure historique (utilisée par la fumée) ──
        self.hero: Locator = page.locator(".hero")
        self.filter_bar: Locator = page.locator(".filter-bar")
        self.job_list: Locator = page.locator(".job-list")
        self.job_cards: Locator = page.locator(".job-card")
        self.top_matches: Locator = page.locator(".top-match-card")
        self.pipeline_steps: Locator = page.locator(".pipeline-step")

        # ── Recherche temps réel + facettes ──
        self.search_input: Locator = page.locator("#jobSearch")
        self.counter: Locator = page.locator("#jobCounter")
        self.seniority_group: Locator = page.locator('.facet-group[data-type="seniority"]')
        self.contract_group: Locator = page.locator('.facet-group[data-type="contract"]')
        self.active_seniority: Locator = page.locator(
            '.facet-group[data-type="seniority"] .facet-btn.active'
        )
        self.active_contract: Locator = page.locator(
            '.facet-group[data-type="contract"] .facet-btn.active'
        )

        # ── Thème / navigation responsive ──
        self.theme_button: Locator = page.locator("#theme-btn")
        self.sidebar: Locator = page.locator("#sidebar")

        # ── Cartes d'offres (panneau actif et global) ──
        # Le panneau actif (France) contient une carte par offre ; le panneau
        # « Tous » les duplique. On scope donc les comptes d'égalité au panneau
        # actif pour ne pas compter deux fois la même offre.
        self.active_panel_cards: Locator = page.locator(".tab-panel.active .job-card[data-id]")
        self.active_matching_cards: Locator = page.locator(
            ".tab-panel.active .job-card[data-id]:not(.filtered-out)"
        )
        self.active_visible_cards: Locator = page.locator(
            ".tab-panel.active .job-card[data-id]:visible"
        )
        self.card_titles: Locator = page.locator(".job-card .jc-title-link")
        self.card_companies: Locator = page.locator(".job-card .jc-company")
        self.card_skill_tags: Locator = page.locator(".job-card .skill-tag")
        self.apply_links: Locator = page.locator(".job-card .btn-apply")

    # --- navigation -------------------------------------------------------
    def open(self) -> "DashboardPage":
        """Ouvre le dashboard et rend la main dès le DOM chargé."""
        self.page.goto(f"{self.base_url}{self.PATH}", wait_until="domcontentloaded")
        return self

    def wait_ready(self) -> "DashboardPage":
        """Attend que le bloc principal soit visible (attente auto, pas de sleep)."""
        self.hero.first.wait_for(state="visible", timeout=self.READY_TIMEOUT_MS)
        return self

    def wait_loaded(self) -> "DashboardPage":
        """Attend que les cartes soient révélées (classe `app-loaded` sur <body>).

        Les cartes restent `visibility:hidden` jusqu'à l'évènement `load`
        observé par l'app : tant que la classe n'est pas posée, aucune carte
        n'est « visible » au sens de Playwright.
        """
        self.page.wait_for_selector("body.app-loaded", timeout=self.READY_TIMEOUT_MS)
        return self

    def open_ready(self) -> "DashboardPage":
        """Navigue, puis attend structure ET cartes révélées."""
        return self.open().wait_ready().wait_loaded()

    def reload_loaded(self) -> "DashboardPage":
        """Recharge la page et attend le même état prêt (persistance)."""
        self.page.reload(wait_until="domcontentloaded")
        return self.wait_ready().wait_loaded()

    # --- interactions -----------------------------------------------------
    def search(self, text: str) -> "DashboardPage":
        """Saisit un terme dans la recherche temps réel."""
        self.search_input.fill(text)
        return self

    def clear_search(self) -> "DashboardPage":
        """Vide la recherche (retour à l'état complet)."""
        self.search_input.fill("")
        return self

    def click_seniority(self, value: str) -> "DashboardPage":
        self.seniority_group.locator(f'.facet-btn[data-val="{value}"]').click()
        return self

    def click_contract(self, value: str) -> "DashboardPage":
        self.contract_group.locator(f'.facet-btn[data-val="{value}"]').click()
        return self

    def toggle_theme(self) -> "DashboardPage":
        self.theme_button.click()
        return self

    def set_stored_theme(self, mode: str) -> "DashboardPage":
        """Prépare localStorage PUIS recharge : la préférence doit être relue à froid."""
        self.page.evaluate("m => localStorage.setItem('jh-theme', m)", mode)
        return self.reload_loaded()

    # --- lectures ---------------------------------------------------------
    def title(self) -> str:
        return self.page.title()

    def url(self) -> str:
        return self.page.url

    def job_cards_count(self) -> int:
        return self.job_cards.count()

    def top_matches_count(self) -> int:
        return self.top_matches.count()

    def pipeline_steps_count(self) -> int:
        return self.pipeline_steps.count()

    def counter_text(self) -> str:
        return self.counter.inner_text()

    def counter_number(self) -> int:
        digits = "".join(ch for ch in self.counter_text() if ch.isdigit())
        return int(digits) if digits else 0

    def total_attribute(self) -> int:
        raw = self.counter.get_attribute("data-total") or "0"
        return int(raw)

    def first_visible_card(self) -> Locator:
        return self.page.locator(".tab-panel.active .job-card[data-id]:visible").first

    # --- thème (état réellement calculé, pas seulement une classe) --------
    def theme_attribute(self) -> Any:
        return self.page.evaluate("document.documentElement.getAttribute('data-theme')")

    def stored_theme(self) -> Any:
        return self.page.evaluate("localStorage.getItem('jh-theme')")

    def background_channel_sum(self) -> int:
        """Somme R+G+B du fond du <body> — mesure l'état sombre/clair réel."""
        return int(
            self.page.evaluate(
                "(() => { const c = getComputedStyle(document.body).backgroundColor;"
                " const n = (c.match(/\\d+/g) || [0,0,0]).map(Number);"
                " return n[0] + n[1] + n[2]; })()"
            )
        )

    def wait_background_dark(self, timeout_ms: int = 5_000) -> "DashboardPage":
        self.page.wait_for_function(
            "() => { const c = getComputedStyle(document.body).backgroundColor;"
            " const n = (c.match(/\\d+/g) || [0,0,0]).map(Number);"
            " return n[0] + n[1] + n[2] < 80; }",
            timeout=timeout_ms,
        )
        return self

    def wait_background_light(self, timeout_ms: int = 5_000) -> "DashboardPage":
        self.page.wait_for_function(
            "() => { const c = getComputedStyle(document.body).backgroundColor;"
            " const n = (c.match(/\\d+/g) || [0,0,0]).map(Number);"
            " return n[0] + n[1] + n[2] > 500; }",
            timeout=timeout_ms,
        )
        return self

    # --- responsive -------------------------------------------------------
    def set_mobile_viewport(self) -> "DashboardPage":
        self.page.set_viewport_size({"width": 375, "height": 800})
        return self

    def wait_sidebar_bottom_bar(self, timeout_ms: int = 5_000) -> "DashboardPage":
        self.page.wait_for_function(
            "() => { const el = document.getElementById('sidebar');"
            " if (!el) return false; const r = el.getBoundingClientRect();"
            " return getComputedStyle(el).position === 'fixed' && r.top > window.innerHeight / 2; }",
            timeout=timeout_ms,
        )
        return self

    def sidebar_geometry(self) -> dict:
        return self.page.evaluate(
            "(() => { const el = document.getElementById('sidebar');"
            " const r = el.getBoundingClientRect();"
            " return {position: getComputedStyle(el).position, top: r.top,"
            " bottom: r.bottom, height: window.innerHeight}; })()"
        )

    def active_panel_layout(self) -> dict:
        """Largeurs/hauts des premières cartes visibles du panneau actif."""
        return self.page.evaluate(
            "(() => { const list = document.querySelector('.tab-panel.active .job-list');"
            " const lw = list ? list.getBoundingClientRect().width : 0;"
            " const cards = [...document.querySelectorAll('.tab-panel.active .job-card')]"
            ".filter(c => c.offsetParent !== null).slice(0, 4);"
            " return {list_width: lw,"
            " widths: cards.map(c => c.getBoundingClientRect().width),"
            " tops: cards.map(c => c.getBoundingClientRect().top)}; })()"
        )
