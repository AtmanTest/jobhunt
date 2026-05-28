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
from scraper import init_db, fetch_all, fetch_all_new_sources, save_jobs, get_jobs, mark_applied, get_stats, export_static_json, get_db as scraper_db
from cv_data import CV

app = Flask(__name__)
app.secret_key = "jobhunt-secret-2026"

DB_PATH = os.path.join(os.path.dirname(__file__), "jobs.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ============================
# ROUTES
# ============================

@app.route("/")
def index():
    stats = get_stats()
    filters = {
        "qa_only": request.args.get("qa", "1") == "1",
        "not_applied": request.args.get("unapplied", "0") == "1",
        "search": request.args.get("search", ""),
        "source": request.args.get("source", ""),
    }
    jobs = get_jobs(filters)
    return render_template("index.html", jobs=jobs, stats=stats, filters=filters)


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


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """API endpoint to trigger refresh."""
    def do_scrape():
        jobs = fetch_all()
        n = save_jobs(jobs)
        print(f"✓ Scrape done: {n} new jobs")
    
    thread = threading.Thread(target=do_scrape, daemon=True)
    thread.start()
    return jsonify({"status": "started"})


@app.route("/api/jobs")
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
    return render_template("about.html")


if __name__ == "__main__":
    # Initialize database
    init_db()
    
    print("""
╔══════════════════════════════════════════════╗
║          JobHunt Dashboard v1.0              ║
║                                              ║
║  🌐 http://localhost:5050                     ║
║                                              ║
║  Ctrl+C pour arrêter                         ║
╚══════════════════════════════════════════════╝
    """)
    app.run(host="127.0.0.1", port=5050, debug=True)
