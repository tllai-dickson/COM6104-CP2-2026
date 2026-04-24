import asyncio
import threading
import sys
import json
import base64
import os
import re
import pandas as pd
from datetime import datetime, timedelta
from contextlib import AsyncExitStack
from pathlib import Path
import requests
import concurrent.futures

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_ollama import OllamaLLM

# ===================================================
# Configuration
# ===================================================
LOCAL_LLM_MODEL = "qwen3:0.6B"
llm = OllamaLLM(model=LOCAL_LLM_MODEL, temperature=0)

# ===================================================
# RAG Helper Functions
# ===================================================
def load_rag_json(filename):
    base_dir = Path(__file__).resolve().parent
    filepath = base_dir / "rag" / filename
    try:
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading {filename}: {e}", file=sys.stderr)
    return None

# ===================================================
# AI Orchestration Logic
# ===================================================
def get_justification(score_dict, job_data):
    """Generates a structured JSON response containing targeted RAG advice for the UI."""
    company_name = str(job_data.get("CompanyName", job_data.get("company", "Unknown")))
    all_courses = load_rag_json("rag_course.json") or []
    aws_courses = [c for c in all_courses if str(c.get("provider", "")).upper() == "AWS"]
    
    company_profiles = load_rag_json("rag_company_profiles.json") or {}
    industry = "Unknown"
    
    if isinstance(company_profiles, dict):
        profile = company_profiles.get(company_name, {})
        industry = profile.get("industry", "Unknown")
    elif isinstance(company_profiles, list):
        for p in company_profiles:
            if str(p.get("company_name", "")).lower() == company_name.lower():
                industry = p.get("industry", "Unknown")
                break
                
    industry_str = industry if industry != "Unknown" else "their specific tech sector"
    
    prompt = f"""
    You are an elite executive career advisor. Evaluate the candidate's Fit Score of {score_dict.get('total_score', 0)}%.
    [JOB & RAG CONTEXT] Company: {company_name}. Industry: {industry_str}. Available AWS Courses: {json.dumps(aws_courses)}

    [REQUIRED OUTPUT FORMAT]
    Respond STRICTLY in valid JSON matching this exact structure:
    {{
        "course": "Suggest ONE most relevant AWS course explicitly by name.",
        "interview_tip": "A strong reminder telling the candidate to research new AI applications related to {industry_str}."
    }}
    """
    try:
        res = requests.post("http://localhost:11434/api/generate", json={"model": LOCAL_LLM_MODEL, "prompt": prompt, "stream": False, "format": "json", "options": {"temperature": 0.0}}, timeout=30)
        clean_json = re.sub(r"```json\n?|```", "", res.json().get("response", "{}")).strip()
        return json.loads(clean_json)
    except Exception as e:
        return {"course": "Unavailable", "interview_tip": "Insight currently unavailable."}

def check_keyword_relevance(keyword):
    prompt = f"""
    Is the job search keyword '{keyword}' related to Information Technology (IT), Data Science, Machine Learning (ML), or Artificial Intelligence (AI)?
    Respond STRICTLY with a valid JSON dictionary: {{"is_tech_related": true}} or {{"is_tech_related": false}}
    """
    try:
        response = llm.invoke(prompt)
        clean_json = re.sub(r"```json\n?|```", "", response).strip()
        data = json.loads(clean_json)
        return bool(data.get("is_tech_related", True))
    except:
        return True

def filter_job_database(df, target_level):
    """Filters jobs by the new specific tech booleans, timeframe, and level."""
    # 1. Tech Relevance Filter
    if 'is_IT' in df.columns:
        tech_filter = (
            (df['is_IT'].astype(str).str.lower() == 'true') | 
            (df['is_DataScience'].astype(str).str.lower() == 'true') | 
            (df['is_AI'].astype(str).str.lower() == 'true') | 
            (df['is_ML'].astype(str).str.lower() == 'true')
        )
        df = df[tech_filter]
    elif 'is_Related' in df.columns:
        # Safe fallback for older CSV formats
        df = df[df['is_Related'].astype(str).str.lower() == 'true']
        
    # 2. Career Level Filter
    if 'Level_of_career' in df.columns:
        df = df[df['Level_of_career'].astype(str).str.lower() == target_level.lower()]
    
    # 3. Timeframe Filter (180 Days)
    cutoff_date = datetime.now() - timedelta(days=180)
    def is_recent(date_str):
        try: return pd.to_datetime(date_str) >= cutoff_date
        except: return True
            
    if 'PostingDate' in df.columns:
        df = df[df['PostingDate'].apply(is_recent)]
        
    return df

# ===================================================
# MCP Orchestration Setup
# ===================================================
def normalize_tool_output(result):
    if hasattr(result, "content"):
        content = result.content
        if isinstance(content, list) and len(content) > 0:
            content = content[0]
        if hasattr(content, "text"):
            try:
                data = json.loads(content.text)
                return data if isinstance(data, dict) else {"raw_text": content.text}
            except:
                return {"raw_text": content.text}
    return result if isinstance(result, dict) else {}

class MCPRuntime:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        self.exit_stack = AsyncExitStack()
        self.sessions = {}
        asyncio.run_coroutine_threadsafe(self._init(), self.loop).result()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def _connect(self, name, script):
        params = StdioServerParameters(command=sys.executable, args=[script])
        read, write = await self.exit_stack.enter_async_context(stdio_client(params))
        session = await self.exit_stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self.sessions[name] = session

    async def _init(self):
        root = Path(__file__).parent.absolute()
        await self._connect("cv_parser", str(root / "tools" / "cv_parser" / "server.py"))
        await self._connect("fit_score", str(root / "tools" / "fit_score" / "server.py"))
        await self._connect("job_scraper", str(root / "tools" / "job_scraper" / "server.py"))

    def call_tool(self, server, tool, args):
        try:
            fut = asyncio.run_coroutine_threadsafe(
                self.sessions[server].call_tool(tool, arguments=args), self.loop
            )
            return fut.result()
        except Exception as e:
            return {"error": str(e)}

_rt = None
def run_agent(action, payload=None):
    global _rt
    if not _rt: _rt = MCPRuntime()

    if action == "process_cv":
        raw_mcp = _rt.call_tool("cv_parser", "parse_cv", {"pdf_base64": payload})
        return normalize_tool_output(raw_mcp)

    if action == "evaluate_levels":
        cv_data = payload.get("cv_data")
        rag_levels = load_rag_json("rag_level_summary.json") or {}
        
        if not rag_levels:
            return {"error": "Could not load rag_level_summary.json"}

        results = {}
        def score_level(level, data):
            mock_job = {
                "JobTitle": f"Standard {level} AI/Data Role",
                "CompanyName": "Tech Industry",
                "MaxYearsExperience": data.get("min_experience_years", 0),
                "Level_of_career": level
            }
            score_raw = _rt.call_tool("fit_score", "compute_fit_score", {"cv": cv_data, "job": mock_job, "company_profile": {}})
            score_dict = normalize_tool_output(score_raw)
            return level, score_dict, data.get("min_experience_years", 0)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(score_level, lvl, data) for lvl, data in rag_levels.items()]
            for future in concurrent.futures.as_completed(futures):
                try:
                    lvl, score_dict, req_exp = future.result()
                    breakdown = score_dict.get("breakdown", {})
                    results[lvl] = {
                        "total": score_dict.get("total_score", 0),
                        "exp_score": breakdown.get("experience_score_raw", 0),
                        "skill_score": breakdown.get("skill_score_raw", 0),
                        "qual_score": breakdown.get("qualification_score_raw", 0),
                        "bonuses": breakdown.get("bonuses", 0),
                        "req_exp": req_exp
                    }
                except Exception as e:
                    print(f"Error scoring sidebar level {lvl}: {e}", file=sys.stderr)
        return results

    if action == "option_1_pipeline":
        keyword = payload.get("keyword", "Data Scientist")
        target_level = payload.get("level", "Entry")
        cv_data = payload.get("cv_data")
        
        is_tech = check_keyword_relevance(keyword)
        if not is_tech:
            return {"error": f"The keyword '{keyword}' is not relevant. Please try a different search."}

        safe_keyword = keyword.replace(" ", "_").lower()
        date_str = datetime.now().strftime("%Y-%m-%d")
        cache_file = os.path.join("job_cache", date_str, f"{safe_keyword}_hk.csv")

        _rt.call_tool("job_scraper", "fetch_live_jobs", {"keyword": keyword})
        
        build_response = _rt.call_tool("job_scraper", "restructure_and_build_db", {"daily_csv_path": cache_file})
        
        return run_agent("option_2_pipeline", {"level": target_level, "cv_data": cv_data, "system_msg": str(build_response)})

    if action == "option_2_pipeline":
        target_level = payload.get("level", "Entry")
        cv_data = payload.get("cv_data")
        system_msg = payload.get("system_msg", "Loaded from local database.")
        
        db_path = "analysised_job_list.csv"
        if not os.path.exists(db_path):
            return {"error": "Database 'analysised_job_list.csv' not found."}
            
        df = pd.read_csv(db_path)
        filtered_df = filter_job_database(df, target_level)
        
        if filtered_df.empty:
            return {"error": f"No valid jobs found."}

        jobs_to_score = filtered_df.to_dict('records')
        all_scored = []
        
        for job in jobs_to_score:
            score_raw = _rt.call_tool("fit_score", "compute_fit_score", {"cv": cv_data, "job": job, "company_profile": {}})
            score_dict = normalize_tool_output(score_raw)
            
            all_scored.append({
                "job_title": job.get("JobTitle", "Unknown"),
                "company": job.get("CompanyName", "Unknown"),
                "url": job.get("JobLink_or_ID", ""),
                "score": score_dict,
                "job_data": job 
            })
            
        all_scored.sort(key=lambda x: x["score"].get("total_score", 0), reverse=True)
        final_results = all_scored[:10]
        
        for i, res in enumerate(final_results):
            res["job_index"] = i + 1
            res["advisor_insight"] = get_justification(res["score"], res["job_data"])
            del res["job_data"] 

        return {"status": "success", "message": system_msg, "results": final_results}

    if action == "option_3_pipeline":
        cv_data = payload.get("cv_data")
        job_ads_b64 = payload.get("job_ads", [])
        
        if not job_ads_b64:
            return {"error": "No PDFs were provided."}
            
        temp_jobs = []
        all_scored_jobs = []
        
        def process_pdf(i, b64_pdf):
            raw_ad_result = _rt.call_tool("cv_parser", "parse_job_ad_pdf", {"pdf_base64": b64_pdf})
            raw_ad = normalize_tool_output(raw_ad_result)
            text_desc = raw_ad.get("raw_text", str(raw_ad))
            
            prompt = f"""
            You are an expert HR Data Engineer. Analyze this job description and return STRICT valid JSON.
            [JOB DESCRIPTION] {text_desc[:2000]}
            [REQUIREMENTS] Keys required: "JobTitle", "CompanyName", "is_IT" (bool), "is_DataScience" (bool), "is_AI" (bool), "is_ML" (bool), "Qualification", "MaxYearsExperience" (int), "Skills": {{"Languages":"", "Cloud":"", "DevOps":"", "Data_and_Frameworks":"", "AI":"", "Visualization":"", "Other":""}}
            """
            try:
                res = requests.post("http://localhost:11434/api/generate", json={"model": LOCAL_LLM_MODEL, "prompt": prompt, "stream": False, "format": "json", "options": {"temperature": 0.0}}, timeout=60)
                ad_data = json.loads(res.json().get("response", "{}"))
            except:
                ad_data = {}

            skills_dict = ad_data.get("Skills", {})
            if isinstance(skills_dict, dict):
                ad_data["Languages"] = skills_dict.get("Languages", "")
                ad_data["Cloud"] = skills_dict.get("Cloud", "")
                ad_data["DevOps"] = skills_dict.get("DevOps", "")
                ad_data["Data and Frameworks"] = skills_dict.get("Data_and_Frameworks", "")
                ad_data["AI"] = skills_dict.get("AI", "")
                ad_data["Visualization"] = skills_dict.get("Visualization", "")
                ad_data["Other"] = skills_dict.get("Other", "")
            
            title_lower = str(ad_data.get("JobTitle", "")).lower()
            management_keywords = ["head", "director", "manager", "lead", "executive"]
            
            try:
                max_exp = float(ad_data.get("MaxYearsExperience", 0))
            except (ValueError, TypeError):
                max_exp = 0.0
                
            if any(kw in title_lower for kw in management_keywords):
                ad_data["Level_of_career"] = "Management"
            elif max_exp >= 5:
                ad_data["Level_of_career"] = "Senior"
            elif 3 <= max_exp < 5:
                ad_data["Level_of_career"] = "Medium"
            else:
                ad_data["Level_of_career"] = "Entry"

            score_raw = _rt.call_tool("fit_score", "compute_fit_score", {"cv": cv_data, "job": ad_data})
            score_dict = normalize_tool_output(score_raw)
            
            return {
                "job_index": i + 1,
                "job_title": ad_data.get("JobTitle", f"Uploaded PDF {i+1}"),
                "company": ad_data.get("CompanyName", "Unknown"),
                "score": score_dict,
                "advisor_insight": get_justification(score_dict, ad_data),
                "temp_ad_data": ad_data
            }

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_pdf, i, b64) for i, b64 in enumerate(job_ads_b64)]
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    temp_jobs.append(result.pop("temp_ad_data"))
                    all_scored_jobs.append(result)
                except Exception as e: print(f"Threading error: {e}", file=sys.stderr)

        all_scored_jobs.sort(key=lambda x: x["job_index"])
        pd.DataFrame(temp_jobs).to_csv("temp.csv", index=False)
        return {"status": "success", "results": all_scored_jobs}

    if action == "cv_advisor":
        cv_data = payload.get("cv_data")
        all_courses = load_rag_json("rag_course.json") or []
        aws_courses = [c for c in all_courses if str(c.get("provider", "")).upper() == "AWS"]
        
        prompt = f"""
        You are an elite IT/AI Career Advisor. Analyze this candidate's CV data and provide an actionable improvement plan.
        [CANDIDATE CV DATA] {json.dumps(cv_data)[:3000]}
        [AVAILABLE CERTIFICATIONS] {json.dumps(aws_courses)}
        Respond STRICTLY with valid JSON matching: {{"executive_summary": "...", "core_strengths": [".."], "critical_skill_gaps": [".."], "recommended_course": "..", "resume_action_points": [".."]}}
        """
        try:
            res = requests.post("http://localhost:11434/api/generate", json={"model": LOCAL_LLM_MODEL, "prompt": prompt, "stream": False, "format": "json", "options": {"temperature": 0.0}}, timeout=300)
            clean_json = re.sub(r"```json\n?|```", "", res.json().get("response", "{}")).strip()
            return json.loads(clean_json)
        except Exception as e:
            return {"error": "The AI Advisor is currently taking too long to respond. Please try again."}

    return {"error": f"Unknown action: {action}"}
