"""Fixtures Playwright — configuration par environnement, isolation, artefacts.

Principes appliqués :
  • la configuration vient de `config/environments.py`, jamais d'un chemin ou d'une
    URL codés en dur ;
  • chaque test reçoit son propre contexte (fixture `page` de pytest-playwright) ;
  • toute donnée créée porte un suffixe unique (voir `unique_suffix`).

Deux étages de serveur coexistent :

  * la fumée (@smoke) cible l'URL fournie par `JOBHUNT_BASE_URL` (ou la config) —
    `base_url` / `dashboard` ci-dessous, comportement inchangé ;
  * la régression (@regression) démarre son PROPRE serveur Flask sur un port libre
    de 127.0.0.1, adossé à une base SQLite temporaire ensemencée de façon
    déterministe par `tests/playwright/fixtures/e2e_data.py`. La base est
    réamorcée avant chaque test : isolation totale, aucun couplage d'ordre,
    parallélisable sans ressource partagée (chaque worker xdist a son serveur,
    son port et son fichier de base).
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import settings  # noqa: E402
from tests.playwright.pages import DashboardPage, KanbanPage, LoginPage  # noqa: E402

# Fragments de bruit réseau à ignorer (chargement de ressource, requête bloquée)
# : ce ne sont pas des erreurs applicatives.
_BENIGN_CONSOLE = ("Failed to load resource", "net::", "ERR_")


@pytest.fixture(scope="session")
def env():
    """Environnement résolu (variable JOBHUNT_ENV, défaut : test)."""
    return settings()


@pytest.fixture(scope="session")
def base_url(env) -> str:
    """URL de base du dashboard — surchargeable par JOBHUNT_BASE_URL.

    Utilisée par la fumée : elle pointe vers l'app démarrée en boucle locale
    (`JOBHUNT_BASE_URL`) ou, à défaut, vers la config d'environnement.
    """
    return os.getenv("JOBHUNT_BASE_URL", env.base_url).rstrip("/")


@pytest.fixture
def unique_suffix() -> str:
    """Suffixe unique par test : aucune collision de données entre workers."""
    return uuid.uuid4().hex[:8]


@pytest.fixture
def dashboard(page, base_url) -> DashboardPage:
    """Page Object du tableau de bord ciblant `base_url` (fumée)."""
    return DashboardPage(page, base_url=base_url)


# ---------------------------------------------------------------------------
# Étages de régression : serveur local dédié + base déterministe
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def live_server(tmp_path_factory):
    """Démarre l'app Flask sur un port libre de 127.0.0.1, base temporaire.

    Le serveur est démarré UNE fois par processus worker (scope session) ;
    chaque test réamorce ensuite la base via la fixture `seeded`.
    """
    import scraper

    # Neutralise le thread de scraping LinkedIn lancé à l'import de app.py :
    # il polluerait la base déterministe avec des offres réelles non reproductibles.
    scraper.fetch_linkedin_countries = lambda *a, **k: []

    import app as app_module

    from tests.playwright.fixtures.e2e_data import seed_database

    db_path = str(tmp_path_factory.mktemp("playwright_e2e") / "e2e_jobs.db")
    seed_database(db_path)

    originals = {
        "fetch_linkedin_countries": scraper.fetch_linkedin_countries,
        "scraper_db_path": scraper.DB_PATH,
        "app_db_path": app_module.DB_PATH,
        "app_populated": app_module.DB_POPULATED,
        "app_ensure": app_module._ensure_db_populated,
    }

    # L'app lit la base par `sqlite3.connect(DB_PATH)` à plusieurs endroits
    # (app.DB_PATH ET scraper.DB_PATH) : on aligne les deux sur la base de test.
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

    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 20
    ready = False
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url + "/api/stats", timeout=1).read()
            ready = True
            break
        except Exception:
            time.sleep(0.05)
    if not ready:
        server.shutdown()
        raise RuntimeError("le serveur Playwright E2E n'a pas démarré")

    yield {"base_url": url, "db_path": db_path, "port": port}

    server.shutdown()
    scraper.fetch_linkedin_countries = originals["fetch_linkedin_countries"]
    scraper.DB_PATH = originals["scraper_db_path"]
    app_module.DB_PATH = originals["app_db_path"]
    app_module.DB_POPULATED = originals["app_populated"]
    app_module._ensure_db_populated = originals["app_ensure"]


@pytest.fixture
def seeded(live_server):
    """Réamorce la base déterministe et expose l'URL + les ids attendus.

    Le réamorçage par test garantit qu'un déplacement Kanban (qui écrit en base)
    ne fuit jamais sur le test suivant, quel que soit l'ordre d'exécution.
    """
    from tests.playwright.fixtures.e2e_data import seed_database

    info = seed_database(live_server["db_path"])
    return {"base_url": live_server["base_url"], "db_path": live_server["db_path"], "info": info}


@pytest.fixture
def reg_dashboard(page, seeded) -> DashboardPage:
    """Page Object du dashboard ciblant le serveur E2E déterministe (régression)."""
    return DashboardPage(page, base_url=seeded["base_url"])


@pytest.fixture
def kanban(page, seeded) -> KanbanPage:
    """Page Object de la vue Kanban ciblant le serveur E2E déterministe."""
    return KanbanPage(page, base_url=seeded["base_url"])


@pytest.fixture
def login(page, seeded) -> LoginPage:
    """Page Object de l'écran de connexion ciblant le serveur E2E déterministe."""
    return LoginPage(page, base_url=seeded["base_url"])


@pytest.fixture
def connected_dashboard(page, seeded) -> DashboardPage:
    """Dashboard avec une session SIMULÉE : le menu utilisateur reste affiché.

    Le dashboard remplace le bouton utilisateur par un lien « Connexion » dès que
    `/api/auth/me` répond « anonyme ». En simulant une réponse authentifiée, on
    exerce la branche connectée (menu, profil, déconnexion) sans dépendre d'un
    vrai fournisseur d'identité. La route est interceptée AVANT la navigation.
    """
    import json as _json

    page.route(
        "**/api/auth/me",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=_json.dumps(
                {
                    "authenticated": True,
                    "user_id": "u-test",
                    "email": "qa@example.com",
                    "full_name": "Atman",
                    "headline": "QA Lead",
                    "avatar_url": "",
                }
            ),
        ),
    )
    return DashboardPage(page, base_url=seeded["base_url"])


@pytest.fixture
def console_errors(page):
    """Collecte les erreurs console/JS, filtrées du bruit réseau.

    Branché AVANT navigation par le test : une erreur JS au chargement doit
    faire échouer un test de régression, pas passer inaperçue.
    """
    errors: list = []

    def _on_console(msg):
        if msg.type == "error" and not any(p in msg.text for p in _BENIGN_CONSOLE):
            errors.append(f"console: {msg.text}")

    page.on("console", _on_console)
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
    return errors
