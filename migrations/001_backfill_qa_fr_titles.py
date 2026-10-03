"""One-shot migration: flag FR/EU QA title variants that were stored with is_qa=0.

Only flips 0 -> 1 (never unmarks). Idempotent: safe to re-run, prints how many rows change.
"""
import sys
from pathlib import Path, sqlite3
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scraper import get_db, DB_PATH

TERMS = ["testeur", "testeuse", "test analyst", "analyste test", "ivvq",
         "assurance qualité", "assurance qualite", "quality analyst",
         "ingénieur test", "ingenieur test", "test lead", "test manager"]

conn = get_db()
cur = conn.cursor()
where = " OR ".join(["LOWER(title) LIKE ?"] * len(TERMS))
params = [f"%{t}%" for t in TERMS]
before = cur.execute(f"SELECT COUNT(*) FROM jobs WHERE is_qa=0 AND ({where})", params).fetchone()[0]
cur.execute(f"UPDATE jobs SET is_qa=1 WHERE is_qa=0 AND ({where})", params)
conn.commit()
after = cur.execute("SELECT COUNT(*) FROM jobs WHERE is_qa=1").fetchone()[0]
print(f"backfill: {before} rows flipped 0->1, is_qa total now {after}")
print("sample:", cur.execute("SELECT id,title,is_qa FROM jobs WHERE LOWER(title) LIKE '%testeur%' LIMIT 3").fetchall())
conn.close()
