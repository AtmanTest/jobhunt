"""Page Object de la vue Kanban « Candidatures » (pipeline).

Écran distinct du tableau de bord (overlay plein écran piloté par `#kanban-tab`),
d'où un Page Object dédié. Tous les locators du Kanban sont centralisés ici ;
aucun sélecteur Kanban n'apparaît dans les specs, et aucune assertion n'est faite
dans ce fichier.
"""

from __future__ import annotations

from playwright.sync_api import Locator, Page

# Stades du pipeline, dans l'ordre d'affichage (source : app, colonnes du board).
STAGES = ("new", "applied", "interview", "offer", "rejected")
STAGE_LABELS = ("À postuler", "Postulé", "Entretien", "Offre", "Refusé")


class KanbanPage:
    """Overlay Kanban — pipeline des candidatures."""

    READY_TIMEOUT_MS = 10_000

    def __init__(self, page: Page, base_url: str = "") -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")

        self.tab: Locator = page.locator("#kanban-tab")
        self.view: Locator = page.locator("#kanban-view")
        self.board: Locator = page.locator("#kanban-board")
        self.columns: Locator = page.locator("#kanban-board .kanban-col")
        self.column_titles: Locator = page.locator("#kanban-board .kanban-col-title")
        self.close_button: Locator = page.locator("#kanban-close")

    # --- locators paramétrés (jamais disséminés dans les specs) -----------
    def column(self, stage: str) -> Locator:
        return self.page.locator(f'#kanban-board .kanban-col[data-stage="{stage}"]')

    def cards_in(self, stage: str) -> Locator:
        return self.column(stage).locator(".kanban-card")

    def card(self, stage: str, job_id) -> Locator:
        return self.column(stage).locator(f'.kanban-card[data-id="{job_id}"]')

    def move_button(self, stage: str, job_id, target: str) -> Locator:
        return self.card(stage, job_id).locator(f'.kanban-move-btn[data-move="{target}"]')

    # --- interactions -----------------------------------------------------
    def open(self) -> "KanbanPage":
        """Ouvre l'onglet Candidatures et attend le premier rendu du board."""
        self.tab.click()
        self.view.wait_for(state="visible", timeout=self.READY_TIMEOUT_MS)
        return self.wait_board_loaded()

    def wait_board_loaded(self, timeout_ms: int = READY_TIMEOUT_MS) -> "KanbanPage":
        """Attend qu'au moins une carte soit rendue dans une colonne."""
        self.board.locator(".kanban-card").first.wait_for(
            state="visible", timeout=timeout_ms
        )
        return self

    def close(self) -> "KanbanPage":
        self.close_button.click()
        self.view.wait_for(state="hidden", timeout=self.READY_TIMEOUT_MS)
        return self

    def close_with_keyboard(self) -> "KanbanPage":
        """Ferme l'écran Kanban au clavier (Échap) — chemin d'accessibilité."""
        self.page.keyboard.press("Escape")
        self.view.wait_for(state="hidden", timeout=self.READY_TIMEOUT_MS)
        return self

    def move_card(self, job_id, from_stage: str, to_stage: str) -> "KanbanPage":
        """Déplace une carte via le bouton de la colonne cible du board."""
        self.move_button(from_stage, job_id, to_stage).click()
        self.wait_card_in_stage(job_id, to_stage)
        return self

    def wait_card_in_stage(self, job_id, stage: str, timeout_ms: int = READY_TIMEOUT_MS) -> "KanbanPage":
        self.card(stage, job_id).wait_for(state="visible", timeout=timeout_ms)
        return self

    # --- lectures ---------------------------------------------------------
    def column_titles_text(self) -> list:
        return self.column_titles.all_inner_texts()

    def column_count(self, stage: str) -> int:
        return self.cards_in(stage).count()
