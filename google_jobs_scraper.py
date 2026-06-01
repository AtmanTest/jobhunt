"""
Google Jobs + existing scrapers with dedup.
"""
import json, re, os, subprocess, urllib.parse, time, sqlite3
from datetime import datetime
from collections import Counter

DB_PATH = os.path.join(os.path.dirname(__file__), "jobs.db")

GOOGLE_QUERIES = [
    "qa test automatisation France",
    "testeur logiciel France freelance",
    "sdet test automation France",
    "ingénieur test validation France",
    "qa assurance qualité France",
    "testeur QA France mission",
    "QA engineer France recrutement",
    "recette logiciel France",
]

SCRIPT_CACHE = {}

def applescript(script):
    """Run AppleScript from string."""
    h = hash(script)
    if h not in SCRIPT_CACHE:
        path = f'/tmp/_gj_{h}.applescript'
        with open(path, 'w') as f:
            f.write(script)
        SCRIPT_CACHE[h] = path
    path = SCRIPT_CACHE[h]
    r = subprocess.run(['osascript', path], capture_output=True, text=True, timeout=30)
    return r.stdout, r.stderr


def scrape_google_all():
    """Scrape all Google Jobs queries, return list of jobs dicts."""
    all_by_key = {}
    
    for query in GOOGLE_QUERIES:
        print(f"  🔍 {query[:45]}...", end=' ', flush=True)
        
        q = query.replace('"', '\\"').replace("'", "'\\''")
        script = f'''
        tell application "Google Chrome"
            set newTab to make new tab at end of tabs of window 1 with properties {{URL:"https://www.google.com/search?q={q}&udm=8"}}
            delay 5
            set bodyText to execute newTab javascript "document.body.innerText"
            set pageUrl to execute newTab javascript "window.location.href"
            close newTab
        end tell
        return pageUrl & "|||" & bodyText
        '''
        
        out, err = applescript(script)
        if err or not out:
            print("✗ err")
            continue
        
        parts = out.split('|||', 1)
        if len(parts) < 2:
            print("✗ no data")
            continue
        
        page_url, html = parts
        if 'sorry' in (page_url or '').lower():
            print("✗ blocked")
            continue
        
        jobs = parse_google_html(html)
        
        for job in jobs:
            key = f"{job['title']}|{job['company']}"
            if key not in all_by_key:
                all_by_key[key] = job
        
        print(f"✓ {len(jobs)} ({len(all_by_key)} unique)")
        time.sleep(0.5)
    
    return list(all_by_key.values())


def parse_google_html(html):
    """Parse Google Jobs HTML for job listings."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    jobs = []
    
    # Google Jobs uses specific patterns
    # Find all text blocks that look like job listings
    text = soup.get_text(separator='\n')
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    # Extract job-like patterns: a title with QA keywords followed by company
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Skip navigation/UI
        if line in ['Emplois', 'Offres d\'emploi', 'Suivre', 'Résultats de recherche',
                     'Tous', 'Actualités', 'Images', 'Vidéos', 'Web', 'Plus', 'Outils',
                     'France', 'Offres enregistrées', 'Suivies', 'Filtres']:
            i += 1
            continue
        
        # Check if this line looks like a job title
        title_keywords = ['qa', 'test', 'sdet', 'qualité', 'qualite', 'recette', 'validation',
                          'ingénieur', 'ingenieur', 'automation', 'testeur']
        is_title = any(k in line.lower() for k in title_keywords) and len(line) > 10 and len(line) < 200
        
        if is_title:
            title = line
            company = ''
            location = ''
            extra = ''
            
            # Look ahead for company + location
            for offset in range(1, min(6, len(lines) - i)):
                next_line = lines[i + offset]
                # Skip empty/short lines
                if len(next_line) < 2:
                    continue
                # Skip obvious non-job lines
                if next_line in ['Fraîcheur', 'il y a 2 jours', 'il y a 3 jours', 
                                 'À plein temps', 'Temps plein', 'CDI', 'CDD']:
                    continue
                # Skip salary lines (contain €)
                if '€' in next_line or '$' in next_line:
                    extra = next_line
                    continue
                # Company detection: not a keyword, not a command
                if not company and len(next_line) > 2:
                    # Check it's not a URL, date, or other misc
                    if not next_line.startswith('http') and len(next_line) < 150:
                        company = next_line
                elif company and not location and len(next_line) < 100 and len(next_line) > 3:
                    location = next_line
                    break
            
            # Clean up company (remove platform suffixes like "• via Indeed")
            if company:
                # Remove "APEC - Offres Gratuites" → keep "APEC"
                company = re.sub(r'\s*[-–—•·]\s*(Offres\s+Gratuites|Annonces?\s*GRATUITES?|Recrutement|Offres?\s+d\'emploi|Emploi|Site de recherche|.*via\s+\S+)$', '', company, flags=re.IGNORECASE).strip()
                company = re.sub(r'\s*[•·]\s*via\s+\S+.*$', '', company).strip()
                company = re.sub(r'\s*•\s*.*$', '', company).strip()
                company = re.sub(r'^\d+\s*', '', company).strip()
                company = re.sub(r' - H/F$', '', company, flags=re.IGNORECASE).strip()
            
            # Clean up location
            if location:
                location = re.sub(r'\s*[•·]\s*via\s+\S+.*$', '', location).strip()
            
            if company:
                is_freelance = any(k in (title + ' ' + company + ' ' + extra).lower() 
                                  for k in ['freelance', 'mission', 'consultant', 'sasu', 
                                           'indépendant', 'independant', 'contractor', 'free-lance',
                                           'tjm', '/jour', 'régie', 'regie'])
                is_cdi = 'cdi' in (title + ' ' + extra).lower()
                
                jobs.append({
                    'title': title.strip(),
                    'company': company.strip(),
                    'source': 'Google Jobs',
                    'url': '',
                    'location': location.strip(),
                    'salary': extra.strip(),
                    'tags': '',
                    'description': '',
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'raw_date': int(datetime.now().timestamp()),
                    'is_qa': 1,
                    'freelance_status': 'VALIDÉE' if is_freelance else 'AMBIGUË',
                    'freelance_score': 55 if is_freelance else 40,
                })
        
        i += 1
    
    return jobs


def dedup_and_merge(new_jobs):
    """
    Save jobs with dedup: Google Jobs is primary source.
    If Google Jobs finds a job already in DB (by title+company),
    skip it. Google Jobs data may be lower quality, so existing
    data from WTTJ/WWR/etc takes priority.
    """
    conn = sqlite3.connect(DB_PATH)
    
    title_keywords = ["qa", "sdet", "quality assurance", "quality engineer",
                      "test engineer", "test automation", "tester", "testing",
                      "automation engineer", "test lead", "test manager",
                      "software test", "qa lead", "qa engineer",
                      "software testing", "test developer", "engineer in test",
                      "recette", "validation", "qualité", "qualite", "testeur"]
    
    new_count = 0
    for job in new_jobs:
        norm_title = job['title'].strip().lower()[:100]
        norm_company = job.get('company', '').strip().lower()[:100]
        
        # Check if already in DB (by title+company)
        existing = conn.execute(
            "SELECT id, source FROM jobs WHERE LOWER(TRIM(title)) = ? AND LOWER(TRIM(company)) = ?",
            (norm_title, norm_company)
        ).fetchone()
        
        if existing:
            # Already exists - skip (existing data is better)
            continue
        
        # Also check URL-based dedup
        if job.get('url'):
            existing_url = conn.execute(
                "SELECT id FROM jobs WHERE url = ?", (job['url'],)
            ).fetchone()
            if existing_url:
                continue
        
        title_lower = job['title'].lower()
        is_qa = 1 if any(k in title_lower for k in title_keywords) else 0
        
        try:
            conn.execute("""
                INSERT OR IGNORE INTO jobs
                (title, company, source, url, location, salary, tags, description,
                 date, raw_date, is_qa, freelance_status, freelance_score, pipeline_stage)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new')
            """, (
                job['title'], job['company'], job['source'], job['url'],
                job['location'], job['salary'], job['tags'], job['description'],
                job['date'], job['raw_date'], is_qa,
                job['freelance_status'], job['freelance_score'],
            ))
            if conn.total_changes:
                new_count += 1
        except Exception as e:
            pass
    
    conn.commit()
    conn.close()
    return new_count


def run_full_scrape(with_google=True):
    """
    Run all scrapers:
    1. Google Jobs (Chrome)
    2. Existing scrapers (WTTJ, WWR, RemoteOK, etc.)
    """
    from scraper import fetch_all_new_sources, save_jobs, fetch_all
    from scraper import _supabase_reachable, export_static_json
    
    all_new = 0
    
    # Step 1: Google Jobs (Chrome)
    if with_google:
        print("\n1️⃣ Google Jobs (Chrome)...")
        google_jobs = scrape_google_all()
        n = dedup_and_merge(google_jobs)
        all_new += n
        print(f"   → {n} nouveaux de Google Jobs")
    
    # Step 2: Existing scrapers
    print("\n2️⃣ Scrapers directs (WTTJ, WWR, etc.)...")
    jobs = fetch_all_new_sources()
    n = save_jobs(jobs)
    all_new += n
    print(f"   → {n} nouveaux des sources directes")
    
    # Step 3: Export + sync to Supabase
    if all_new > 0:
        print("\n3️⃣ Export + sync...")
        export_static_json()
    
    return all_new


if __name__ == "__main__":
    print("=" * 50)
    print("JobHunt Full Scrape (Google Jobs + all sources)")
    print("=" * 50)
    
    start = time.time()
    n = run_full_scrape(with_google=True)
    elapsed = time.time() - start
    
    print(f"\n✅ {n} nouveaux jobs ajoutés ({elapsed:.0f}s)")
    
    # Stats
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    by_source = conn.execute("SELECT source, COUNT(*) as cnt FROM jobs GROUP BY source ORDER BY cnt DESC").fetchall()
    conn.close()
    
    print(f"\n📊 Total: {total} jobs")
    for s, c in by_source:
        print(f"   {s}: {c}")
