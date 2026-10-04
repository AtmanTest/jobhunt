"""Page Object du tableau de bord JobHunt.

Règle de locator : role > label > data-testid > CSS. Jamais de XPath.
Les sélecteurs sont centralisés ici : un changement d'UI ne casse qu'un seul fichier.
"""

from __future__ import annotations

from playwright.sync_api import Page


class DashboardPage:
    """Parcours du tableau de bord."""

    PATH = "/"

    def __init__(self, page: Page, base_url: str = "") -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")

    def open(self) -> "DashboardPage":
        self.page.goto(f"{self.base_url}{self.PATH}", wait_until="domcontentloaded")
        return self

    def wait_ready(self) -> "DashboardPage":
        self.page.wait_for_selector("[data-testid='dashboard'], body", timeout=10_000)
        return self

    def title(self) -> str:
        return self.page.title()

    def job_cards_count(self) -> int:
        return self.page.locator("[data-testid='job-card']").count()

    def top_matches_count(self) -> int:
        return self.page.locator("[data-testid='top-match']").count()

    def select_country(self, label: str) -> "DashboardPage":
        self.page.get_by_role("tab", name=label).click()
        return self

    def search(self, text: str) -> "DashboardPage":
        self.page.get_by_role("searchbox").fill(text)
        self.page.keyboard.press("Enter")
        return self
