# 🔍 Job Source Monitor — Multi-Agent System (Agent #1)

An automated AI agent that monitors job sources (websites, GitHub repos) and provides structured job updates via a dashboard.

## Features

- **Automated Scanning** — Background scheduler scrapes sources every 30 minutes
- **Smart Parsing** — Kimi K2.5 (via NVIDIA NIM) extracts job info from raw content
- **Multiple Sources** — Supports websites and GitHub repos
- **Deduplication** — Only surfaces new/changed listings
- **Dashboard UI** — Dark-themed dashboard with source management, job feed, and chat
- **Chat with Agent** — Ask questions about your job updates

## Quick Start

### 1. Set up your API key

```bash
cp .env.example .env
# Edit .env and add your NVIDIA API key
```

Get your key at: [build.nvidia.com/settings/api-keys](https://build.nvidia.com/settings/api-keys)

### 2. Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Run the server

```bash
cd backend
uvicorn main:app --reload --port 8000
```

### 4. Open the dashboard

Visit [http://localhost:8000](http://localhost:8000)

## Architecture

```
User → Dashboard UI → FastAPI Backend → Kimi K2.5 (NVIDIA NIM)
                              ↓
                    APScheduler (background)
                              ↓
                    Web Scraper / GitHub Fetcher
                              ↓
                    SQLite (job_updates, sources)
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/sources` | Add a source URL |
| GET | `/api/sources` | List all sources |
| DELETE | `/api/sources/{id}` | Remove a source |
| GET | `/api/updates` | Get latest job updates |
| POST | `/api/scan` | Trigger manual scan |
| GET | `/api/status` | Scheduler status |
| POST | `/api/chat` | Chat with the agent |

## Tech Stack

- **Python + FastAPI** — Backend
- **Kimi K2.5 via NVIDIA NIM** — LLM (OpenAI-compatible)
- **APScheduler** — Background job scheduling
- **httpx + BeautifulSoup** — Web scraping
- **SQLite** — Data storage
- **Vanilla HTML/CSS/JS** — Frontend dashboard
