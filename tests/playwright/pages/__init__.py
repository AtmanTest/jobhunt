"""Page Objects des parcours UI."""

from .dashboard_page import DashboardPage
from .kanban_page import STAGE_LABELS, STAGES, KanbanPage
from .login_page import LoginPage

__all__ = ["DashboardPage", "KanbanPage", "LoginPage", "STAGES", "STAGE_LABELS"]
