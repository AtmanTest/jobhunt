"""
Test suites definition for JobHunt QA Dashboard.
Organized by category, each test has id, name, description, and runner reference.
"""

import json, os, glob

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ─── Test Plans ──────────────────────────────────────────────
PLANS = {
    "smoke": {
        "name": "Smoke Test",
        "description": "Tests rapides pour valider le cœur du dashboard",
        "icon": "🔥",
        "suites": ["playwright"],
    },
    "regression": {
        "name": "Régression complète",
        "description": "Tous les tests — Playwright + BDD + API",
        "icon": "🔄",
        "suites": ["playwright", "bdd", "api"],
    },
    "playwright_demo": {
        "name": "Démo Playwright",
        "description": "Tests UI du dashboard pour démo recruteur",
        "icon": "🎭",
        "suites": ["playwright"],
    },
}

# ─── Test Suites ────────────────────────────────────────────

def get_suites(base_url="http://localhost:5050"):
    """Build all suites dynamically."""

    # ── Playwright Suite ──
    playwright_tests = [
        {"id": "pw_01", "name": "Page load & title", "description": "Vérifie le chargement du dashboard", "timeout": 10},
        {"id": "pw_02", "name": "Hero stats display", "description": "4 cartes de stats visibles", "timeout": 10},
        {"id": "pw_03", "name": "Country tabs", "description": "Onglets France, Suisse, Lux, Dubaï, SG", "timeout": 10},
        {"id": "pw_04", "name": "Remote filter", "description": "Filtre Remote/Hybride/Sur site", "timeout": 10},
        {"id": "pw_05", "name": "Job cards", "description": "Offres d'emploi affichées", "timeout": 15},
        {"id": "pw_06", "name": "Top matches", "description": "Section top matches avec scores", "timeout": 10},
        {"id": "pw_07", "name": "CV page", "description": "Page CV avec profil et expériences", "timeout": 10},
        {"id": "pw_08", "name": "Pagination", "description": "Navigation entre les pages", "timeout": 10},
    ]

    # ── BDD Suite (parsed from .feature files) ──
    bdd_tests = []
    features_dir = os.path.join(BASE_DIR, "tests", "features")
    if os.path.isdir(features_dir):
        for root, dirs, files in os.walk(features_dir):
            for fname in sorted(files):
                if not fname.endswith(".feature"):
                    continue
                fpath = os.path.join(root, fname)
                rel_dir = os.path.relpath(root, features_dir)
                category = rel_dir if rel_dir != "." else "root"
                with open(fpath, encoding="utf-8") as f:
                    content = f.read()
                scenario_count = content.count("Scenario:")
                tid = f"bdd_{len(bdd_tests)+1:02d}"
                bdd_tests.append({
                    "id": tid,
                    "name": fname.replace(".feature", ""),
                    "description": f"{category}/ — {scenario_count} scénarios",
                    "file": fpath,
                    "timeout": 30,
                })

    # ── API Suite ──
    api_tests = [
        {"id": "api_01", "name": "GET / → 200", "description": "Page d'accueil du dashboard", "timeout": 5},
        {"id": "api_02", "name": "GET /cv → 200", "description": "Page CV", "timeout": 5},
        {"id": "api_03", "name": "GET /api/deepseek/balance", "description": "Endpoint balance DeepSeek", "timeout": 5},
        {"id": "api_04", "name": "GET /api/stats → JSON", "description": "Endpoint stats", "timeout": 5},
        {"id": "api_05", "name": "GET /qa/api/test-cases", "description": "Endpoint cas de test", "timeout": 5},
        {"id": "api_06", "name": "GET /api/linkedin/jobs", "description": "Endpoint jobs LinkedIn", "timeout": 10},
        {"id": "api_07", "name": "GET /marche-qa → 200", "description": "Page Marché QA", "timeout": 5},
        {"id": "api_08", "name": "GET /about → 200", "description": "Page À propos", "timeout": 5},
    ]

    suites = {
        "playwright": {
            "name": "Playwright",
            "icon": "🎭",
            "description": "Tests d'interface utilisateur du dashboard (Chrome headless)",
            "tests": playwright_tests,
        },
        "bdd": {
            "name": "BDD / Feature",
            "icon": "🧪",
            "description": "Tests comportementaux Gherkin (./tests/features/)",
            "tests": bdd_tests,
        },
        "api": {
            "name": "API",
            "icon": "🔌",
            "description": "Tests des endpoints Flask du dashboard",
            "tests": api_tests,
        },
    }

    return suites
