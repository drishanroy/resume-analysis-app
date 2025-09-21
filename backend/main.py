
import os
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from utils import (
    read_ontology, extract_text_from_pdf, detect_sections, extract_skills,
    score_bullets, readability_score, concision_bonus, tense_consistency,
    structure_ats, projects_evidence, hygiene, two_line_summary, jd_compare,
    improvements, bullets
)

ONTOLOGY = read_ontology(os.path.join(os.path.dirname(__file__), 'ontology.json'))

app = FastAPI(title="Resume Analysis API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalysisResponse(BaseModel):
    overall_score: float
    subscores: dict
    highlights: dict
    improvements: list
    two_line_summary: str
    jd_comparison: dict

@app.get("/health")
async def health():
    return {"ok": True, "version": "0.1.0"}

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze(
    file: UploadFile = File(...),
    target_role: Optional[str] = Form(None),
    job_description: Optional[str] = Form(None)
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF resume.")
    file_bytes = await file.read()

    # Parse & segment
    try:
        text = extract_text_from_pdf(file_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse PDF: {e}")

    sections = detect_sections(text)
    whole = text

    # Features
    skills = extract_skills(whole, ONTOLOGY)
    blts = bullets(sections.get("experience","") + "\n" + sections.get("projects",""))
    bullets_score = score_bullets(blts, ONTOLOGY)
    clarity = readability_score(whole) + concision_bonus(whole) + tense_consistency(whole)  # up to ~2.0
    ats_score, ats_reasons = structure_ats(whole)
    proj_score = projects_evidence(sections.get("projects",""))
    hygiene_score = hygiene(whole)

    # Map to rubric weights to 10.0 total
    impact_bullets = min(3.0, bullets_score["score"])                 # /3.0
    keyword_alignment = min(2.0, round(2.0 * len(skills[:10]) / 10, 2))  # crude density proxy
    clarity_tone = min(2.0, round(clarity, 2))
    structure_ats_score = min(1.5, ats_score)
    projects_sub = min(1.0, proj_score)
    hygiene_sub = min(0.5, hygiene_score)

    total = impact_bullets + keyword_alignment + clarity_tone + structure_ats_score + projects_sub + hygiene_sub
    overall = round(float(total), 2)

    # Improvements
    tips = improvements(sections)
    if ats_reasons:
        tips.append({"section": "Structure/ATS", "issue": "; ".join(ats_reasons), "fix_example": "Use simple headers and bullet lists; avoid tables/columns."})

    # Summary & JD compare
    summary = two_line_summary(skills, target_role=target_role)
    jdcomp = jd_compare(job_description or "", skills)

    response = {
        "overall_score": overall,
        "subscores": {
            "impact_bullets": round(impact_bullets,2),
            "skill_alignment": round(keyword_alignment,2),
            "clarity_tone": round(clarity_tone,2),
            "structure_ats": round(structure_ats_score,2),
            "projects": round(projects_sub,2),
            "hygiene": round(hygiene_sub,2)
        },
        "highlights": {
            "skills_detected": skills,
            "bullets_analyzed": blts[:10]
        },
        "improvements": tips,
        "two_line_summary": summary,
        "jd_comparison": jdcomp
    }
    return response
