#!/usr/bin/env python3
"""
Repair fields wiped by auto_enrich.py.

Bug fixed here: auto_enrich.update_job() used to write every extracted column
unconditionally, so an LLM answer of null/[]/"" overwrote deterministic values
produced by scraper.py (detect_remote_type / detect_contract_type). Result:
~500 jobs lost their remote_type, ~300 their contract_type, and 207 jobs got
the LLM's foreign vocabulary ("fulltime") instead of the FR labels the site
filters on.

Repair strategy, in order of trust:
  1. history  – last non-empty value seen in any committed docs/jobs.json
  2. detector – scraper.detect_remote_type / detect_contract_type re-run on the
                stored title/description/location (deterministic, no API cost)

Usage: python3 repair_enrich_fields.py [--dry-run]
"""
import json
import os
import subprocess
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scraper import detect_remote_type, detect_contract_type  # noqa: E402

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PROJECT_DIR, "jobs.db")
EXPORT = "docs/jobs.json"
EXPORT_FIELDS = ("remote_type", "contract_type", "seniority")
REMOTE_ALIASES = {"fully_remote": "remote", "full_remote": "remote",
                  "fullremote": "remote", "async_first": "remote",
                  "async-first": "remote", "telework": "remote"}
# contract_type values that only ever came from the LLM (foreign vocabulary)
AI_CONTRACT_VALUES = {"fulltime", "full-time", "part-time", "parttime",
                      "permanent", "contract", "contractor", "internship"}


CANONICAL_REMOTE = {"remote", "hybrid", "onsite"}


def normalize_remote(value):
    """Map any stored remote wording onto the site's canonical vocabulary."""
    v = (value or "").strip().lower()
    if not v:
        return None
    if v in REMOTE_ALIASES:
        return REMOTE_ALIASES[v]
    if "hybrid" in v or "hybride" in v or "mixte" in v:
        return "hybrid"
    if any(k in v for k in ("remote", "télétravail", "teletravail", "distanciel",
                            "distance", "wfh", "home office")):
        return "remote"
    if any(k in v for k in ("onsite", "on-site", "présentiel", "presentiel",
                            "sur site", "sur place")):
        return "onsite"
    return v


def latest_from_history():
    """{job_id: {field: value}} keeping the most recent non-empty value per field."""
    hashes = subprocess.run(["git", "log", "--format=%H", "--", EXPORT],
                            cwd=PROJECT_DIR, capture_output=True, text=True).stdout.split()
    found = {}
    for sha in hashes:  # newest first -> first non-empty value wins
        blob = subprocess.run(["git", "show", f"{sha}:{EXPORT}"], cwd=PROJECT_DIR,
                              capture_output=True, text=True)
        if blob.returncode != 0:
            continue
        try:
            data = json.loads(blob.stdout)
        except json.JSONDecodeError:
            continue
        jobs = data.get("jobs") if isinstance(data, dict) else data
        if not isinstance(jobs, list):
            continue
        for job in jobs:
            if not isinstance(job, dict):
                continue
            jid = str(job.get("id", "")).strip()
            if not jid:
                continue
            slot = found.setdefault(jid, {})
            for field in EXPORT_FIELDS:
                if field in slot:
                    continue
                val = job.get(field)
                if isinstance(val, str) and val.strip():
                    slot[field] = val.strip()
    return found


def main():
    dry = "--dry-run" in sys.argv
    hist = latest_from_history()
    print(f"history: {len(hist)} job ids with recoverable values")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cols = {r[1] for r in conn.execute("PRAGMA table_info(jobs)")}
    print(f"db columns ok: {sorted(EXPORT_FIELDS) } -> {[c for c in EXPORT_FIELDS if c in cols]}")

    stats = {}

    def bump(key, n=1):
        stats[key] = stats.get(key, 0) + n

    def blank(val):
        return val is None or (isinstance(val, str) and not val.strip())

    rows = conn.execute(
        "SELECT id, title, description, location, remote_type, contract_type FROM jobs"
    ).fetchall()
    print(f"scanning {len(rows)} jobs\n")

    for row in rows:
        jid = str(row["id"])
        title = row["title"] or ""
        desc = row["description"] or ""
        loc = row["location"] or ""
        h = hist.get(jid, {})

        # --- remote_type ---
        cur = row["remote_type"]
        cur_s = str(cur).strip().lower() if cur else ""
        if cur_s and cur_s not in CANONICAL_REMOTE:
            new = normalize_remote(cur)
            if new and new != str(cur).strip():
                if not dry:
                    conn.execute("UPDATE jobs SET remote_type=? WHERE id=?", (new, row["id"]))
                bump("remote_alias_normalized")
        elif blank(cur):
            new = h.get("remote_type")
            if new:
                src = "history"
            else:
                new = detect_remote_type(loc, title, desc) or None
                src = "detector"
            if new:
                new = normalize_remote(new)
                if not dry:
                    conn.execute("UPDATE jobs SET remote_type=? WHERE id=?", (new, row["id"]))
                bump(f"remote_restored_{src}")

        # --- contract_type ---
        cur = row["contract_type"]
        cur_s = str(cur).strip().lower() if cur else ""
        if not cur_s or cur_s in AI_CONTRACT_VALUES:
            new = h.get("contract_type")
            if new and new.lower() not in AI_CONTRACT_VALUES:
                src = "history"
            else:
                new, _score = detect_contract_type(title, desc)
                src = "detector"
            if new:
                if not dry:
                    conn.execute("UPDATE jobs SET contract_type=? WHERE id=?", (new, row["id"]))
                bump(f"contract_restored_{src}")

    if not dry:
        conn.commit()

    print("changes:")
    for k in sorted(stats):
        print(f"  {k}: {stats[k]}")
    if not stats:
        print("  (nothing to repair)")

    print("\nbefore/after check (enriched rows):")
    for field in ("remote_type", "contract_type"):
        n = conn.execute(
            f"SELECT count(*) FROM jobs WHERE ai_enriched=1 AND ({field} IS NULL OR {field}='')"
        ).fetchone()[0]
        print(f"  ai_enriched=1 AND {field} empty: {n}")
    print("\ncontract_type distribution:")
    for val, ai, non in conn.execute(
        "SELECT coalesce(contract_type,'NULL'), sum(ai_enriched=1), sum(ai_enriched=0) "
        "FROM jobs GROUP BY 1 ORDER BY 3 DESC"
    ):
        print(f"  {val}: enriched={ai} not_enriched={non}")
    print("\nremote_type distribution:")
    for val, n in conn.execute(
        "SELECT coalesce(nullif(remote_type,''),'EMPTY'), count(*) FROM jobs GROUP BY 1 ORDER BY 2 DESC"
    ):
        print(f"  {val}: {n}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
