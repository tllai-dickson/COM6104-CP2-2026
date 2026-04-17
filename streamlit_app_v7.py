import streamlit as st
import pandas as pd
import base64
import os
from orchestrator_v4 import run_agent

st.set_page_config(page_title="AI Career Agent", layout="wide")

# ==========================================
# ⬅️ SIDEBAR CONTROL PANEL
# ==========================================
with st.sidebar:
    st.title("🤖 AI Career Agent")

    st.markdown("### 📄 Step 1: Your Profile")
    cv_file = st.file_uploader("Upload Your CV (PDF)", type=["pdf"])
    
    if cv_file and st.button("Process CV", type="primary"):
        b64_cv = base64.b64encode(cv_file.read()).decode()
        with st.spinner("Parsing CV Data with AI..."):
            st.session_state.cv_data = run_agent("process_cv", b64_cv)
            
            # Immediately calculate Level Readiness after parsing
            st.session_state.level_scores = run_agent("evaluate_levels", {"cv_data": st.session_state.cv_data})
            
        st.success("✅ CV Loaded & Processed!")

    if "cv_data" in st.session_state:
        with st.expander("🔍 Preview Parsed CV"):
            st.json(st.session_state.cv_data)
            
        # Display the RAG Level Readiness Scores
        if "level_scores" in st.session_state and "error" not in st.session_state.level_scores:
            st.markdown("### 📊 Career Level Readiness")
            st.caption("Based on Full AI Evaluation against standard RAG requirements.")
            
            # Force the display order from Junior to Senior
            level_order = ["Entry", "Medium", "Senior", "Management"]
            
            for level in level_order:
                if level in st.session_state.level_scores:
                    scores = st.session_state.level_scores[level]
                    st.write(f"**{level}** ({scores['total']}%)")
                    
                    # Progress bar out of 100%
                    progress_val = min(scores['total'] / 100.0, 1.0)
                    st.progress(progress_val)
                    
                    # Exact breakdown including LLM Qualifications and Bonuses
                    st.caption(f"Exp: {scores['exp_score']}/50 (Req: {scores['req_exp']}y) | Skills: {scores['skill_score']}/25 | Edu: {scores['qual_score']}/25 | Bonus: +{scores['bonuses']}")
            st.markdown("---")

        # ==========================================
        # NEW: AI CV Advisor Section
        # ==========================================
        if st.button("💡 Get AI CV Advice", use_container_width=True):
            with st.spinner("Analyzing your profile for improvements..."):
                st.session_state.cv_advice = run_agent("cv_advisor", {"cv_data": st.session_state.cv_data})
        
        # Display the Advice if it exists in session state
        if "cv_advice" in st.session_state:
            advice = st.session_state.cv_advice
            
            if "error" in advice:
                st.error(advice["error"])
            else:
                with st.container(border=True):
                    st.markdown("### 🎓 AI Career Advisor")
                    st.write(f"*{advice.get('executive_summary', '')}*")
                    
                    st.markdown("**✅ Core Strengths:**")
                    for s in advice.get("core_strengths", []):
                        st.caption(f"- {s}")
                        
                    st.markdown("**⚠️ Skill Gaps:**")
                    for g in advice.get("critical_skill_gaps", []):
                        st.caption(f"- {g}")
                        
                    st.markdown("**📚 Recommended Certification:**")
                    st.info(advice.get("recommended_course", "None available at this time."))
                    
                    st.markdown("**📝 Resume Action Plan:**")
                    for act in advice.get("resume_action_points", []):
                        st.caption(f"- {act}")
        st.markdown("---")

    st.info("💡 **Instructions:** Upload your CV first, then select a tab on the main screen to begin your job search or evaluation.")

# ==========================================
# Helper UI Function for Results
# ==========================================
def display_results(results_list):
    """Cleanly displays the scored job results with AI recommendations."""
    if not results_list:
        st.warning("No jobs found matching your criteria.")
        return
        
    for res in results_list:
        score_data = res.get("score", {})
        total_score = score_data.get("total_score", 0)
        
        with st.expander(f"Top {res.get('job_index')}: {res.get('job_title')} @ {res.get('company')} - Score: {total_score}%", expanded=(res.get('job_index')==1)):
            if res.get('url'):
                st.markdown(f"🔗 **[View Original Job Posting]({res.get('url')})**")
            
            st.info(f"**🧠 Career Advisor Insight:**\n\n{res.get('advisor_insight', 'No insight provided.')}")
            
            # Show Score Breakdown
            st.markdown("**📊 Scoring Details**")
            cols = st.columns(4)
            cols[0].metric("Experience", f"{score_data.get('breakdown', {}).get('experience_score_raw', 0)} / 50")
            cols[1].metric("Education", f"{score_data.get('breakdown', {}).get('qualification_score_raw', 0)} / 25")
            cols[2].metric("Skills", f"{score_data.get('breakdown', {}).get('skill_score_raw', 0)} / 25")
            cols[3].metric("Bonuses", f"+{score_data.get('breakdown', {}).get('bonuses', 0)} pts")
            
            with st.popover("View Full AI Reasoning JSON"):
                st.json(score_data)

# ==========================================
# 🖥️ MAIN DASHBOARD TABS
# ==========================================
tab1, tab2, tab3 = st.tabs([
    "🔍 Option 1: Live Market Matcher", 
    "🗄️ Option 2: Database Matcher", 
    "📁 Option 3: PDF Ad-Hoc Evaluator"
])

# --- TAB 1: LIVE MARKET MATCHER ---
with tab1:
    st.header("Live Market Matcher")
    st.write("Scrape the latest jobs (past 14 days), extract requirements via AI, and rank them against your CV.")
    
    col1, col2 = st.columns(2)
    with col1:
        keyword = st.text_input("Search Keyword", "Data Scientist", key="opt1_keyword")
    with col2:
        target_level_1 = st.selectbox("Target Career Level", ["Entry", "Medium", "Senior", "Management"], key="opt1_level")
        
    if st.button("▶️ Run Live Search & Score", type="primary"):
        if "cv_data" not in st.session_state:
            st.error("⚠️ Please upload and process your CV in the sidebar first.")
        elif not keyword:
            st.warning("Please enter a search keyword.")
        else:
            with st.spinner(f"Scraping '{keyword}' jobs, building database, and scoring... (This may take a few minutes)"):
                res = run_agent("option_1_pipeline", {
                    "keyword": keyword, 
                    "level": target_level_1,
                    "cv_data": st.session_state.cv_data
                })
                
            if "error" in res:
                st.error(res["error"])
            else:
                st.success("✅ Live search and analysis complete!")
                st.caption(res.get("message", ""))
                display_results(res.get("results", []))

# --- TAB 2: MASTER DATABASE MATCHER ---
with tab2:
    st.header("Master Database Matcher")
    st.write("Evaluate your CV against jobs already saved in the local database (`analysised_job_list.csv`). Filters out non-tech jobs and postings older than 180 days.")
    
    target_level_2 = st.selectbox("Target Career Level", ["Entry", "Medium", "Senior", "Management"], key="opt2_level")
    
    if st.button("📊 Evaluate Local Database", type="primary"):
        if "cv_data" not in st.session_state:
            st.error("⚠️ Please upload and process your CV in the sidebar first.")
        else:
            with st.spinner("Filtering database and calculating fit scores..."):
                res = run_agent("option_2_pipeline", {
                    "level": target_level_2,
                    "cv_data": st.session_state.cv_data
                })
                
            if "error" in res:
                st.error(res["error"])
            else:
                st.success("✅ Database evaluation complete!")
                display_results(res.get("results", []))

# --- TAB 3: PDF AD-HOC EVALUATOR ---
with tab3:
    st.header("PDF Job Evaluator")
    st.write("Upload offline job advertisements (PDF format). The AI will extract the requirements, score them against your CV, and save them to `temp.csv`.")
    
    job_pdfs = st.file_uploader("Upload Job Ads (PDF format only, Max 5)", type=["pdf"], accept_multiple_files=True)
    
    if st.button("📁 Evaluate Uploaded PDFs", type="primary"):
        if "cv_data" not in st.session_state:
            st.error("⚠️ Please upload and process your CV in the sidebar first.")
        elif not job_pdfs:
            st.warning("Please upload at least one PDF job ad.")
        elif len(job_pdfs) > 5:
            st.error("You can only upload a maximum of 5 PDFs at a time.")
        else:
            with st.spinner(f"Analyzing {len(job_pdfs)} PDF Job Ads..."):
                # Convert PDFs to base64
                job_ads_b64 = [base64.b64encode(f.read()).decode() for f in job_pdfs]
                
                res = run_agent("option_3_pipeline", {
                    "cv_data": st.session_state.cv_data, 
                    "job_ads": job_ads_b64
                })
                
            if "error" in res:
                st.error(res["error"])
            else:
                st.success("✅ PDF Evaluation Complete! Results saved to temp.csv.")
                display_results(res.get("results", []))