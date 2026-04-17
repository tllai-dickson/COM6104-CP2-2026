import streamlit as st
import pandas as pd
import base64
import os
from orchestrator import run_agent

# Set page config to wide for the new layout
st.set_page_config(page_title="AI Career Agent", layout="wide")

# Custom CSS for the "Cyber Engine Room" styling
st.markdown("""
    <style>
    /* Dark Cyber Theme Overrides */
    .main {
        background-color: #0d1117;
        color: #c9d1d9;
    }
    .engine-room {
        background-color: #161b22;
        padding: 30px;
        border-radius: 12px;
        border: 1px solid #30363d;
        margin-bottom: 30px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.5);
    }
    h1, h2, h3 {
        color: #58a6ff !important;
        font-family: 'Courier New', Courier, monospace;
    }
    .stButton>button {
        border-radius: 5px;
        text-transform: uppercase;
        font-weight: bold;
        letter-spacing: 1px;
    }
    .stProgress > div > div > div > div {
        background-image: linear-gradient(to right, #1f6feb, #58a6ff);
    }
    /* Style the tabs for dark mode */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        min-width: 200px;
        background-color: #161b22;
        border-radius: 8px 8px 0px 0px;
        color: #8b949e;
        padding-left: 30px;
        padding-right: 30px;
        border: 1px solid #30363d;
        border-bottom: none;
    }
    .stTabs [aria-selected="true"] {
        background-color: #30363d !important;
        color: #58a6ff !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Helper function to display job results
def display_results(results):
    if not results:
        st.info("No matching jobs found.")
        return
        
    for job in results:
        with st.expander(f"💼 {job.get('title', 'Unknown')} at {job.get('company', 'Unknown')} — FIT: {job.get('total_score', 0)}%"):
            # Advisor Insight Section
            advisor = job.get("advisor_insight", {})
            st.info(f"**💡 AI Advisor Insight:**\n\n*Targeted Course:* {advisor.get('course', 'N/A')}\n\n*Interview Strategy:* {advisor.get('interview_tip', 'N/A')}")
            
            # Metrics Columns
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Experience", f"{job.get('experience_score', 0)}/50")
            m2.metric("Education", f"{job.get('education_score', 0)}/25")
            m3.metric("Skills", f"{job.get('skills_score', 0)}/25")
            m4.metric("Bonus", f"+{job.get('bonus_score', 0)}")
            
            # Reasoning JSON
            if st.button("View AI Reasoning JSON", key=f"btn_{job.get('id', 'x')}"):
                st.json(job)

# ==========================================
# ⚡ CYBER ENGINE ROOM
# ==========================================
st.title("🤖 AI CAREER AGENT")

with st.container():
    
    # --- Row 1: Profile Management ---
    st.markdown("### 📄 Step 1: Your Profile Initiation")
    row1_col1, row1_col2 = st.columns([5, 5])
    
    with row1_col1:
        st.write("") 
        st.markdown("**Uplink Source:** Upload PDF Resume to begin analysis...")
        cv_file = st.file_uploader("Upload Your CV (PDF)", type=["pdf"], label_visibility="collapsed")
        
    with row1_col2:
        if cv_file and st.button("EXECUTE ANALYSIS", type="primary", use_container_width=True):
            b64_cv = base64.b64encode(cv_file.read()).decode()
            with st.spinner("DECRYPTING CV DATA..."):
                st.session_state.cv_data = run_agent("process_cv", b64_cv)
                st.session_state.level_scores = run_agent("evaluate_levels", {"cv_data": st.session_state.cv_data})
            st.success("✅ ANALYSIS COMPLETE")
        if "cv_data" in st.session_state:
            with st.expander("🔍 Preview Parsed CV"):
                st.json(st.session_state.cv_data)

    st.divider()

    # --- Row 2: Matrix & Intelligence ---
    st.markdown("### 📊 Step 2: Career Level Readiness")
    col_matrix, col_advisor = st.columns([2, 3])

    with col_matrix:
        # Display the RAG Level Readiness Scores
        if "level_scores" in st.session_state and "error" not in st.session_state.level_scores:
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
        else:
            st.caption("Awaiting user profile uplink...")

    with col_advisor:
        if st.button("💡 Get AI Advice", use_container_width=True):
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
        else:
            st.warning("Uplink required.")

    st.markdown('</div>', unsafe_allow_html=True)
    st.divider()
    
# ==========================================
# 🎯 OPERATIONS DASHBOARD (TABS)
# ==========================================

st.markdown("### 🎯 Step 3: Job Matcher")
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

                
