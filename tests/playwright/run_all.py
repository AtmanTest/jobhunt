"""
Playwright tests for JobHunt Dashboard — live demo of QA automation skills.
Run: python3 tests/playwright/run_all.py
Requires: the Flask app to be running on http://localhost:5050
"""

import os, sys, json, time

# Use the Playwright venv we set up
PW_PYTHON = "/tmp/pw_venv/bin/python3"

TEST_FILE = os.path.join(os.path.dirname(__file__), "test_dashboard.py")

TEST_CASES = [
    {
        "name": "Page load & title",
        "description": "Vérifie que le dashboard se charge et que le titre est correct",
        "file": "test_dashboard.py",
        "scenario": "test_page_title",
    },
    {
        "name": "Hero stats display",
        "description": "Vérifie que les 4 cartes de stats (Offres QA, Cette semaine, Marchés, Balance) sont visibles",
        "file": "test_dashboard.py",
        "scenario": "test_hero_stats",
    },
    {
        "name": "Country tabs switching",
        "description": "Vérifie que les onglets pays (France, Suisse, Luxembourg, Dubaï, Singapour) sont cliquables",
        "file": "test_dashboard.py",
        "scenario": "test_country_tabs",
    },
    {
        "name": "Remote filter",
        "description": "Vérifie que le filtre Remote/Hybride/Sur site fonctionne",
        "file": "test_dashboard.py",
        "scenario": "test_remote_filter",
    },
    {
        "name": "Job cards rendering",
        "description": "Vérifie que les offres d'emploi s'affichent dans le panneau actif",
        "file": "test_dashboard.py",
        "scenario": "test_job_cards",
    },
    {
        "name": "Top matches section",
        "description": "Vérifie que la section Top matches est visible avec des scores",
        "file": "test_dashboard.py",
        "scenario": "test_top_matches",
    },
    {
        "name": "CV page loads",
        "description": "Vérifie que la page CV se charge avec le nom et les sections",
        "file": "test_dashboard.py",
        "scenario": "test_cv_page",
    },
    {
        "name": "Pagination navigation",
        "description": "Vérifie que la pagination fonctionne (page suivante/précédente)",
        "file": "test_dashboard.py",
        "scenario": "test_pagination",
    },
]


def run_test(scenario: str) -> dict:
    """Run a single Playwright test scenario and return result."""
    import subprocess
    start = time.time()
    try:
        result = subprocess.run(
            [PW_PYTHON, "-c", f"""
import sys, json
sys.path.insert(0, '{os.path.dirname(__file__)}')
from test_dashboard import run_scenario
result = run_scenario('{scenario}')
print(json.dumps(result))
"""],
            capture_output=True, text=True, timeout=60,
        )
        elapsed = round(time.time() - start, 2)
        if result.returncode == 0:
            data = json.loads(result.stdout.strip())
            data["duration"] = elapsed
            return data
        return {"name": scenario, "passed": False, "error": result.stderr[:200], "duration": elapsed}
    except subprocess.TimeoutExpired:
        return {"name": scenario, "passed": False, "error": "TIMEOUT (60s)", "duration": 60}
    except Exception as e:
        return {"name": scenario, "passed": False, "error": str(e)[:200], "duration": round(time.time() - start, 2)}


def run_all() -> list:
    results = []
    for tc in TEST_CASES:
        print(f"  Running: {tc['name']}...", end=" ")
        sys.stdout.flush()
        result = run_test(tc["scenario"])
        result["name"] = tc["name"]
        result["description"] = tc["description"]
        results.append(result)
        status = "✅" if result.get("passed") else "❌"
        print(f"{status} ({result.get('duration', '?')}s)")
    return results


if __name__ == "__main__":
    print(f"\n🧪 Running {len(TEST_CASES)} Playwright tests on JobHunt Dashboard\n")
    print(f"{'='*50}")
    results = run_all()
    passed = sum(1 for r in results if r.get("passed"))
    failed = sum(1 for r in results if not r.get("passed"))
    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed / {len(results)} total")
    # Output JSON for the QA page to consume
    output_path = os.path.join(os.path.dirname(__file__), "..", "..", ".qa_runs", "playwright_latest.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({"results": results, "timestamp": time.time(), "total": len(results), "passed": passed, "failed": failed}, f)
    print(f"Results saved to {output_path}")
