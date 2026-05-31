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
import os
import re
import urllib.request
import urllib.error


# ─── Supabase integration ────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    env_path = os.path.expanduser("~/.hermes/.env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("SUPABASE_URL="):
                    SUPABASE_URL = line.split("=", 1)[1].strip().strip("\"'")
                elif line.startswith("SUPABASE_KEY="):
                    SUPABASE_KEY = line.split("=", 1)[1].strip().strip("'\"")

_SUPABASE_BASE = f"{SUPABASE_URL}/rest/v1" if SUPABASE_URL else ""
_SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
} if SUPABASE_KEY else {}


def _supabase_reachable():
    return bool(SUPABASE_URL and SUPABASE_KEY)


def _supabase_bulk_upsert(table, records):
    """Upsert records into Supabase table. Falls back silently on failure."""
    if not _supabase_reachable() or not records:
        return
    for i in range(0, len(records), 100):
        batch = records[i:i+100]
        body = json.dumps(batch).encode()
        req = urllib.request.Request(
            f"{_SUPABASE_BASE}/{table}",
            data=body,
            headers={**_SUPABASE_HEADERS, "Prefer": "resolution=merge-duplicates"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15):
                pass
        except Exception:
            pass  # silent fallback


# ─────────────────────────────────────────────────────────────


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
    {
        "name": "Indeed",
        "url": "https://fr.indeed.com/jobs?q=QA+testeur+test+automation&l=France&jt=freelance_contract",
        "type": "indeed"
    },
    {
        "name": "Comet",
        "url": "https://www.comet.co/fr/freelances/trouver-une-mission",
        "type": "comet"
    },
    {
        "name": "Malt",
        "url": "https://www.malt.fr/search?keyword=QA+test",
        "type": "malt"
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
                                   "software test", "software testing", "test developer",
                                   "engineer in test", "sdet engineer"]
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
                else:
                    # Try to extract salary from description
                    desc = item.get("description", "")
                    # Patterns: $XXk-$YYk, $XX,000-$YY,000, XX€-YY€/day, TJM XXX€, $XX/hr
                    patterns = [
                        r'\$(\d{2,3})k\s*[-–]\s*\$?(\d{2,3})k',              # $80k-$120k
                        r'\$(\d{2,3}[,\d]*)\s*[-–]\s*\$?(\d{2,3}[,\d]*)',     # $80,000-$120,000
                        r'(\d{3,4})\s*[€€]\s*/?\s*(?:day|j(?:our)?)',          # 500€/day, 500€/j
                        r'(?:tjm|TJ[MN]|taux\s+journalier)\s*:?\s*(\d{3,4})\s*[€€]?',  # TJM 500€
                        r'\$(\d{2,3})\s*[-–]\s*\$?(\d{2,3})\s*/hr',            # $50-$70/hr
                        r'(\d{2,3}[kK]?)\s*[-–]\s*(\d{2,3}[kK]?)\s*[€€]',      # 80k-120k€
                    ]
                    for pattern in patterns:
                        m = re.search(pattern, desc)
                        if m:
                            groups = m.groups()
                            if len(groups) == 2:
                                salary = f"${groups[0]}-${groups[1]}"
                            elif len(groups) == 1:
                                salary = f"{groups[0]}€/j"
                            break
                
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


def fetch_wwr_rss():
    """Fetch QA jobs from WWR RSS feed."""
    import xml.etree.ElementTree as ET
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    }
    jobs = []
    filter_keywords = ["qa", "sdet", "quality assurance", "quality engineer",
                       "test engineer", "test automation", "tester",
                       "testing", "automation engineer", "test lead",
                       "test manager", "qa lead", "qa engineer",
                       "software test", "software testing"]
    try:
        resp = requests.get(
            "https://weworkremotely.com/remote-jobs.rss",
            headers=headers, timeout=15
        )
        if resp.status_code == 200:
            root = ET.fromstring(resp.text)
            for item in root.iter("item"):
                title = item.findtext("title", "")
                title_lower = title.lower()
                if not any(k in title_lower for k in filter_keywords):
                    continue
                link = item.findtext("link", "")
                desc = item.findtext("description", "")
                pubdate = item.findtext("pubDate", "")
                jobs.append({
                    "title": title,
                    "company": "",
                    "source": "WWR RSS",
                    "url": link,
                    "location": "Remote",
                    "salary": "",
                    "tags": "",
                    "date": pubdate[:10] if len(pubdate) > 10 else datetime.now().strftime("%Y-%m-%d"),
                    "description": desc,
                    "raw_date": int(time.time()),
                })
        else:
            print(f"  WWR RSS returned {resp.status_code}")
    except Exception as e:
        print(f"  WWR RSS error: {e}")
    return jobs


def fetch_wellfound():
    """Scrape Wellfound (AngelList) for QA/SDET roles.
    Note: Wellfound typically blocks scraping. Falls back gracefully.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    jobs = []
    filter_keywords = ["qa", "sdet", "quality assurance", "quality engineer",
                       "test engineer", "test automation", "tester",
                       "testing", "automation engineer", "qa lead", "qa engineer"]
    urls_to_try = [
        "https://wellfound.com/role/s/quality-assurance",
    ]
    for url in urls_to_try:
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select("div[class*='card'], div[class*='job'], li[class*='job'], article[class*='job']")
                for card in cards[:50]:
                    title_el = card.select_one("a[class*='title'], h2, h3, h4")
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    title_lower = title.lower()
                    if not any(k in title_lower for k in filter_keywords):
                        continue
                    company_el = card.select_one("span[class*='company'], div[class*='company']")
                    company = company_el.get_text(strip=True) if company_el else ""
                    link_el = card.select_one("a[href*='/jobs/'], a[href*='/startups/']")
                    url_val = "https://wellfound.com" + link_el["href"] if link_el and link_el.get("href") else ""
                    if url_val and not url_val.startswith("http"):
                        url_val = "https://wellfound.com" + url_val
                    location_el = card.select_one("span[class*='location'], div[class*='location']")
                    location = location_el.get_text(strip=True) if location_el else "Remote"
                    jobs.append({
                        "title": title, "company": company, "source": "Wellfound",
                        "url": url_val, "location": location, "salary": "", "tags": "",
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "description": "", "raw_date": int(time.time()),
                    })
                if jobs:
                    break  # Found jobs, stop trying
            else:
                print(f"  Wellfound returned {resp.status_code} for {url}")
        except Exception as e:
            print(f"  Wellfound error ({url}): {e}")
    if not jobs:
        print("  Wellfound: 0 jobs (site blocked scraping)")
    return jobs


def fetch_linkedin_rss():
    """Parse LinkedIn RSS for QA jobs.
    Note: LinkedIn RSS feeds are often deprecated/blocked. Falls back gracefully.
    """
    import xml.etree.ElementTree as ET
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    }
    jobs = []
    filter_keywords = ["qa", "sdet", "quality assurance", "quality engineer",
                       "test engineer", "test automation", "tester",
                       "testing", "automation engineer", "qa lead", "qa engineer"]
    urls_to_try = [
        "https://www.linkedin.com/jobs/search/rss?keywords=QA+Engineer&location=Remote",
    ]
    for url in urls_to_try:
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                root = ET.fromstring(resp.text)
                for item in root.iter("item"):
                    title = item.findtext("title", "")
                    title_lower = title.lower()
                    if not any(k in title_lower for k in filter_keywords):
                        continue
                    link = item.findtext("link", "")
                    desc = item.findtext("description", "")
                    company = ""
                    location = "Remote"
                    title_clean = title
                    if " at " in title:
                        parts = title.split(" at ", 1)
                        title_clean = parts[0].strip()
                        company = parts[1].strip()
                    jobs.append({
                        "title": title_clean,
                        "company": company, "source": "LinkedIn RSS",
                        "url": link, "location": location, "salary": "", "tags": "",
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "description": desc, "raw_date": int(time.time()),
                    })
                if jobs:
                    break
            else:
                print(f"  LinkedIn RSS returned {resp.status_code}")
        except Exception as e:
            print(f"  LinkedIn RSS error: {e}")
    if not jobs:
        print("  LinkedIn RSS: 0 jobs (RSS may be unavailable)")
    return jobs


def fetch_jobboard_io():
    """Scrape jobboard.io for QA roles."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    }
    jobs = []
    filter_keywords = ["qa", "sdet", "quality assurance", "quality engineer",
                       "test engineer", "test automation", "tester",
                       "testing", "automation engineer", "qa lead", "qa engineer"]
    try:
        resp = requests.get(
            "https://remoteok.com/remote-quality-assurance-jobs",
            headers=headers, timeout=15
        )
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for tr in soup.select("tr.job")[:50]:
                title_el = tr.select_one("td[class*='position'] h2, a[class*='title']")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                title_lower = title.lower()
                if not any(k in title_lower for k in filter_keywords):
                    continue
                company_el = tr.select_one("span[class*='company'], div[class*='company']")
                company = company_el.get_text(strip=True) if company_el else ""
                link_el = title_el if title_el.name == "a" else title_el.select_one("a")
                url = link_el["href"] if link_el and link_el.get("href") else ""
                if url and not url.startswith("http"):
                    url = "https://remoteok.com" + url
                jobs.append({
                    "title": title, "company": company, "source": "JobBoard.io",
                    "url": url, "location": "Remote", "salary": "", "tags": "",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "description": "", "raw_date": int(time.time()),
                })
        else:
            print(f"  JobBoard.io returned {resp.status_code}")
    except Exception as e:
        print(f"  JobBoard.io error: {e}")
    return jobs


def fetch_otta():
    """Scrape Otta.com for QA/SDET roles.
    Note: Otta may return 404 for some URLs as they use JS rendering.
    Falls back gracefully.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    }
    jobs = []
    filter_keywords = ["qa", "sdet", "quality assurance", "quality engineer",
                       "test engineer", "test automation", "tester",
                       "testing", "automation engineer", "qa lead", "qa engineer"]
    urls_to_try = [
        "https://otta.com/jobs?role=quality-assurance",
    ]
    for url in urls_to_try:
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select("a[href*='/jobs/'], div[class*='job-card'], article")
                for card in cards[:50]:
                    title_el = card.select_one("h2, h3, h4, span[class*='title']")
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    title_lower = title.lower()
                    if not any(k in title_lower for k in filter_keywords):
                        continue
                    company_el = card.select_one("span[class*='company'], div[class*='company'], p[class*='company']")
                    company = company_el.get_text(strip=True) if company_el else ""
                    href = card.get("href") if card.name == "a" else ""
                    if not href:
                        link_el = card.select_one("a[href*='/jobs/']")
                        href = link_el["href"] if link_el else ""
                    url_val = "https://otta.com" + href if href and not href.startswith("http") else href
                    jobs.append({
                        "title": title, "company": company, "source": "Otta",
                        "url": url_val, "location": "Remote", "salary": "", "tags": "",
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "description": "", "raw_date": int(time.time()),
                    })
                if jobs:
                    break
            else:
                if resp.status_code not in [404, 403]:
                    print(f"  Otta returned {resp.status_code}")
        except Exception as e:
            print(f"  Otta error: {e}")
    if not jobs:
        print("  Otta: 0 jobs (may require JS rendering)")
    return jobs


def fetch_freework():
    """Fetch QA freelance jobs from Free-Work (French marketplace)."""
    import urllib.parse
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    jobs = []
    filter_keywords = ["qa", "sdet", "quality assurance", "quality engineer",
                       "test engineer", "test automation", "tester",
                       "testing", "automation engineer", "qa lead", "qa engineer",
                       "test lead", "testeur", "recette", "qualité", "qualite",
                       "software test", "software testing", "test developer"]

    try:
        resp = requests.get(
            "https://www.free-work.com/api/job_postings",
            headers=headers, timeout=15
        )
        if resp.status_code == 200:
            data = resp.json()
            for item in data:
                title = item.get("title", "")
                title_lower = title.lower()
                if not any(k in title_lower for k in filter_keywords):
                    continue

                company = ""
                if isinstance(item.get("company"), dict):
                    company = item["company"].get("name", "")

                location = ""
                loc_obj = item.get("location", {})
                if isinstance(loc_obj, dict):
                    loc_label = loc_obj.get("label", "")
                    loc_country = loc_obj.get("country", "")
                    location = f"{loc_label}" if loc_label else loc_country

                # Build URL
                slug = item.get("slug", "")
                url = f"https://www.free-work.com/fr/tech-it/job-mission/{slug}" if slug else ""

                # Extract salary
                salary = ""
                min_daily = item.get("minDailySalary")
                max_daily = item.get("maxDailySalary")
                currency = item.get("currency", "EUR")
                if min_daily or max_daily:
                    if min_daily and max_daily:
                        salary = f"{min_daily} - {max_daily} {currency}/jour"
                    elif min_daily:
                        salary = f"From {min_daily} {currency}/jour"
                    elif max_daily:
                        salary = f"Up to {max_daily} {currency}/jour"

                # Tags/skills
                skills = item.get("skills", [])
                tags = ", ".join(s.get("name", "") for s in skills if isinstance(s, dict)) if skills else ""

                # Description
                desc = item.get("description", "") or ""
                candidate = item.get("candidateProfile", "") or ""
                full_desc = f"{desc}\n{candidate}".strip()

                # Date
                created = item.get("createdAt", "")
                date = created[:10] if created else datetime.now().strftime("%Y-%m-%d")

                # Contract type
                contracts = item.get("contracts", [])
                contract_type = ""
                if isinstance(contracts, list):
                    for c in contracts:
                        if isinstance(c, dict):
                            ct = c.get("name", "").lower()
                            if "freelance" in ct:
                                contract_type = "freelance"
                            elif "contract" in ct:
                                contract_type = "contract"

                jobs.append({
                    "title": title,
                    "company": company, "source": "Free-Work",
                    "url": url, "location": location, "salary": salary,
                    "tags": tags, "description": full_desc,
                    "date": date, "raw_date": int(time.time()),
                    "contract_type": contract_type or "freelance",
                })

        if not jobs:
            print("  Free-Work: 0 QA jobs found")
    except Exception as e:
        print(f"  Free-Work error: {e}")

    return jobs

# ─── French-specific scrapers ──────────────────────────────────────

def fetch_lesjeudis():
    """Fetch QA freelance jobs from LesJeudis (French IT freelance platform) via __NEXT_DATA__ JSON."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }
    jobs = []
    filter_keywords = ["qa", "sdet", "quality assurance", "quality engineer",
                       "test", "tester", "testing", "automation",
                       "testeur", "recette", "qualite"]

    try:
        resp = requests.get(
            "https://www.lesjeudis.com/recherche?q=QA&type=Mission&field=IT",
            headers=headers, timeout=15
        )
        if resp.status_code != 200:
            print(f"  LesJeudis error: HTTP {resp.status_code}")
            return jobs

        # Extract __NEXT_DATA__ JSON from the script tag
        match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            resp.text, re.DOTALL
        )
        if not match:
            print("  LesJeudis: __NEXT_DATA__ script tag not found")
            return jobs

        data = json.loads(match.group(1))
        apollo_state = data.get("props", {}).get("pageProps", {}).get("__APOLLO_STATE__", {})
        if not apollo_state:
            print("  LesJeudis: __APOLLO_STATE__ not found in page props")
            return jobs

        # Walk all Apollo cache entries looking for Job: prefixed keys
        for key, entry in apollo_state.items():
            if not key.startswith("Job:"):
                continue
            if not isinstance(entry, dict):
                continue
            # Must have title, slug, locationText
            title = entry.get("title")
            slug = entry.get("slug")
            location_text = entry.get("locationText")
            if not title or not slug:
                continue

            title_lower = title.lower()
            if not any(k in title_lower for k in filter_keywords):
                continue

            # Company: dict with 'name' key, might be {} empty
            company_dict = entry.get("company") or {}
            company = company_dict.get("name", "") if isinstance(company_dict, dict) else ""

            # Build URL from slug
            url = f"https://lesjeudis.com/jobs/{slug}"

            location = location_text if location_text else "France"

            jobs.append({
                "title": title, "company": company, "source": "LesJeudis",
                "url": url, "location": location, "salary": "", "tags": "",
                "description": "", "date": datetime.now().strftime("%Y-%m-%d"),
                "raw_date": int(time.time()),
            })

    except json.JSONDecodeError as e:
        print(f"  LesJeudis JSON parse error: {e}")
    except Exception as e:
        print(f"  LesJeudis error: {e}")

    if not jobs:
        print("  LesJeudis: 0 jobs")
    return jobs


def fetch_optioncarriere():
    """Fetch QA jobs from Optioncarriere (French job aggregator).

    NOTE: Optioncarriere uses Cloudflare Turnstile anti-bot protection.
    The correct search URL is /recherche/emplois (not /recherche/s-emplois).
    This function tries cloudscraper first (better at bypassing), then falls
    back to plain requests if cloudscraper is unavailable.
    """
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "darwin", "desktop": True}
        )
        use_scraper = True
    except ImportError:
        scraper = requests
        use_scraper = False

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html",
    }
    jobs = []
    filter_keywords = ["qa", "sdet", "quality assurance", "quality engineer",
                       "test automate", "test engineer", "tester",
                       "software test", "testeur", "recette", "qualite"]

    try:
        url = "https://www.optioncarriere.com/recherche/emplois?q=QA&l=France&t=freelance"
        resp = scraper.get(url, headers=headers, timeout=20)
        if resp.status_code != 200:
            print(f"  Optioncarriere: HTTP {resp.status_code}")
            return jobs

        soup = BeautifulSoup(resp.text, "html.parser")

        # Check if Cloudflare blocked us
        if "turnstile" in resp.text.lower() or "trafic inhabituel" in resp.text.lower():
            print("  Optioncarriere: blocked by Cloudflare Turnstile")
            return jobs

        # Select job articles — structure: ul.jobs > li > article.job
        # or article.job directly on search results page
        cards = soup.select("article.job")
        if not cards:
            cards = soup.select("ul.jobs > li > article.job")
        if not cards:
            # Fallback: look inside any jobs section
            jobs_section = soup.select_one("section.jobs-contextual, .jobs-list, [class*=result]")
            if jobs_section:
                cards = jobs_section.select("article.job")

        for card in cards:
            # Title & URL
            title_el = card.select_one("header h3 a")
            if not title_el:
                # Fallback: any a with title attribute
                title_el = card.select_one("a[title], h3 a, h2 a")
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            title_lower = title.lower()
            if not any(k in title_lower for k in filter_keywords):
                continue

            url_href = title_el.get("href", "")
            if url_href and not url_href.startswith("http"):
                url_href = "https://www.optioncarriere.com" + url_href

            # Company
            company_el = card.select_one("p.company, .company, [class*=company]")
            company = company_el.get_text(strip=True) if company_el else ""

            # Location: ul.location li contains SVG + text node
            location_el = card.select_one("ul.location li")
            location = ""
            if location_el:
                # Get text, stripping out SVG content
                for tag in location_el.find_all(["svg", "use"]):
                    tag.decompose()
                location = location_el.get_text(strip=True)
            if not location:
                location_el = card.select_one(".location, .place, .city")
                location = location_el.get_text(strip=True) if location_el else "France"

            # Salary (nice to have)
            salary_el = card.select_one("ul.salary li")
            salary = ""
            if salary_el:
                for tag in salary_el.find_all(["svg", "use"]):
                    tag.decompose()
                salary = salary_el.get_text(strip=True)

            jobs.append({
                "title": title, "company": company, "source": "Optioncarriere",
                "url": url_href, "location": location, "salary": salary, "tags": "",
                "description": "", "date": datetime.now().strftime("%Y-%m-%d"),
                "raw_date": int(time.time()),
            })

    except Exception as e:
        print(f"  Optioncarriere error: {e}")

    if not jobs:
        print("  Optioncarriere: 0 jobs (site blocked by Cloudflare Turnstile)")
    return jobs


def parse_relative_date(text):
    """Parse LinkedIn-style relative dates like '1 week ago', '2 days ago', '30+ min ago'.
    Returns YYYY-MM-DD string, or today if unparseable.
    """
    from datetime import timedelta
    if not text:
        return datetime.now().strftime("%Y-%m-%d"), int(time.time())
    text = text.strip().lower()
    import re
    # Patterns: "X day(s) ago", "X week(s) ago", "X month(s) ago", "X hour(s) ago"
    m = re.search(r'(\d+)\s*(d|day|days|h|hour|hours|min|minute|minutes|week|weeks|month|months)\s*ago', text)
    if m:
        num = int(m.group(1))
        unit = m.group(2)
        now = datetime.now()
        if unit in ('d', 'day', 'days'):
            delta = timedelta(days=num)
        elif unit in ('h', 'hour', 'hours', 'min', 'minute', 'minutes'):
            delta = timedelta(days=0)  # today for hours/minutes
        elif unit in ('week', 'weeks'):
            delta = timedelta(weeks=num)
        elif unit in ('month', 'months'):
            delta = timedelta(days=num * 30)
        else:
            delta = timedelta(days=0)
        dt = now - delta
        return dt.strftime("%Y-%m-%d"), int(dt.timestamp())
    # "just now", "moments ago", "today"
    if any(k in text for k in ('just now', 'moments ago', 'today', 'now')):
        return datetime.now().strftime("%Y-%m-%d"), int(time.time())
    return datetime.now().strftime("%Y-%m-%d"), int(time.time())


def fetch_linkedin_guest(country, location_query, keywords="QA"):
    """Fetch jobs from LinkedIn guest search API for a specific country."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html",
    }
    jobs = []
    from bs4 import BeautifulSoup

    filter_keywords = ["qa", "sdet", "quality assurance", "quality engineer",
                       "test engineer", "test automation", "tester",
                       "testing", "automation engineer", "qa lead", "qa engineer",
                       "test lead", "test manager"]

    encoded_location = requests.utils.quote(location_query)
    encoded_keywords = requests.utils.quote(keywords)
    urls = [
        f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={encoded_keywords}&location={encoded_location}",
        f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={encoded_keywords}&location={encoded_location}&f_WT=2",
    ]

    for url in urls:
        if jobs:
            break
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("div", class_="base-card")

            for card in cards:
                try:
                    title_el = card.find("span", class_="sr-only")
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    title_lower = title.lower()
                    if not any(k in title_lower for k in filter_keywords):
                        continue

                    link_el = card.find("a", class_="base-card__full-link")
                    url = link_el["href"] if link_el and link_el.has_attr("href") else ""

                    # Extract company name from the card
                    company_el = card.find("a", class_="hidden-nested-link")
                    company = company_el.get_text(strip=True) if company_el else ""

                    # Location
                    location_el = card.find("span", class_="job-search-card__location")
                    location = location_el.get_text(strip=True) if location_el else location_query

                    # Extract real publication date from <time> element
                    time_el = card.find("time")
                    date_str = datetime.now().strftime("%Y-%m-%d")
                    raw_date = int(time.time())
                    if time_el:
                        time_text = time_el.get_text(strip=True)
                        date_str, raw_date = parse_relative_date(time_text)

                    jobs.append({
                        "title": title, "company": company, "source": f"LinkedIn {country}",
                        "url": url, "location": location, "salary": "", "tags": "",
                        "description": "", "date": date_str,
                        "raw_date": raw_date,
                    })
                except Exception:
                    continue
        except Exception as e:
            print(f"  LinkedIn {country} error: {e}")

    return jobs


def fetch_linkedin_countries():
    """Fetch QA jobs from LinkedIn for target countries."""
    all_jobs = []
    countries = {
        "France": "France",
        "Suisse": "Switzerland",
        "Luxembourg": "Luxembourg",
        "Dubaï": "Dubai",
        "Singapour": "Singapore",
    }
    for country_name, location in countries.items():
        try:
            jobs = fetch_linkedin_guest(country_name, location)
            all_jobs.extend(jobs)
            print(f"  LinkedIn {country_name}: {len(jobs)} jobs")
            time.sleep(1.5)  # Be nice to LinkedIn
        except Exception as e:
            print(f"  LinkedIn {country_name}: Error {e}")
    return all_jobs


def compute_freshness_score(date_str):
    """Return freshness score A-D based on how recent the date is.
    A = today or yesterday
    B = 2-3 days ago
    C = 4-7 days ago
    D = 7+ days ago
    """
    if not date_str:
        return "D"
    try:
        if isinstance(date_str, (int, float)):
            job_date = datetime.fromtimestamp(date_str).date()
        else:
            # Try common formats
            for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
                try:
                    job_date = datetime.strptime(str(date_str)[:19], fmt).date()
                    break
                except ValueError:
                    continue
            else:
                # Try parsing with dateutil-style flexibility
                job_date = datetime.fromisoformat(str(date_str)[:19]).date() if "T" in str(date_str) else datetime.strptime(str(date_str)[:10], "%Y-%m-%d").date()
    except Exception:
        return "D"
    
    today = datetime.now().date()
    diff = (today - job_date).days
    
    if diff < 0:
        return "A"  # Future date = fresh
    if diff <= 1:
        return "A"
    if diff <= 3:
        return "B"
    if diff <= 7:
        return "C"
    return "D"


def fetch_wttj():
    """Fetch QA jobs from Welcome to the Jungle using their Algolia search API.

    WTTJ rebranded from welcome-to-the-jungle.com to welcometothejungle.com.
    The old GraphQL API no longer exists. The new site uses Algolia for job
    search with a publicly accessible API key.
    """
    algolia_app_id = "CSEKHVMS53"
    algolia_api_key = "4bd8f6215d0cc52b26430765769e65a0"
    algolia_index = "wttj_jobs_production_fr"

    # QA/testing profession sub-category reference from Algolia
    qa_sub_category = "quality-assurance-and-testing-hNDAz"

    jobs = []

    # Algolia returns max 1000 hits total; fetch up to 200 QA jobs across pages
    hits_per_page = 100
    max_pages = 2

    for page in range(max_pages):
        try:
            resp = requests.post(
                f"https://{algolia_app_id}-dsn.algolia.net/1/indexes/{algolia_index}/query",
                json={
                    "params": (
                        f"query="
                        f"&hitsPerPage={hits_per_page}"
                        f"&page={page}"
                        f"&filters=new_profession.sub_category_reference:{qa_sub_category}"
                        f"&attributesToRetrieve="
                        f"name,slug,organization.name,organization.slug,"
                        f"published_at,published_at_date,"
                        f"offices,salary_minimum,salary_maximum,"
                        f"salary_currency,salary_period,remote,contract_type,"
                        f"summary,new_profession,has_remote,"
                        f"experience_level_minimum"
                    )
                },
                headers={
                    "Content-Type": "application/json",
                    "X-Algolia-API-Key": algolia_api_key,
                    "X-Algolia-Application-Id": algolia_app_id,
                    "Referer": "https://www.welcometothejungle.com/fr/jobs",
                    "Origin": "https://www.welcometothejungle.com",
                },
                timeout=20,
            )

            if resp.status_code != 200:
                print(f"  WTTJ Algolia returned {resp.status_code}: {resp.text[:200]}")
                break

            data = resp.json()
            hits = data.get("hits", [])
            if not hits:
                break

            for hit in hits:
                title = hit.get("name", "")
                org = hit.get("organization", {}) or {}
                company = org.get("name", "")

                org_slug = org.get("slug", "")
                job_slug = hit.get("slug", "")
                if org_slug and job_slug:
                    url = f"https://www.welcometothejungle.com/fr/companies/{org_slug}/jobs/{job_slug}"
                else:
                    url = ""

                # Location from offices array
                offices = hit.get("offices", []) or []
                if offices:
                    location = ", ".join(
                        filter(None, [
                            o.get("city", "").strip()
                            for o in offices
                            if o.get("city")
                        ])
                    )
                    if not location:
                        countries = set(
                            o.get("country_code", "") for o in offices if o.get("country_code")
                        )
                        location = ", ".join(sorted(countries))
                else:
                    location = "Remote"

                remote = hit.get("remote", "")
                if remote:
                    location += f" ({remote})"

                # Salary
                salary = ""
                min_sal = hit.get("salary_minimum")
                max_sal = hit.get("salary_maximum")
                currency = hit.get("salary_currency", "EUR")
                period = hit.get("salary_period", "yearly")
                if min_sal or max_sal:
                    period_label = "/yr" if period == "yearly" else "/mo"
                    if min_sal and max_sal:
                        if min_sal == max_sal:
                            salary = f"{min_sal:,.0f} {currency}{period_label}"
                        else:
                            salary = f"{min_sal:,.0f} - {max_sal:,.0f} {currency}{period_label}"
                    elif min_sal:
                        salary = f"From {min_sal:,.0f} {currency}{period_label}"
                    elif max_sal:
                        salary = f"Up to {max_sal:,.0f} {currency}{period_label}"

                # Contract type as tags
                tags = ""
                contract_type = hit.get("contract_type", "")
                contract_labels = {
                    "full_time": "Full-time",
                    "part_time": "Part-time",
                    "internship": "Internship",
                    "apprenticeship": "Apprenticeship",
                    "freelance": "Freelance",
                    "temporary": "Temporary",
                    "contract": "Contract",
                    "other": "Other",
                    "vie": "VIE",
                }
                if contract_type:
                    tags = contract_labels.get(contract_type, contract_type)

                # Description (summary + key missions)
                description = hit.get("summary", "") or ""
                key_missions = hit.get("key_missions", []) or []
                if key_missions:
                    if description:
                        description += "\n\nKey missions:\n"
                    else:
                        description = "Key missions:\n"
                    description += "\n".join(f"- {m}" for m in key_missions)

                # Date
                published = hit.get("published_at", "") or ""
                date = published[:10] if published else datetime.now().strftime("%Y-%m-%d")
                raw_date = 0
                if published:
                    try:
                        raw_date = int(datetime.fromisoformat(published.replace("Z", "+00:00")).timestamp())
                    except Exception:
                        raw_date = int(time.time())
                else:
                    raw_date = int(time.time())

                jobs.append({
                    "title": title,
                    "company": company,
                    "source": "WTTJ",
                    "url": url,
                    "location": location,
                    "salary": salary,
                    "tags": tags,
                    "date": date,
                    "description": description,
                    "raw_date": raw_date,
                })

            # Stop if we've hit the last page
            page_count = data.get("nbPages", 0)
            if page + 1 >= page_count:
                break

        except Exception as e:
            print(f"  WTTJ Algolia error (page {page}): {e}")
            break

    if not jobs:
        print("  WTTJ: 0 jobs found")
    else:
        print(f"  WTTJ: {len(jobs)} QA jobs fetched via Algolia")
    return jobs


def fetch_francetravail():
    """Fetch QA jobs from France Travail (ex Pôle Emploi) API.

    The old API at api.pole-emploi-dsp.fr no longer resolves (DNS failure).
    The new API at api.francetravail.io requires OAuth2 authentication via
    client credentials (client_id + client_secret). To use it, register at
    https://developer.francetravail.io and set FRANCE_TRAVAIL_CLIENT_ID and
    FRANCE_TRAVAIL_CLIENT_SECRET environment variables, or pre-fetch a token
    and set FRANCE_TRAVAIL_ACCESS_TOKEN.
    """
    jobs = []
    filter_keywords = ["qa", "sdet", "quality assurance", "quality engineer",
                       "test engineer", "test automation", "tester",
                       "testing", "automation engineer", "test lead",
                       "test manager", "qa lead", "qa engineer",
                       "testeur", "recette", "qualite", "qualité",
                       "testeur logiciel", "testeur QA", "test automatise"]

    # Check for France Travail API credentials
    client_id = os.environ.get("FRANCE_TRAVAIL_CLIENT_ID", "")
    client_secret = os.environ.get("FRANCE_TRAVAIL_CLIENT_SECRET", "")
    access_token = os.environ.get("FRANCE_TRAVAIL_ACCESS_TOKEN", "")

    if not access_token and (not client_id or not client_secret):
        print("  France Travail: API requires OAuth2 authentication. Set FRANCE_TRAVAIL_CLIENT_ID and")
        print("    FRANCE_TRAVAIL_CLIENT_SECRET env vars, or FRANCE_TRAVAIL_ACCESS_TOKEN.")
        print("    Register at https://developer.francetravail.io to obtain credentials.")
        print("  France Travail: 0 jobs (no API credentials configured)")
        return jobs

    try:
        # Obtain access token if not already set
        if not access_token:
            token_resp = requests.post(
                "https://api.francetravail.io/partenaire/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "scope": "api_offresdemploiv2 o2dsoffre",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15,
            )
            if token_resp.status_code != 200:
                print(f"  France Travail: failed to obtain access token (HTTP {token_resp.status_code})")
                print(f"  France Travail: 0 jobs (authentication failure)")
                return jobs
            token_data = token_resp.json()
            access_token = token_data.get("access_token", "")
            if not access_token:
                print("  France Travail: access token not found in response")
                print("  France Travail: 0 jobs (authentication failure)")
                return jobs

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        resp = requests.get(
            "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search",
            params={
                "motsCles": "QA OR testeur OR test OR assurance qualité",
                "typeContrat": "MIS,CDI,CDD",  # Mission, CDI, CDD
                "rayon": "50",
                "domaine": "M17",  # Informatique
                "dureeHebdo": "35",
            },
            headers=headers,
            timeout=20,
        )
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("resultats", []) if isinstance(data, dict) else data if isinstance(data, list) else []
            for item in results:
                title = item.get("intitule", "") or item.get("title", "")
                title_lower = title.lower()
                if not any(k in title_lower for k in filter_keywords):
                    continue

                company = ""
                entreprise = item.get("entreprise", {}) if isinstance(item.get("entreprise"), dict) else {}
                if entreprise:
                    company = entreprise.get("nom", "") or entreprise.get("name", "")
                if not company:
                    company = item.get("nomEntreprise", "") or ""

                # URL - France Travail jobs have detail pages
                job_id = item.get("id") or item.get("origineOffre", {}).get("id", "")
                url = f"https://candidat.francetravail.fr/offre/recherche/detail/{job_id}" if job_id else ""

                # Location
                lieu = item.get("lieuTravail", {}) if isinstance(item.get("lieuTravail"), dict) else {}
                location = ""
                if lieu:
                    commune = lieu.get("libelle", "") or lieu.get("ville", "")
                    if commune:
                        location = commune
                if not location:
                    location = "France"

                # Check for remote
                remote = item.get("télétravail", "") or item.get("teletravail", "") or item.get("remote", "")
                if remote or "remote" in str(remote).lower() or "tele" in str(remote).lower():
                    location = "Remote / " + location

                # Salary
                salary = ""
                salaire = item.get("salaire", {}) if isinstance(item.get("salaire"), dict) else {}
                if salaire:
                    libelle = salaire.get("libelle", "") or salaire.get("commentaire", "")
                    if libelle:
                        salary = libelle

                # Description
                description = item.get("description", "") or item.get("intitule", "")

                # Date
                date_publication = item.get("dateCreation", "") or item.get("datePublication", "") or item.get("dateActualisation", "")
                date = date_publication[:10] if date_publication else datetime.now().strftime("%Y-%m-%d")
                raw_date = int(time.time())
                if date_publication:
                    try:
                        raw_date = int(datetime.fromisoformat(date_publication.replace("Z", "+00:00")).timestamp())
                    except Exception:
                        pass

                jobs.append({
                    "title": title,
                    "company": company,
                    "source": "FranceTravail",
                    "url": url,
                    "location": location,
                    "salary": salary,
                    "tags": "",
                    "date": date,
                    "description": description,
                    "raw_date": raw_date,
                })
        elif resp.status_code == 401:
            print("  France Travail: API returned 401 Unauthorized")
            print("    The API requires OAuth2 authentication. Set FRANCE_TRAVAIL_CLIENT_ID and")
            print("    FRANCE_TRAVAIL_CLIENT_SECRET env vars, or FRANCE_TRAVAIL_ACCESS_TOKEN.")
            print("    Register at https://developer.francetravail.io to obtain credentials.")
        else:
            print(f"  France Travail: API returned HTTP {resp.status_code}")
            try:
                err_detail = resp.json()
                print(f"    Detail: {err_detail}")
            except Exception:
                print(f"    Response: {resp.text[:200]}")
    except requests.exceptions.ConnectionError as e:
        print(f"  France Travail: connection error - {e}")
    except Exception as e:
        print(f"  France Travail: error - {e}")

    if not jobs:
        print("  France Travail: 0 jobs found")
    return jobs


def fetch_remotive():
    """Fetch QA/SDET jobs from Remotive API."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }
    jobs = []
    filter_keywords = ["qa", "sdet", "quality assurance", "quality engineer",
                       "test engineer", "test automation", "tester",
                       "testing", "automation engineer", "test lead",
                       "test manager", "qa lead", "qa engineer",
                       "software test", "software testing", "test developer",
                       "engineer in test", "sdet engineer",
                       "quality analyst", "qa analyst"]

    try:
        # Remotive has a simple JSON API - first get software-dev category then filter
        resp = requests.get(
            "https://remotive.com/api/remote-jobs",
            params={"category": "software-dev", "limit": 100},
            headers=headers,
            timeout=20,
        )
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("jobs", [])
            for item in results:
                title = item.get("title", "")
                title_lower = title.lower()
                if not any(k in title_lower for k in filter_keywords):
                    continue

                company = item.get("company_name", "")
                url = item.get("url", "") or item.get("apply_url", "")
                if not url:
                    url = f"https://remotive.com/remote-jobs/{item.get('id', '')}"

                # Location
                location = item.get("candidate_required_location", "") or "Remote"
                if not location or location.lower() in ("anywhere", "remote", "worldwide"):
                    location = "Remote"

                # Salary
                salary = item.get("salary", "") or ""

                # Tags
                tags_list = item.get("tags", []) or []
                tags = ", ".join(tags_list) if isinstance(tags_list, list) else str(tags_list)

                # Description
                description = item.get("description", "") or ""

                # Date
                pub_date = item.get("publication_date", "")
                date = pub_date[:10] if pub_date else datetime.now().strftime("%Y-%m-%d")
                raw_date = int(time.time())
                if pub_date:
                    try:
                        raw_date = int(datetime.fromisoformat(pub_date.replace("Z", "+00:00")).timestamp())
                    except Exception:
                        pass

                jobs.append({
                    "title": title,
                    "company": company,
                    "source": "Remotive",
                    "url": url,
                    "location": location,
                    "salary": salary,
                    "tags": tags,
                    "date": date,
                    "description": description,
                    "raw_date": raw_date,
                })
        else:
            print(f"  Remotive API returned {resp.status_code}")
    except Exception as e:
        print(f"  Remotive error: {e}")

    if not jobs:
        print("  Remotive: 0 QA jobs found")
    return jobs


def fetch_hn_whoishiring():
    """Fetch QA/testing job mentions from Hacker News 'Who is Hiring' thread.
    Uses Algolia API to find the latest thread, then fetches comments via Firebase API.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }
    jobs = []
    filter_keywords = ["qa", "sdet", "quality assurance", "quality engineer",
                       "test engineer", "test automation", "tester",
                       "testing", "automation engineer", "test lead",
                       "test manager", "qa lead", "qa engineer",
                       "software test", "software testing", "test developer",
                       "engineer in test", "sdet engineer", "quality analyst",
                       "manual test", "automation test"]

    try:
        # Step 1: Find the latest 'Who is hiring?' thread via Algolia
        algolia_resp = requests.get(
            "https://hn.algolia.com/api/v1/search_by_date",
            params={
                "tags": "ask_hn",
                "query": "who is hiring",
                "hitsPerPage": 1,
            },
            headers=headers,
            timeout=15,
        )
        if algolia_resp.status_code != 200:
            print(f"  HN Algolia returned {algolia_resp.status_code}")
            return jobs

        algolia_data = algolia_resp.json()
        hits = algolia_data.get("hits", [])
        if not hits:
            # Fallback: use the known May 2026 thread
            print("  HN Hiring: No Algolia results, using fallback thread")
            thread_id = "42328932"
            thread_title = "Ask HN: Who is hiring? (May 2026)"
            thread_date = "2026-05-01"
        else:
            hit = hits[0]
            thread_id = hit.get("objectID", "42328932")
            thread_title = hit.get("title", "Who is hiring?")
            created_at = hit.get("created_at", "")
            thread_date = created_at[:10] if created_at else "2026-05-01"

        # Step 2: Fetch comments from the thread via Firebase API
        firebase_url = f"https://hacker-news.firebaseio.com/v0/item/{thread_id}.json"
        thread_resp = requests.get(firebase_url, headers=headers, timeout=15)
        if thread_resp.status_code != 200:
            print(f"  HN Firebase returned {thread_resp.status_code}")
            return jobs

        thread_data = thread_resp.json()
        kid_ids = thread_data.get("kids", [])

        # Step 3: Fetch each top-level comment and parse for QA/testing mentions
        for kid_id in kid_ids[:100]:  # Limit to 100 top-level comments
            try:
                comment_resp = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{kid_id}.json",
                    headers=headers,
                    timeout=10,
                )
                if comment_resp.status_code != 200:
                    continue

                comment_data = comment_resp.json()
                text = comment_data.get("text", "") or ""
                text_lower = text.lower()

                if not any(k in text_lower for k in filter_keywords):
                    continue

                # Extract company name (usually at the start or in bold)
                company = ""
                # Try to find company name - often in bold or at start of comment
                company_match = re.search(r'<b>(.*?)</b>', text)
                if company_match:
                    company = BeautifulSoup(company_match.group(0), "html.parser").get_text(strip=True)
                if not company:
                    # First line before a pipe or newline often has the company
                    first_line = text.split("\n")[0] if "\n" in text else text
                    first_line = re.sub(r'<[^>]+>', '', first_line).strip()
                    if first_line and len(first_line) < 100:
                        company = first_line

                # Extract title - often part of the text mentioning "QA" keywords
                title = "QA/Testing role"
                # Try to find a more specific title
                sentences = re.split(r'[.|;|\n]', text)
                for sent in sentences:
                    sent_clean = re.sub(r'<[^>]+>', '', sent).strip()
                    sent_lower = sent_clean.lower()
                    if any(k in sent_lower for k in filter_keywords):
                        title = sent_clean[:100]  # First matching sentence
                        break

                # Build URL
                url = f"https://news.ycombinator.com/item?id={kid_id}"

                # Date from the thread
                comment_time = comment_data.get("time", 0)
                if comment_time:
                    comment_date = datetime.fromtimestamp(comment_time).strftime("%Y-%m-%d")
                    raw_date = int(comment_time)
                else:
                    comment_date = thread_date
                    raw_date = int(time.time())

                # Clean HTML from text for description
                desc_soup = BeautifulSoup(text, "html.parser")
                clean_desc = desc_soup.get_text(separator="\n", strip=True)

                jobs.append({
                    "title": title,
                    "company": company,
                    "source": "HN Hiring",
                    "url": url,
                    "location": "Remote (HN)",
                    "salary": "",
                    "tags": "HN, WhoIsHiring",
                    "date": comment_date,
                    "description": clean_desc[:500] if clean_desc else "",
                    "raw_date": raw_date,
                })
            except Exception:
                continue

    except Exception as e:
        print(f"  HN Hiring error: {e}")

    if not jobs:
        print("  HN Hiring: 0 QA job mentions found")
    return jobs


def fetch_indeed():
    """Fetch QA freelance/contract jobs from Indeed France.
    
    Primary: Scrape fr.indeed.com with requests+BeautifulSoup.
    Fallback: Indeed RSS feed when captcha/block page detected.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    }
    jobs = []
    filter_keywords = ["qa", "sdet", "quality assurance", "quality engineer",
                       "test", "tester", "testing", "automation",
                       "testeur", "recette", "qualite"]

    # ── Helper: check if a response is a block/captcha page ──
    def is_block_page(html_text):
        indicators = [
            "captcha", "cf-challenge", "challenge-platform",
            "verify you are human", "please verify you are a human",
            "are you a human", "attention required", "unusual traffic",
            "enable javascript", "please enable javascript",
            "access denied", "blocked", "cf-browser-verify",
        ]
        lower = html_text.lower()
        return any(ind in lower for ind in indicators)

    # ── Helper: filter and append job dicts ──
    def add_job(title, company, url, location, salary):
        title_lower = title.lower()
        if not any(k in title_lower for k in filter_keywords):
            return
        if url and not url.startswith("http"):
            url = "https://fr.indeed.com" + url
        jobs.append({
            "title": title, "company": company, "source": "Indeed",
            "url": url, "location": location, "salary": salary,
            "tags": "", "description": "", "date": datetime.now().strftime("%Y-%m-%d"),
            "raw_date": int(time.time()),
        })

    # ── Primary: scrape Indeed HTML ──
    try:
        base_url = "https://fr.indeed.com/jobs"
        params = {
            "q": "QA+testeur+test+automation",
            "l": "France",
            "jt": "freelance_contract",
        }
        resp = requests.get(base_url, params=params, headers=headers, timeout=20)
        text = resp.text

        if resp.status_code != 200 or is_block_page(text):
            # Indeed blocked us – attempt fallback
            print("  Indeed: blocked or captcha (status %s), trying RSS fallback..." % resp.status_code)
            raise BlockingIOError("Blocked")

        soup = BeautifulSoup(text, "html.parser")

        # Indeed job cards (structure varies by region/ab-test, try multiple selectors)
        cards = soup.select(
            "div.job_seen_beacon, div.job-card-container, "
            "div.job-search-item, div[class*=jobCard], "
            "div[class*=tapItem], div.slider_container, "
            "li.css-1ac2h1w, li[class*=job-listing]"
        )
        if not cards:
            # Fallback: try Indeed's mosaic layout
            cards = soup.select("div[data-tn-component*=jobCard], div[class*=resultContent]")
        if not cards:
            cards = soup.select("a[class*=jobtitle], div[class*=title]")
        if not cards:
            # Last resort: look for any link containing job title pattern
            cards = soup.find_all("div", class_=lambda c: c and ("job" in c.lower() or "card" in c.lower()))

        for card in cards:
            # Title
            title_el = (
                card.select_one("h2.jobTitle a, h2 a, a.jobtitle, a[data-jk]")
                or card.select_one("a[class*=title], a[id*=job], span[title]")
                or card.select_one("a > span[class*=title]")
            )
            if not title_el:
                continue
            title = title_el.get_text(strip=True)

            # URL
            url = ""
            link_el = title_el if title_el.name == "a" else card.find("a", href=True)
            if link_el:
                url = link_el.get("href", "")
                # Indeed relative URLs
                if url and url.startswith("/"):
                    url = "https://fr.indeed.com" + url
                # Indeed internal redirect
                if "rd?to=" in url or "clk" in url:
                    # Keep as-is, it will redirect to the actual employer page
                    url = "https://fr.indeed.com" + url if url.startswith("/") else url

            # Company
            company_el = (
                card.select_one("[class*=company], [data-testid=company-name]")
                or card.select_one("span.companyName, div.company, span[class*=employer]")
            )
            company = company_el.get_text(strip=True) if company_el else ""

            # Location
            location_el = (
                card.select_one("[class*=location], [data-testid=location]")
                or card.select_one("div[class*=location], span[class*=location]")
            )
            location = location_el.get_text(strip=True) if location_el else "France"

            # Salary
            salary_el = (
                card.select_one("[class*=salary], [data-testid=salary]")
                or card.select_one("div.salaryOnly, span.salary, div[class*=salary]")
            )
            salary = salary_el.get_text(strip=True) if salary_el else ""

            add_job(title, company, url, location, salary)

    except (BlockingIOError, Exception) as e:
        if not isinstance(e, BlockingIOError):
            print(f"  Indeed scrape error: {e}")

        # ── Fallback: Indeed RSS feed ──
        try:
            print("  Indeed: using RSS fallback...")
            rss_urls = [
                "https://fr.indeed.com/rss/jobs?q=QA+testeur+test+automation&l=France&jt=freelance_contract",
                "https://fr.indeed.com/rss?q=QA+testeur+test+automation&l=France",
                "https://fr.indeed.com/rss?q=QA+automation+test&l=France",
            ]
            fallback_jobs = set()
            for rss_url in rss_urls:
                if len(fallback_jobs) >= 50:
                    break
                try:
                    rss_resp = requests.get(rss_url, headers=headers, timeout=15)
                    if rss_resp.status_code != 200:
                        continue
                    rss_soup = BeautifulSoup(rss_resp.text, "xml")
                    items = rss_soup.find_all("item")
                    if not items:
                        items = rss_soup.find_all("entry")
                    for item in items:
                        title = ""
                        title_el = item.find("title")
                        if title_el:
                            title = title_el.get_text(strip=True)

                        link = ""
                        link_el = item.find("link")
                        if link_el:
                            link = link_el.get_text(strip=True) or link_el.get("href", "")
                        if link and link.startswith("/"):
                            link = "https://fr.indeed.com" + link

                        desc = ""
                        desc_el = item.find("description") or item.find("summary")
                        if desc_el:
                            desc = desc_el.get_text(strip=True)

                        location = "France"
                        salary = ""
                        # Parse description for location and salary hints
                        if desc:
                            loc_match = re.search(r'(?:localisation|location|lieu)[:\s]+([^\n<,]+)', desc, re.I)
                            if loc_match:
                                location = loc_match.group(1).strip()
                            sal_match = re.search(r'(\d[\d\s.,]*(?:EUR|€|\$|k|K).*?(?:jour|mois|an|hour|hr))', desc)
                            if sal_match:
                                salary = sal_match.group(1).strip()

                        company = ""
                        # Some RSS feeds include company in description or category
                        cat_el = item.find("category")
                        if cat_el:
                            company = cat_el.get_text(strip=True)
                        if not company and desc:
                            co_match = re.search(r'(?:entreprise|company|societe|employer)[:\s]+([^\n<,]+)', desc, re.I)
                            if co_match:
                                company = co_match.group(1).strip()

                        if title:
                            # Deduplicate within fallback
                            dedup_key = (title, company, link)
                            if dedup_key not in fallback_jobs:
                                fallback_jobs.add(dedup_key)
                                add_job(title, company, link or "https://fr.indeed.com", location, salary)

                except Exception as rss_e:
                    print(f"  Indeed RSS sub-error: {rss_e}")
                    continue

        except Exception as rss_fatal:
            print(f"  Indeed RSS fallback failed: {rss_fatal}")

    if not jobs:
        print("  Indeed: 0 jobs (blocked or no matches)")
    else:
        print(f"  Indeed: {len(jobs)} jobs found")
    return jobs


def fetch_comet():
    """Scrape QA missions from Comet (comet.co - French freelance platform for IT consultants).

    Comet is a JS-heavy Vue app (app.comet.co) backed by a private GraphQL API
    (api.comet.co/api/graphql) that requires authentication. The public-facing
    website (www.comet.co) is built on HubSpot CMS and does not render mission
    data server-side. No RSS feed is available.

    This function attempts to access the GraphQL API first. Since the API is
    private (requires auth token), it falls back gracefully with a clear message.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }
    jobs = []
    filter_keywords = ["qa", "sdet", "quality assurance", "quality engineer",
                       "test engineer", "test automation", "tester",
                       "testing", "automation engineer", "test lead",
                       "test manager", "qa lead", "qa engineer",
                       "software test", "software testing", "test developer",
                       "engineer in test", "testeur", "recette", "qualite",
                       "automation"]

    # Try 1: GraphQL API (requires auth, will return 401/403)
    try:
        # The mission listing query used by the Vue frontend
        resp = requests.post(
            "https://api.comet.co/api/graphql",
            json={
                "query": (
                    "query MissionsSearch($search: String!, $filters: MissionSearchInput!) {"
                    "  missionsSearch(search: $search, groups: [{key: \"all\", filters: $filters, limit: 50}]) {"
                    "    items {"
                    "      id title"
                    "    }"
                    "  }"
                    "}"
                ),
                "variables": {
                    "search": "QA test",
                    "filters": {},
                },
            },
            headers={**headers, "Content-Type": "application/json"},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            if "errors" not in data and data.get("data", {}).get("missionsSearch"):
                items = data["data"]["missionsSearch"].get("items", []) or []
                for item in items:
                    title = item.get("title", "")
                    title_lower = title.lower()
                    if not any(k in title_lower for k in filter_keywords):
                        continue
                    mission_id = item.get("id", "")
                    jobs.append({
                        "title": title,
                        "company": "Comet client",
                        "source": "Comet",
                        "url": f"https://app.comet.co/freelancer/explore/mission/{mission_id}" if mission_id else "",
                        "location": "France",
                        "salary": "",
                        "tags": "",
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "description": "",
                        "raw_date": int(time.time()),
                    })
                if jobs:
                    print(f"  Comet GraphQL: {len(jobs)} QA missions")
                    return jobs
            else:
                err_msg = data.get("errors", [{}])[0].get("message", "unknown")
                print(f"  Comet GraphQL returned error: {err_msg}")
        elif resp.status_code in (401, 403):
            print(f"  Comet GraphQL: API requires authentication (HTTP {resp.status_code})")
        else:
            print(f"  Comet GraphQL returned HTTP {resp.status_code}")
    except requests.exceptions.ConnectionError:
        print("  Comet GraphQL: connection error")
    except Exception as e:
        print(f"  Comet GraphQL error: {e}")

    # Try 2: Public search page (HubSpot CMS - won't have mission data rendered server-side)
    try:
        pub_resp = requests.get(
            "https://www.comet.co/fr/freelances/trouver-une-mission",
            headers={**headers, "Accept": "text/html"},
            timeout=15,
        )
        if pub_resp.status_code == 200:
            soup = BeautifulSoup(pub_resp.text, "html.parser")
            # The actual missions are loaded client-side via Vue/GraphQL.
            # The server HTML only contains static HubSpot CMS content.
            # Check for any embedded JSON or __NEXT_DATA__ equivalent
            scripts = soup.find_all("script")
            for script in scripts:
                text = script.string or ""
                if "mission" in text.lower() and ("title" in text.lower() or "id" in text.lower()):
                    try:
                        data = json.loads(text)
                        # Attempt to parse any embedded mission data
                        if isinstance(data, dict):
                            missions = data.get("missions", []) or data.get("results", []) or []
                            for item in missions:
                                title = item.get("title", "")
                                title_lower = title.lower()
                                if not any(k in title_lower for k in filter_keywords):
                                    continue
                                company = item.get("company", "") or item.get("client", "")
                                url = item.get("url", "") or ""
                                location = item.get("location", "") or "France"
                                budget = item.get("budget", "") or item.get("salary", "") or ""
                                jobs.append({
                                    "title": title, "company": company, "source": "Comet",
                                    "url": url, "location": location, "salary": budget,
                                    "tags": "", "description": "",
                                    "date": datetime.now().strftime("%Y-%m-%d"),
                                    "raw_date": int(time.time()),
                                })
                    except (json.JSONDecodeError, TypeError):
                        continue
            if not jobs:
                print("  Comet public page: no embedded mission data (page requires JS rendering)")
        else:
            print(f"  Comet public page returned HTTP {pub_resp.status_code}")
    except Exception as e:
        print(f"  Comet public page error: {e}")

    if not jobs:
        print("  Comet: 0 missions (API is private, search requires authentication)")
    return jobs


def fetch_malt():
    """Fetch QA missions from Malt.fr (leading French freelance platform).
    Malt.fr is behind Cloudflare challenge - direct scraping is blocked.
    This function attempts the public search page; if blocked, reports gracefully."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }
    jobs = []
    filter_keywords = ["qa", "sdet", "quality assurance", "quality engineer",
                       "test", "tester", "testing", "automation",
                       "testeur", "recette", "qualite", "recetteur"]

    try:
        resp = requests.get(
            "https://www.malt.fr/search?keyword=QA+test&sort=relevance",
            headers=headers, timeout=15
        )
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            # Try to find mission cards - Malt uses various selectors
            cards = soup.select("[class*=mission], [class*=card], [class*=result], article, li[class*=job]")
            for card in cards:
                title_el = card.select_one("h2, h3, a[title], [class*=title] a")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                title_lower = title.lower()
                if not any(k in title_lower for k in filter_keywords):
                    continue

                url = title_el.get("href", "")
                if url and not url.startswith("http"):
                    url = "https://www.malt.fr" + url

                company_el = card.select_one("[class*=company], [class*=client], [class*=author]")
                company = company_el.get_text(strip=True) if company_el else ""

                location_el = card.select_one("[class*=location], [class*=place], [class*=city]")
                location = location_el.get_text(strip=True) if location_el else "France"

                jobs.append({
                    "title": title, "company": company, "source": "Malt",
                    "url": url, "location": location, "salary": "", "tags": "",
                    "description": "", "date": datetime.now().strftime("%Y-%m-%d"),
                    "raw_date": int(time.time()),
                })
        elif resp.status_code == 403 or "challenge" in resp.text.lower() or "cf-browser-verification" in resp.text:
            print("  Malt: blocked by Cloudflare challenge")
        else:
            print(f"  Malt: HTTP {resp.status_code}")
    except Exception as e:
        print(f"  Malt error: {e}")

    if not jobs:
        print("  Malt: 0 missions (Cloudflare or JS required)")
    return jobs


def fetch_jeanmichel():
    """Fetch QA jobs from Jean-Michel.io (French IT freelance/CDI platform) via their API."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    jobs = []

    # Freelance only (le CDI ne nous intéresse pas)
    contracts = ["freelance"]
    base_url = "https://sebs.jean-michel.io/offers"

    filter_keywords = ["qa", "sdet", "quality assurance", "quality engineer",
                       "test engineer", "test automation", "tester",
                       "testing", "automation engineer", "qa lead", "qa engineer",
                       "test lead", "testeur", "recette", "qualité", "qualite"]

    for contract in contracts:
        page = 1
        nb_pages = 1
        while page <= nb_pages:
            try:
                params = {
                    "page": page,
                    "query": "QA test qualité",
                    "sortBy": "pertinence",
                    "includeUnknownRemote": "true",
                    "minExperience": 0,
                    "maxExperience": 20,
                    "includeUnknownExperience": "true",
                    "minTjm": 0,
                    "includeOnRequestRemuneration": "true",
                    "contract": contract,
                }
                qs = "&".join(f"{k}={v}" for k, v in params.items())
                url = f"{base_url}?{qs}"
                resp = requests.get(url, headers=headers, timeout=15)
                if resp.status_code != 200:
                    print(f"  Jean-Michel.io ({contract}) page {page}: HTTP {resp.status_code}")
                    break

                data = resp.json()
                nb_pages = data.get("nbPages", 1)
                offers = data.get("offers", [])

                for item in offers:
                    title = item.get("title", "")
                    title_lower = title.lower()
                    if not any(k in title_lower for k in filter_keywords):
                        continue

                    company = ""
                    if isinstance(item.get("company"), dict):
                        company = item["company"].get("name", "")

                    location = ""
                    if isinstance(item.get("city"), dict):
                        location = item["city"].get("name", "")

                    offer_id = item.get("id")
                    offer_url = f"https://consultant.jean-michel.io/annonces/{offer_id}" if offer_id else ""

                    # Salary / TJM
                    salary = ""
                    salary_min = item.get("salaryMin")
                    salary_max = item.get("salaryMax")
                    tjm_min = item.get("tjmMin")
                    tjm_max = item.get("tjmMax")

                    if salary_min or salary_max:
                        if salary_min and salary_max:
                            salary = f"{salary_min} - {salary_max} €/an"
                        elif salary_min:
                            salary = f"From {salary_min} €/an"
                        elif salary_max:
                            salary = f"Up to {salary_max} €/an"
                    if tjm_min or tjm_max:
                        tjm_str = ""
                        if tjm_min and tjm_max:
                            tjm_str = f"{tjm_min} - {tjm_max} €/jour"
                        elif tjm_min:
                            tjm_str = f"{tjm_min} €/jour"
                        elif tjm_max:
                            tjm_str = f"{tjm_max} €/jour"
                        if tjm_str:
                            salary = f"{tjm_str}" if not salary else f"{salary} | {tjm_str}"

                    remote_days = item.get("remoteDaysPerWeek")
                    tags = item["contract"] if item.get("contract") else ""
                    if remote_days is not None:
                        tags += f", {remote_days}j télétravail/sem"
                    category = item.get("category", "")
                    if category:
                        tags += f", {category}" if tags else category

                    desc = item.get("description", "") or ""
                    # Clean HTML from description
                    import re as _re
                    desc = _re.sub(r"<[^>]+>", " ", desc)
                    desc = _re.sub(r"\s+", " ", desc).strip()

                    pub_date = item.get("publishDate", "")
                    date = pub_date[:10] if pub_date else datetime.now().strftime("%Y-%m-%d")

                    jobs.append({
                        "title": title,
                        "company": company,
                        "source": "Jean-Michel.io",
                        "url": offer_url,
                        "location": location,
                        "salary": salary,
                        "tags": tags,
                        "description": desc[:2000],
                        "date": date,
                        "raw_date": int(time.time()),
                        "contract_type": "freelance" if "freelance" in (item.get("contract") or "") else contract,
                    })

                page += 1
                time.sleep(0.5)

            except Exception as e:
                print(f"  Jean-Michel.io ({contract}) page {page} error: {e}")
                break

    if not jobs:
        print("  Jean-Michel.io: 0 QA jobs found")
    return jobs


def fetch_all():
    """Fetch jobs from all sources - legacy wrapper."""
    return fetch_all_new_sources()


def fetch_all_new_sources():
    """Fetch jobs from all sources including new ones."""
    all_jobs = []
    
    sources = [
        ("RemoteOK", fetch_remoteok),
        ("WWR", fetch_wwr),
        ("WWR RSS", fetch_wwr_rss),
        ("Wellfound", fetch_wellfound),
        ("LinkedIn RSS", fetch_linkedin_rss),
        ("JobBoard.io", fetch_jobboard_io),
        ("Otta", fetch_otta),
        ("Free-Work (FR)", fetch_freework),
        ("LesJeudis (FR)", fetch_lesjeudis),
        ("Optioncarriere (FR)", fetch_optioncarriere),
        ("WTTJ", fetch_wttj),
        ("FranceTravail", fetch_francetravail),
        ("Remotive", fetch_remotive),
        ("HN Hiring", fetch_hn_whoishiring),
        ("LinkedIn Countries", fetch_linkedin_countries),
        ("Indeed", fetch_indeed),
        ("Comet", fetch_comet),
        ("Malt", fetch_malt),
        ("Jean-Michel.io", fetch_jeanmichel),
    ]
    
    for name, fetcher in sources:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching {name}...")
        try:
            jobs = fetcher()
            all_jobs.extend(jobs)
            print(f"  -> {len(jobs)} jobs")
        except Exception as e:
            print(f"  -> Error: {e}")
        time.sleep(1)  # Be nice to servers
    
    # Deduplicate by URL
    seen = set()
    unique = []
    for job in all_jobs:
        url = job.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(job)
        elif not url:
            unique.append(job)
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Total: {len(unique)} unique jobs from {len(all_jobs)} total")
    return unique


# ─── DB path ─────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
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
        CREATE TABLE IF NOT EXISTS dismissed_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT,
            url TEXT,
            dismissed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_dismissed_title_company ON dismissed_jobs(title, company);
        CREATE INDEX IF NOT EXISTS idx_jobs_url ON jobs(url);
        CREATE INDEX IF NOT EXISTS idx_jobs_qa ON jobs(is_qa);
    """)
    # Add new columns if they don't exist
    new_columns = [
        ("tech_stack", "TEXT"),
        ("seniority", "TEXT"),
        ("contract_type", "TEXT"),
        ("remote_type", "TEXT"),
        ("salary_min", "INTEGER"),
        ("salary_max", "INTEGER"),
        ("currency", "TEXT"),
        ("ai_enriched", "INTEGER DEFAULT 0"),
        ("saved", "INTEGER DEFAULT 0"),
        ("viewed", "INTEGER DEFAULT 0"),
        ("freelance_status", "TEXT"),
        ("freelance_score", "INTEGER DEFAULT 0"),
        ("duration_info", "TEXT"),
        ("budget_info", "TEXT"),
        ("source_publish_date", "TEXT"),
        ("pipeline_stage", "TEXT DEFAULT 'new'"),
        ("applied_at", "DATETIME"),
    ]
    for col_name, col_type in new_columns:
        try:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass  # Column already exists

    # Update applications table
    for col_name, col_type in [("notes", "TEXT"), ("job_title", "TEXT"), ("company", "TEXT")]:
        try:
            conn.execute(f"ALTER TABLE applications ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()





# ─── Freelance Classifier ──────────────────────────────────────────

FREELANCE_KEYWORDS = [
    "freelance", "freelancer", "free-lance", "free lance",
    "mission", "independan", "consultant", "contractor", "contracting",
    "regie", "prestation", "prestataire", "extern", "externalisation",
    "tjm", "/jour", "per day", "/day", "daily rate",
    "sasu", "portage", "salaire en mission",
]

CDI_KEYWORDS = [
    "cdi", "permanent", "full-time", "full time", "employe permanent",
    "indetermine", "indéterminé", "temps plein", "en cdi",
    "poste fixe", "salarie", "salarié",
]

CDD_KEYWORDS = [
    "cdd", "fixed-term", "fixed term", "duree determinee", "durée déterminée",
    "temporaire", "temporary", "contrat court",
]

STAGE_KEYWORDS = [
    "stage", "intern", "internship", "alternance", "apprenti",
    "apprenticeship", "junior", "debutant", "débutant",
]

EXCLUDE_KEYWORDS = [
    "cdi", "cdd", "stage", "intern", "alternance", "apprenti",
    "interim", "intérim", "salarie", "salarié",
    "employee", "temps plein", "full time employee",
]

REMOTE_KEYWORDS = {
    "remote": ["remote", "full remote", "full-remote", "work from home",
               "work-from-home", "wfh", "home office", "100% remote",
               "100% tele", "a distance", "à distance", "telework",
               "teleworking", "telecommute", "teletravail", "télétravail",
               "100% distanciel", "distanciel"],
    "hybrid": ["hybrid", "hybride", "mixte", "presentiel partiel",
               "partiellement", "2 jours", "3 jours", "2-3 jours"],
    "onsite": ["on-site", "on site", "sur site", "sur place",
               "presentiel", "présentiel", "site based",
               "en agence", "au bureau"],
}

REMOTE_OVERRIDE_LOCATIONS = {
    "à distance": "remote", "a distance": "remote",
    "remote": "remote", "100% remote": "remote",
    "télétravail": "remote", "teletravail": "remote",
    "full remote": "remote",
}


def detect_remote_type(location, title, description=""):
    """Detect if job is remote/hybrid/onsite."""
    text = f"{location} {title} {description}".lower()
    
    for rtype, keywords in REMOTE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return rtype
    
    # Check location override
    for loc_val, result in REMOTE_OVERRIDE_LOCATIONS.items():
        if loc_val in location.lower():
            return result
    
    # Default: look for location hints
    if not location or location.strip() in ("", "-", "N/A"):
        return "remote"  # No location specified = assume remote
    if location.lower() in ("france", "france métropolitaine", "national"):
        return "remote"
    
    return ""  # Unknown


def detect_contract_type(title, description=""):
    """Detect freelance vs CDI vs CDD vs stage."""
    text = f"{title} {description}".lower()
    
    # First check for explicit "freelance ou CDI" which is ambiguous
    if "freelance ou cdi" in text or "freelance or permanent" in text:
        return "ambigüe", None
    
    # Score-based detection
    score = 0
    detected_type = None
    
    for kw in FREELANCE_KEYWORDS:
        if kw in text:
            score += 2
    for kw in CDI_KEYWORDS:
        if kw in text:
            score -= 3
    for kw in CDD_KEYWORDS:
        if kw in text:
            score -= 2
    for kw in STAGE_KEYWORDS:
        if kw in text:
            score -= 4
    
    if score >= 2:
        return "mission/freelance", score
    elif score <= -2:
        if "stage" in text or "alternance" in text or "intern" in text:
            return "stage/alternance", score
        if "cdd" in text or "temporaire" in text:
            return "cdd", score
        return "cdi (rejeté)", score
    elif score >= 0:
        return "ambigüe", score
    else:
        return "probablement cdi (à vérifier)", score


def detect_linkedin_date(card):
    """Try to extract real posting date from LinkedIn card."""
    try:
        # LinkedIn often has time-ago text like "il y a 2 heures", "3 days ago"
        time_el = card.select_one("time, .job-search-card__listdate, [datetime], .posting-date")
        if time_el:
            datetime_attr = time_el.get("datetime", "")
            if datetime_attr:
                return datetime_attr[:10]  # YYYY-MM-DD
            text = time_el.get_text(strip=True)
            # Parse relative dates
            now = int(time.time())
            text_lower = text.lower()
            if "heure" in text_lower or "hour" in text_lower:
                hours = int(re.search(r"\d+", text).group()) if re.search(r"\d+", text) else 1
                return datetime.fromtimestamp(now - hours * 3600).strftime("%Y-%m-%d")
            if "jour" in text_lower or "day" in text_lower or "día" in text_lower:
                days = int(re.search(r"\d+", text).group()) if re.search(r"\d+", text) else 1
                return datetime.fromtimestamp(now - days * 86400).strftime("%Y-%m-%d")
            if "semaine" in text_lower or "week" in text_lower:
                weeks = int(re.search(r"\d+", text).group()) if re.search(r"\d+", text) else 1
                return datetime.fromtimestamp(now - weeks * 604800).strftime("%Y-%m-%d")
            if "mois" in text_lower or "month" in text_lower:
                months = int(re.search(r"\d+", text).group()) if re.search(r"\d+", text) else 1
                return datetime.fromtimestamp(now - months * 2592000).strftime("%Y-%m-%d")
    except:
        pass
    return None


def classify_freelance_job(job):
    """Classify a job as freelance VALIDÉE, AMBIGUË, or REJETÉE.
    Returns dict with freelance_status, freelance_score, contract_type_fr, remote_type, duration_info, budget_info, source_publish_date
    """
    title = job.get("title", "")
    description = job.get("description", "")
    location = job.get("location", "")
    salary = job.get("salary", "")
    source = job.get("source", "")
    
    # Detect contract type
    contract_type, c_score = detect_contract_type(title, description)
    if contract_type is None and c_score is None:
        contract_type = "ambigüe"
        c_score = 0
    
    # Detect remote type
    remote_type = detect_remote_type(location, title, description)
    
    # Calculate score
    score = c_score
    text_lower = f"{title} {description} {salary}".lower()
    
    # Source bonus: known freelance platforms
    freelance_sources = [
        "Free-Work", "LesJeudis", "Optioncarriere", "LinkedIn France",
        "LinkedIn Suisse", "LinkedIn Luxembourg", "LinkedIn Dubaï",
        "LinkedIn Singapour", "LinkedIn Countries", "Malt", "Comet"
    ]
    for fs in freelance_sources:
        if fs.lower() in source.lower():
            score += 2
            break
    
    # Bonus for explicit freelance indicators
    if "/jour" in text_lower or "tjm" in text_lower:
        score += 4
    if "mission" in title.lower():
        score += 3
    if "freelance" in title.lower():
        score += 4
    if "consultant" in title.lower():
        score += 2
    if "sasu" in text_lower or "portage" in text_lower:
        score += 3
    if "contract" in title.lower() or "contractor" in title.lower():
        score += 3
    if "régie" in text_lower or "regie" in text_lower:
        score += 2
    
    # Bonus for QA+tech keywords (more likely freelance-friendly)
    qa_bonus = ["qa engineer", "qa automation", "sdet", "test engineer",
                 "test automation", "test lead", "qa lead", "test analyst",
                 "testeur", "qa tester"]
    for qk in qa_bonus:
        if qk in title.lower():
            score += 1
            break
    
    # Bonus for remote/hybrid (common in freelance)
    if remote_type in ("remote", "hybrid"):
        score += 1
    
    # Penalty for explicit permanent indicators
    for kw in CDI_KEYWORDS:
        if kw in title.lower():
            score -= 5
    
    # Check for salary-based clues (daily rate = freelance)
    if salary:
        sal_lower = salary.lower()
        if "/jour" in sal_lower or "daily" in sal_lower or "/day" in sal_lower or "tjm" in sal_lower:
            score += 3
        elif "/mois" in sal_lower or "/year" in sal_lower or "/an" in sal_lower:
            score -= 2  # Monthly salary = likely CDI
    
    # Determine status
    if score >= 4:
        status = "VALIDÉE"
    elif score >= 1:
        if "freelance ou cdi" in text_lower or "freelance or permanent" in text_lower:
            status = "AMBIGUË"
        else:
            status = "VALIDÉE"
    else:
        status = "AMBIGUË"
    
    if contract_type in ("stage/alternance", "cdi (rejeté)"):
        status = "REJETÉE"
    
    # Extract budget/TJM info
    budget_info = ""
    if salary:
        budget_info = salary
    
    # Extract duration info
    duration_info = ""
    dur_patterns = [
        r"(\d+\s*(mois|months|semaines|weeks|ans|years|an))",
        r"dur[ée]e.*?\d+.*?(mois|semaines|ans)",
        r"mission.*?\d+.*?(mois|semaines)",
        r"(\d+)\s*(-|à|to)\s*(\d+)\s*(mois|months)",
    ]
    for p in dur_patterns:
        m = re.search(p, text_lower)
        if m:
            duration_info = m.group(0)
            break
    
    return {
        "freelance_status": status,
        "freelance_score": min(max(score, 0), 10),  # Clamp 0-10
        "contract_type_fr": contract_type,
        "remote_type": remote_type,
        "duration_info": duration_info,
        "budget_info": budget_info,
        "source_publish_date": "",
    }


def save_jobs(jobs):
    """Save jobs to database, skipping duplicates."""
    conn = get_db()
    cursor = conn.cursor()
    # Keywords for QA matching in title/tags
    title_keywords = ["qa", "sdet", "quality assurance", "quality engineer",
                      "test engineer", "test automation", "sdet", "tester",
                      "testing", "automation engineer", "test lead", "test manager",
                      "software test", "qa lead", "qa engineer",
                      "engineer in test", "test developer"]
    # Broader keywords only checked against tags (less likely to false-positive)
    tag_keywords = ["qa", "testing", "test", "quality assurance", "automation testing"]
    
    new_count = 0
    for job in jobs:
        # Also check title+company dedup (catches same job with different URLs)
        norm_title = job["title"].strip().lower()[:100]
        norm_company = job.get("company", "").strip().lower()[:100]
        existing = cursor.execute(
            "SELECT id FROM jobs WHERE LOWER(TRIM(title)) = ? AND LOWER(TRIM(company)) = ?",
            (norm_title, norm_company)
        ).fetchone()
        if existing:
            continue
        
        # Skip if this job was previously dismissed by the user
        dismissed = cursor.execute(
            "SELECT id FROM dismissed_jobs WHERE LOWER(TRIM(title)) = ? AND LOWER(TRIM(company)) = ?",
            (norm_title, norm_company)
        ).fetchone()
        if dismissed:
            continue
        
        url_hash = hashlib.md5(job["url"].encode()).hexdigest()
        
        # Check if QA-related
        title_lower = job["title"].lower()
        tags_lower = job["tags"].lower() if job.get("tags") else ""
        
        # Match against title first (strict), then tags (broader)
        is_qa = 1 if any(k in title_lower for k in title_keywords) else 0
        if not is_qa:
            is_qa = 1 if any(k in tags_lower for k in tag_keywords) else 0
        
        # Run freelance classifier
        classification = classify_freelance_job(job)
        freelance_status = classification["freelance_status"]
        freelance_score = classification["freelance_score"]
        duration_info = classification.get("duration_info", "")
        budget_info = classification.get("budget_info", "")
        
        # Skip rejected jobs
        if freelance_status == "REJETÉE":
            continue
        
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO jobs
                (title, company, source, url, location, salary, tags, 
                 description, date, raw_date, is_qa,
                 tech_stack, seniority, contract_type, remote_type,
                 salary_min, salary_max, currency, ai_enriched, saved,
                 freelance_status, freelance_score, duration_info, budget_info)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?)
            """, (
                job["title"], job["company"], job["source"], job["url"],
                job["location"], job["salary"], job["tags"],
                job["description"], job["date"], job["raw_date"], is_qa,
                job.get("tech_stack"), job.get("seniority"),
                classification.get("contract_type_fr", job.get("contract_type")),
                classification.get("remote_type", job.get("remote_type")),
                job.get("salary_min"), job.get("salary_max"),
                job.get("currency"), job.get("ai_enriched", 0),
                job.get("saved", 0),
                freelance_status, freelance_score, duration_info, budget_info
            ))
            if cursor.rowcount > 0:
                new_count += 1
        except Exception as e:
            print(f"  DB error: {e}")
    
    conn.commit()
    conn.close()
    
    # Sync new jobs to Supabase
    if new_count > 0 and _supabase_reachable():
        # Re-fetch the new jobs to get assigned IDs, then upsert
        try:
            conn2 = get_db()
            all_jobs = [dict(r) for r in conn2.execute(
                "SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (new_count,)
            ).fetchall()]
            conn2.close()
            _supabase_bulk_upsert("jobs", all_jobs)
        except Exception:
            pass
    
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
        if filters.get("seniority"):
            query += " AND seniority = ?"
            params.append(filters["seniority"])
        if filters.get("contract_type"):
            query += " AND contract_type = ?"
            params.append(filters["contract_type"])
        if filters.get("remote_type"):
            query += " AND remote_type = ?"
            params.append(filters["remote_type"])
        if filters.get("salary_min"):
            query += " AND (salary_min >= ? OR salary_max >= ?)"
            params.extend([filters["salary_min"], filters["salary_min"]])
        if filters.get("salary_max"):
            query += " AND salary_max <= ?"
            params.append(filters["salary_max"])
        if filters.get("tech_stack"):
            # JSON contains: check if any keyword from tech_stack is in the tech_stack JSON array
            query += " AND ("
            terms = filters["tech_stack"].split(",")
            conditions = []
            for t in terms:
                t = t.strip()
                if t:
                    conditions.append("tech_stack LIKE ?")
                    params.append(f"%{t}%")
            if conditions:
                query += " OR ".join(conditions) + ")"
        if filters.get("saved"):
            query += " AND saved = 1"
        if filters.get("applied_filter"):
            query += " AND applied = 1"
        if filters.get("not_dismissed"):
            query += " AND (pipeline_stage IS NULL OR pipeline_stage != 'dismissed')"
    
    # ALWAYS filter out dismissed jobs
    query += " AND (pipeline_stage IS NULL OR pipeline_stage != 'dismissed')"
    
    query += " ORDER BY raw_date DESC, date DESC LIMIT 200"
    
    cursor = conn.execute(query, params)
    jobs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jobs


def export_static_json(output_path="docs/jobs.json"):
    """Export jobs to JSON for the static site."""
    import json, os
    jobs = get_jobs({"qa_only": True, "not_dismissed": True})
    # Clean up for export - keep new enriched fields
    for j in jobs:
        j.pop("description", None)
        j.pop("notes", None)
        j.pop("cover_letter", None)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({"jobs": jobs, "exported_at": datetime.now().isoformat()}, f, indent=2)
    print(f"✓ Exported {len(jobs)} jobs to {output_path}")
    
    # Also sync full dataset to Supabase
    if _supabase_reachable():
        try:
            conn = get_db()
            all_jobs = [dict(r) for r in conn.execute("SELECT * FROM jobs").fetchall()]
            conn.close()
            _supabase_bulk_upsert("jobs", all_jobs)
            print(f"  ✓ Synced {len(all_jobs)} jobs to Supabase")
        except Exception as e:
            print(f"  ✗ Supabase sync failed: {e}")
    
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
    
    # Sync to Supabase
    if _supabase_reachable():
        try:
            _supabase_bulk_upsert("jobs", [{"id": job_id, "applied": 1, "cover_letter": cover_letter}])
            _supabase_bulk_upsert("applications", [{"job_id": job_id, "cover_letter": cover_letter, "status": "applied"}])
        except Exception:
            pass


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
