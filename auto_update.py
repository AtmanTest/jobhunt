#!/usr/bin/env python3
"""
Auto-update script for JobHunt.
Scrapes jobs → exports JSON → pushes GitHub → triggers Render deploy.
GitHub Pages + Render = double backup.
"""
import os, sys, subprocess, json, requests
from datetime import datetime

GH_TOKEN = None
RENDER_DEPLOY_HOOK = None

# Try to read tokens
token_file = os.path.expanduser("~/.hermes/jobhunt_token")
if os.path.exists(token_file):
    with open(token_file) as f:
        GH_TOKEN = f.read().strip()

render_hook_file = os.path.expanduser("~/.hermes/render_deploy_hook")
if os.path.exists(render_hook_file):
    with open(render_hook_file) as f:
        RENDER_DEPLOY_HOOK = f.read().strip()

PROJECT_DIR = os.path.expanduser("~/jobhunt")
REPO = "AtmanTest/jobhunt"


def run(cmd, timeout=120):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, 
                              cwd=PROJECT_DIR, timeout=timeout)
        if result.returncode != 0:
            print(f"⚠ {cmd[:50]}: exit {result.returncode}")
            print(f"   {result.stderr[:200]}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"⚠ {cmd[:50]}: timed out after {timeout}s")
        return False
    except Exception as e:
        print(f"⚠ {cmd[:50]}: {e}")
        return False


def trigger_render():
    """Trigger Render deploy via deploy hook URL."""
    if not RENDER_DEPLOY_HOOK:
        print("⚠ No Render deploy hook configured (set in ~/.hermes/render_deploy_hook)")
        return False
    try:
        r = requests.post(RENDER_DEPLOY_HOOK, timeout=30)
        print(f"   Render deploy trigger: HTTP {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"⚠ Render trigger failed: {e}")
        return False


def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("=" * 50)
    print(f"JobHunt Auto-Update — {now}")
    print("=" * 50)
    
    # 0. Google Jobs (Chrome) — source principale, scan tout
    print("\n0️⃣ Google Jobs (Chrome)...")
    run('python3 -c "from google_jobs_scraper import scrape_google_all; from scraper import save_jobs; j=scrape_google_all(); n=save_jobs(j); print(f\'✅ {n} nouveaux de Google Jobs\')"', timeout=180)
    
    # 1. Scrape (sources directes: WTTJ, WWR, etc.)
    print("\n1️⃣ Scraping sources directes...")
    run("python3 scraper.py")
    
    # 2. Export static JSON + write timestamp
    print("\n2️⃣ Exporting static JSON...")
    run('python3 -c "from scraper import export_static_json; export_static_json()"')
    # Write timestamp for the dashboard
    with open(os.path.join(PROJECT_DIR, "docs", "last_update.txt"), "w") as f:
        f.write(now)
    
    # 3. Enrich (soft fail)
    print("\n3️⃣ Enriching jobs with AI...")
    run('python3 auto_enrich.py --limit 5', timeout=60)
    
    # 4. Git push → GitHub Pages
    print("\n4️⃣ Pushing to GitHub (Pages + Render trigger)...")
    run("git add -A")
    
    result = subprocess.run("git status --porcelain", shell=True, 
                          capture_output=True, text=True, cwd=PROJECT_DIR)
    if result.stdout.strip():
        run('git commit -m "auto-update: jobs refresh"')
        if GH_TOKEN:
            run(f"git push https://{GH_TOKEN}@github.com/{REPO}.git main")
        else:
            run("git push")
        print("\n✅ GitHub Pages updated!")
    else:
        print("\n✅ No changes to commit")
    
    # 5. Trigger Render deploy
    print("\n5️⃣ Triggering Render deploy...")
    trigger_render()
    
    print(f"\n📊 GitHub Pages: https://atmantest.github.io/jobhunt/")
    print(f"🌐 Render:       https://jobhunt-1-ar3w.onrender.com")


if __name__ == "__main__":
    main()
