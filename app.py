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
from datetime import datetime

# Import scraper
import sys
sys.path.insert(0, os.path.dirname(__file__))
from scraper import init_db, fetch_all, save_jobs, get_jobs, mark_applied, get_stats
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
