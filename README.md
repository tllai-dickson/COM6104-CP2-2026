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
