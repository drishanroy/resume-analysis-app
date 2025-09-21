# GenAI-Powered Resume Analysis App

A smart tool to analyze resumes and help students/professionals stand out.

Upload a PDF resume (and an optional Job Description) and get:
- ✅ Extracted **skills, projects, and impactful keywords**
- ⭐ A **transparent score /10** with subscores and reasons
- ✍️ **Section-wise suggestions** with example rewrites
- 📝 A crisp **2-line professional summary**
- 🎯 **JD comparison**: coverage %, missing skills, and tailored recommendations

---

## 🚀 Quick Demo
1. Run API:
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
2. Open **web/index.html** → upload a resume → see results.

Or call via cURL:
```bash
curl -X POST "http://127.0.0.1:8000/analyze"   -F "file=@backend/tests/sample_resume.pdf"   -F "target_role=Data Analyst"   -F "job_description=We need SQL, Python, PowerBI, A/B testing"
```

---

## 📡 API
### `POST /analyze` (multipart/form-data)
- `file`: PDF resume (required)
- `target_role`: string (optional)
- `job_description`: string (optional)

**Example response**
```json
{
  "overall_score": 7.6,
  "subscores": {
    "impact_bullets": 2.4,
    "skill_alignment": 1.6,
    "clarity_tone": 1.8,
    "structure_ats": 1.3,
    "projects": 0.8,
    "hygiene": 0.4
  },
  "highlights": {
    "skills_detected": ["Python","Pandas","SQL","TensorFlow","Docker","React","PowerBI"],
    "bullets_analyzed": ["Built ...", "Optimized ..."]
  },
  "improvements": [
    {"section":"Experience/Projects","issue":"Bullet lacks measurable result","fix_example":"Improved ... resulting in +23% / −120ms"}
  ],
  "two_line_summary": "Early-career Data Analyst ...",
  "jd_comparison": {
    "coverage_pct": 68,
    "missing_skills": ["Airflow","A/B testing"],
    "matched_keywords": ["Python","SQL","PowerBI"],
    "recommendations": ["Add a bullet showing Airflow usage tied to a metric."]
  }
}
```

---

## 📊 Scoring Rubric (10 points)
1. **Impactful bullets (3.0)** → action verb, metric/result, tech/context  
2. **Keyword alignment (2.0)** → relevant skills present & varied  
3. **Clarity & tone (2.0)** → readability G10–12, concision, tense/voice  
4. **Structure & ATS (1.5)** → headers, bullets>paragraphs, parseable  
5. **Projects evidence (1.0)** → problem→approach→result (+ links)  
6. **Basics & hygiene (0.5)** → contact info, length, typos  

---

## ⚙️ Architecture
- **FastAPI** backend → parsing (PyMuPDF) → features (regex + heuristics) → rubric → JSON  
- Skills via **hybrid ontology + fuzzy match**  
- **CORS** enabled for web client  

---

## 🔒 Privacy
- Files processed in memory; no storage by default  
- PII redaction possible for LLMs  
- Prompt-injection safe (user text treated as data)  

---

## 🌐 Local Development
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
Open docs: http://127.0.0.1:8000/docs

---

## 🛠 Roadmap
- Export one-page PDF report  
- Add role presets (SWE / Analyst / PM / MLE)  
- LLM rewrites with cost guardrails  
