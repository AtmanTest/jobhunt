#!/usr/bin/env python3
"""
Auto-update script for JobHunt GitHub Pages.
Run this to scrape, export, commit and push in one command.
"""
import os, sys, subprocess, json, requests

GH_TOKEN = None

# Try to read token from a safe source
token_file = os.path.expanduser("~/.hermes/jobhunt_token")
if os.path.exists(token_file):
    with open(token_file) as f:
        GH_TOKEN = f.read().strip()

PROJECT_DIR = os.path.expanduser("~/Desktop/jobhunt")
REPO = "AtmanTest/jobhunt"


def run(cmd, timeout=60):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, 
                              cwd=PROJECT_DIR, timeout=timeout)
        if result.returncode != 0:
            print(f"⚠ {cmd[:50]}: exit {result.returncode}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"⚠ {cmd[:50]}: timed out after {timeout}s")
        return False
    except Exception as e:
        print(f"⚠ {cmd[:50]}: {e}")
        return False


def main():
    print("=" * 50)
    print("JobHunt Auto-Update")
    print("=" * 50)
    
    # 1. Scrape
    print("\n1️⃣ Scraping jobs...")
    run("python3 scraper.py")
    
    # 2. Export static JSON
    print("\n2️⃣ Exporting static JSON...")
    run('python3 -c "from scraper import export_static_json; export_static_json()"')
    
    # 3. Enrich jobs with AI (extract salary, tech stack, etc.) — skip if slow
    print("\n3️⃣ Enriching jobs with AI...")
    run('python3 auto_enrich.py --limit 5', timeout=60)
    # Note: if enrichment times out, the site still works — data just won't be enriched
    
    # 4. Git add, commit, push
    print("\n4️⃣ Pushing to GitHub...")
    run("git add -A")
    
    # Check if there's anything to commit
    result = subprocess.run("git status --porcelain", shell=True, 
                          capture_output=True, text=True, cwd=PROJECT_DIR)
    if result.stdout.strip():
        run('git commit -m "auto-update: jobs refresh"')
        if GH_TOKEN:
            run(f"git push https://{GH_TOKEN}@github.com/{REPO}.git main")
        else:
            run("git push")
        print("\n✅ Pushed to GitHub!")
    else:
        print("\n✅ No changes to push")
    
    print(f"\n📊 Site: https://{REPO.split('/')[0].lower()}.github.io/{REPO.split('/')[1].lower()}/")


if __name__ == "__main__":
    main()
