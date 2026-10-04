"""Page Objects des parcours UI."""

from .dashboard_page import DashboardPage
from .kanban_page import STAGE_LABELS, STAGES, KanbanPage

__all__ = ["DashboardPage", "KanbanPage", "STAGES", "STAGE_LABELS"]
