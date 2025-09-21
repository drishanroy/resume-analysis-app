
import io, json, re
from typing import List, Dict, Any
import fitz  # PyMuPDF
from rapidfuzz import fuzz
import textstat

ACTION_BULLET_RE = re.compile(r"^(?:[-•*]\s*)?([A-Z][^\n]{0,200})", re.M)
METRIC_RE = re.compile(r"(?:(\d+\.?\d*)%|\b\d+\b\s*(?:ms|s|min|hr|days?|x|k|K|M|million|billion))")
HEADER_HINTS = ["experience","work","projects","education","skills","summary","certifications"]


def read_ontology(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract plain text from a PDF using PyMuPDF."""
    doc = fitz.open(stream=file_bytes, filetype='pdf')
    blocks = []
    for page in doc:
        blocks.append(page.get_text("text"))
    return "\n".join(blocks)


def detect_sections(text: str) -> Dict[str, str]:
    """Very simple header-based segmentation that is resilient to common headings."""
    lines = [l.strip() for l in text.splitlines()]
    sections: Dict[str, List[str]] = {k: [] for k in HEADER_HINTS}
    current = "summary"
    for ln in lines:
        key = ln.lower()
        matched = None
        for h in HEADER_HINTS:
            if h in key and len(ln) <= 40:
                matched = h
                break
        if matched:
            current = matched
            continue
        sections[current].append(ln)
    return {k: "\n".join(v).strip() for k, v in sections.items() if v}


def normalize_token(t: str) -> str:
    return re.sub(r"[^a-z0-9+.#]", " ", t.lower()).strip()


def extract_skills(text: str, ontology: Dict[str, Any]) -> List[str]:
    tokens = set(normalize_token(w) for w in re.split(r"\W+", text.lower()))
    found = set()
    norm_text = normalize_token(text)
    for bucket, syns in ontology.get("skills", {}).items():
        for s in syns:
            key = normalize_token(s)
            if key in tokens:
                found.add(s)
            else:
                # fuzzy contains for variants
                if fuzz.partial_ratio(key, norm_text) > 90:
                    found.add(s)
    return sorted(found)


def bullets(text: str) -> List[str]:
    return [m.group(1).strip() for m in ACTION_BULLET_RE.finditer(text)]


def score_bullets(bullets_list: List[str], ontology: Dict[str, Any]) -> Dict[str, Any]:
    if not bullets_list:
        return {"score": 0.0, "reasons": ["No bullet points detected."]}
    action_verbs = set(ontology.get("action_verbs", []))
    action_hits = 0
    metric_hits = 0
    tech_hits = 0
    reasons = []
    for b in bullets_list:
        if not b.split():
            continue
        tok0 = b.split()[0].lower()
        if tok0 in action_verbs:
            action_hits += 1
        if METRIC_RE.search(b):
            metric_hits += 1
        if any(s in b.lower() for s in ["python","sql","react","docker","pandas","tensorflow","pytorch","powerbi","tableau","fastapi","flask","airflow"]):
            tech_hits += 1
    n = max(1, len(bullets_list))
    # weight: verbs 0.8, metrics 1.2, tech 1.0 → cap at 3.0
    composite = 0.8 * (action_hits / n) + 1.2 * (metric_hits / n) + 1.0 * (tech_hits / n)
    score = min(3.0, round(composite * 3.0, 2)) / 3.0 * 3.0
    if action_hits < n/2:
        reasons.append("Many bullets lack strong action verbs.")
    if metric_hits < n/2:
        reasons.append("Few bullets quantify impact (%, #, time).")
    if tech_hits < n/2:
        reasons.append("Bullets often miss concrete tech/context.")
    return {"score": round(score,2), "reasons": reasons}


def readability_score(text: str) -> float:
    try:
        grade = textstat.flesch_kincaid_grade(text)
        # ideal 10–12 → full 0.8
        if 10 <= grade <= 12:
            return 0.8
        # linear decay around sweet spot
        return max(0.0, 0.8 - abs(11 - grade) * 0.1)
    except Exception:
        return 0.4


def concision_bonus(text: str) -> float:
    blts = bullets(text)
    if not blts:
        return 0.3
    long = sum(1 for b in blts if len(b.split()) > 28)
    frac = long / len(blts)
    # 0.7 when concise, linearly reduced if many are long
    return max(0.0, 0.7 - 0.7 * frac)


def tense_consistency(text: str) -> float:
    # very rough heuristic: balance between 'ed' and 'ing'
    past = len(re.findall(r"\b\w+ed\b", text.lower()))
    present = len(re.findall(r"\b\w+ing\b", text.lower()))
    total = past + present + 1
    ratio = min(past, present) / total  # more mismatch → higher score
    return 0.2 + 0.3 * (1 - ratio)  # 0.2–0.5


def structure_ats(text: str) -> (float, List[str]):
    reasons = []
    score = 1.5
    if len(text) > 18000:  # ~3 pages raw text
        reasons.append("Resume likely exceeds recommended length.")
        score -= 0.4
    if "\t" in text:
        reasons.append("Tabs/tables may hurt ATS parsing.")
        score -= 0.3
    if text.count("•") + text.count("-") < 5:
        reasons.append("Too few bullet points detected.")
        score -= 0.3
    if not any(h in text.lower() for h in HEADER_HINTS):
        reasons.append("Missing standard section headers.")
        score -= 0.3
    return max(0.0, round(score,2)), reasons


def projects_evidence(sec_text: str) -> float:
    score = 0.0
    if re.search(r"(problem|challenge|goal)", sec_text, re.I):
        score += 0.3
    if re.search(r"(approach|method|stack|tech)", sec_text, re.I):
        score += 0.3
    if METRIC_RE.search(sec_text):
        score += 0.4
    return min(1.0, round(score,2))


def hygiene(text: str) -> float:
    score = 0.5
    if not re.search(r"@", text):
        score -= 0.2
    if not re.search(r"\+?\d{7,}", text):
        score -= 0.1
    if len(text) < 500:
        score -= 0.2
    return max(0.0, round(score,2))


def two_line_summary(skills: List[str], target_role: str = None) -> str:
    lead = target_role or "technology"
    top = ", ".join(skills[:4]) if skills else "impactful projects"
    return (f"Early‑career {lead} candidate with hands‑on experience in {top}. "
            f"Delivers measurable outcomes through clear problem framing, rapid experimentation, and clean deliverables.")


def jd_compare(jd: str, skills: List[str]) -> Dict[str, Any]:
    if not jd:
        return {"coverage_pct": None, "missing_skills": [], "matched_keywords": [], "recommendations": []}
    jd_tokens = set(normalize_token(w) for w in jd.split())
    matched = [s for s in skills if normalize_token(s) in jd_tokens]
    # shortlist a canonical set we care about for missing
    canon = {"python","sql","powerbi","docker","airflow","react","tableau","pandas","numpy","tensorflow","pytorch"}
    missing = [s for s in canon if s not in set(normalize_token(x) for x in skills) and s in jd_tokens]
    coverage = int(100 * len(matched) / max(1, len(matched)+len(missing)))
    recs = [f"Add a bullet showing {m} in context of a project/result." for m in list(missing)[:5]]
    return {"coverage_pct": coverage, "missing_skills": list(missing)[:8], "matched_keywords": matched, "recommendations": recs}


def improvements(section_texts: Dict[str,str]) -> List[Dict[str,str]]:
    tips = []
    exp = section_texts.get('experience','') + "\n" + section_texts.get('projects','')
    blts = bullets(exp)
    if blts:
        for b in blts[:3]:
            if not METRIC_RE.search(b):
                tips.append({
                    "section": "Experience/Projects",
                    "issue": "Bullet lacks measurable result",
                    "fix_example": f"{b.split()[0].capitalize()} ... resulting in {{metric}} (e.g., +23%, −120ms, 2× throughput)."
                })
                break
    if len(section_texts.get('skills','').split()) < 6:
        tips.append({
            "section": "Skills",
            "issue": "Skills too generic or short",
            "fix_example": "Group as Languages / Libraries / Tools with 4–6 items each."
        })
    if not section_texts.get('projects'):
        tips.append({
            "section": "Projects",
            "issue": "Missing or weak projects section",
            "fix_example": "Add 2 projects with Problem→Approach→Result and links."
        })
    return tips
