#!/usr/bin/env python3
"""
auto_enrich.py - Standalone script to enrich job descriptions via DeepSeek API.
Queries jobs without ai_enriched=1, extracts structured data, updates DB.
"""
import sqlite3
import json
import os
import time
import requests
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), "jobs.db")
DEEPSEEK_MODEL = "deepseek-chat"
RATE_LIMIT_SLEEP = 1.0  # 1 request per second


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_api_key():
    """Get DeepSeek API key from env or ~/.hermes/.env"""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        env_file = os.path.expanduser("~/.hermes/.env")
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    if line.startswith("DEEPSEEK_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip("\"'")
                        break
    return api_key


def extract_fields(description, api_key):
    """Send description to DeepSeek Flash API and parse structured data."""
    prompt = f"""Extract structured JSON from this job description. Return ONLY valid JSON with these fields:
- tech_stack: array of technologies/tools mentioned (e.g. ["Cypress","Playwright","Python"])
- seniority: one of junior/mid/senior/lead/null based on experience level mentioned
- contract_type: one of freelance/contract/fulltime/null
- remote_type: one of fully_remote/hybrid/async_first/null
- salary_min: minimum salary as integer or null
- salary_max: maximum salary as integer or null
- currency: USD/EUR/GBP or null

Job Description:
{description[:3000]}"""

    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 500,
            },
            timeout=30
        )
        if resp.status_code != 200:
            print(f"  API error ({resp.status_code}): {resp.text[:200]}")
            return None

        result = resp.json()
        content = result["choices"][0]["message"]["content"]

        # Strip markdown fences if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        data = json.loads(content)
        return data
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"  API request error: {e}")
        return None


def update_job(job_id, data, conn):
    """Update job record with extracted fields."""
    conn.execute("""
        UPDATE jobs SET
            tech_stack = ?,
            seniority = ?,
            contract_type = ?,
            remote_type = ?,
            salary_min = ?,
            salary_max = ?,
            currency = ?,
            ai_enriched = 1
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


def enrich_all(limit=None, dry_run=False):
    """
    Main function: iterate over unenriched jobs with descriptions and enrich them.
    
    Args:
        limit: Max jobs to process (None = all)
        dry_run: If True, only show what would be processed
    Returns:
        Number of jobs successfully enriched
    """
    api_key = get_api_key()
    if not api_key:
        print("ERROR: DEEPSEEK_API_KEY not found in env or ~/.hermes/.env")
        return 0

    conn = get_db()
    query = "SELECT id, title, company, description FROM jobs WHERE (ai_enriched IS NULL OR ai_enriched = 0) AND description IS NOT NULL AND description != '' ORDER BY id"
    cursor = conn.execute(query)
    jobs = cursor.fetchall()
    print(f"Found {len(jobs)} jobs to enrich")

    if dry_run:
        for job in jobs[:limit]:
            print(f"  Would enrich: [{job['id']}] {job['title']} @ {job['company']} ({len(job['description'])} chars)")
        conn.close()
        return 0

    enriched = 0
    total = len(jobs)

    for idx, job in enumerate(jobs):
        if limit and enriched >= limit:
            break

        print(f"[{idx+1}/{total}] Enriching [{job['id']}] {job['title']} @ {job['company']}...")

        data = extract_fields(job["description"], api_key)
        if data is None:
            print(f"  Failed, skipping")
            time.sleep(RATE_LIMIT_SLEEP)
            continue

        try:
            update_job(job["id"], data, conn)
            conn.commit()
            enriched += 1
            print(f"  OK: tech_stack={data.get('tech_stack')}, seniority={data.get('seniority')}, contract={data.get('contract_type')}")
        except Exception as e:
            print(f"  DB error: {e}")
            conn.rollback()

        time.sleep(RATE_LIMIT_SLEEP)

    conn.close()
    print(f"\nDone: {enriched}/{total} jobs enriched")
    return enriched


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Enrich job descriptions with AI-extracted fields")
    parser.add_argument("--limit", type=int, default=None, help="Max jobs to process")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed without doing it")
    args = parser.parse_args()

    n = enrich_all(limit=args.limit, dry_run=args.dry_run)
    print(f"Enriched: {n} jobs")
