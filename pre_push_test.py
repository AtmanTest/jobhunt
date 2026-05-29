"""Test suite: validate all fixes before pushing to GitHub/Render."""
import sys, os
sys.path.insert(0, os.path.expanduser("~/jobhunt"))

print("=" * 50)
print("PRE-PUSH TEST SUITE")
print("=" * 50)

# 1. Test match_job_to_cv with null fields
print("\n1️⃣ Test matcher NoneType bug...")
from matcher import match_job_to_cv

# Simulate a job from GitHub export (null tags/description)
job_null = {
    "title": "QA Tester",
    "company": "Test Corp",
    "tags": None,
    "description": None,
    "salary": None,
    "freelance_status": "VALIDÉE",
    "freelance_score": 30,
    "remote_type": "remote"
}
try:
    score, skills = match_job_to_cv(job_null)
    print(f"   ✅ match_job_to_cv(null fields): score={score}, skills={skills}")
except Exception as e:
    print(f"   ❌ match_job_to_cv(null fields) CRASHED: {e}")
    sys.exit(1)

# 2. Test match_job_to_cv with normal fields
job_normal = {
    "title": "Senior QA Engineer - Playwright Automation",
    "company": "ACME Corp",
    "tags": "playwright, selenium, python",
    "description": "Looking for a QA engineer with automation skills",
    "salary": "500-700 €/jour",
    "freelance_status": "VALIDÉE",
    "freelance_score": 35,
    "remote_type": "remote"
}
try:
    score, skills = match_job_to_cv(job_normal)
    print(f"   ✅ match_job_to_cv(normal): score={score}, skills={skills}")
except Exception as e:
    print(f"   ❌ match_job_to_cv(normal) CRASHED: {e}")
    sys.exit(1)

# 3. Test analyze_tjm with null fields
print("\n2️⃣ Test analyze_tjm with null fields...")
from matcher import analyze_tjm
try:
    result = analyze_tjm(job_null)
    print(f"   ✅ analyze_tjm(null): {result}")
except Exception as e:
    print(f"   ❌ analyze_tjm(null) CRASHED: {e}")
    sys.exit(1)

# 4. Test filter_jobs_by_country SQL
print("\n3️⃣ Test filter_jobs_by_country SQL...")
import sqlite3
db_path = "/tmp/test_prepush.db"
if os.path.exists(db_path):
    os.remove(db_path)
conn = sqlite3.connect(db_path)
conn.executescript("""
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
        freelance_status TEXT,
        freelance_score INTEGER DEFAULT 0,
        viewed INTEGER DEFAULT 0
    )
""")
conn.execute("INSERT INTO jobs (title, company, location, url) VALUES (?,?,?,?)",
    ("QA Tester", "ACME", "Paris, France", "http://x.com/1"))
conn.execute("INSERT INTO jobs (title, company, location, url) VALUES (?,?,?,?)",
    ("QA Tester", "ACME", "Paris, France", "http://x.com/2"))  # duplicate title+company
conn.commit()

try:
    cursor = conn.execute("""
        SELECT * FROM jobs 
        WHERE id IN (
            SELECT MAX(id) FROM jobs 
            WHERE (location LIKE ? OR location LIKE ?)
            AND (freelance_status IS NULL OR freelance_status IN ('VALIDÉE', 'AMBIGUË'))
            GROUP BY LOWER(TRIM(title)), LOWER(TRIM(company))
        )
        ORDER BY viewed ASC
    """, ('%Paris%', '%France%'))
    rows = cursor.fetchall()
    assert len(rows) == 1, f"Expected 1 deduplicated row, got {len(rows)}"
    print(f"   ✅ filter_jobs_by_country SQL: {len(rows)} result (dedup OK)")
except Exception as e:
    print(f"   ❌ filter_jobs_by_country SQL CRASHED: {e}")
    sys.exit(1)
finally:
    conn.close()
    os.remove(db_path)

# 5. Test Flask app starts without 500 on /
print("\n4️⃣ Test Flask index route...")
os.environ["RENDER"] = "true"
from app import app

with app.test_client() as client:
    # First hit the debug endpoint (populates DB + remove debug endpoint later)
    resp = client.get("/debug")
    print(f"   ✅ Debug endpoint: HTTP {resp.status_code}")
    
    resp = client.get("/")
    if resp.status_code == 500:
        print(f"   ❌ Home page CRASHED (HTTP 500)")
        # Print traceback
        html = resp.data.decode()
        print(f"   Response: {html[:300]}")
        sys.exit(1)
    else:
        print(f"   ✅ Home page: HTTP {resp.status_code} ({len(resp.data)} bytes)")

print("\n" + "=" * 50)
print("✅ ALL TESTS PASSED")
print("=" * 50)
