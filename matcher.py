"""Matching CV <-> offres, TJM, skills gap, doublons, stats sources."""
import re
import unicodedata
from collections import Counter

# Valeurs métier reconnues (comparées après normalisation, jamais à l'identique)
REMOTE_ALIASES = {
    "remote", "fully_remote", "fully remote", "full remote", "remote work",
    "100% remote", "100%remote", "a distance", "en remote",
    "teletravail total", "teletravail complet",
}
HYBRID_ALIASES = {
    "hybrid", "hybride", "hybrid remote", "semi remote", "remote partiel",
    "teletravail", "teletravail partiel", "partiel",
}

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
    "confluence", "zephyr", "ranorex",
    # Équivalents français : le marché visé publie en français
    "recette", "plan de test", "cas de test", "non-régression", "anomalie"
]


def _norm(value):
    """Normalise une chaîne : minuscules, sans accents, espaces réduits.

    Base de toutes les comparaisons du module : deux écritures d'une même
    valeur métier (VALIDÉE / validee / Validée) doivent produire le même score.
    """
    if not isinstance(value, str):
        return ""
    txt = unicodedata.normalize("NFKD", value)
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", txt).strip().lower()


def _kw(text_norm, keyword):
    """Mot-clé présent comme mot entier dans un texte déjà passé par _norm().

    Évite les faux positifs par sous-chaîne (« api » dans « capital »,
    « test » dans « latest »). Les mots-clés contenant un séparateur
    technique ("ci/cd", "/jour") restent testés en sous-chaîne.
    """
    kw = _norm(keyword)
    if not kw or not text_norm:
        return False
    if " " in kw:
        pattern = r"(?<![a-z0-9])" + r"\s+".join(re.escape(p) for p in kw.split(" ")) + r"(?![a-z0-9])"
        return re.search(pattern, text_norm) is not None
    if re.fullmatch(r"[a-z0-9]+", kw):
        return re.search(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])", text_norm) is not None
    return kw in text_norm


def _remote_points(remote_type):
    """10 = full remote, 5 = hybride, 0 = sur site ou inconnu."""
    rt = _norm(remote_type)
    if rt in REMOTE_ALIASES or ("remote" in rt and "non" not in rt and "partiel" not in rt):
        return 10
    if rt in HYBRID_ALIASES or "hybrid" in rt or "hybride" in rt or "partiel" in rt:
        return 5
    return 0


def _freelance_points(freelance_status):
    """10 = statut validé, 5 = ambigu, 0 = non freelance ou inconnu."""
    fs = _norm(freelance_status)
    if fs.startswith("valid"):
        return 10
    if fs.startswith("ambig"):
        return 5
    return 0


def get_country_id(location):
    """Marché de référence d'une offre d'après sa localisation.

    Retourne "inconnu" si aucun marché n'est reconnu : appliquer le marché
    français à une offre suisse (ou allemande) produit une comparaison de TJM
    fausse, ce qui est pire qu'aucune comparaison.
    """
    loc = _norm(location)
    markets = [
        ("france", ("france", "paris", "lyon", "marseille", "toulouse", "bordeaux",
                    "lille", "nantes", "ile-de-france", "ile de france", "nice",
                    "rennes", "strasbourg", "bagnolet")),
        ("suisse", ("suisse", "switzerland", "swiss", "zurich", "geneve", "lausanne",
                    "berne", "bern", "bale", "basel", "zug", "lucerne", "lugano")),
        ("luxembourg", ("luxembourg", "luxemburg", "lux.")),
        ("dubai", ("dubai", "uae", "emirates", "abu dhabi")),
        ("singapour", ("singapore", "singapour")),
    ]
    for country, words in markets:
        if any(_kw(loc, w) for w in words):
            return country
    return "inconnu"


def match_job_to_cv(job, cv_skills=None):
    """Score /100: pertinence du job par rapport au profil."""
    if cv_skills is None:
        cv_skills = CV_SKILLS
    title = _norm(job.get("title"))
    desc = _norm(job.get("description")) + " " + _norm(job.get("tags"))
    text = title + " " + desc

    score = 0

    # Titre (20pts max)
    title_points = 0
    if any(_kw(title, k) for k in ["qa", "quality", "qualite", "test", "testeur",
                                   "sdet", "tester", "recette", "assurance qualite"]):
        title_points += 10
    if any(_kw(title, k) for k in ["lead", "senior", "manager", "consultant"]):
        title_points += 5
    if any(_kw(title, k) for k in ["automation", "engineer", "architect"]):
        title_points += 5
    score += min(title_points, 20)

    # Skills cibles (30pts max)
    skill_score = 0
    matched = []
    for skill in cv_skills:
        if _kw(text, skill):
            skill_score += 3
            matched.append(skill)
    score += min(skill_score, 30)

    # Remote (10pts)
    score += _remote_points(job.get("remote_type"))

    # Freelance (10pts)
    score += _freelance_points(job.get("freelance_status"))

    # Keywords bonus (20pts)
    bonus_kw = ["contract", "mission", "freelance", "régie", "prestation",
                "sasu", "consultant", "independent", "tjm", "/jour", "daily rate"]
    bonus = sum(2 for kw in bonus_kw if _kw(text, kw))
    score += min(bonus, 20)

    # TJM bonus (10pts)
    salary = _norm(job.get("salary"))
    if "/jour" in salary or "/j" in salary or _kw(salary, "tjm"):
        score += 10
    elif "chf" in salary or "€" in salary:
        score += 5

    return min(score, 100), matched


def filtrer_par_budget(offres, budget_min=None):
    """Retient les offres dont le TJM analysé atteint le budget minimum.

    Règle métier validée avec le PO :
      - la borne est inclusive (une offre à 600 passe un budget de 600) ;
      - une offre sans budget renseigné est exclue dès qu'un budget est demandé :
        on ne suppose jamais un budget absent, on l'écarte ;
      - un budget absent (None) ne filtre rien ; un budget à 0 demande simplement
        que le budget soit renseigné ;
      - l'ordre d'entrée est conservé : le tri est la responsabilité de trier().
    """
    if not offres:
        return []
    if budget_min is None:
        return list(offres)
    retenues = []
    for offre in offres:
        if not isinstance(offre, dict):
            continue
        tjm = analyze_tjm(offre).get("tjm")
        if tjm is not None and tjm >= budget_min:
            retenues.append(offre)
    return retenues


def analyze_tjm(job):
    """Détecte TJM dans le job et compare au marché."""
    text = _norm(f"{job.get('salary') or ''} {job.get('title') or ''} {job.get('description') or ''}")
    tjm = None
    currency = ""
    unit = ""

    # Patterns TJM
    patterns = [
        r"(\d+)\s*(?:[-–—]|a|à|to|jusqu\'?à)\s*(\d+)\s*(€|eur|chf|usd|sgd)?\s*/?\s*(jour|day|jr|h|hr|heure)",
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
        text = _norm(f"{job.get('title', '')} {job.get('description', '')} {job.get('tags', '')}")
        for skill in cv_skills + ["playwright", "aws", "docker", "kubernetes",
                                   "cypress", "rest assured", "postman", "soapui",
                                   "devops", "ci/cd", "jenkins", "gitlab"]:
            if _kw(text, skill):
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
        if _norm(job.get("freelance_status")).startswith("valid"):
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
