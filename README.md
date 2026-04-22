# 🤖 AI Career Agent

An advanced, multi-agent AI career advisor and job-matching platform. This application leverages the **Model Context Protocol (MCP)**, local LLMs via **Ollama**, and **Streamlit** to parse resumes, evaluate career readiness, and score candidates against live or offline job markets.

## ✨ Key Features

* **Intelligent CV Parsing:** Extracts education, experience, skills, and certifications from PDF resumes using PyMuPDF and local LLMs.
* **Career Level Readiness:** Automatically evaluates your CV against standard industry requirements for Entry, Medium, Senior, and Management levels.
* **AI Career Advisor:** Generates a tailored, actionable improvement plan, identifying skill gaps and recommending specific industry certifications.
* **Live Market Matcher:** Scrapes recent job postings, extracts their requirements natively via AI, and ranks them against your CV.
* **Local Database Matcher:** Rapidly evaluates your fit against an offline repository of verified tech jobs.
* **PDF Job Ad Evaluator:** Upload offline PDF job descriptions for ad-hoc extraction and instant fit-scoring.

## 🏗️ Architecture

This project is built on a distributed micro-agent architecture using [MCP (Model Context Protocol)](https://modelcontextprotocol.io/):
1. **Frontend:** `Streamlit` provides the interactive UI.
2. **Orchestrator:** `orchestrator_v4.py` manages asynchronous communication, threading, and LangChain LLM prompts.
3. **MCP Servers:** Dedicated FastMCP tools handle specific intensive tasks:
   * `cv_parser`: PDF text extraction and entity recognition.
   * `fit_score`: Complex RAG-assisted scoring algorithms calculating experience, education, and skill match percentages.
   * `job_scraper`: Live job market fetching and database restructuring.

## 🚀 Prerequisites

Before you begin, ensure you have the following installed:
* **Python 3.8+**
* **[Ollama](https://ollama.com/)** (Running locally)

You must pull the specific LLM model used in this application. Open your terminal and run:
```bash
ollama run qwen3:0.6B
```

🛠️ Installation & Setup
1. Clone the repository:
```bash
git clone https://github.com/tllai-dickson/COM6104-CP2-2026.git
cd COM6104-CP2-2026
```

2. Set up a virtual environment (Recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Project Structure Configuration:
Ensure your files are organized exactly like this for the MCP Orchestrator to find the local servers and RAG data:
```Plaintext
ai-career-agent/
│
├── streamlit_app_v7.py       # Main Streamlit frontend
├── orchestrator_v4.py        # Brain/Routing logic
├── requirements.txt
├── analysised_job_list.csv   # Required for Option 2 (Offline Database)
│
├── rag/                      # RAG JSON files
│   ├── rag_course.json
│   ├── rag_level_summary.json
│   └── rag_company_profiles.json
│
└── tools/                    # MCP Local Servers
    ├── cv_parser/
    │   └── server.py         # (Your server(cv_parser).py)
    ├── fit_score/
    │   └── server.py         # (Your server(fit_score).py)
    └── job_scraper/
        └── server.py         # (Your server(job_scraper).py)
```

💻 Usage
Start the application by running the Streamlit app:
```bash
streamlit run streamlit_app_v7.py
```

Upload your CV: Use the sidebar to upload a PDF of your resume. Wait for the AI to parse it and generate your readiness scores.

Get Advice: Click "Get AI CV Advice" in the sidebar for personalized upskilling tips.

Choose a Matching Mode:

Option 1: Search for live jobs via keyword.

Option 2: Evaluate against the local master database.

Option 3: Upload up to 5 PDF job descriptions for targeted scoring.

⚠️ Known Limitations
The application relies heavily on a local LLM. Depending on your hardware, processing PDFs and generating justifications may take 15-30 seconds.

The job_scraper functionality requires an active internet connection and may be subject to rate-limiting depending on the target job board.
