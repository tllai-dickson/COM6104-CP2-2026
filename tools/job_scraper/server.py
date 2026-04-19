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
            
            if response.status_code != 200:
                error_msg = response.text
                if "exceeded" in error_msg.lower() or "quota" in error_msg.lower():
                    print("CRITICAL ERROR: RapidAPI Monthly Quota Exceeded!", file=sys.stderr)
                    return None
                    
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

            print(f"DEBUG: Fetching page {page} for '{keyword}'...", file=sys.stderr)
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
                
            time.sleep(3.5) 

    if all_results:
        print(f"DEBUG: Fetched {len(all_results)} jobs. Saving to cache.", file=sys.stderr)
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
        "is_IT": true or false,
        "is_DataScience": true or false,
        "is_AI": true or false,
        "is_ML": true or false,
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
        "format": "json",
        "options": {"temperature": 0.0} 
    }
    
    try:
        res = requests.post("http://localhost:11434/api/generate", json=payload, timeout=60)
        return json.loads(res.json().get("response", "{}"))
    except Exception as e:
        print(f"Ollama Error: {e}", file=sys.stderr)
        return {}

def determine_career_level(title, max_years):
    """Deterministically calculates career level based on title keywords and experience."""
    title_lower = str(title).lower()
    management_keywords = ["head", "director", "manager", "lead", "executive"]
    
    if any(keyword in title_lower for keyword in management_keywords):
        return "Management"
        
    try:
        years = float(max_years)
    except (ValueError, TypeError):
        years = 0.0
        
    if years >= 5:
        return "Senior"
    elif 3 <= years < 5:
        return "Medium"
    else:
        return "Entry"

@mcp.tool()
def restructure_and_build_db(daily_csv_path: str) -> str:
    """Ingests scraped data, unifies schema, calculates deterministic fields, and appends to Master DB."""
    global JOB_DETAILS_MEMORY
    
    master_file = "analysised_job_list.csv" 
    
    if not os.path.exists(daily_csv_path):
        return f"Error: Could not find {daily_csv_path}"
        
    df_daily = pd.read_csv(daily_csv_path).fillna("")
    
    # EXACT Column Order as requested
    target_columns = [
        "RowID", "JobLink_or_ID", "JobTitle", "CompanyName", "PostingDate", "FullText", 
        "is_IT", "is_DataScience", "is_AI", "is_ML", "is_Related", "Qualification", 
        "MaxYearsExperience", "Level_of_career", "Languages", "Cloud", "DevOps", 
        "Data and Frameworks", "AI", "Visualization", "Other"
    ]
    
    if os.path.exists(master_file):
        df_master = pd.read_csv(master_file).fillna("")
    else:
        df_master = pd.DataFrame(columns=target_columns)

    transformed_links = set(df_master['JobLink_or_ID'].astype(str).tolist()) if 'JobLink_or_ID' in df_master.columns else set()

    processed_count = 0
    skipped_count = 0
    new_rows = []

    with redirect_stdout(sys.stderr):
        for _, row in df_daily.iterrows():
            job_link = str(row.get('url', ''))
            
            if job_link in transformed_links:
                skipped_count += 1
                continue
                
            processed_count += 1
            print(f"DEBUG: AI Extracting data for: {row.get('title')}...", file=sys.stderr)
            
            desc = JOB_DETAILS_MEMORY.get(str(row.get('job_id', '')), row.get('descriptionText', ''))
            ext_data = call_local_ollama(desc)
            
            is_it = ext_data.get("is_IT", False)
            is_ds = ext_data.get("is_DataScience", False)
            is_ai = ext_data.get("is_AI", False)
            is_ml = ext_data.get("is_ML", False)
            max_exp = ext_data.get("MaxYearsExperience", 0)
            
            is_related = bool(is_it or is_ds or is_ai or is_ml)
            calculated_level = determine_career_level(row.get('title'), max_exp)
                
            new_rows.append({
                "RowID": "", # Will be calculated sequentially below
                "JobLink_or_ID": job_link,
                "JobTitle": row.get('title'),
                "CompanyName": row.get('company'),
                "PostingDate": row.get('post_date'), 
                "FullText": desc,
                "is_IT": is_it,
                "is_DataScience": is_ds,
                "is_AI": is_ai,
                "is_ML": is_ml,
                "is_Related": is_related,
                "Qualification": ext_data.get("Qualification", "N/A"),
                "MaxYearsExperience": max_exp,
                "Level_of_career": calculated_level,
                "Languages": ext_data.get("Languages", ""),
                "Cloud": ext_data.get("Cloud", ""),
                "DevOps": ext_data.get("DevOps", ""),
                "Data and Frameworks": ext_data.get("Data_and_Frameworks", ""),
                "AI": ext_data.get("AI", ""),
                "Visualization": ext_data.get("Visualization", ""),
                "Other": ext_data.get("Other", "")
            })

    if new_rows:
        df_new = pd.DataFrame(new_rows)
        df_combined = pd.concat([df_master, df_new], ignore_index=True)
        
        # Deduplicate
        if 'JobLink_or_ID' in df_combined.columns:
            df_combined = df_combined.drop_duplicates(subset=['JobLink_or_ID'], keep='last')
            
        # Ensure all target columns exist to prevent KeyError
        for col in target_columns:
            if col not in df_combined.columns:
                df_combined[col] = ""
                
        # Calculate fresh RowIDs (1 to N)
        df_combined = df_combined.reset_index(drop=True)
        df_combined['RowID'] = df_combined.index + 1
        
        # Enforce exact column order
        df_combined = df_combined[target_columns]
                
        df_combined.to_csv(master_file, index=False)
        
    return f"Pipeline Complete! Processed {processed_count} new jobs. Skipped {skipped_count} already transformed jobs."

if __name__ == "__main__":
    mcp.run()
