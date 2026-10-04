"""Page Object du tableau de bord JobHunt.

Règles :
  • un Page Object décrit des INTERACTIONS, il n'assertionne pas (l'assertion reste
    dans le spec) ;
  • les locators sont centralisés ici : une refonte de l'UI ne casse qu'un fichier ;
  • ordre de préférence : role > label > text > testid > CSS. Jamais de XPath.
"""

from __future__ import annotations

from playwright.sync_api import Locator, Page


class DashboardPage:
    """Page `/` — tableau de bord des offres QA."""

    PATH = "/"
    READY_TIMEOUT_MS = 10_000

    def __init__(self, page: Page, base_url: str = "") -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")

        # Locators exposés (lecture seule pour les specs)
        self.hero: Locator = page.locator(".hero")
        self.filter_bar: Locator = page.locator(".filter-bar")
        self.job_list: Locator = page.locator(".job-list")
        self.job_cards: Locator = page.locator(".job-card")
        self.top_matches: Locator = page.locator(".top-match-card")
        self.pipeline_steps: Locator = page.locator(".pipeline-step")

    # --- navigation -------------------------------------------------------
    def open(self) -> "DashboardPage":
        """Ouvre le dashboard et rend la main dès le DOM chargé."""
        self.page.goto(f"{self.base_url}{self.PATH}", wait_until="domcontentloaded")
        return self

    def wait_ready(self) -> "DashboardPage":
        """Attend que le bloc principal soit visible (attente auto, pas de sleep)."""
        self.hero.first.wait_for(state="visible", timeout=self.READY_TIMEOUT_MS)
        return self

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
