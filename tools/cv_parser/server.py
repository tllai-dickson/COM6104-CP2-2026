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

# Ensure logs go to stderr to protect the MCP JSON-RPC pipe
sys.stdout.reconfigure(line_buffering=False)

CERT_KEYWORDS = {
    "aws": {"name": "AWS Certified Solutions Architect / ML Specialty", "level": "Professional", "bonus": 5},
    "azure": {"name": "Microsoft Certified: Azure AI Engineer", "level": "Associate", "bonus": 3},
    "google": {"name": "Google Professional Machine Learning Engineer", "level": "Professional", "bonus": 5},
    "nvidia": {"name": "NVIDIA Deep Learning Institute", "level": "Specialist", "bonus": 3},
    "tensorflow": {"name": "TensorFlow Developer Certificate", "level": "Specialist", "bonus": 2}
}

@contextmanager
def silence_system_stdout():
    """Physically redirects the system-level stdout to dev/null to prevent library spam."""
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

def extract_education_llm(text):
    """Leverages local LLM to extract an array of degrees and associated subject domains."""
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
    payload = {"model": "qwen3:0.6B", "prompt": prompt, "stream": False, "format": "json"}
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

    # 1. Education Extraction 
    education_list = extract_education_llm(md_text)

    # 2. Markdown Experience Extraction
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
        "education": education_list,  
        "experience_list": experience_list,
        "skills": list(set(skills)),
        "certifications": found_certs
    }

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
    payload = {"model": "qwen3:0.6B", "prompt": prompt, "stream": False, "format": "json"}
    try:
        res = requests.post("http://localhost:11434/api/generate", json=payload, timeout=15)
        clean = re.sub(r"```json\n?|```", "", res.json().get("response", "{}")).strip()
        return json.loads(clean)
    except Exception:
        return {}

@mcp.tool()
def parse_job_ad_text(raw_text: str) -> dict:
    """Processes plain text job descriptions for downstream evaluations."""
    return extract_job_ad_llm(raw_text)

@mcp.tool()
def parse_job_ad_pdf(pdf_base64: str) -> dict:
    """Extracts raw markdown text from PDF job ads for the Orchestrator LLM parsing pipeline."""
    md_text = extract_md_from_b64(pdf_base64)
    if not md_text.strip(): 
        return {"error": "Could not extract text from PDF."}
        
    return {"raw_text": md_text}

if __name__ == "__main__":
    mcp.run(transport="stdio")
