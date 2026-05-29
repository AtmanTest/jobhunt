#!/usr/bin/env python3
"""
JobHunt Dashboard - Application Flask pour la chasse d'emploi automatisée.
Lance avec: python3 app.py
Ouvre: http://localhost:5050
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import sqlite3
import json
import os
import subprocess
import threading
import requests
from datetime import datetime

# Import scraper
import sys
sys.path.insert(0, os.path.dirname(__file__))
from scraper import init_db, fetch_all, fetch_all_new_sources, save_jobs, get_jobs, mark_applied, get_stats, export_static_json, get_db as scraper_db, compute_freshness_score
from version import get_version, get_git_commit, get_git_tag, is_dirty, DB_SCHEMA_VERSION
from matcher import match_job_to_cv, analyze_tjm, detect_duplicates, analyze_skills_gap, source_stats as src_stats
from cv_data import CV

# ─── QA Module ───────────────────────────────────────────────────
QA_RUNS_DIR = os.path.join(os.path.dirname(__file__), ".qa_runs")
os.makedirs(QA_RUNS_DIR, exist_ok=True)

GITHUB_TOKEN = None
token_paths = [
    os.path.expanduser("~/.hermes/jobhunt_token"),
    os.path.expanduser("~/.hermes/gh_token"),
]
for tp in token_paths:
    if os.path.exists(tp):
        with open(tp) as f:
            GITHUB_TOKEN = f.read().strip()
        break

FEATURES_DIR = os.path.join(os.path.dirname(__file__), "tests", "features")


def parse_feature_files():
    """Parse all .feature files and return structured data."""
    categories = []
    if not os.path.isdir(FEATURES_DIR):
        return {"categories": []}

    for root, dirs, files in os.walk(FEATURES_DIR):
        for fname in sorted(files):
            if not fname.endswith(".feature"):
                continue
            fpath = os.path.join(root, fname)
            rel_dir = os.path.relpath(root, FEATURES_DIR)
            category_name = rel_dir if rel_dir != "." else "root"

            with open(fpath, encoding="utf-8") as f:
                content = f.read()

            scenarios = []
            lines = content.split("\n")
            current_scenario = None
            current_tags = []

            for line in lines:
                stripped = line.strip()
                if stripped.startswith("@"):
                    current_tags = [t.strip() for t in stripped.split("@") if t.strip()]
                elif stripped.startswith("Scenario"):
                    if current_scenario:
                        scenarios.append(current_scenario)
                    current_scenario = {"name": stripped, "tags": list(current_tags)}
                elif stripped.startswith(("Given ", "When ", "Then ", "And ")) and current_scenario:
                    if "steps" not in current_scenario:
                        current_scenario["steps"] = []
                    current_scenario["steps"].append(stripped)

            if current_scenario:
                scenarios.append(current_scenario)

            categories.append({
                "category": category_name + "/" + fname.replace(".feature", ""),
                "file": fname,
                "path": fpath,
                "scenarios": scenarios,
            })

    return {"categories": categories}


def run_pytest_async():
    """Run pytest in a thread, save output to a timestamped file."""
    import uuid
    run_id = str(uuid.uuid4())[:8]
    out_path = os.path.join(QA_RUNS_DIR, f"{run_id}.json")

    def _run():
        import subprocess, json, time
        start = time.time()
        try:
            proc = subprocess.run(
                ["python3", "-m", "pytest", "tests/", "-v", "--tb=short", "--no-header"],
                capture_output=True, text=True, timeout=120,
                cwd=os.path.dirname(__file__),
            )
            output = proc.stdout + proc.stderr
            elapsed = time.time() - start

            # Parse summary line
            passed = failed = skipped = total = 0
            for line in output.split("\n"):
                if "passed" in line and "failed" in line:
                    import re
                    m = re.search(r'([\d]+)\s+failed', line)
                    if m: failed = int(m.group(1))
                    m = re.search(r'([\d]+)\s+passed', line)
                    if m: passed = int(m.group(1))
                    m = re.search(r'([\d]+)\s+skipped', line)
                    if m: skipped = int(m.group(1))
                    total = passed + failed + skipped
                    break

            result = {
                "run_id": run_id,
                "status": "completed" if proc.returncode == 0 else "failed",
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "total": total,
                "output": output,
                "duration": round(elapsed, 2),
                "timestamp": datetime.now().isoformat(),
            }
        except subprocess.TimeoutExpired:
            result = {
                "run_id": run_id,
                "status": "failed",
                "passed": 0, "failed": 0, "skipped": 0, "total": 0,
                "output": "TIMEOUT: pytest exceeded 120s",
                "duration": 120,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            result = {
                "run_id": run_id,
                "status": "failed",
                "passed": 0, "failed": 0, "skipped": 0, "total": 0,
                "output": str(e),
                "duration": 0,
                "timestamp": datetime.now().isoformat(),
            }

        with open(out_path, "w") as f:
            json.dump(result, f)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return run_id


def get_qa_runs(limit=10):
    """Get recent test runs from stored JSON files."""
    runs = []
    if not os.path.isdir(QA_RUNS_DIR):
        return runs
    for fname in sorted(os.listdir(QA_RUNS_DIR), reverse=True)[:limit]:
        if fname.endswith(".json"):
            with open(os.path.join(QA_RUNS_DIR, fname)) as f:
                runs.append(json.load(f))
    return runs


app = Flask(__name__)
app.secret_key = "jobhunt-secret-2026"

DB_PATH = os.path.join(os.path.dirname(__file__), "jobs.db")
GITHUB_JOBS_URL = "https://raw.githubusercontent.com/AtmanTest/jobhunt/main/docs/jobs.json"
ON_RENDER = os.environ.get("RENDER", False) or not os.path.exists(DB_PATH)


def _populate_from_github():
    """Fetch jobs from GitHub raw JSON and populate local SQLite."""
    try:
        resp = requests.get(GITHUB_JOBS_URL, timeout=30)
        if resp.status_code != 200:
            print(f"[Render] GitHub fetch failed: HTTP {resp.status_code}")
            return
        data = resp.json()
        jobs = data.get("jobs", [])
        conn = sqlite3.connect(DB_PATH)
        for job in jobs:
            conn.execute("""INSERT OR IGNORE INTO jobs
                (title, company, source, url, location, salary, tags,
                 description, date, raw_date, is_qa, freelance_status, freelance_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (job.get("title",""), job.get("company",""), job.get("source",""),
                 job.get("url",""), job.get("location",""), job.get("salary",""),
                 job.get("tags",""), "", job.get("date",""), job.get("raw_date",0),
                 job.get("is_qa",1), job.get("freelance_status","VALIDÉE"),
                 job.get("freelance_score",30)))
        conn.commit()
        conn.close()
        print(f"[Render] Loaded {len(jobs)} jobs from GitHub")
    except Exception as e:
        print(f"[Render] Error populating DB: {e}")


# Initialize DB on import (needed for gunicorn on Render)
init_db()


DB_POPULATED = False


def _ensure_db_populated():
    """Lazy populate DB from GitHub on first request if on Render."""
    global DB_POPULATED
    if DB_POPULATED:
        return
    if not (os.environ.get("RENDER") or not os.path.exists(DB_PATH)):
        DB_POPULATED = True
        return
    # Check if DB has data
    try:
        conn = sqlite3.connect(DB_PATH)
        cnt = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        conn.close()
        if cnt > 0:
            DB_POPULATED = True
            return
    except:
        pass
    _populate_from_github()
    DB_POPULATED = True


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn




# Auto-scrape LinkedIn pays au démarrage
def _startup_scrape():
    import time
    time.sleep(5)
    try:
        print("[Startup] Scraping LinkedIn pays...")
        from scraper import fetch_linkedin_countries, save_jobs
        jobs = fetch_linkedin_countries()
        if jobs:
            n = save_jobs(jobs)
            print(f"[Startup] {n} nouveaux jobs LinkedIn ajoutés")
        else:
            print("[Startup] Aucun nouveau job LinkedIn")
    except Exception as e:
        print(f"[Startup] Erreur scrape: {e}")

threading.Thread(target=_startup_scrape, daemon=True).start()


# ============================
# ROUTES
# ============================

# ─── Country-based job filtering ──────────────────────────────
COUNTRY_KEYWORDS = {
    'france': ['France', 'Paris', 'Lyon', 'Toulouse', 'Nantes', 'Lille', 'Marseille', 'Bordeaux',
               'Grenoble', 'Rennes', 'Strasbourg', 'Montpellier', 'Nice', 'Aix-en-Provence',
               'Sophia Antipolis', 'Lille', 'Toulon', 'Le Mans', 'Brest', 'Metz', 'Nancy', 'Île-de-France'],
    'suisse': ['Suisse', 'Switzerland', 'Genève', 'Geneva', 'Zürich', 'Zurich', 'Lausanne',
               'Bern', 'Berne', 'Basel', 'Bâle', 'Lugano', 'Swiss'],
    'luxembourg': ['Luxembourg', 'Luxemburg'],
    'dubai': ['Dubai', 'Dubaï', 'UAE', 'Émirats', 'Emirates', 'Abu Dhabi', 'Qatar', 'Doha',
              'Middle East', 'Moyen-Orient', 'Riyad', 'Dubaï'],
    'singapour': ['Singapore', 'Singapour', 'SG'],
}

COUNTRY_DATA = {
    'france': {
        'name': 'France', 'flag': '🇫🇷',
        'tjm': '550 - 700 €/jour',
        'tip': 'Paris plus cher, missions longues 6-18 mois',
        'tips': 'Mets à jour ton profil Malt avec "Playwright", "Xray/JIRA", "API testing". TJM entrée 550€/j, monte à 650€ après 2 missions.',
        'platforms': [
            {'name': 'Malt.fr', 'url': 'https://malt.fr', 'desc': '80% des missions QA. Incontournable.', 'tag': 'local'},
            {'name': 'Free-Work', 'url': 'https://free-work.com', 'desc': 'SSII, banques, assurances. Beaucoup d\'annonces.', 'tag': 'local'},
            {'name': 'Comet', 'url': 'https://comet.co', 'desc': 'Freelance IT haut de gamme, missions QA.', 'tag': 'local'},
            {'name': 'Freelance.com', 'url': 'https://freelance.com', 'desc': 'Grosse plateforme généraliste, filtrer QA.', 'tag': 'local'},
            {'name': 'Crème de la Crème', 'url': 'https://cremedelacreme.io', 'desc': 'Talents tech, missions IT sélectionnées.', 'tag': 'local'},
            {'name': 'Freelance Republik', 'url': 'https://freelancerepublik.com', 'desc': 'Plateforme freelance IT française.', 'tag': 'local'},
            {'name': 'Codeur.com', 'url': 'https://codeur.com', 'desc': 'Projets freelance IT, missions QA possibles.', 'tag': 'local'},
            {'name': 'ComeUp', 'url': 'https://comeup.com', 'desc': 'Prestations IT, missions courtes.', 'tag': 'local'},
            {'name': '404Works', 'url': 'https://404works.com', 'desc': 'Freelance IT français, missions tech.', 'tag': 'local'},
            {'name': 'Collective.work', 'url': 'https://collective.work', 'desc': 'Freelance en équipe, projets IT.', 'tag': 'local'},
            {'name': 'LesBonsFreelances', 'url': 'https://lesbonsfreelances.com', 'desc': 'Mise en relation freelance IT.', 'tag': 'local'},
            {'name': 'Jean-Michel.io', 'url': 'https://jean-michel.io', 'desc': 'Freelance IT, missions QA et test.', 'tag': 'local'},
            {'name': 'Fiverr', 'url': 'https://fiverr.com', 'desc': 'Prestations QA à l\'international.', 'tag': 'intl'},
            {'name': 'Upwork', 'url': 'https://upwork.com', 'desc': 'Plus gros marché freelance mondial, filtrer QA.', 'tag': 'intl'},
            {'name': 'Freelance-info', 'url': 'https://freelance-informatique.fr', 'desc': 'Missions en régions et niches.', 'tag': 'local'},
            {'name': 'InFreelancing', 'url': 'https://infreelancing.com', 'desc': 'Missions longues, pas mal de QA.', 'tag': 'local'},
            {'name': 'LinkedIn France', 'url': 'https://linkedin.com', 'desc': 'Recruteurs actifs, active #OpenToWork.', 'tag': 'intl'},
        ]
    },
    'suisse': {
        'name': 'Suisse', 'flag': '🇨🇭',
        'tjm': '110 - 160 CHF/h',
        'tip': 'Genève banque/pharma, Zurich fintech',
        'tips': 'Spécialise-toi "QA Lead Banque" ou "Test Manager Pharma". ISTQB Advanced quasi obligatoire. Vise Genève en frontalier d\'abord.',
        'platforms': [
            {'name': 'Jem.ch', 'url': 'https://jem.ch', 'desc': 'LA plateforme suisse du contracting IT.', 'tag': 'local'},
            {'name': 'SwissDevJobs', 'url': 'https://swissdevjobs.ch', 'desc': 'Annonces bien rémunérées, test automation.', 'tag': 'local'},
            {'name': 'JobUp.ch', 'url': 'https://jobup.ch', 'desc': 'Portail généraliste, filtrer "Test/QA".', 'tag': 'local'},
            {'name': 'Hays Switzerland', 'url': 'https://hays.ch', 'desc': 'Plus gros acteur contracting QA Suisse.', 'tag': 'intl'},
            {'name': 'Robert Half CH', 'url': 'https://robert-half.ch', 'desc': 'Très présent missions QA.', 'tag': 'intl'},
        ]
    },
    'luxembourg': {
        'name': 'Luxembourg', 'flag': '🇱🇺',
        'tjm': '550 - 750 €/jour',
        'tip': 'Banque/finance, institutions UE',
        'tips': 'Petit marché, 80% passe par les régies (Hays, NSI, SFE). Spécialisation SAP testing ou core banking = TJM max.',
        'platforms': [
            {'name': 'Hays Luxembourg', 'url': 'https://hays.lu', 'desc': 'Leader du contracting QA Lux.', 'tag': 'local'},
            {'name': 'NSI Luxembourg', 'url': 'https://nsi.lu', 'desc': 'Régie majeure, missions longues durée.', 'tag': 'local'},
            {'name': 'Moovijob', 'url': 'https://moovijob.com', 'desc': 'Portail emploi luxembourgeois, filtrer IT.', 'tag': 'local'},
            {'name': 'LinkedIn Lux', 'url': 'https://linkedin.com', 'desc': 'Activer Luxembourg comme localisation.', 'tag': 'intl'},
        ]
    },
    'dubai': {
        'name': 'Dubaï / EAU', 'flag': '🇦🇪',
        'tjm': '600 - 900 $/jour',
        'tip': 'Fintech, consulting, missions 3-12 mois',
        'tips': 'Le marché QA freelance à Dubaï est petit mais très bien payé. Passe par des boîtes de consulting internationales (Capgemini, Accenture) ou des plateformes spécialisées.',
        'platforms': [
            {'name': 'Testvox', 'url': 'https://testvox.com', 'desc': 'Plateforme QA freelance internationale, présente Dubaï.', 'tag': 'local'},
            {'name': 'Truelancer', 'url': 'https://truelancer.ae', 'desc': 'Freelance généraliste, section QA active.', 'tag': 'local'},
            {'name': 'Dubai Freelance', 'url': 'https://dubaifreelance.ae', 'desc': 'Portail freelance EAU.', 'tag': 'local'},
            {'name': 'Toptal', 'url': 'https://toptal.com', 'desc': 'Réseau freelance premium, QA bien présent.', 'tag': 'intl'},
        ]
    },
    'singapour': {
        'name': 'Singapour', 'flag': '🇸🇬',
        'tjm': '80 - 150 SGD/h',
        'tip': 'Fintech asiatique, hub régional',
        'tips': 'Marché exigeant, profils automation + ISTQB Advanced. Les missions sont souvent via agences de recrutement (Hays SG, Robert Walters) plutôt que plateformes.',
        'platforms': [
            {'name': 'NodeFlair', 'url': 'https://nodeflair.com', 'desc': 'Plateforme tech SG, filtres QA/disponible.', 'tag': 'local'},
            {'name': 'Hays Singapore', 'url': 'https://hays.com.sg', 'desc': 'Recrutement contracting QA.', 'tag': 'local'},
            {'name': 'Robert Walters SG', 'url': 'https://robertwalters.com.sg', 'desc': 'Agence majeure, missions QA.', 'tag': 'local'},
            {'name': 'LinkedIn SG', 'url': 'https://linkedin.com', 'desc': 'Activer Singapore comme localisation.', 'tag': 'intl'},
        ]
    },
}


def filter_jobs_by_country(country_id):
    """Filter jobs by country keywords + freelance/contract only."""
    conn = get_db()
    keywords = COUNTRY_KEYWORDS.get(country_id, [])
    if not keywords:
        return []

    # Build location filter
    placeholders = ' OR '.join(['location LIKE ?'] * len(keywords))
    params = [f'%{k}%' for k in keywords]

    query = f"""
        SELECT * FROM jobs 
        WHERE id IN (
            SELECT MAX(id)
            FROM jobs 
            WHERE ({placeholders})
            AND (freelance_status IS NULL OR freelance_status IN ('VALIDÉE', 'AMBIGUË'))
            GROUP BY LOWER(TRIM(title)), LOWER(TRIM(company))
        )
        ORDER BY 
            viewed ASC,
            CASE freelance_status WHEN 'VALIDÉE' THEN 0 ELSE 1 END,
            raw_date DESC, date DESC LIMIT 100
    """
    cursor = conn.execute(query, params)
    jobs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jobs


@app.route("/debug")
def debug_info():
    """Debug endpoint to check app state."""
    lines = []
    lines.append(f"Python: {sys.version}")
    lines.append(f"DB exists: {os.path.exists(DB_PATH)}")
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            cnt = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            cols = conn.execute("PRAGMA table_info(jobs)").fetchall()
            lines.append(f"Jobs count: {cnt}")
            lines.append(f"Columns: {len(cols)}")
            conn.close()
        except Exception as e:
            lines.append(f"DB error: {e}")
    lines.append(f"ON_RENDER: {os.environ.get('RENDER', 'not set')}")
    lines.append(f"CWD: {os.getcwd()}")
    lines.append(f"Files: {os.listdir('.')[:20]}")
    import traceback
    try:
        _ensure_db_populated()
        conn = get_db()
        cnt = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        lines.append(f"After populate: {cnt} jobs")
        conn.close()
    except Exception as e:
        lines.append(f"Populate error: {e}")
        lines.append(traceback.format_exc())
    return "<pre>" + "\n".join(lines) + "</pre>"


@app.route("/")
def index():
    _ensure_db_populated()
    stats = get_stats()

    # Build country data with jobs
    countries = {}
    country_counts = []
    total_filtered = 0

    for cid, cdata in COUNTRY_DATA.items():
        jobs = filter_jobs_by_country(cid)
        # Enrichir avec score + TJM + fraîcheur
        for j in jobs:
            score, matched = match_job_to_cv(j)
            j['match_score'] = score
            j['matched_skills'] = matched[:5]
            j['tjm_analysis'] = analyze_tjm(j)
            j['freshness_score'] = compute_freshness_score(j.get('date'))
        cdata['jobs'] = jobs
        countries[cid] = cdata
        cnt = len(jobs)
        country_counts.append({'key': cid, 'count': cnt})
        total_filtered += cnt

    # 'tous' = all unique jobs from all countries (deduplicate by id)
    all_jobs = []
    seen_ids = set()
    for cid, cdata in countries.items():
        for job in cdata['jobs']:
            if job['id'] not in seen_ids:
                seen_ids.add(job['id'])
                all_jobs.append(job)
    country_counts.append({'key': 'tous', 'count': len(all_jobs)})

    # Top matches (top 10 tous pays)
    top_matches = sorted(all_jobs, key=lambda j: -j.get('match_score', 0))[:10]

    # Jobs du Jour : les 3 plus récents (frais A en priorité)
    fresh_jobs = [j for j in all_jobs if j.get('freshness_score') in ('A', 'B') and j.get('match_score', 0) >= 10]
    jobs_of_day = []
    if fresh_jobs:
        jobs_of_day = sorted(fresh_jobs, key=lambda j: (-j.get('match_score', 0), -(j.get('freelance_score') or 0)))[:3]

    # Stats sources
    s_stats = src_stats(all_jobs)
    
    # Skills gap
    skills = analyze_skills_gap(all_jobs)

    # Last update timestamp
    last_update = "—"
    ts_path = os.path.join(os.path.dirname(__file__), "docs", "last_update.txt")
    if os.path.exists(ts_path):
        try:
            with open(ts_path) as f:
                last_update = f.read().strip()
        except:
            pass

    return render_template("dashboard.html",
        stats=stats,
        countries=countries,
        country_counts=country_counts,
        tous_jobs=all_jobs,
        top_matches=top_matches,
        job_of_day=jobs_of_day[0] if jobs_of_day else None,
        jobs_of_day=jobs_of_day,
        source_stats=s_stats,
        skills_gap=skills,
        version=get_version(),
        last_update=last_update)


@app.route("/refresh")
def refresh():
    """Manual refresh of job listings."""
    def do_scrape():
        jobs = fetch_all()
        n = save_jobs(jobs)
        print(f"✓ Scrape done: {n} new jobs")
    
    thread = threading.Thread(target=do_scrape, daemon=True)
    thread.start()
    return redirect(url_for("index"))


@app.route("/api/refresh", methods=["GET", "POST"])
def api_refresh():
    """API endpoint to trigger refresh."""
    def do_scrape():
        jobs = fetch_all()
        n = save_jobs(jobs)
        print(f"✓ Scrape done: {n} new jobs")
    
    thread = threading.Thread(target=do_scrape, daemon=True)
    thread.start()
    return jsonify({"status": "started"})


@app.route("/api/job/<int:job_id>/click")
def api_job_click(job_id):
    """Mark a job as viewed/clicked."""
    conn = scraper_db()
    conn.execute("UPDATE jobs SET viewed = 1 WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


@app.route("/api/job/<int:job_id>/stage", methods=["POST"])
def api_job_stage(job_id):
    """Mettre à jour le stage pipeline."""
    data = request.get_json() or {}
    stage = data.get("stage", "saved")
    conn = get_db()
    conn.execute("UPDATE jobs SET pipeline_stage = ? WHERE id = ?", (stage, job_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


@app.route("/cover-letter/<int:job_id>")
def cover_letter(job_id):
    """Générer une cover letter personnalisée."""
    conn = get_db()
    job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    if not job:
        return "Job non trouvé", 404
    job = dict(job)
    score, matched_skills = match_job_to_cv(job)
    
    # Générer la lettre
    company = job.get("company", "l'entreprise")
    title = job.get("title", "le poste")
    cl = f"""Bonjour,

Je vous adresse ma candidature pour le poste de {title} au sein de {company}.

Fort de 12+ années d'expérience en tant que consultant QA senior, j'accompagne les DSI et équipes produit dans la mise en place de stratégies de test robustes, la gestion des campagnes de recette et l'automatisation des processus de validation.

Mon parcours chez BRED Bank (conformité réglementaire bancaire), Accor Hotels (QA Lead mobile 100+ pays) et Oodrive (cloud B2B souverain) m'a permis de développer une expertise transverse : test automation, API testing, DevOps et management de la qualité.

Compétences clés : {", ".join(matched_skills[:8]) if matched_skills else "QA, test automation, gestion de campagne, ISTQB, Agile/Scrum"}.

En tant que freelance en SASU, je suis disponible rapidement pour des missions en régie ou au forfait, en full remote ou hybride.

Dans l'attente de pouvoir échanger sur cette opportunité, je reste à votre disposition pour un entretien.

Cordialement,
Jahangir
Senior QA Consultant - SASU"""

    return render_template("cover_letter.html",
        job=job, cover_letter=cl, score=score,
        matched_skills=matched_skills[:8],
        version=get_version())


@app.route("/stats")
def stats_page():
    """Page des statistiques : sources, skills gap, top matches."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM jobs WHERE freelance_status IN ('VALIDÉE', 'AMBIGUË') ORDER BY raw_date DESC").fetchall()
    conn.close()
    all_jobs = [dict(r) for r in rows]
    
    # Enrichir avec score
    for j in all_jobs:
        score, matched = match_job_to_cv(j)
        j['match_score'] = score
        j['matched_skills'] = matched[:5]
        j['tjm_analysis'] = analyze_tjm(j)
    
    s_stats = src_stats(all_jobs)
    skills = analyze_skills_gap(all_jobs)
    top_matches = sorted(all_jobs, key=lambda j: -j.get('match_score', 0))[:20]
    dup_groups = detect_duplicates(all_jobs)
    
    return render_template("stats.html",
        source_stats=s_stats,
        skills_gap=skills,
        top_matches=top_matches,
        duplicate_count=len(dup_groups),
        total_jobs=len(all_jobs),
        version=get_version())
def api_jobs():
    filters = {}
    if request.args.get("qa"):
        filters["qa_only"] = request.args.get("qa") == "1"
    if request.args.get("unapplied"):
        filters["not_applied"] = request.args.get("unapplied") == "1"
    if request.args.get("search"):
        filters["search"] = request.args.get("search")
    if request.args.get("source"):
        filters["source"] = request.args.get("source")
    
    jobs = get_jobs(filters)
    return jsonify(jobs)


@app.route("/api/stats")
def api_stats():
    return jsonify(get_stats())


@app.route("/api/stats/advanced")
def api_stats_advanced():
    """Return advanced aggregated stats for analytics."""
    conn = get_db()
    stats = {}
    
    # Count by seniority
    cur = conn.execute("SELECT seniority, COUNT(*) as cnt FROM jobs WHERE seniority IS NOT NULL GROUP BY seniority ORDER BY cnt DESC")
    stats["by_seniority"] = [dict(r) for r in cur.fetchall()]
    
    # Count by contract_type
    cur = conn.execute("SELECT contract_type, COUNT(*) as cnt FROM jobs WHERE contract_type IS NOT NULL GROUP BY contract_type ORDER BY cnt DESC")
    stats["by_contract_type"] = [dict(r) for r in cur.fetchall()]
    
    # Top tech stacks
    cur = conn.execute("SELECT tech_stack FROM jobs WHERE tech_stack IS NOT NULL AND tech_stack != ''")
    all_stacks = []
    for row in cur.fetchall():
        try:
            stacks = json.loads(row[0]) if row[0].startswith("[") else [row[0]]
            all_stacks.extend(s.strip() for s in stacks if s.strip())
        except (json.JSONDecodeError, AttributeError):
            if row[0]:
                all_stacks.extend(s.strip() for s in row[0].split(",") if s.strip())
    stack_counts = {}
    for s in all_stacks:
        stack_counts[s] = stack_counts.get(s, 0) + 1
    stats["top_tech_stacks"] = sorted(stack_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    
    # Salary stats
    cur = conn.execute("SELECT salary_min, salary_max FROM jobs WHERE salary_min IS NOT NULL OR salary_max IS NOT NULL")
    salaries = [dict(r) for r in cur.fetchall()]
    mins = [s["salary_min"] for s in salaries if s["salary_min"]]
    maxs = [s["salary_max"] for s in salaries if s["salary_max"]]
    all_sals = mins + maxs
    if all_sals:
        stats["salary_avg"] = sum(all_sals) / len(all_sals)
        sorted_sals = sorted(all_sals)
        n = len(sorted_sals)
        stats["salary_median"] = sorted_sals[n // 2] if n % 2 else (sorted_sals[n // 2 - 1] + sorted_sals[n // 2]) / 2
        stats["salary_min_val"] = min(all_sals)
        stats["salary_max_val"] = max(all_sals)
    else:
        stats.update({"salary_avg": 0, "salary_median": 0, "salary_min_val": 0, "salary_max_val": 0})
    
    # Jobs per day last 30 days
    cur = conn.execute("""
        SELECT date, COUNT(*) as cnt FROM jobs 
        WHERE date >= date('now', '-30 days') 
        GROUP BY date ORDER BY date
    """)
    stats["jobs_per_day"] = [dict(r) for r in cur.fetchall()]
    
    # Top locations/countries
    cur = conn.execute("""
        SELECT location, COUNT(*) as cnt FROM jobs 
        WHERE location IS NOT NULL AND location != '' 
        GROUP BY location ORDER BY cnt DESC LIMIT 20
    """)
    stats["top_locations"] = [dict(r) for r in cur.fetchall()]
    
    conn.close()
    return jsonify(stats)


@app.route("/api/deepseek/balance")
def api_deepseek_balance():
    """Live DeepSeek balance depuis l'API officielle."""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        env_file = os.path.expanduser("~/.hermes/.env")
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    if line.startswith("DEEPSEEK_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip("\"'")
                        break
    if not api_key:
        return jsonify({"error": "No API key", "balance": 0, "currency": "USD", "live": False}), 200

    try:
        resp = requests.get(
            "https://api.deepseek.com/user/balance",
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            for b in data.get("balance_infos", []):
                return jsonify({
                    "balance": float(b.get("total_balance", 0)),
                    "topped_up": float(b.get("topped_up_balance", 0)),
                    "currency": b.get("currency", "USD"),
                    "live": True
                })
        return jsonify({"error": f"API error {resp.status_code}", "balance": 0, "live": False}), 200
    except Exception as e:
        return jsonify({"balance": 0, "error": str(e), "live": False}), 200


LINKEDIN_JOBS_FILE = os.path.join(os.path.dirname(__file__), "linkedin_jobs.json")


@app.route("/api/linkedin/jobs")
def api_linkedin_jobs():
    """Return LinkedIn-scraped QA jobs."""
    if os.path.exists(LINKEDIN_JOBS_FILE):
        with open(LINKEDIN_JOBS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    return jsonify({"jobs": [], "qa_jobs": [], "count": 0})


@app.route("/api/linkedin/refresh", methods=["POST"])
def api_linkedin_refresh():
    """Trigger LinkedIn resrape via subprocess."""
    try:
        scraper = os.path.join(os.path.dirname(__file__), "linkedin_scraper.py")
        thread = threading.Thread(target=lambda: subprocess.run(
            ["python3", scraper], capture_output=True, timeout=120), daemon=True)
        thread.start()
        return jsonify({"status": "started"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs/saved")
def api_saved_jobs():
    """Get saved (bookmarked) jobs."""
    jobs = get_jobs({"saved": True})
    return jsonify(jobs)


@app.route("/api/jobs/applied")
def api_applied_jobs():
    """Get applied jobs with pipeline status."""
    conn = get_db()
    cursor = conn.execute("""
        SELECT j.*, a.status as pipeline_status, a.applied_at as applied_date,
               a.notes as app_notes, a.job_title, a.company as app_company
        FROM jobs j
        LEFT JOIN applications a ON j.id = a.job_id
        WHERE j.applied = 1
        ORDER BY a.applied_at DESC
    """)
    jobs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(jobs)


@app.route("/api/jobs/<int:job_id>/save", methods=["POST"])
def api_toggle_save(job_id):
    """Toggle saved status for a job."""
    conn = get_db()
    cursor = conn.execute("SELECT saved FROM jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Job not found"}), 404
    new_val = 0 if row["saved"] else 1
    conn.execute("UPDATE jobs SET saved = ? WHERE id = ?", (new_val, job_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "saved": bool(new_val)})


@app.route("/api/jobs/<int:job_id>/apply", methods=["POST"])
def api_mark_applied_v2(job_id):
    """Mark job as applied with status (à_poster/postulé/entretien/offre/refusé)."""
    data = request.get_json() or {}
    status = data.get("status", "applied")
    cover_letter = data.get("cover_letter", "")
    notes = data.get("notes", "")
    
    conn = get_db()
    cursor = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    job = cursor.fetchone()
    if not job:
        conn.close()
        return jsonify({"error": "Job not found"}), 404
    
    now = datetime.now().isoformat()
    conn.execute("""
        UPDATE jobs SET applied = 1, cover_letter = ?, applied_at = ? WHERE id = ?
    """, (cover_letter, now, job_id))
    
    # Upsert into applications
    cursor = conn.execute("SELECT id FROM applications WHERE job_id = ?", (job_id,))
    existing = cursor.fetchone()
    if existing:
        conn.execute("""
            UPDATE applications SET status = ?, cover_letter = ?, notes = ?, applied_at = ?
            WHERE job_id = ?
        """, (status, cover_letter, notes, now, job_id))
    else:
        conn.execute("""
            INSERT INTO applications (job_id, cover_letter, status, notes, job_title, company, applied_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (job_id, cover_letter, status, notes, job["title"], job["company"], now))
    
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "pipeline_status": status})


@app.route("/api/jobs/<int:job_id>/notes", methods=["POST"])
def api_save_notes(job_id):
    """Save notes for a job."""
    data = request.get_json() or {}
    notes = data.get("notes", "")
    conn = get_db()
    conn.execute("UPDATE jobs SET notes = ? WHERE id = ?", (notes, job_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


@app.route("/api/jobs/<int:job_id>/pipeline", methods=["POST"])
def api_update_pipeline(job_id):
    """Update pipeline status for a job."""
    data = request.get_json() or {}
    status = data.get("status", "applied")
    conn = get_db()
    cursor = conn.execute("SELECT id FROM applications WHERE job_id = ?", (job_id,))
    existing = cursor.fetchone()
    if existing:
        conn.execute("UPDATE applications SET status = ? WHERE job_id = ?", (status, job_id))
    else:
        conn.execute("""
            INSERT INTO applications (job_id, status, job_title, company)
            VALUES (?, ?, (SELECT title FROM jobs WHERE id = ?), (SELECT company FROM jobs WHERE id = ?))
        """, (job_id, status, job_id, job_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "pipeline_status": status})


@app.route("/api/jobs/enrich/<int:job_id>")
def api_enrich_job(job_id):
    """Enrich job description via DeepSeek API to extract structured data."""
    import os as os_mod
    conn = get_db()
    cursor = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    job = cursor.fetchone()
    conn.close()
    if not job:
        return jsonify({"error": "Job not found"}), 404
    desc = job["description"]
    if not desc or len(desc) < 50:
        return jsonify({"error": "Description too short or empty"}), 400
    
    # Get DeepSeek API key
    api_key = os_mod.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        env_file = os_mod.path.expanduser("~/.hermes/.env")
        if os_mod.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    if line.startswith("DEEPSEEK_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip("\"'")
                        break
    
    if not api_key:
        return jsonify({"error": "DEEPSEEK_API_KEY not found"}), 500
    
    prompt = f"""Extract structured JSON from this job description. Return ONLY valid JSON with these fields:
- tech_stack: array of technologies/tools mentioned (e.g. ["Cypress","Playwright","Python"])
- seniority: one of junior/mid/senior/lead/null based on experience level mentioned
- contract_type: one of freelance/contract/fulltime/null
- remote_type: one of fully_remote/hybrid/async_first/null
- salary_min: minimum salary as integer or null
- salary_max: maximum salary as integer or null
- currency: USD/EUR/GBP or null

Job Description:
{desc[:3000]}"""  # Limit to 3000 chars
    
    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 500,
            },
            timeout=30
        )
        if resp.status_code != 200:
            return jsonify({"error": f"DeepSeek API error: {resp.status_code}", "detail": resp.text}), 500
        
        result = resp.json()
        content = result["choices"][0]["message"]["content"]
        # Try to extract JSON from response (it may have markdown fences)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        data = json.loads(content)
        
        # Update job record
        conn = get_db()
        conn.execute("""
            UPDATE jobs SET
                tech_stack = ?, seniority = ?, contract_type = ?,
                remote_type = ?, salary_min = ?, salary_max = ?,
                currency = ?, ai_enriched = 1
            WHERE id = ?
        """, (
            json.dumps(data.get("tech_stack", [])),
            data.get("seniority"),
            data.get("contract_type"),
            data.get("remote_type"),
            data.get("salary_min"),
            data.get("salary_max"),
            data.get("currency"),
            job_id
        ))
        conn.commit()
        conn.close()
        
        return jsonify({"status": "ok", "data": data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/apply/<int:job_id>", methods=["POST"])
def api_apply(job_id):
    data = request.get_json() or {}
    cover_letter = data.get("cover_letter", "")
    mark_applied(job_id, cover_letter)
    return jsonify({"status": "ok"})


@app.route("/api/generate-cover/<int:job_id>")
def generate_cover(job_id):
    """Generate a cover letter for a specific job using LLM."""
    conn = get_db()
    cursor = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    job = cursor.fetchone()
    conn.close()
    
    if not job:
        return jsonify({"error": "Job not found"})
    
    # Simple template-based cover letter (could be enhanced with LLM)
    job_title = job["title"]
    company = job["company"] or "your company"
    
    cover = (
        f"Hi {company} team,\n\n"
        f"I'm applying for the {job_title} position. "
        f"With 12+ years of QA engineering experience across banking (BRED), "
        f"hospitality (Accor Hotels - global mobile QA lead), healthcare (Visiodent), "
        f"and cloud (Oodrive), I bring a breadth of sector expertise to this role.\n\n"
        f"I'm PSPO certified, ISTQB-trained, and have deep hands-on experience with "
        f"JIRA/Xray, Gherkin, SQL Oracle, Mainframe, and mobile testing (Android/iOS). "
        f"I'm currently expanding my skills in AI, automation, and prompt engineering.\n\n"
        f"I work as a freelance consultant (SASU), am fully remote, and available "
        f"to start immediately. Would love to discuss how my experience matches "
        f"your needs.\n\n"
        f"Best regards,\n"
        f"Jahangir\n"
        f"Senior QA Consultant - Test Manager\n"
    )
    
    return jsonify({"cover_letter": cover})


@app.route("/cv")
def cv_page():
    return render_template("cv.html", cv=CV)


@app.route("/api/cv")
def api_cv():
    return jsonify(CV)


@app.route("/about")
def about():
    return render_template("about.html",
        version=get_version(),
        commit=get_git_commit(),
        tag=get_git_tag(),
        dirty=is_dirty(),
        db_schema=DB_SCHEMA_VERSION)


@app.route("/changelog")
def changelog():
    import markdown
    try:
        with open("CHANGELOG.md") as f:
            html = markdown.markdown(f.read(), extensions=["fenced_code"])
    except:
        html = "<p>Changelog non disponible</p>"
    return render_template("changelog.html",
        content=html,
        version=get_version())


@app.route("/marche-qa")
def marche_qa():
    return render_template("marche_qa.html")


# ─── QA Routes ──────────────────────────────────────────────────

@app.route("/qa")
def qa_dashboard():
    return render_template("qa.html")


@app.route("/qa/api/test-cases")
def qa_api_test_cases():
    return jsonify(parse_feature_files())


@app.route("/qa/api/runs", methods=["GET", "POST"])
def qa_api_runs():
    if request.method == "POST":
        run_id = run_pytest_async()
        return jsonify({"run_id": run_id, "status": "started"})
    return jsonify({"runs": get_qa_runs(10)})


@app.route("/qa/api/runs/<run_id>")
def qa_api_run_detail(run_id):
    path = os.path.join(QA_RUNS_DIR, f"{run_id}.json")
    if os.path.exists(path):
        with open(path) as f:
            return jsonify(json.load(f))
    return jsonify({"run_id": run_id, "status": "pending", "output": ""})


@app.route("/qa/api/github/trigger", methods=["POST"])
def qa_github_trigger():
    if not GITHUB_TOKEN:
        return jsonify({"error": "GITHUB_TOKEN not configured"}), 400
    try:
        resp = requests.post(
            "https://api.github.com/repos/AtmanTest/jobhunt/actions/workflows/ci.yml/dispatches",
            headers={"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"},
            json={"ref": "main"},
            timeout=10,
        )
        if resp.status_code in (204, 201):
            return jsonify({"status": "triggered"})
        return jsonify({"error": f"GitHub API error: {resp.status_code}", "detail": resp.text}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/qa/api/github/runs")
def qa_github_runs():
    if not GITHUB_TOKEN:
        return jsonify({"runs": [], "error": "no token"})
    try:
        resp = requests.get(
            "https://api.github.com/repos/AtmanTest/jobhunt/actions/runs?per_page=10",
            headers={"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"},
            timeout=10,
        )
        if resp.status_code != 200:
            return jsonify({"runs": [], "error": f"API: {resp.status_code}"})
        data = resp.json()
        runs = []
        for run in data.get("workflow_runs", []):
            runs.append({
                "id": run["id"],
                "display_title": run.get("display_title") or "CI",
                "event": run.get("event"),
                "branch": run.get("head_branch"),
                "status": run.get("status"),
                "conclusion": run.get("conclusion"),
                "created_at": run.get("created_at"),
                "html_url": run.get("html_url"),
            })
        return jsonify({"runs": runs})
    except Exception as e:
        return jsonify({"runs": [], "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print(f"""
╔══════════════════════════════════════════════╗
║          JobHunt Dashboard v1.0              ║
║                                              ║
║  🌐 http://localhost:{port}                     ║
║                                              ║
║  Ctrl+C pour arrêter                         ║
╚══════════════════════════════════════════════╝
    """)
    app.run(host="0.0.0.0", port=port, debug=True)
