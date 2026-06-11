"""Matching CV <-> offres, TJM, skills gap, doublons, stats sources."""
import re
from collections import Counter

# TJM refs par marché
TJM_RANGES = {
    "france": (550, 700, "€/jour"),
    "suisse": (110, 160, "CHF/h"),
    "luxembourg": (550, 750, "€/jour"),
    "dubai": (600, 900, "$/jour"),
    "singapour": (80, 150, "SGD/h"),
}

# Skills du CV pour matching
CV_SKILLS = [
    "jira", "xray", "sql", "python", "gherkin", "agile", "scrum",
    "automation", "playwright", "selenium", "api", "rest", "test strategy",
    "regression", "acceptance", "mobile", "ios", "android",
    "sap", "oracle", "mainframe", "docker", "ci/cd",
    "test management", "qa lead", "test lead", "regulatory",
    "confluence", "zephyr", "ranorex"
]


def get_country_id(location):
    loc = location.lower()
    if any(k in loc for k in ["france", "paris", "lyon", "marseille", "toulouse"]):
        return "france"
    if any(k in loc for k in ["suisse", "switzerland", "zurich", "geneve", "genève"]):
        return "suisse"
    if any(k in loc for k in ["luxembourg", "luxemburg"]):
        return "luxembourg"
    if any(k in loc for k in ["dubai", "dubaï", "uae", "emirates", "abu dhabi"]):
        return "dubai"
    if any(k in loc for k in ["singapore", "singapour"]):
        return "singapour"
    return "france"


def match_job_to_cv(job, cv_skills=None):
    """Score /100: pertinence du job par rapport au profil."""
    if cv_skills is None:
        cv_skills = CV_SKILLS
    title = (job.get("title") or "").lower()
    desc = ((job.get("description") or "") + " " + (job.get("tags") or "")).lower()
    text = title + " " + desc

    score = 0

    # Titre (20pts max)
    title_points = 0
    if any(k in title for k in ["qa", "quality", "test", "sdet", "tester"]):
        title_points += 10
    if any(k in title for k in ["lead", "senior", "manager", "consultant"]):
        title_points += 5
    if any(k in title for k in ["automation", "engineer", "architect"]):
        title_points += 5
    score += min(title_points, 20)

    # Skills cibles (30pts max)
    skill_score = 0
    matched = []
    for skill in cv_skills:
        if skill in text:
            skill_score += 3
            matched.append(skill)
    score += min(skill_score, 30)

    # Remote (10pts)
    if job.get("remote_type") == "remote":
        score += 10
    elif job.get("remote_type") == "hybrid":
        score += 5

    # Freelance (10pts)
    if job.get("freelance_status") == "VALIDÉE":
        score += 10
    elif job.get("freelance_status") == "AMBIGUË":
        score += 5

    # Keywords bonus (20pts)
    bonus_kw = ["contract", "mission", "freelance", "régie", "prestation",
                "sasu", "consultant", "independent", "tjm", "/jour", "daily rate"]
    bonus = sum(2 for kw in bonus_kw if kw in text)
    score += min(bonus, 20)

    # TJM bonus (10pts)
    salary = (job.get("salary") or "").lower()
    if "/jour" in salary or "/j" in salary or "tjm" in salary:
        score += 10
    elif "chf" in salary or "€" in salary:
        score += 5

    return min(score, 100), matched


def analyze_tjm(job):
    """Détecte TJM dans le job et compare au marché."""
    text = f"{job.get('salary') or ''} {job.get('title') or ''} {job.get('description') or ''}".lower()
    tjm = None
    currency = ""
    unit = ""

    # Patterns TJM
    patterns = [
        r"(\d+)\s*[-àà]\s*(\d+)\s*(€|eur|chf|usd|sgd)?\s*/?\s*(jour|day|jr|h|hr|heure)",
        r"(\d+)\s*(€|eur|chf|usd|sgd)?\s*/?\s*(jour|day|jr|h|hr)",
        r"tjm\s*[:\s]*(\d+)",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            vals = [int(x) for x in m.groups() if x and x.isdigit()]
            if vals:
                tjm = sum(vals) // len(vals)
                # Detect currency
                full = m.group(0)
                if "chf" in full: currency = "CHF"
                elif "usd" in full: currency = "$"
                elif "sgd" in full: currency = "SGD"
                elif "€" in full or "eur" in full: currency = "€"
                if "/h" in full or "/hr" in full or "heure" in full: unit = "/h"
                elif "/jour" in full or "/day" in full or "/jr" in full: unit = "/jour"
            break

    # Comparaison marché
    country = get_country_id(job.get("location", ""))
    market_min, market_max, market_unit = TJM_RANGES.get(country, (0, 0, ""))

    flag = ""
    if tjm and market_min:
        if tjm < market_min * 0.7:
            flag = "🔻 Très bas"
        elif tjm < market_min:
            flag = "⬇ Sous marché"
        elif tjm > market_max * 1.3:
            flag = "🔺 Très haut"
        elif tjm > market_max:
            flag = "⬆ Au-dessus marché"

    return {
        "tjm": tjm,
        "currency": currency,
        "unit": unit,
        "range": f"{market_min}-{market_max} {market_unit}" if market_min else "",
        "flag": flag,
    }


def _tokenize(text):
    """Tokenize text into a set of normalized words."""
    return set(text.lower().split())

def _jaccard_sim(a, b):
    """Jaccard similarity between two token sets."""
    if not a or not b:
        return 0.0
    inter = a & b
    union = a | b
    return len(inter) / len(union) if union else 0.0

def detect_duplicates(jobs):
    """Regroupe les jobs similaires (même titre + même boîte).
    
    Utilise Jaccard similarity sur tokens, avec pré-groupement par 
    premier mot-clé du titre pour éviter O(n²) sur tous les jobs.
    """
    if not jobs:
        return []

    # Pre-compute token sets
    titles = [_tokenize(j.get("title", "")) for j in jobs]
    companies = [_tokenize(j.get("company", "")) for j in jobs]

    # Group by first keyword of title to reduce comparisons
    buckets = {}
    for i, t in enumerate(titles):
        key = next((w for w in t if w not in {"senior", "lead", "test", "qa", "quality",
                   "engineer", "manager", "consultant", "h/f", "f/h", "h/", "f/",
                   "automation", "software", "engineer", "ingénieur", "consultant"}), 
                   next(iter(t), "zzz"))
        buckets.setdefault(key, []).append(i)

    groups = []
    used = set()
    for bucket in buckets.values():
        for i, a_idx in enumerate(bucket):
            if a_idx in used:
                continue
            group = [jobs[a_idx]]
            used.add(a_idx)
            at, ac = titles[a_idx], companies[a_idx]
            for b_idx in bucket[i+1:]:
                if b_idx in used:
                    continue
                t_sim = _jaccard_sim(at, titles[b_idx])
                c_sim = _jaccard_sim(ac, companies[b_idx])
                if t_sim > 0.6 and c_sim > 0.5:
                    group.append(jobs[b_idx])
                    used.add(b_idx)
            if len(group) > 1:
                groups.append(group)
    return groups


def analyze_skills_gap(jobs, cv_skills=None):
    """Compare skills demandés vs CV, retourne les manquants."""
    if cv_skills is None:
        cv_skills = CV_SKILLS
    all_skills = Counter()
    for job in jobs:
        text = f"{job.get('title', '')} {job.get('description', '')} {job.get('tags', '')}".lower()
        for skill in cv_skills + ["playwright", "aws", "docker", "kubernetes",
                                   "cypress", "rest assured", "postman", "soapui",
                                   "devops", "ci/cd", "jenkins", "gitlab"]:
            if skill in text:
                all_skills[skill] += 1

    top_demanded = [s for s, _ in all_skills.most_common(20)]
    cv_skills_set = set(cv_skills)
    missing = [s for s in top_demanded if s not in cv_skills_set]
    return {
        "top_demanded": top_demanded[:15],
        "missing": missing[:10],
        "match_rate": max(0, 100 - len(missing) * 10),
    }


def source_stats(jobs):
    """Stats par source : volume, freelance rate, TJM."""
    sources = {}
    for job in jobs:
        src = job.get("source", "Unknown")
        if src not in sources:
            sources[src] = {"total": 0, "validee": 0, "tjm_sum": 0, "tjm_count": 0}
        sources[src]["total"] += 1
        if job.get("freelance_status") == "VALIDÉE":
            sources[src]["validee"] += 1
        tjm_info = analyze_tjm(job)
        if tjm_info["tjm"]:
            sources[src]["tjm_sum"] += tjm_info["tjm"]
            sources[src]["tjm_count"] += 1

    return [
        {
            "name": name,
            "total": s["total"],
            "freelance_pct": round(s["validee"] / s["total"] * 100) if s["total"] else 0,
            "avg_tjm": round(s["tjm_sum"] / s["tjm_count"]) if s["tjm_count"] else None,
        }
        for name, s in sorted(sources.items(), key=lambda x: -x[1]["total"])
    ]
