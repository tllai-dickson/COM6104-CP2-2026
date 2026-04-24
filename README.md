# 🤖 AI Career Agent

An advanced, multi-agent AI career advisor and job-matching platform. This application leverages the **Model Context Protocol (MCP)**, local LLMs via **Ollama**, and **Streamlit** to parse resumes, evaluate career readiness, and score candidates against live or offline job markets.

Demo Video: https://docs.google.com/videos/d/1o7tCBTtc0pJsqdNN9Tf2-q9OR6hJBnZ6XiDv2R4AADE/edit?usp=sharing

<img width="761" height="882" alt="orchestrator_pipeline_final_escaped drawio" src="https://github.com/user-attachments/assets/6459f032-87c9-47d9-be2a-dce54d28e1b8" />

## ✨ Key Features

* **Intelligent CV Parsing:** Extracts education, experience, skills, and certifications from PDF resumes using PyMuPDF and local LLMs.
* **Career Level Readiness:** Automatically evaluates your CV against standard industry requirements for Entry, Medium, Senior, and Management levels.
* **AI Career Advisor:** Generates a tailored, actionable improvement plan, identifying skill gaps and recommending specific industry certifications.
* **Live Market Matcher:** Scrapes recent job postings, extracts their requirements natively via AI, and ranks them against your CV.
* **Local Database Matcher:** Rapidly evaluates your fit against an offline repository of verified tech jobs.
* **PDF Job Ad Evaluator:** Upload offline PDF job descriptions for ad-hoc extraction and instant fit-scoring.

## 🏗️ Architecture

This project is built on a distributed micro-agent architecture using [MCP (Model Context Protocol)](https://modelcontextprotocol.io/):
1. **Frontend:** `ai_agent_ui.py` provides the interactive UI.
2. **Orchestrator:** `orchestrator.py` manages asynchronous communication, threading, and LangChain LLM prompts.
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
├── ai_agent_ui.py            # Main Streamlit frontend
├── orchestrator.py           # Brain/Routing logic
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
streamlit run ai_agent_ui.py
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

## 📊 RAG Data Structure

1. rag_level_summary.json
```bash
{
    "Entry": {
        "min_experience_years": 2,
        "typical_titles": [
            "AI Engineer Trainee",
            "Junior Data Scientist",
            "Machine Learning Assistant",
            "AI Analyst"
        ],
        "preferred_education": "AI/IT Degree or equivalent",
        "summary": "Entry-level AI roles focus on foundational machine learning knowledge, programming basics, and supervised tasks.",
        "required_techniques": {
            "Languages": [
                "Bash", "Css", "Go", "Golang", "Html", "Java", "Javascript", "Js", 
                "Kotlin", "Php", "Python", "R", "Ruby", "Rust", "Scala", "Sql", 
                "Swift", "Typescript"
            ],
            "Cloud": [
                "Alibaba Cloud", "Aws", "Azure", "Cloud", "Gcp", "Google Cloud"
            ],
            "DevOps": [
                "Agile", "Ansible", "Ci/Cd", "Continuous Deployment", "Continuous Integration", 
                "Devops", "Docker", "Git", "Influx", "Kubernetes", "Linux", "Pub/Sub", 
                "Scrum", "Terraform"
            ],
            "Data and Frameworks": [
                "Angular", "Data Science", "Databricks", "Elasticsearch", "Hadoop", "Kafka", 
                "Mongodb", "Mysql", "Node.Js", "Nosql", "Numpy", "Pandas", "Postgresql", 
                "React", "Redis", "Relational Databases", "Snowflake", "Spark", "Spring", "Vue"
            ],
            "AI": [
                "Ai", "Artificial Intelligence", "Computer Vision", "Deep Learning", "Genai", 
                "Keras", "Llms", "Machine Learning", "Ml", "Nlp", "Openai", "Pytorch", 
                "Scikit-Learn", "Tensorflow"
            ],
            "Visualization": [
                "Business Intelligence", "D3", "Dashboards", "Grafana", "Matplotlib", 
                "Powerbi", "Qlik", "Tableau"
            ],
            "Others": []
        }
    }
  }
```

2. rag_course.json
```bash
{
    "course_name": "AWS Certified AI Practitioner",
    "provider": "AWS",
    "target_skills": [
      "AI/ML Concepts",
      "Generative AI",
      "Cloud Security",
      "Ethics"
    ],
    "level": "Foundation",
    "url": "https://aws.amazon.com/certification/certified-ai-practitioner/",
    "score": 1
  }
```
3. rag_company_profiles.json
```bash
{
 "chiyu_banking_corporation_limited": {
    "domain": [
      "Banking",
      "Financial Services"
    ],
    "industry": "Finance",
    "size": "Medium"
  }
}
```
## 📄 LLM System Prompt
<img width="546" height="266" alt="image" src="https://github.com/user-attachments/assets/f6920503-5065-4a46-a653-eca274b5ced5" />
<img width="436" height="611" alt="image" src="https://github.com/user-attachments/assets/061a9c05-7516-4cbc-8140-c8e8d78e0b6b" />
<img width="565" height="409" alt="image" src="https://github.com/user-attachments/assets/413f2103-4502-46bd-83a8-5f2233112266" />
<img width="379" height="563" alt="image" src="https://github.com/user-attachments/assets/ca782953-bba4-4348-bc64-bb6a3b64607d" />
<img width="571" height="179" alt="image" src="https://github.com/user-attachments/assets/4f5b0edf-6ff5-47ef-8f3b-74e1e493f4e9" />
<img width="562" height="263" alt="image" src="https://github.com/user-attachments/assets/7cae9b1e-ce4c-4e2d-ab39-e0c67820fbe0" />
<img width="500" height="596" alt="image" src="https://github.com/user-attachments/assets/fa8d9560-ebbf-4ae4-a34c-528dc789f4d4" />

