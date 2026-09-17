# DB VITHRA — AI-Powered Universal Database & Data Management Platform

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/vishnuarumugam17806-dev/new-repository)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3118/)
[![Flask](https://img.shields.io/badge/flask-3.0.3-green.svg)](https://palletsprojects.com/p/flask/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Where Data Meets Intelligence.**  
> *VITHRA — Versatile Intelligent Technology for Handling, Retrieval & Analytics*

**DB VITHRA** is an AI-powered universal database and data management platform that enables users to create, connect, manage, query, visualize, modify, import, export, and analyze data across multiple database systems and data sources.

---

## 🚀 Instant 1-Click Cloud Deployment to Render

You can deploy DB VITHRA directly to Render in one click:

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/vishnuarumugam17806-dev/new-repository)

**1-Click Deploy Link:**  
👉 **[https://render.com/deploy?repo=https://github.com/vishnuarumugam17806-dev/new-repository](https://render.com/deploy?repo=https://github.com/vishnuarumugam17806-dev/new-repository)**

---

## 🛠️ Step-by-Step Render Deployment Guide

### Option 1: Render Blueprint (Recommended - 1 Click)
1. Navigate to: [Deploy on Render](https://render.com/deploy?repo=https://github.com/vishnuarumugam17806-dev/new-repository)
2. Connect your GitHub account if prompted.
3. Render will read `render.yaml` automatically, configuring:
   - **Web Service**: `db-vithra`
   - **PostgreSQL Database**: `db-vithra-postgres`
   - Environment variables, build command (`pip install -r requirements.txt`), and start command (`gunicorn app:app`).
4. Click **Apply Blueprint**.
5. Once deployment completes, your live public URL will be accessible on your Render dashboard.

---

### Option 2: Render Web Service (Manual)
1. Go to your [Render Dashboard](https://dashboard.render.com).
2. Click **New +** → **Web Service**.
3. Select **Build and deploy from a Git repository** and pick `vishnuarumugam17806-dev/new-repository`.
4. Configure settings:
   - **Name:** `db-vithra`
   - **Region:** Any (e.g. Oregon, Frankfurt, Singapore)
   - **Branch:** `main`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
   - **Instance Type:** `Free`
5. Under **Environment Variables**, add:
   - `PYTHON_VERSION`: `3.11.8`
   - `FLASK_ENV`: `production`
   - `SECRET_KEY`: *(click generate or enter random secret)*
   - `OPENAI_API_KEY`: *(Optional: your OpenAI API key for AI generation)*
6. Click **Deploy Web Service**.
7. Render will provide your public URL instantly.

---

## 🌟 Key Features
- **AI Schema Architect & Creation Wizard:** Generate normalized DDL schemas across SQL Server, MySQL, Oracle, MongoDB, and Excel from natural language requirements.
- **Universal Multi-DBMS Connectivity:** Native live adapters for SQL Server, MySQL, Oracle, MongoDB, and Excel datasets with connection verification.
- **AI Query Assistant:** Dual-engine natural language to query translation with intelligent schema introspection and multi-dialect query generation.
- **Interactive Data Explorer & CRUD Operations:** Full table hierarchy browsing, column inspection, and live CRUD management.
- **Interactive ER Diagram Engine:** Real-time visual ER diagram rendering powered by Mermaid.js with pan/zoom controls.
- **DB Store Schema Catalog:** Community and enterprise multi-database schema catalog.
- **High-Performance Import & Export:** Instant dataset preview, data type inferencing, batch ingestion, and JSON/CSV/SQL export capabilities.
- **Real-Time Analytics Dashboard:** Engine distribution, schema metrics, query logs, and activity telemetry.

---

## 💻 Local Development Setup

```bash
# 1. Clone repository
git clone https://github.com/vishnuarumugam17806-dev/new-repository.git
cd new-repository

# 2. Create virtual environment & activate
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env

# 5. Run development server
python app.py
```
App will be running locally at `http://localhost:5000`.

---

## 🧪 Running Tests
```bash
pytest
```
All 21 unit and integration tests pass successfully.
