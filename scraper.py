"""
JobHunt Scraper - récupère les offres QA/SDET remote depuis plusieurs sources.
"""
import requests
from bs4 import BeautifulSoup
import sqlite3
import hashlib
from datetime import datetime
import time
import json


SOURCES = [
    {
        "name": "RemoteOK",
        "url": "https://remoteok.com/remote-quality-assurance-jobs",
        "type": "remoteok"
    },
    {
        "name": "We Work Remotely - QA",
        "url": "https://weworkremotely.com/categories/remote-software-development-jobs",
        "type": "wwr"
    },
]


def fetch_remoteok():
    """Scrape RemoteOK QA jobs."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }
    
    jobs = []
    
    # RemoteOK has a JSON API that returns raw job data
    try:
        resp = requests.get(
            "https://remoteok.com/api",
            headers=headers,
            timeout=15
        )
        if resp.status_code == 200:
            data = resp.json()
            # Skip first item (it's usually a meta/ad item)
            for item in data[1:]:
                if not isinstance(item, dict):
                    continue
                title = item.get("position", "")
                tags_list = item.get("tags", []) or []
                all_tags = " ".join(tags_list).lower()
                title_lower = title.lower()
                
                # Filter for QA/test/SDET roles (check title AND tags)
                filter_keywords = ["qa", "sdet", "quality assurance", "quality engineer",
                                   "test engineer", "test automation", "tester",
                                   "testing", "automation engineer", "test lead",
                                   "test manager", "qa lead", "qa engineer",
                                   "software test", "software testing"]
                matches = any(k in title_lower for k in filter_keywords) or \
                          any(k in all_tags for k in ["qa", "testing", "test", "quality assurance"])
                if not matches:
                    continue
                    
                company = item.get("company", "")
                tags = ", ".join(tags_list)
                date_str = item.get("date", "")
                # Build the proper job URL from slug
                slug = item.get("slug", "")
                if slug:
                    url = f"https://remoteok.com/remote-jobs/{slug}"
                else:
                    url = item.get("apply_url") or item.get("url", "")
                location = item.get("location", "Worldwide")
                
                # Nice salary display if available
                salary_min = item.get("salary_min")
                salary_max = item.get("salary_max")
                salary = ""
                if salary_min or salary_max:
                    currency = item.get("currency", "$")
                    if salary_min and salary_max:
                        salary = f"{currency}{salary_min:,.0f} - {currency}{salary_max:,.0f}"
                    elif salary_min:
                        salary = f"From {currency}{salary_min:,.0f}"
                    elif salary_max:
                        salary = f"Up to {currency}{salary_max:,.0f}"
                
                jobs.append({
                    "title": title,
                    "company": company,
                    "source": "RemoteOK",
                    "url": url,
                    "location": location,
                    "salary": salary,
                    "tags": tags,
                    "date": date_str[:10] if date_str else "",
                    "description": item.get("description", ""),
                    "raw_date": item.get("epoch", 0),
                })
        else:
            print(f"  RemoteOK API returned {resp.status_code}")
    except Exception as e:
        print(f"  RemoteOK error: {e}")
    
    return jobs


def fetch_wwr():
    """Scrape We Work Remotely for dev jobs, filter for QA."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
    }
    jobs = []
    
    categories = [
        "https://weworkremotely.com/categories/remote-software-development-jobs",
        "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs",
    ]
    
    for cat_url in categories:
        try:
            resp = requests.get(cat_url, headers=headers, timeout=15)
            if resp.status_code != 200:
                continue
                
            soup = BeautifulSoup(resp.text, "html.parser")
            # Find all job listing articles
            articles = soup.select("article li")
            if not articles:
                # Try alternate selector
                articles = soup.select("li[class*='job']")
            
            for article in articles:
                # Extract job info
                title_el = article.select_one("span[class*='title']")
                if not title_el:
                    title_el = article.select_one("h4, h3, h2, a[href*='/jobs/']")
                if not title_el:
                    continue
                    
                title = title_el.get_text(strip=True)
                
                # Filter: keep everything but flag QA roles
                company_el = article.select_one("span[class*='company']")
                company = company_el.get_text(strip=True) if company_el else ""
                
                url_el = article.select_one("a[href*='/jobs/']")
                url = "https://weworkremotely.com" + url_el["href"] if url_el and url_el.get("href") else ""
                if url and not url.startswith("http"):
                    url = "https://weworkremotely.com" + url
                
                jobs.append({
                    "title": title,
                    "company": company,
                    "source": "WWR",
                    "url": url,
                    "location": "Remote",
                    "salary": "",
                    "tags": "",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "description": "",
                    "raw_date": int(time.time()),
                })
        except Exception as e:
            print(f"  WWR error: {e}")
    
    return jobs


def fetch_all():
    """Fetch jobs from all sources."""
    all_jobs = []
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching RemoteOK...")
    all_jobs.extend(fetch_remoteok())
    
    # Be nice to servers
    time.sleep(1)
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching WWR...")
    all_jobs.extend(fetch_wwr())
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Total: {len(all_jobs)} jobs found")
    return all_jobs


def get_db():
    conn = sqlite3.connect("/Users/jahangir/Desktop/jobhunt/jobs.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
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
            applied INTEGER DEFAULT 0,
            cover_letter TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            cover_letter TEXT,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_url ON jobs(url);
        CREATE INDEX IF NOT EXISTS idx_jobs_qa ON jobs(is_qa);
    """)
    conn.commit()
    conn.close()


def save_jobs(jobs):
    """Save jobs to database, skipping duplicates."""
    conn = get_db()
    cursor = conn.cursor()
    # Keywords for QA matching in title/tags
    title_keywords = ["qa", "sdet", "quality assurance", "quality engineer",
                      "test engineer", "test automation", "sdet", "tester",
                      "testing", "automation engineer", "test lead", "test manager",
                      "software test", "qa lead", "qa engineer"]
    # Broader keywords only checked against tags (less likely to false-positive)
    tag_keywords = ["qa", "testing", "test", "quality assurance", "automation testing"]
    
    new_count = 0
    for job in jobs:
        # Generate a unique URL hash for dedup
        url_hash = hashlib.md5(job["url"].encode()).hexdigest()
        
        # Check if QA-related
        title_lower = job["title"].lower()
        tags_lower = job["tags"].lower() if job.get("tags") else ""
        
        # Match against title first (strict), then tags (broader)
        is_qa = 1 if any(k in title_lower for k in title_keywords) else 0
        if not is_qa:
            is_qa = 1 if any(k in tags_lower for k in tag_keywords) else 0
        
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO jobs
                (title, company, source, url, location, salary, tags, 
                 description, date, raw_date, is_qa)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job["title"], job["company"], job["source"], job["url"],
                job["location"], job["salary"], job["tags"],
                job["description"], job["date"], job["raw_date"], is_qa
            ))
            if cursor.rowcount > 0:
                new_count += 1
        except Exception as e:
            print(f"  DB error: {e}")
    
    conn.commit()
    conn.close()
    return new_count


def get_jobs(filters=None):
    """Get jobs with optional filters."""
    conn = get_db()
    query = "SELECT * FROM jobs WHERE 1=1"
    params = []
    
    if filters:
        if filters.get("qa_only"):
            query += " AND is_qa = 1"
        if filters.get("not_applied"):
            query += " AND applied = 0"
        if filters.get("search"):
            query += " AND (title LIKE ? OR company LIKE ? OR description LIKE ?)"
            term = f"%{filters['search']}%"
            params.extend([term, term, term])
        if filters.get("source"):
            query += " AND source = ?"
            params.append(filters["source"])
    
    query += " ORDER BY raw_date DESC, date DESC LIMIT 200"
    
    cursor = conn.execute(query, params)
    jobs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jobs


def export_static_json(output_path="docs/jobs.json"):
    """Export jobs to JSON for the static site."""
    import json, os
    jobs = get_jobs({"qa_only": True})
    # Clean up for export
    for j in jobs:
        # Remove fields not needed in static export
        j.pop("description", None)
        j.pop("notes", None)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({"jobs": jobs, "exported_at": datetime.now().isoformat()}, f, indent=2)
    print(f"✓ Exported {len(jobs)} jobs to {output_path}")
    return len(jobs)


def mark_applied(job_id, cover_letter=""):
    """Mark a job as applied."""
    conn = get_db()
    conn.execute("UPDATE jobs SET applied = 1, cover_letter = ? WHERE id = ?",
                 (cover_letter, job_id))
    conn.execute("INSERT INTO applications (job_id, cover_letter, status) VALUES (?, ?, 'applied')",
                 (job_id, cover_letter))
    conn.commit()
    conn.close()


def get_stats():
    """Get dashboard statistics."""
    conn = get_db()
    stats = {}
    cursor = conn.execute("SELECT COUNT(*) FROM jobs")
    stats["total"] = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM jobs WHERE is_qa = 1")
    stats["qa"] = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM jobs WHERE applied = 1")
    stats["applied"] = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM jobs WHERE date >= date('now', '-7 days')")
    stats["this_week"] = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(DISTINCT company) FROM jobs")
    stats["companies"] = cursor.fetchone()[0]
    conn.close()
    return stats


if __name__ == "__main__":
    init_db()
    print("JobHunt Scraper - Initialisation...")
    jobs = fetch_all()
    n = save_jobs(jobs)
    print(f"✓ {n} nouvelles offres ajoutées")
    
    stats = get_stats()
    print(f"  Total en base: {stats['total']}")
    print(f"  Offres QA: {stats['qa']}")
    print(f"  Candidatures: {stats['applied']}")
