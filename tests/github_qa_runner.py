#!/usr/bin/env python3
"""
GitHub QA Runner — exécute les suites Playwright + API contre une URL distante.
Produit un rapport détaillé par test case dans .qa_runs/ + affiche le summary.
Usage: python tests/github_qa_runner.py --url https://... --suites playwright,api
"""
import argparse, json, os, glob, sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

os.makedirs(os.path.join(BASE_DIR, ".qa_runs"), exist_ok=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://jobhunt-1-ar3w.onrender.com")
    parser.add_argument("--suites", default="playwright,api")
    args = parser.parse_args()

    from tests.test_runner import run_suite

    suites_to_run = [s.strip() for s in args.suites.split(",")]
    all_results = []
    combined_summary = {"passed": 0, "failed": 0, "total": 0}

    for suite_id in suites_to_run:
        print(f"\n▶ Exécution de la suite : {suite_id}")
        print(f"  Cible : {args.url}")
        result = run_suite(suite_id, args.url)

        if "error" in result:
            print(f"  ❌ Erreur : {result['error']}")
            continue

        s = result["summary"]
        combined_summary["passed"] += s["passed"]
        combined_summary["failed"] += s["failed"]
        combined_summary["total"] += s["total"]
        all_results.append(result)

        print(f"  Suite : {result['suite_name']} ({result['id']})")
        print(f"  Résumé : {s['passed']} ✅ / {s['failed']} ❌ / {s['total']} total — {result.get('duration',0)}s")
        for r in result.get("results", []):
            icon = "✅" if r.get("passed") else "❌"
            dur = r.get("duration", 0)
            err = f" — {r['error'][:120]}" if not r.get("passed") and r.get("error") else ""
            print(f"    {icon}  {r['id']} | {r['name']} ({dur}s){err}")

    # Save combined run result
    combined = {
        "id": f"gh_{int(datetime.now().timestamp())}",
        "source": "github_actions",
        "target_url": args.url,
        "timestamp": datetime.now().isoformat(),
        "summary": combined_summary,
        "suites": [r["suite_name"] for r in all_results],
    }
    cp = os.path.join(BASE_DIR, ".qa_runs", "github_latest.json")
    os.makedirs(os.path.dirname(cp), exist_ok=True)
    with open(cp, "w") as f:
        json.dump(combined, f, indent=2)

    print(f"\n{'='*55}")
    print(f"📊 RÉSULTATS GLOBAUX")
    print(f"{'='*55}")
    print(f"  Total : {combined_summary['total']}")
    print(f"  ✅ Passés : {combined_summary['passed']}")
    print(f"  ❌ Échoués : {combined_summary['failed']}")
    print(f"  Taux : {combined_summary['passed']/max(combined_summary['total'],1)*100:.0f}%")
    print(f"{'='*55}")

    # Exit with error if any failed
    if combined_summary["failed"] > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
