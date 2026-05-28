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
    """Fetch QA freelance jobs from LesJeudis (French IT freelance platform)."""
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
        if resp.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select("article.job-card, div.job-item, li.job, div[class*=job]")
            for card in cards:
                title_el = card.select_one("h2 a, h3 a, a[title], .job-title a, .posting-title")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                title_lower = title.lower()
                if not any(k in title_lower for k in filter_keywords):
                    continue

                url = title_el.get("href", "")
                if url and not url.startswith("http"):
                    url = "https://www.lesjeudis.com" + url

                company_el = card.select_one(".company, .org, [class*=company]")
                company = company_el.get_text(strip=True) if company_el else ""

                location_el = card.select_one(".location, .place, [class*=location]")
                location = location_el.get_text(strip=True) if location_el else "France"

                jobs.append({
                    "title": title, "company": company, "source": "LesJeudis",
                    "url": url, "location": location, "salary": "", "tags": "",
                    "description": "", "date": datetime.now().strftime("%Y-%m-%d"),
                    "raw_date": int(time.time()),
                })
    except Exception as e:
        print(f"  LesJeudis error: {e}")

    if not jobs:
        print("  LesJeudis: 0 jobs (selector may need update)")
    return jobs


def fetch_optioncarriere():
    """Fetch QA jobs from Optioncarriere (French job aggregator)."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html",
    }
    jobs = []
    filter_keywords = ["qa", "sdet", "quality assurance", "quality engineer",
                       "test automate", "test engineer", "tester",
                       "software test", "testeur", "recette", "qualite"]

    try:
        resp = requests.get(
            "https://www.optioncarriere.com/recherche/s-emplois?q=QA&l=France&t=freelance",
            headers=headers, timeout=15
        )
        if resp.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select("article, .job, .result, li.result, div[class*=job]")
            for card in cards:
                title_el = card.select_one("a[title], h2 a, h3 a, .title a")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                title_lower = title.lower()
                if not any(k in title_lower for k in filter_keywords):
                    continue

                url = title_el.get("href", "")
                if url and not url.startswith("http"):
                    url = "https://www.optioncarriere.com" + url

                company_el = card.select_one(".company, .employer, [class*=company]")
                company = company_el.get_text(strip=True) if company_el else ""

                location_el = card.select_one(".location, .place, .city")
                location = location_el.get_text(strip=True) if location_el else "France"

                jobs.append({
                    "title": title, "company": company, "source": "Optioncarriere",
                    "url": url, "location": location, "salary": "", "tags": "",
                    "description": "", "date": datetime.now().strftime("%Y-%m-%d"),
                    "raw_date": int(time.time()),
                })
    except Exception as e:
        print(f"  Optioncarriere error: {e}")

    if not jobs:
        print("  Optioncarriere: 0 jobs (selector may need update)")
    return jobs


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

                    jobs.append({
                        "title": title, "company": company, "source": f"LinkedIn {country}",
                        "url": url, "location": location, "salary": "", "tags": "",
                        "description": "", "date": datetime.now().strftime("%Y-%m-%d"),
                        "raw_date": int(time.time()),
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
        ("LinkedIn Countries", fetch_linkedin_countries),
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
    
    # Adjust location if remote detected
    if remote_type == "remote" and location and "france" not in location.lower() and "remote" not in location.lower():
        # If remote but location only has a city name
        location_display = f"{location} (remote)"
    elif remote_type == "remote":
        location_display = location or "Remote"
    else:
        location_display = location
    
    # Calculate score
    score = c_score
    # Bonus for explicit freelance indicators
    text_lower = f"{title} {description} {salary}".lower()
    if "/jour" in text_lower or "tjm" in text_lower:
        score += 3
    if "mission" in title.lower():
        score += 2
    if "freelance" in title.lower():
        score += 3
    if "consultant" in title.lower():
        score += 1
    if "sasu" in text_lower or "portage" in text_lower:
        score += 2
    
    # Penalty for explicit permanent indicators
    for kw in CDI_KEYWORDS:
        if kw in title.lower():
            score -= 4
    
    # Determine status
    if score >= 3:
        status = "VALIDÉE"
    elif score >= 0:
        # Check for ambiguous patterns
        if "freelance ou cdi" in text_lower or "freelance or permanent" in text_lower:
            status = "AMBIGUË"
        else:
            status = "VALIDÉE" if score >= 1 else "AMBIGUË"
    else:
        status = "REJETÉE"
    
    if contract_type in ("stage/alternance", "cdi (rejeté)"):
        status = "REJETÉE"
    elif contract_type == "cdd" and score < 0:
        status = "REJETÉE"
    
    # Extract budget/TJM info
    budget_info = ""
    if salary:
        budget_info = salary
    elif re.search(r"\d+\s*[-àà]\s*\d+\s*(€|eur|chf|usd|sgd)", text_lower):
        match = re.search(r"(\d+\s*[-àà]\s*\d+\s*(€|eur|chf|usd|sgd)?/?(jour|day|h|hr)?)", text_lower, re.IGNORECASE)
        if match:
            budget_info = match.group(0)
    
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
        "freelance_score": min(score, 10),  # Cap at 10
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
        # Generate a unique URL hash for dedup
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
    
    query += " ORDER BY raw_date DESC, date DESC LIMIT 200"
    
    cursor = conn.execute(query, params)
    jobs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jobs


def export_static_json(output_path="docs/jobs.json"):
    """Export jobs to JSON for the static site."""
    import json, os
    jobs = get_jobs({"qa_only": True})
    # Clean up for export - keep new enriched fields
    for j in jobs:
        j.pop("description", None)
        j.pop("notes", None)
        j.pop("cover_letter", None)
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
