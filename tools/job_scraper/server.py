from fastmcp import FastMCP
import sys
import os
import requests
import pandas as pd
import time
from datetime import datetime
from contextlib import redirect_stdout
import re
import json

# Ensure logs go to stderr to protect the MCP JSON-RPC pipe
sys.stdout.reconfigure(line_buffering=False)

mcp = FastMCP("job_scraper")

# API Configuration
RAPIDAPI_KEY = "YOUR_KEY"
API_HOST = "indeed-scraper-api.p.rapidapi.com"

JOB_DETAILS_MEMORY = {}

def safe_post_request(url, headers, payload, max_retries=5):
    """Executes API requests with exponential backoff for handling HTTP 429 Rate Limits."""
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 429:
                wait_time = 5 * (attempt + 1)
                print(f"Rate Limit (429). Pausing for {wait_time} seconds...", file=sys.stderr)
                time.sleep(wait_time)
                continue
                
            if response.status_code in [502, 504]:
                print(f"Server busy ({response.status_code}). Retrying...", file=sys.stderr)
                time.sleep(3)
                continue
                
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            if attempt == max_retries - 1: 
                print(f"API Error: {e}", file=sys.stderr)
                return None
            time.sleep(3)
    return None

@mcp.tool()
def fetch_live_jobs(keyword: str, location: str = "Hong Kong") -> list:
    """Performs deep search pagination across job boards and caches results locally."""
    global JOB_DETAILS_MEMORY
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    safe_keyword = keyword.replace(" ", "_").lower()
    folder_path = os.path.join("job_cache", date_str)
    os.makedirs(folder_path, exist_ok=True)
    cache_file = os.path.join(folder_path, f"{safe_keyword}_hk.csv")
    
    url = f"https://{API_HOST}/api/job"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY, 
        "x-rapidapi-host": API_HOST, 
        "Content-Type": "application/json"
    }

    all_results = []
    max_pages = 5 

    with redirect_stdout(sys.stderr):
        for page in range(1, max_pages + 1):
            
            payload = {
                "scraper": {
                    "maxRows": 20,
                    "page": page,
                    "query": keyword, 
                    "location": location, 
                    "sort": "date", 
                    "fromDays": "14", 
                    "country": "hk"
                }
            }

            data = safe_post_request(url, headers, payload)
            
            if not data:
                break
                
            jobs_list = data.get("returnvalue", {}).get("data", [])
            
            if not jobs_list:
                break 

            for index, job in enumerate(jobs_list):
                url_str = job.get("jobUrl", "")
                jk = url_str.split("jk=")[1].split("&")[0] if "jk=" in url_str else f"idx_{page}_{index}"
                
                JOB_DETAILS_MEMORY[jk] = job.get("descriptionText", "")

                all_results.append({
                    "job_id": jk,
                    "title": job.get("title", "Unknown"),
                    "company": job.get("companyName", "Unknown"),
                    "location": job.get("location", {}).get("formattedAddressShort", "HK"),
                    "post_date": date_str, 
                    "url": url_str
                })
                
            # Maintain API speed limit compliance
            time.sleep(3.5) 

    if all_results:
        df_to_save = pd.DataFrame(all_results).fillna("")
        df_to_save.to_csv(cache_file, index=False)
        return df_to_save.to_dict('records')
    
    return []

@mcp.tool()
def fetch_job_detail(job_id: str) -> str:
    global JOB_DETAILS_MEMORY
    return JOB_DETAILS_MEMORY.get(job_id, "Description not found.")

def call_local_ollama(description_text):
    """Leverages local LLM to extract structured job schema for the master database."""
    if not description_text or len(str(description_text)) < 50:
        return {}

    prompt = f"""
    You are an expert HR Data Engineer. Analyze this job description and return STRICT valid JSON.
    
    [JOB DESCRIPTION]
    {str(description_text)[:3000]}
    
    [REQUIREMENTS]
    Extract the following keys exactly:
    {{
        "is_Related": true or false (Is this an IT, AI, or Data Science job?),
        "Level_of_career": "Entry", "Medium", "Senior", or "Management" (Evaluate based on text),
        "MaxYearsExperience": <int> (Extract the minimum or maximum years of experience required, default 0),
        "Qualification": "Extracted education requirements",
        "Languages": "e.g., Python, SQL, Java",
        "Cloud": "e.g., AWS, Azure",
        "DevOps": "e.g., Docker, CI/CD",
        "Data_and_Frameworks": "e.g., Pandas, PyTorch",
        "AI": "e.g., Machine Learning, LLM",
        "Visualization": "e.g., Tableau, PowerBI",
        "Other": "Any other required tech skills"
    }}
    """
    
    payload = {
        "model": "qwen3:0.6B",
        "prompt": prompt,
        "stream": False,
        "format": "json" 
    }
    
    try:
        res = requests.post("http://localhost:11434/api/generate", json=payload, timeout=60)
        return json.loads(res.json().get("response", "{}"))
    except Exception as e:
        print(f"Ollama Error: {e}", file=sys.stderr)
        return {}

@mcp.tool()
def restructure_and_build_db(daily_csv_path: str, search_tag: str) -> str:
    """Ingests scraped data, prevents duplicate processing, extracts LLM metrics, and appends to the database."""
    global JOB_DETAILS_MEMORY
    
    master_file = "analysised_job_list.csv" 
    
    if not os.path.exists(daily_csv_path):
        return f"Error: Could not find {daily_csv_path}"
        
    df_daily = pd.read_csv(daily_csv_path).fillna("")
    
    if os.path.exists(master_file):
        df_master = pd.read_csv(master_file).fillna("")
    else:
        df_master = pd.DataFrame(columns=[
            "job_id", "search_tag", "PostingDate", "CompanyName", "JobTitle", 
            "JobLink_or_ID", "is_Related", "Level_of_career", "MaxYearsExperience", 
            "Qualification", "Languages", "Cloud", "DevOps", "Data and Frameworks", 
            "AI", "Visualization", "Other", "full_description"
        ])

    processed_count = 0
    skipped_count = 0
    new_rows = []

    # Map existing jobs to prevent redundant LLM processing
    transformed_jobs = {}
    if not df_master.empty:
        for _, row in df_master.iterrows():
            jid = str(row.get('job_id', ''))
            if jid:
                transformed_jobs[jid] = True

    with redirect_stdout(sys.stderr):
        for _, row in df_daily.iterrows():
            jid = str(row.get('job_id', ''))
            
            if jid in transformed_jobs:
                skipped_count += 1
                continue
                
            processed_count += 1
            desc = JOB_DETAILS_MEMORY.get(jid, row.get('descriptionText', ''))
            ext_data = call_local_ollama(desc)
                
            new_rows.append({
                "job_id": jid,
                "search_tag": search_tag,
                "PostingDate": row.get('post_date'), 
                "CompanyName": row.get('company'),
                "JobTitle": row.get('title'),
                "JobLink_or_ID": row.get('url'),
                "is_Related": ext_data.get("is_Related", True),
                "Level_of_career": ext_data.get("Level_of_career", "Entry"),
                "MaxYearsExperience": ext_data.get("MaxYearsExperience", 0),
                "Qualification": ext_data.get("Qualification", "N/A"),
                "Languages": ext_data.get("Languages", ""),
                "Cloud": ext_data.get("Cloud", ""),
                "DevOps": ext_data.get("DevOps", ""),
                "Data and Frameworks": ext_data.get("Data_and_Frameworks", ""),
                "AI": ext_data.get("AI", ""),
                "Visualization": ext_data.get("Visualization", ""),
                "Other": ext_data.get("Other", ""),
                "full_description": desc
            })

    if new_rows:
        df_new = pd.DataFrame(new_rows)
        df_combined = pd.concat([df_master, df_new], ignore_index=True)
        df_combined = df_combined.drop_duplicates(subset=['job_id'], keep='last')
        df_combined.to_csv(master_file, index=False)
        
    return f"Pipeline Complete! Processed {processed_count} new jobs. Skipped {skipped_count} already transformed jobs."

if __name__ == "__main__":
    mcp.run()
