"""Fixtures Playwright — configuration par environnement, isolation, artefacts.

Principes appliqués :
  • la configuration vient de `config/environments.py`, jamais d'un chemin ou d'une
    URL codés en dur ;
  • chaque test reçoit son propre contexte (fixture `page` de pytest-playwright) ;
  • toute donnée créée porte un suffixe unique (voir `unique_suffix`).
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import settings  # noqa: E402
from tests.playwright.pages import DashboardPage  # noqa: E402


@pytest.fixture(scope="session")
def env():
    """Environnement résolu (variable JOBHUNT_ENV, défaut : test)."""
    return settings()


@pytest.fixture(scope="session")
def base_url(env) -> str:
    """URL de base du dashboard — surchargeable par JOBHUNT_BASE_URL."""
    return os.getenv("JOBHUNT_BASE_URL", env.base_url).rstrip("/")


@pytest.fixture
def unique_suffix() -> str:
    """Suffixe unique par test : aucune collision de données entre workers."""
    return uuid.uuid4().hex[:8]


@pytest.fixture
def dashboard(page, base_url) -> DashboardPage:
    """Page Object du tableau de bord, prêt à l'emploi."""
    return DashboardPage(page, base_url=base_url)
