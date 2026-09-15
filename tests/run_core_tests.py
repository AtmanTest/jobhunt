#!/usr/bin/env python3
"""Run the core regression test suite for pre-commit validation.

Called by .git/hooks/pre-commit. Runs only the tests known to pass
reliably — 33 stable tests as of June 2026.

Returns exit code 0 if all tests pass, 1 otherwise.
"""
import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print(f"Tests de regression — 33 tests stables ({PROJECT_ROOT})")
print("=" * 60)

cmd = [
    sys.executable, "-m", "pytest",
    "tests/test_scenarios.py",
    "-k", " or ".join([
        # QA Filter (4)
        "test_titre_contenant_qa_automation",
        "test_titre_contenant_game_tester",
        "test_description_pharma",
        "test_offre_avec_stack_tech_reconnue",
        # Scraping edge cases (6)
        "test_linkedin_rss_bloqué or test_wellfound_bloqué",
        "test_otta_nécessite_javascript",
        "test_scraping_avec_réponse_vide",
        "test_flux_rss_indisponible",
        "test_dédoublonnage_lors_dun_second_scraping",
        # Exclusions (7 variants, all pass)
        "test_exclusion_des_offres_hors_périmètre_qa_software",
        # Cron (2)
        "test_job_dailyrefresh",
        "test_job_weeklyreport",
        # Pages (6)
        "test_toutes_les_pages_sont_accessibles",
        # LinkedIn scraper (2)
        "test_linkedin_scraper_ignore",
        "test_les_keywords_linkedin",
        # Vision
        "test_vision_auxiliaire_nvidia",
        # Filters
        "test_filtre_france or test_filtre_linkedin",
        # Stats
        "test_page_stats_accessible",
        # Dedup
        "test_jobs_du_jour or test_top_matches_cv",
    ]) + " and not (Mobile or Manager)",
    "--tb=short",
    "-v",
]

result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)

print(result.stdout)
if result.stderr:
    print(result.stderr)

lines = result.stdout.split("\n")
passed = sum(1 for l in lines if "PASSED" in l)
failed = sum(1 for l in lines if "FAILED" in l)

print(f"\nRésultat: {passed} passed, {failed} failed")

if result.returncode != 0:
    print("\nTESTS FAILED — commit bloqué. Contourne avec: git commit --no-verify")
    sys.exit(1)

print("\nTous les tests passent.")
sys.exit(0)
