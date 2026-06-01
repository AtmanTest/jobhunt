"""Database helper functions for JobHunt test suite."""

import sqlite3
import json


def insert_test_jobs(conn, jobs_list):
    """Insert test jobs into the database and return list of inserted IDs.

    Args:
        conn: SQLite connection
        jobs_list: List of dicts with job fields

    Returns:
        List of inserted job IDs (integers)
    """
    ids = []
    cursor = conn.cursor()
    for job in jobs_list:
        cursor.execute(
            """
            INSERT OR IGNORE INTO jobs
            (title, company, source, url, location, salary, tags,
             description, date, raw_date, is_qa, applied, cover_letter,
             notes, tech_stack, seniority, contract_type, remote_type,
             salary_min, salary_max, currency, ai_enriched, saved)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.get("title", ""),
                job.get("company", ""),
                job.get("source", "RemoteOK"),
                job.get("url", ""),
                job.get("location", "Worldwide"),
                job.get("salary", ""),
                job.get("tags", ""),
                job.get("description", ""),
                job.get("date", ""),
                job.get("raw_date", 0),
                job.get("is_qa", 1),
                job.get("applied", 0),
                job.get("cover_letter", ""),
                job.get("notes", ""),
                job.get("tech_stack"),
                job.get("seniority"),
                job.get("contract_type"),
                job.get("remote_type"),
                job.get("salary_min"),
                job.get("salary_max"),
                job.get("currency"),
                job.get("ai_enriched", 0),
                job.get("saved", 0),
            ),
        )
        if cursor.lastrowid:
            ids.append(cursor.lastrowid)
    conn.commit()
    return ids


def get_job_by_id(conn, job_id):
    """Fetch a single job by its ID.

    Args:
        conn: SQLite connection
        job_id: Job ID integer

    Returns:
        Dict of job fields, or None if not found
    """
    cursor = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    if row:
        return dict(row)
    return None


def get_application_by_job_id(conn, job_id):
    """Fetch an application record by job ID.

    Args:
        conn: SQLite connection
        job_id: Job ID integer

    Returns:
        Dict of application fields, or None if not found
    """
    cursor = conn.execute("SELECT * FROM applications WHERE job_id = ?", (job_id,))
    row = cursor.fetchone()
    if row:
        return dict(row)
    return None


def count_jobs(conn, filters=None):
    """Count jobs in the database with optional WHERE conditions.

    Args:
        conn: SQLite connection
        filters: Optional dict of column -> value conditions

    Returns:
        Integer count of matching rows
    """
    query = "SELECT COUNT(*) FROM jobs WHERE 1=1"
    params = []
    if filters:
        for col, val in filters.items():
            query += f" AND {col} = ?"
            params.append(val)
    cursor = conn.execute(query, params)
    return cursor.fetchone()[0]


def clear_test_db(conn):
    """Remove all rows from jobs and applications tables.

    Args:
        conn: SQLite connection
    """
    conn.execute("DELETE FROM applications")
    conn.execute("DELETE FROM jobs")
    conn.commit()


def create_schema(conn):
    """Create the jobs and applications tables with all columns.

    This mirrors the production schema from scraper.init_db().

    Args:
        conn: SQLite connection
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT,
            source TEXT,
            url TEXT UNIQUE,
            location TEXT,
            salary TEXT,
            tags TEXT,
            description TEXT,
            date TEXT,
            raw_date INTEGER DEFAULT 0,
            is_qa INTEGER DEFAULT 0,
            applied INTEGER DEFAULT 0,
            cover_letter TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tech_stack TEXT,
            seniority TEXT,
            contract_type TEXT,
            remote_type TEXT,
            salary_min INTEGER,
            salary_max INTEGER,
            currency TEXT,
            ai_enriched INTEGER DEFAULT 0,
            saved INTEGER DEFAULT 0,
            applied_at DATETIME
        );
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            cover_letter TEXT,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',
            notes TEXT,
            job_title TEXT,
            company TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_url ON jobs(url);
        CREATE INDEX IF NOT EXISTS idx_jobs_qa ON jobs(is_qa);
    """
    )
    conn.commit()
