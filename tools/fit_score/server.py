import sys
import os
import re
import json
import base64
import requests
from contextlib import redirect_stdout
from fastmcp import FastMCP
import fitz
import pymupdf4llm
from contextlib import contextmanager

# Initialize FastMCP
mcp = FastMCP("cv_parser")

# CRITICAL: Force logs to stderr immediately
sys.stdout.reconfigure(line_buffering=False)

CERT_KEYWORDS = {
    "aws certified cloud practitioner": {"name": "AWS Certified Cloud Practitioner", "level": "Foundation", "bonus": 1},
    "aws certified ai practitioner": {"name": "AWS Certified AI Practitioner", "level": "Foundation", "bonus": 1},
    "cloud digital leader": {"name": "Cloud Digital Leader", "level": "Foundation", "bonus": 2},
    "aws certified solutions architect associate": {"name": "AWS Certified Solutions Architect – Associate", "level": "Associate", "bonus": 2},
    "aws certified developer associate": {"name": "AWS Certified Developer – Associate", "level": "Associate", "bonus": 2},
    "aws certified cloudops engineer associate": {"name": "AWS Certified CloudOps Engineer – Associate", "level": "Associate", "bonus": 2},
    "aws certified data engineer associate": {"name": "AWS Certified Data Engineer – Associate", "level": "Associate", "bonus": 2},
    "aws certified machine learning engineer associate": {"name": "AWS Certified Machine Learning Engineer – Associate", "level": "Associate", "bonus": 2},
    "associate cloud engineer": {"name": "Associate Cloud Engineer", "level": "Associate", "bonus": 2},
    "cloud developer associate": {"name": "Cloud Developer (Associate)", "level": "Associate", "bonus": 2},
    "cloud devops engineer associate": {"name": "Cloud DevOps Engineer (Associate)", "level": "Associate", "bonus": 2},
    "azure administrator associate": {"name": "Microsoft Certified: Azure Administrator Associate", "level": "Associate", "bonus": 2},
    "power platform developer associate": {"name": "Microsoft Certified: Power Platform Developer Associate", "level": "Associate", "bonus": 2},
    "azure ai engineer associate": {"name": "Microsoft Certified: Azure AI Engineer Associate", "level": "Associate", "bonus": 2},
    "azure data scientist associate": {"name": "Microsoft Certified: Azure Data Scientist Associate", "level": "Associate", "bonus": 2},
    "azure database administrator associate": {"name": "Microsoft Certified: Azure Database Administrator Associate", "level": "Associate", "bonus": 2},
    "azure network engineer associate": {"name": "Microsoft Certified: Azure Network Engineer Associate", "level": "Associate", "bonus": 2},
    "power bi data analyst associate": {"name": "Microsoft Certified: Power BI Data Analyst Associate", "level": "Associate", "bonus": 3},
    "aws certified solutions architect professional": {"name": "AWS Certified Solutions Architect – Professional", "level": "Professional", "bonus": 3},
    "aws certified devops engineer professional": {"name": "AWS Certified DevOps Engineer – Professional", "level": "Professional", "bonus": 3},
    "aws certified generative ai developer professional": {"name": "AWS Certified Generative AI Developer – Professional", "level": "Professional", "bonus": 3},
    "professional cloud architect": {"name": "Professional Cloud Architect", "level": "Professional", "bonus": 3},
    "professional cloud developer": {"name": "Professional Cloud Developer", "level": "Professional", "bonus": 3},
    "professional cloud devops engineer": {"name": "Professional Cloud DevOps Engineer", "level": "Professional", "bonus": 3},
    "professional cloud security engineer": {"name": "Professional Cloud Security Engineer", "level": "Professional", "bonus": 3},
    "professional cloud network engineer": {"name": "Professional Cloud Network Engineer", "level": "Professional", "bonus": 3},
    "professional data engineer": {"name": "Professional Data Engineer", "level": "Professional", "bonus": 3},
    "professional machine learning engineer": {"name": "Professional Machine Learning Engineer", "level": "Professional", "bonus": 3},
    "professional collaboration engineer": {"name": "Professional Collaboration Engineer", "level": "Professional", "bonus": 3},
    "azure solutions architect expert": {"name": "Microsoft Certified: Azure Solutions Architect Expert", "level": "Professional", "bonus": 3},
    "power platform solutions architect expert": {"name": "Microsoft Certified: Power Platform Solutions Architect Expert", "level": "Professional", "bonus": 3},
    "devops engineer expert": {"name": "Microsoft Certified: DevOps Engineer Expert", "level": "Professional", "bonus": 3},
    "aws certified security specialty": {"name": "AWS Certified Security – Specialty", "level": "Specialty", "bonus": 3},
    "aws certified advanced networking specialty": {"name": "AWS Certified Advanced Networking – Specialty", "level": "Specialty", "bonus": 3},
    "aws certified machine learning specialty": {"name": "AWS Certified Machine Learning – Specialty", "level": "Specialty", "bonus": 3},
    "azure virtual desktop specialty": {"name": "Microsoft Certified: Azure Virtual Desktop Specialty", "level": "Specialty", "bonus": 3},
    "azure cosmos db developer specialty": {"name": "Microsoft Certified: Azure Cosmos DB Developer Specialty", "level": "Specialty", "bonus": 1},
    "huawei cloud migration competency": {"name": "Huawei Cloud Certified - Cloud Migration Competency (Advanced)", "level": "General", "bonus": 1},
    "huawei cloud service partner": {"name": "Huawei Cloud Service Partner / Consulting Partners / Cloud Solution Provider", "level": "General", "bonus": 1},
    "outsystems partner": {"name": "OutSystems Partner", "level": "General", "bonus": 1},
    "cisa": {"name": "CISA – Certified Information Systems Auditor (ISACA)", "level": "General", "bonus": 1},
    "cism": {"name": "CISM – Certified Information Security Manager (ISACA)", "level": "General", "bonus": 1},
    "ccsp": {"name": "CCSP – Certified Cloud Security Professional ((ISC)²)", "level": "General", "bonus": 1},
    "iso 27001 certified": {"name": "ISO/IEC 27001:2013 Certified (Information Security Management System)", "level": "General", "bonus": 1},
    "iso 27001 registered": {"name": "ISO 27001 Registered", "level": "General", "bonus": 3}
}

@contextmanager
def silence_system_stdout():
    """Physically redirects the system-level stdout to dev/null."""
    new_target = os.open(os.devnull, os.O_WRONLY)
    old_stdout_fd = os.dup(sys.stdout.fileno())
    try:
        os.dup2(new_target, sys.stdout.fileno())
        yield
    finally:
        os.dup2(old_stdout_fd, sys.stdout.fileno())
        os.close(new_target)
        os.close(old_stdout_fd)

def extract_md_from_b64(pdf_base64):
    try:
        pdf_bytes = base64.b64decode(pdf_base64)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        with silence_system_stdout():
            md_text = pymupdf4llm.to_markdown(doc)
            
        return md_text
    except Exception as e:
        print(f"Extraction Error: {e}", file=sys.stderr)
        return ""

# ==========================================
# NEW: Targeted LLM Call just for Education
# ==========================================
def extract_education_llm(text):
    """Uses LLM to extract an array of all degrees with their specific subjects."""
    prompt = f"""
    Extract ALL educational degrees from the following CV text.
    Return STRICTLY valid JSON matching this exact structure:
    [
        {{
            "degree_level": "e.g., Bachelor, Master, PhD, Diploma",
            "subject": "e.g., Computer Science, Data Science, Finance",
            "institution": "University Name"
        }}
    ]
    If no education is found, return [].
    
    [CV TEXT]
    {text[:4000]}
    """
    payload = {"model": "qwen3:0.6B", "prompt": prompt, "stream": False, "format": "json","options": {"temperature": 0.0}}
    try:
        res = requests.post("http://localhost:11434/api/generate", json=payload, timeout=15)
        clean = re.sub(r"```json\n?|```", "", res.json().get("response", "[]")).strip()
        return json.loads(clean)
    except Exception as e:
        print(f"LLM Education Parsing Error: {e}", file=sys.stderr)
        return []

TECH_DICTIONARY = [
    "python", "sql", "r", "matlab", "tensorflow", "pytorch", 
    "pandas", "numpy", "scikit-learn", "nlp", "computer vision", 
    "llm", "aws", "azure", "gcp", "docker", "git"
]

@mcp.tool()
def parse_cv(pdf_base64: str) -> dict:
    md_text = extract_md_from_b64(pdf_base64)
    text_lower = md_text.lower()

    # 1. Education Extraction (Upgraded to LLM to capture all degrees + subjects)
    education_list = extract_education_llm(md_text)

    # 2. Markdown Experience Extraction + Hierarchy of Rules (KEPT EXACTLY AS YOU WROTE IT)
    experience_list = []
    lines = md_text.split('\n')
    
    for line in lines:
        line_l = line.lower().strip()
        
        if line_l.startswith("#") or line_l.startswith("**"):
            date_match = re.search(r'(\d{4})|([A-Z][a-z]+\s\d{4})', line)
            
            if date_match:
                job_title = line.strip().replace('#', '').replace('*', '').strip()[:30]
                
                if "student assistant" in line_l:
                    continue
                    
                pt_keywords = ["intern", "part-time", "trainee", "undergraduate", "summer"]
                is_intern = any(kw in line_l for kw in pt_keywords)
                
                ft_keywords = [
                    "analyst", "engineer", "specialist", "scientist", 
                    "manager", "developer", "consultant", 
                    "research assistant", "teaching assistant"
                ]
                is_fulltime = any(kw in line_l for kw in ft_keywords)
                
                if is_intern:
                    experience_list.append({"title": job_title, "years": 1.0, "is_internship": True})
                elif is_fulltime and not is_intern:
                    experience_list.append({"title": job_title, "years": 3.0, "is_internship": False})

    if not experience_list and any(word in text_lower for word in ["intern", "part-time"]):
        experience_list.append({"title": "Intern / PT", "years": 1.0, "is_internship": True})

    # 3. Skills Extraction
    skills = [skill for skill in TECH_DICTIONARY if skill in text_lower]

    # 4. Certification Extraction
    found_certs = []
    for key, info in CERT_KEYWORDS.items():
        if key in text_lower:
            found_certs.append({
                "cert_name": info["name"], "quality_level": info["level"], "bonus_mark": info["bonus"]
            })

    return {
        "education": education_list,  # Now returns the full array of degrees!
        "experience_list": experience_list,
        "skills": list(set(skills)),
        "certifications": found_certs
    }

# ==========================================
# NEW: Job Ad Parsers for UI Tabs 4 & 5
# ==========================================
def extract_job_ad_llm(text):
    prompt = f"""
    Extract job requirements from this text.
    Return STRICTLY valid JSON matching this structure:
    {{
        "qualification": "Required degree level and specific subject/major",
        "min_experience": <float, required years>,
        "skills_required": ["skill1", "skill2"],
        "role_overview": "Brief 1-sentence summary"
    }}
    
    [TEXT]
    {text[:4000]}
    """
    payload = {"model": "qwen3:0.6B", "prompt": prompt, "stream": False, "format": "json", "options": {"temperature": 0.0}}
    try:
        res = requests.post("http://localhost:11434/api/generate", json=payload, timeout=15)
        clean = re.sub(r"```json\n?|```", "", res.json().get("response", "{}")).strip()
        return json.loads(clean)
    except Exception:
        return {}

@mcp.tool()
def parse_job_ad_text(raw_text: str) -> dict:
    """Used by Tab 4: Quick Paste Evaluator"""
    return extract_job_ad_llm(raw_text)

@mcp.tool()
def parse_job_ad_pdf(pdf_base64: str) -> dict:
    """Used by Tab 5: PDF Evaluator"""
    md_text = extract_md_from_b64(pdf_base64)
    if not md_text.strip(): 
        return {"error": "Could not extract text from PDF."}
        
    # FIX: Return the raw markdown text directly!
    # Do NOT pass it through extract_job_ad_llm, which destroys the 
    # Job Title and Company Name before the Orchestrator can parse it.
    return {"raw_text": md_text}

if __name__ == "__main__":
    mcp.run(transport="stdio")
