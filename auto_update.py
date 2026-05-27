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


def run(cmd, timeout=30):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, 
                          cwd=PROJECT_DIR, timeout=timeout)
    if result.returncode != 0:
        print(f"⚠ {cmd[:50]}: {result.stderr[:200]}")
    return result.returncode == 0


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
    
    # 3. Git add, commit, push
    print("\n3️⃣ Pushing to GitHub...")
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
