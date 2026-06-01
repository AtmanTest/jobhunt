"""
Supabase integration for JobHunt Dashboard.
Replaces SQLite with Supabase for cloud persistence.

Usage:
    from supa import get_supabase, supabase_get_jobs, supabase_save_jobs, ...

Requires env vars:
    SUPABASE_URL=https://auisrsmcjjnhytrztndd.supabase.co
    SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsIn...
"""
import os
import json
from datetime import datetime
from typing import Optional

try:
    from supabase import create_client, Client
except ImportError:
    Client = None


def _get_client() -> Optional[Client]:
    """Get Supabase client. Returns None if not configured."""
    if Client is None:
        return None
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        # Fallback: try .hermes/.env
        env_path = os.path.expanduser("~/.hermes/.env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("SUPABASE_URL="):
                        url = line.split("=", 1)[1].strip().strip("\"'"')
                    elif line.startswith("SUPABASE_KEY="):
                        key = line.split("=", 1)[1].strip().strip("\"'"')
        if not url or not key:
            return None
    return create_client(url, key)


def get_supabase() -> Optional[Client]:
    """Get the global Supabase client."""
    return _get_client()


# ─── Jobs CRUD ────────────────────────────────────────────

def supabase_get_jobs(filters: dict = None) -> list:
    """Get jobs from Supabase with optional filters."""
    sb = get_supabase()
    if not sb:
        return []
    
    query = sb.table("jobs").select("*")
    
    if filters:
        if filters.get("qa_only"):
            query = query.eq("is_qa", 1)
        if filters.get("not_applied"):
            query = query.eq("applied", 0)
        if filters.get("source"):
            query = query.eq("source", filters["source"])
        if filters.get("search"):
            query = query.or_(f"title.ilike.%{filters['search']}%,company.ilike.%{filters['search']}%")
        if filters.get("saved"):
            query = query.eq("saved", 1)
    
    # Default order: newest first
    query = query.order("raw_date", desc=True).limit(500)
    
    result = query.execute()
    return result.data if result.data else []


def supabase_save_jobs(jobs: list) -> int:
    """Save jobs to Supabase (upsert by url). Returns count of new jobs."""
    sb = get_supabase()
    if not sb or not jobs:
        return 0
    
    new_count = 0
    for job in jobs:
        # Clean None dates
        if job.get("date") is None:
            job["date"] = ""
        if job.get("created_at") is None:
            job["created_at"] = datetime.now().isoformat()
        
        # Upsert by url
        try:
            result = sb.table("jobs").upsert(job, on_conflict="url").execute()
            if result.data:
                new_count += 1
        except Exception as e:
            print(f"[Supabase] Error saving job {job.get('title', '?')}: {e}")
    
    return new_count


def supabase_update_job(job_id: int, data: dict) -> bool:
    """Update a single job's fields."""
    sb = get_supabase()
    if not sb:
        return False
    try:
        sb.table("jobs").update(data).eq("id", job_id).execute()
        return True
    except Exception as e:
        print(f"[Supabase] Update error: {e}")
        return False


def supabase_mark_applied(job_id: int, applied: bool = True) -> bool:
    """Mark job as applied."""
    return supabase_update_job(job_id, {"applied": 1 if applied else 0})


# ─── Applications CRUD ────────────────────────────────────

def supabase_get_applications(job_id: int = None) -> list:
    """Get applications, optionally filtered by job_id."""
    sb = get_supabase()
    if not sb:
        return []
    query = sb.table("applications").select("*")
    if job_id:
        query = query.eq("job_id", job_id)
    result = query.order("applied_at", desc=True).execute()
    return result.data if result.data else []


def supabase_save_application(app: dict) -> bool:
    """Save or update an application."""
    sb = get_supabase()
    if not sb:
        return False
    try:
        sb.table("applications").upsert(app, on_conflict="job_id").execute()
        return True
    except Exception as e:
        print(f"[Supabase] App save error: {e}")
        return False


# ─── Stats ────────────────────────────────────────────────

def supabase_get_stats() -> dict:
    """Get aggregate stats from Supabase."""
    sb = get_supabase()
    if not sb:
        return {"total": 0, "applied": 0, "qa_only": 0, "saved": 0, "sources": {}}
    
    try:
        total = len(sb.table("jobs").select("id", count="exact").execute().data or [])
        applied = len(sb.table("jobs").select("id", count="exact").eq("applied", 1).execute().data or [])
        qa = len(sb.table("jobs").select("id", count="exact").eq("is_qa", 1).execute().data or [])
        saved = len(sb.table("jobs").select("id", count="exact").eq("saved", 1).execute().data or [])
        
        # Source stats
        all_jobs = sb.table("jobs").select("source").execute().data or []
        sources = {}
        for j in all_jobs:
            s = j.get("source", "unknown")
            sources[s] = sources.get(s, 0) + 1
        
        return {
            "total": total,
            "applied": applied,
            "qa_only": qa,
            "saved": saved,
            "sources": sources,
        }
    except Exception as e:
        print(f"[Supabase] Stats error: {e}")
        return {"total": 0, "applied": 0, "qa_only": 0, "saved": 0, "sources": {}}


# ─── Migration from SQLite ────────────────────────────────

def migrate_from_sqlite(sqlite_path: str) -> dict:
    """Migrate all data from a SQLite jobs.db to Supabase."""
    import sqlite3
    sb = get_supabase()
    if not sb:
        return {"error": "Supabase not configured"}
    
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    
    # Migrate jobs
    rows = conn.execute("SELECT * FROM jobs ORDER BY id").fetchall()
    jobs_migrated = 0
    for row in rows:
        d = dict(row)
        # Convert datetime objects to strings
        for k, v in d.items():
            if isinstance(v, datetime):
                d[k] = v.isoformat()
        try:
            sb.table("jobs").upsert(d, on_conflict="url").execute()
            jobs_migrated += 1
        except Exception as e:
            print(f"[Migrate] Error job {d.get('id')}: {e}")
    
    # Migrate applications
    rows = conn.execute("SELECT * FROM applications ORDER BY id").fetchall()
    apps_migrated = 0
    for row in rows:
        d = dict(row)
        for k, v in d.items():
            if isinstance(v, datetime):
                d[k] = v.isoformat()
        try:
            sb.table("applications").upsert(d, on_conflict="id").execute()
            apps_migrated += 1
        except Exception as e:
            print(f"[Migrate] Error app {d.get('id')}: {e}")
    
    conn.close()
    return {"jobs": jobs_migrated, "applications": apps_migrated}


# ─── Health check ─────────────────────────────────────────

def supabase_health() -> dict:
    """Check if Supabase is accessible."""
    sb = get_supabase()
    if not sb:
        return {"status": "error", "message": "Client not configured"}
    try:
        result = sb.table("jobs").select("id").limit(1).execute()
        return {"status": "ok", "message": "Connected", "data": result.data}
    except Exception as e:
        return {"status": "error", "message": str(e)[:200]}
