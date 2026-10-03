#!/usr/bin/env python3
"""
Auto-update script for JobHunt GitHub Pages.
Run this to scrape, export, commit and push in one command.

Push auth: relies on the repo remote + git credential helper (osxkeychain / gh).
NEVER hardcode a token in the remote URL — expired tokens make push fail silently.
"""
import os, sys, subprocess, json

PROJECT_DIR = os.path.expanduser("~/jobhunt")
REPO = os.environ.get("JOBHUNT_REPO", "AtmanTest/jobhunt")
DEPLOY_BRANCH = "main"  # branch GitHub Pages actually serves


def run(cmd, timeout=60):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              cwd=PROJECT_DIR, timeout=timeout)
        if result.returncode != 0:
            print(f"⚠ {cmd[:50]}: exit {result.returncode}")
            if result.stderr.strip():
                print("   " + result.stderr.strip().splitlines()[-1][:200])
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"⚠ {cmd[:50]}: timed out after {timeout}s")
        return False
    except Exception as e:
        print(f"⚠ {cmd[:50]}: {e}")
        return False


def branch():
    r = subprocess.run("git branch --show-current", shell=True, capture_output=True,
                       text=True, cwd=PROJECT_DIR)
    return r.stdout.strip()


def main():
    print("=" * 50)
    print("JobHunt Auto-Update")
    print("=" * 50)

    # 1. Scrape
    print("\n1️⃣ Scraping jobs...")
    run("python3 scraper.py", timeout=300)

    # 2. Export static JSON
    print("\n2️⃣ Exporting static JSON...")
    run('python3 -c "from scraper import export_static_json; export_static_json()"', timeout=180)

    # 3. Enrich jobs with AI (extract salary, tech stack, etc.) — skip if slow
    print("\n3️⃣ Enriching jobs with AI...")
    run('python3 auto_enrich.py --limit 5', timeout=60)
    # Note: if enrichment times out, the site still works — data just won't be enriched

    # 4. Git add, commit, push
    print("\n4️⃣ Pushing to GitHub...")
    run("git add -A")

    result = subprocess.run("git status --porcelain", shell=True,
                          capture_output=True, text=True, cwd=PROJECT_DIR)
    if not result.stdout.strip():
        print("\n✅ No changes to push")
    else:
        run('git commit -m "auto-update: jobs refresh"')
        if not run("git push origin HEAD", timeout=600):
            print("\n❌ PUSH FAILED — no update reached GitHub")
            print(f"   remote: {subprocess.run('git remote get-url origin', shell=True, capture_output=True, text=True, cwd=PROJECT_DIR).stdout.strip()}")
            return 1
        print("\n✅ Pushed to GitHub!")

    cur = branch()
    if cur != DEPLOY_BRANCH:
        print(f"\n⚠ Pushed branch '{cur}' — GitHub Pages serves '{DEPLOY_BRANCH}'.")
        print(f"  Live site is NOT refreshed until {cur} → {DEPLOY_BRANCH} is merged/pushed.")

    print(f"\n📊 Site: https://{REPO.split('/')[0].lower()}.github.io/{REPO.split('/')[1].lower()}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
