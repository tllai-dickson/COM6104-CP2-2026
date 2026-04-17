from fastmcp import FastMCP
import sys
import json
import re
import requests
import os
from pathlib import Path

# Ensure logs go to stderr to protect the MCP JSON-RPC pipe
sys.stdout.reconfigure(line_buffering=False)

mcp = FastMCP("fit_score")

# Configuration
LOCAL_LLM_MODEL = "qwen3:0.6B"
OLLAMA_API_URL = "http://localhost:11434/api/generate"

def load_rag_skills(level: str) -> dict:
    """Safely loads the RAG skills JSON file."""
    base_dir = Path(__file__).resolve().parent.parent.parent
    rag_file = base_dir / "rag" / "rag_level_summary.json"
    
    try:
        if rag_file.exists():
            with open(rag_file, "r", encoding="utf-8") as f:
                rag_data = json.load(f)
                
            level_data = rag_data.get(level, {})
            if level == "Management":
                return level_data.get("core_skills", {})
            else:
                return level_data.get("required_techniques", {})
    except Exception as e:
        print(f"Error loading RAG Skills: {e}", file=sys.stderr)
        
    return {}

def load_rag_courses() -> list:
    """Safely loads the recognized certifications from RAG."""
    base_dir = Path(__file__).resolve().parent.parent.parent
    rag_file = base_dir / "rag" / "rag_course.json"
    
    try:
        if rag_file.exists():
            with open(rag_file, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading RAG Courses: {e}", file=sys.stderr)
        
    return []

def check_academic_relevance_llm(title, description):
    """Uses LLM to double-check if a Research/Teaching Assistant role is highly technical."""
    prompt = f"""
    Analyze this academic role. 
    Does it involve heavy, hands-on technical work in AI, Data Science, or Software Engineering (e.g., building deep learning models, writing production code, advanced data pipelines)?
    Or is it mostly administrative, basic grading, or non-technical academic research? Or is it overlapping with candidant higher-education period?

    [TITLE]: {title}
    [DESCRIPTION]: {str(description)[:1000]}

    Respond STRICTLY with valid JSON containing a single boolean key "is_heavy_tech". 
    Set it to true if it is heavy engineering/data science. Set it to false if it is standard academic/admin work. Set it to false if it is overlapping with candidant higher-education period.
    """
    
    payload = {"model": LOCAL_LLM_MODEL, "prompt": prompt, "stream": False, "format": "json"}
    
    try:
        res = requests.post(OLLAMA_API_URL, json=payload, timeout=15)
        text = res.json().get("response", "{}")
        clean_json = re.sub(r"```json\n?|```", "", text).strip()
        data = json.loads(clean_json)
        return bool(data.get("is_heavy_tech", False))
    except Exception as e:
        print(f"LLM Academic Eval Error: {e}", file=sys.stderr)
        return False # Safely default to discounting if LLM fails

def evaluate_qual_and_bonus_llm(cv_edu, cv_exp, job_role, company_name, matched_certs):
    """Uses local LLM to evaluate Qualifications and Industry Bonuses."""
    
    cert_text = ", ".join(matched_certs) if matched_certs else "None"
    
    prompt = f"""
    You are an expert HR AI. Evaluate the candidate against the Job.

    [CANDIDATE DATA]
    Education History: {str(cv_edu)[:1000]}
    Experience Text: {str(cv_exp)[:1000]}
    Recognized AI/Tech Certificates Found: {cert_text}

    [JOB DATA]
    Role: {job_role}
    Company: {company_name}

    Task 1: Qualification Score (Find the Maximum)
    Assign the HIGHEST applicable score based on the candidate's education:
    25: Master degree or above IN AI, Data, or IT.
    20: Bachelor degree IN AI, Data, or IT.
    15: Higher Diploma / Associate Degree IN AI, Data, or IT.
    10: Degree in a non-IT field, BUT the candidate has at least one Recognized AI/Tech Certificate listed above.
    0: Degree in a non-IT field with no recognized tech certs, or no degree.

    Task 2: Bonuses
    - bonus_academic (5 or 0): Is the degree major directly related to the company's specific industry?
    - bonus_domain (5 or 0): Does the candidate's past work experience match the company's industry?

    Respond STRICTLY in valid JSON. You MUST write a detailed "reasoning" step FIRST before outputting the scores.
    {{
        "reasoning": "Step 1: The candidate holds a Master's in Data Science, which is an IT field, so the base is 25. Step 2: The company is... ",
        "qualification_score": <int>,
        "bonus_academic": <int>,
        "bonus_domain": <int>
    }}
    """
    
    payload = {"model": LOCAL_LLM_MODEL, "prompt": prompt, "stream": False, "format": "json"}
    
    try:
        res = requests.post(OLLAMA_API_URL, json=payload, timeout=15)
        text = res.json().get("response", "{}")
        clean_json = re.sub(r"```json\n?|```", "", text).strip()
        data = json.loads(clean_json)
        
        q_score = int(data.get("qualification_score", 0))
        if q_score not in [0, 10, 15, 20, 25]: q_score = 0
        
        return {
            "qualification_score": q_score,
            "bonus_academic": 5 if int(data.get("bonus_academic", 0)) > 0 else 0,
            "bonus_domain": 5 if int(data.get("bonus_domain", 0)) > 0 else 0,
            "justification": data.get("reasoning", "LLM Evaluated.")
        }
    except Exception as e:
        print(f"LLM Eval Error: {e}", file=sys.stderr)
        return {"qualification_score": 0, "bonus_academic": 0, "bonus_domain": 0, "justification": "Error connecting to LLM."}

@mcp.tool()
def compute_fit_score(cv: dict, job: dict, company_profile: dict = None) -> dict:
    
    # ------------------------------------------
    # 0. PRE-PROCESSING: Match Certificates
    # ------------------------------------------
    rag_courses = load_rag_courses()
    cv_full_text_lower = json.dumps(cv).lower()
    
    matched_cert_names = []
    cert_bonus_raw = 0
    
    for course in rag_courses:
        course_name = course.get("course_name", "")
        if course_name and course_name.lower() in cv_full_text_lower:
            matched_cert_names.append(course_name)
            cert_bonus_raw += course.get("score", 0)
            
    bonus_cert = min(cert_bonus_raw, 5)

    # ==========================================
    # 1. EXPERIENCE SCORING (50%)
    # ==========================================
    try: 
        required_exp = float(job.get("MaxYearsExperience", 0))
    except (ValueError, TypeError): 
        required_exp = 0.0

    total_exp = 0.0
    ai_exp = 0.0
    ai_keywords = ['ai', 'data', 'machine learning', 'software', 'developer', 'it', 'tech', 'python', 'analytics', 'research']
    cv_experiences = cv.get("experience_list", cv.get("experience", []))
    
    for exp in cv_experiences:
        try: yrs = float(exp.get("years", 0))
        except (ValueError, TypeError): yrs = 0.0
        
        title_desc = (str(exp.get("title", "")) + " " + str(exp.get("description", ""))).lower()
        
        # --- NEW: LLM-VERIFIED STUDENT/INTERN DISCOUNT LOGIC ---
        is_intern_flag = exp.get("is_internship", False)
        
        basic_academic_keywords = ["intern", "internship", "student", "part-time", "trainee"]
        assistant_keywords = ["research assistant", "teaching assistant"]
        
        is_basic_academic = is_intern_flag or any(kw in title_desc for kw in basic_academic_keywords)
        is_assistant = any(kw in title_desc for kw in assistant_keywords)
        
        apply_discount = False
        
        if is_basic_academic:
            apply_discount = True
        elif is_assistant:
            # It's an RA/TA role. Double-check with LLM!
            is_heavy_tech = check_academic_relevance_llm(exp.get("title", ""), exp.get("description", ""))
            if not is_heavy_tech:
                apply_discount = True # Standard academic work gets the discount
                
        # Apply the 50% discount if triggered
        if apply_discount:
            yrs = yrs * 0.5 
            
        total_exp += yrs
        if any(kw in title_desc for kw in ai_keywords):
            ai_exp += yrs

    effective_exp = 0.5 * (total_exp + ai_exp)

    if required_exp <= 0:
        exp_score = 50.0
        exp_just = f"Job requires 0 yrs. Candidate has {effective_exp:.1f} effective yrs. (50/50)"
    else:
        calculated_ratio = (effective_exp / required_exp) * 50.0
        exp_score = min(calculated_ratio, 50.0)
        exp_just = f"Total Exp: {total_exp:.1f}y, AI Exp: {ai_exp:.1f}y. Effective = {effective_exp:.1f}y. Req: {required_exp}y. Math: min(({effective_exp:.1f}/{required_exp}) * 50, 50) = {exp_score:.1f}/50"

    # ==========================================
    # 2 & 4. QUALIFICATION (25%) AND BONUSES (Max 15% Total)
    # ==========================================
    job_role_desc = str(job.get("JobTitle", job.get("job_title", "Unknown Role")))
    
    llm_eval = evaluate_qual_and_bonus_llm(
        cv_edu=cv.get("education", ""),
        cv_exp=cv.get("experience_list", cv.get("experience", "")),
        job_role=job_role_desc,
        company_name=str(job.get("CompanyName", job.get("company_name", "Unknown Company"))),
        matched_certs=matched_cert_names
    )
    
    qual_score = llm_eval["qualification_score"]
    bonus_acad = llm_eval["bonus_academic"]
    bonus_dom = llm_eval["bonus_domain"]
    
    qual_just = f"Score: {qual_score}/25. AI Eval: {llm_eval['justification']}"
    
    cert_str = f"Recognized Certs ({', '.join(matched_cert_names)}): +{bonus_cert}%" if matched_cert_names else "Recognized Certs: +0%"
    bonus_just = f"Academic Align: +{bonus_acad}%. Domain Knowledge: +{bonus_dom}%. {cert_str}."

    # ==========================================
    # 3. CORE SKILLS SCORING (25%) - RAG INTEGRATED
    # ==========================================
    cv_skills_lower = json.dumps(cv.get("skills", "")).lower()
    job_level = job.get("Level_of_career", "Entry")
    rag_skills_for_level = load_rag_skills(job_level)

    skill_groups = {
        "Languages": "Languages",
        "Cloud": "Cloud",
        "DevOps": "DevOps",
        "Data and Frameworks": "Data and Frameworks",
        "AI": "AI",
        "Visualization": "Visualization",
        "Other": "Others"
    }

    total_skill_score = 0
    skill_justification_parts = []

    for job_key, rag_key in skill_groups.items():
        matched_skills = []
        is_rag_fallback = False
        
        job_val = str(job.get(job_key, "")).strip().lower()
        if not job_val or job_val in ["n/a", "nan", "none"]:
            is_rag_fallback = True
            required_skills = [s.lower() for s in rag_skills_for_level.get(rag_key, [])]
        else:
            required_skills = [s.strip() for s in job_val.split(",") if s.strip()]
            
        for req in required_skills:
            if req and req in cv_skills_lower:
                matched_skills.append(req)
                
        group_score = min(len(matched_skills), 5)
        total_skill_score += group_score
        
        source_str = "RAG Level Standard" if is_rag_fallback else "Job Req"
        if matched_skills:
            skill_justification_parts.append(f"{job_key} [{group_score}/5] (via {source_str}): {', '.join(matched_skills)}")
        else:
            skill_justification_parts.append(f"{job_key} [0/5] (via {source_str}): None matched")

    final_skill_score = min(total_skill_score, 25.0)
    skill_just = "\n".join(skill_justification_parts) + f"\n--> Total Cap Applied: {final_skill_score}/25"

    # ==========================================
    # FINAL CALCULATION
    # ==========================================
    base_score = exp_score + qual_score + final_skill_score
    total_score = base_score + bonus_acad + bonus_dom + bonus_cert
    
    total_score = min(total_score, 100.0)

    return {
        "total_score": round(total_score, 1),
        "breakdown": {
            "experience_score_raw": round(exp_score, 1),
            "qualification_score_raw": qual_score,
            "skill_score_raw": round(final_skill_score, 1),
            "bonuses": bonus_acad + bonus_dom + bonus_cert
        },
        "justification_data": {
            "experience": exp_just,
            "qualification": qual_just,
            "skills": skill_just,
            "bonuses": bonus_just
        },
        "final_math": f"Base ({base_score:.1f}) + Bonuses ({bonus_acad + bonus_dom + bonus_cert}) = {total_score}%"
    }

if __name__ == "__main__":
    mcp.run()
