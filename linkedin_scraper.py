#!/usr/bin/env python3
"""
LinkedIn Scraper - utilise Chrome (AppleScript) pour scraper les offres QA.
Prérequis : Chrome ouvert, connecté à LinkedIn, JavaScript AppleScript activé.
"""

import subprocess
import json
import time
import os
import re
from datetime import datetime

BASE_DIR = os.path.dirname(__file__)
OUTPUT_FILE = os.path.join(BASE_DIR, "linkedin_jobs.json")

# ─── Recherches multi-pays, multi-mots-clés ────────────────────
SEARCHES = [
    # France
    {"keywords": "QA+quality+assurance+test", "country": "France", "location": "France"},
    {"keywords": "test+automation+Playwright+Cypress+Selenium", "country": "France", "location": "France"},
    {"keywords": "QA+freelance+test", "country": "France", "location": "France"},
    # Suisse
    {"keywords": "QA+quality+assurance+test", "country": "Suisse", "location": "Suisse"},
    {"keywords": "test+automation+QA", "country": "Suisse", "location": "Suisse"},
    # Luxembourg
    {"keywords": "QA+quality+assurance", "country": "Luxembourg", "location": "Luxembourg"},
    # Dubaï
    {"keywords": "QA+quality+assurance+test", "country": "Dubaï", "location": "Duba%C3%AF"},
    # Singapour
    {"keywords": "QA+quality+assurance+test", "country": "Singapour", "location": "Singapour"},
]


def chrome_exec(js_code):
    """Execute JS in Chrome's active tab via AppleScript."""
    b64 = __import__('base64').b64encode(js_code.encode()).decode()
    cmd = f'tell application "Google Chrome" to execute (active tab of front window) javascript "eval(atob(\\\"{b64}\\\"))"'
    result = subprocess.run(["osascript", "-e", cmd], capture_output=True, text=True, timeout=20)
    return result.stdout.strip()


def chrome_navigate(url):
    """Navigate active tab."""
    b64 = __import__('base64').b64encode(f'window.location.href = "{url}";'.encode()).decode()
    cmd = f'tell application "Google Chrome" to execute (active tab of front window) javascript "eval(atob(\\\"{b64}\\\"))"'
    subprocess.run(["osascript", "-e", cmd], capture_output=True, timeout=10)


def scrape_search(keywords, location, country):
    """Scrape one LinkedIn job search page."""
    url = f"https://www.linkedin.com/jobs/search/?keywords={keywords}&location={location}"
    print(f"\n🔍 [{country}] {keywords.replace('+', ' ')}")
    chrome_navigate(url)
    time.sleep(6)

    # Count jobs
    count_js = 'document.querySelectorAll(".job-card-container").length'
    count = chrome_exec(count_js)
    if count and count.isdigit():
        n = int(count)
    else:
        n = 0
    print(f"   Jobs trouvés: {n}")

    jobs = []
    for i in range(min(n, 10)):  # Max 10 per search
        js = f"""
        (function(){{
            var c = document.querySelectorAll('.job-card-container')[{i}];
            if(!c) return 'N/A|||';
            var t = c.querySelector('.job-card-list__title') || c.querySelector('a[data-anonymize=job-title]') || c.querySelector('a[id^=ember]');
            var co = c.querySelector('.job-card-container__company-name') || c.querySelector('.artdeco-entity-lockup__subtitle');
            var l = c.querySelector('.job-card-container__metadata-wrapper') || c.querySelector('.artdeco-entity-lockup__caption');
            var lnk = '';
            if(t) lnk = t.href || '';
            if(!lnk) {{ var a = c.querySelector('a[href*=jobs]'); if(a) lnk = a.href; }}
            var title = t ? t.textContent.trim() : '';
            // Remove duplicate text (LinkedIn bug)
            var mid = Math.floor(title.length/2);
            if(title.substring(0,mid) === title.substring(mid)) title = title.substring(0,mid);
            return (title || 'N/A') + '|' + (co ? co.textContent.trim() : '') + '|' + (l ? l.textContent.trim() : '') + '|' + (lnk || '');
        }})()
        """
        result = chrome_exec(js)
        parts = result.split('|', 3)
        if len(parts) >= 3:
            title, company, location_raw = parts[0], parts[1], parts[2]
            url_job = parts[3] if len(parts) > 3 else ''
            if title and title != 'N/A' and company:
                jobs.append({
                    "title": title,
                    "company": company,
                    "location": location_raw,
                    "country": country,
                    "url": url_job,
                    "source": "LinkedIn",
                    "scraped_at": datetime.now().isoformat(),
                })
                print(f"   ✓ {title[:50]}")

    return jobs


def extract_salary(description):
    """Extract salary/TJM from description text."""
    patterns = [
        r'(\d{3,4})\s*[-à]\s*(\d{3,4})\s*(€|EUR|euro)',
        r'(?:TJM|tjm|taux|jour)\s*(?:de\s*)?(\d{3,4})\s*(€|EUR)',
        r'(\d{3,4})\s*(€|EUR)\s*/?\s*(jour|day)',
        r'salaire\s*[:\s]*(\d{3,5})\s*[-à]\s*(\d{3,5})\s*(€|EUR)',
    ]
    salaries = []
    for p in patterns:
        matches = re.findall(p, description, re.IGNORECASE)
        for m in matches:
            salaries.append(m)
    return salaries


def scrape_job_description(url):
    """Navigate to a job detail page and get description."""
    chrome_navigate(url)
    time.sleep(3)
    
    js = """
    (function() {
        var desc = document.querySelector('.jobs-description-content__text, .jobs-box__html-content, .description, [data-jobs-description]');
        if(!desc) {
            // Try getting the whole page text
            return document.body.innerText.substring(0, 5000);
        }
        return desc.innerText.substring(0, 5000);
    })()
    """
    return chrome_exec(js)


def main():
    all_jobs = []
    seen_urls = set()
    
    for search in SEARCHES:
        jobs = scrape_search(search["keywords"], search["location"], search["country"])
        for job in jobs:
            if job["url"] and job["url"] not in seen_urls:
                seen_urls.add(job["url"])
                all_jobs.append(job)
    
    # Save results
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"jobs": all_jobs, "scraped_at": datetime.now().isoformat(), "count": len(all_jobs)}, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*50}")
    print(f"✅ Total: {len(all_jobs)} offres LinkedIn scrappées")
    print(f"📁 Sauvegardé dans: {OUTPUT_FILE}")
    
    return all_jobs


if __name__ == "__main__":
    main()
