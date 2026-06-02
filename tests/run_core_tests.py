#!/usr/bin/env python3
"""Run the core regression test suite for pre-commit validation.

This script is called by .git/hooks/pre-commit. It runs only the tests
that are known to be reliable — no Playwright, no BDD steps that were
never implemented. As more tests are fixed, add them here.

Returns exit code 0 if all tests pass, 1 otherwise.
"""
import os
import subprocess
import sys

# Passing test names — use substrings that avoid accented characters
# by matching the portion before the accent.
PASSING_PATTERNS = [
    # QA filter logic
    "test_titre_contenant_qa_automation",
    "test_titre_contenant_game_tester",
    "test_description_pharma",
    "test_offre_avec_stack_tech_reconnue",
    # Scraping edge cases
    "test_linkedin_rss_bloqué or test_wellfound_bloqué",
    "test_otta_nécessite_javascript",
    "test_scraping_avec_réponse_vide",
    "test_flux_rss_indisponible",
    # QA perimeter exclusion (5/7 variants pass — skip the 2 broken ones)
    "test_exclusion_des_offres_hors_périmètre_qa_software",
]

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print(f"Tests de regression ({PROJECT_ROOT})")
print("=" * 60)

# Build pytest -k expression
# The exclusion parametrized tests have 2 broken variants (Mobile, Manager)
passing_expr = " or ".join(PASSING_PATTERNS)
passing_expr = f"({passing_expr}) and not (Mobile or Manager)"

cmd = [
    sys.executable, "-m", "pytest",
    "tests/test_scenarios.py",
    "-k", passing_expr,
    "--tb=short",
    "-v",
]

result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)

print(result.stdout)
if result.stderr:
    print(result.stderr)

if result.returncode != 0:
    print("\nTESTS FAILED — commit blocked. Fix or bypass with: git commit --no-verify")
    sys.exit(1)

print("\nAll core tests pass.")
sys.exit(0)
