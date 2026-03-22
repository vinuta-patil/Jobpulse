"""FastAPI application — Job Source Monitor Agent."""

import os
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()

from .models import SourceCreate, Source, ScanStatus, ChatMessage, ChatResponse, JobSearchQuery
from . import database as db
from .scheduler import start_scheduler, stop_scheduler, trigger_manual_scan, get_scan_state, trigger_ats_scan, get_ats_scan_state
from .llm import chat_with_agent
from .search_agent import search_jobs
from .settings import get_settings, update_settings
from .resume_parser import process_resume, load_resume, save_resume


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup 
    await db.init_db()
    interval = int(os.getenv("SCAN_INTERVAL_MINUTES", "30"))
    start_scheduler(interval)
    print("[App] Job Source Monitor started.")
    yield
    # Shutdown
    stop_scheduler()
    print("[App] Job Source Monitor stopped.")


app = FastAPI(
    title="Job Source Monitor Agent",
    description="Automated agent that monitors job sources and provides updates",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Source Management ---

@app.post("/api/sources")
async def add_source(source: SourceCreate):
    """Add a new source URL to monitor."""
    name = source.name or source.url.split("/")[-1] or source.url
    try:
        result = await db.add_source(source.url, source.type.value, name)
        return {"status": "ok", "source": result}
    except Exception as e:
        if "UNIQUE" in str(e):
            raise HTTPException(status_code=409, detail="Source URL already exists")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sources")
async def list_sources():
    """List all registered sources."""
    sources = await db.list_sources()
    return {"sources": sources}


@app.delete("/api/sources/{source_id}")
async def delete_source(source_id: int):
    """Remove a source."""
    deleted = await db.delete_source(source_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"status": "ok"}


@app.put("/api/sources/{source_id}/toggle")
async def toggle_source(source_id: int, body: dict):
    """Toggle a source enabled/disabled."""
    enabled = body.get("enabled", True)
    try:
        result = await db.toggle_source(source_id, enabled)
        return {"status": "ok", "source": result}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- Job Updates ---

@app.get("/api/updates")
async def get_job_updates(limit: int = 50, offset: int = 0, source_id: Optional[int] = None, agent_id: Optional[str] = None, date_from: Optional[str] = None, include_hidden: bool = False):
    """Get the latest job updates. Optionally filter by agent_id and date_from. By default, hidden jobs are excluded."""
    scan_updates = await db.get_updates(limit=limit, offset=offset, source_id=source_id, agent_id=agent_id, date_from=date_from, include_hidden=include_hidden)
    return {"updates": scan_updates, "total": len(scan_updates)}


@app.put("/api/jobs/{job_id}/hide")
async def hide_job(job_id: int):
    """Hide a job from the feed."""
    try:
        result = await db.hide_job(job_id)
        return {"status": "ok", "job": result}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.put("/api/jobs/{job_id}/unhide")
async def unhide_job(job_id: int):
    """Unhide a previously hidden job."""
    try:
        result = await db.unhide_job(job_id)
        return {"status": "ok", "job": result}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- Scanning ---

@app.post("/api/scan")
async def trigger_scan():
    """Trigger an immediate scan of all sources."""
    state = get_scan_state()
    if state["is_running"]:
        raise HTTPException(status_code=409, detail="Scan already in progress")
    results = await trigger_manual_scan()
    return {"status": "ok", "results": results}


@app.get("/api/status")
async def get_status():
    """Get scheduler and scan status."""
    state = get_scan_state()
    last_scan = await db.get_last_scan()
    sources = await db.list_sources()
    updates = await db.get_updates(limit=5)
    return {
        "is_running": state["is_running"],
        "last_scan_at": state.get("last_scan_at"),
        "interval_minutes": int(os.getenv("SCAN_INTERVAL_MINUTES", "30")),
        "total_sources": len(sources),
        "recent_updates": len(updates),
        "last_scan_details": last_scan,
    }


# --- Chat ---

@app.post("/api/chat")
async def chat(msg: ChatMessage):
    """Chat with the agent about job updates."""
    # Get recent updates as context
    updates = await db.get_updates(limit=20)
    sources = await db.list_sources()
    context = f"Sources monitored: {len(sources)}\nRecent job updates:\n"
    for u in updates[:10]:
        context += f"- {u.get('title', 'N/A')} at {u.get('company', 'N/A')} ({u.get('source_name', '')})\n"

    response = await chat_with_agent(msg.message, context)
    return ChatResponse(response=response, updates=[])

# --- Agent #2: Job Search ---

@app.post("/api/search")
async def search(query: JobSearchQuery):
    """Search for jobs across JSearch + Adzuna APIs (Agent #2)."""
    results = await search_jobs(
        query=query.query,
        location=query.location,
        date_posted=query.date_posted,
        remote_only=query.remote_only,
        employment_type=query.employment_type,
        country=query.country,
    )
    return results


# --- Agent #3: ATS Auto-Scanner ---

@app.post("/api/ats-scan")
async def ats_scan():
    """Trigger a manual ATS batch scan across Lever + Greenhouse."""
    results = await trigger_ats_scan()
    return results


@app.get("/api/ats-status")
async def ats_status():
    """Get the current ATS scanner state."""
    state = get_ats_scan_state()
    return {
        "is_running": state["is_running"],
        "last_scan_at": state["last_scan_at"],
        "last_scan_results": state["last_results"],
    }


# --- Settings ---

@app.get("/api/settings")
async def read_settings():
    """Get agent settings (search role, etc.)."""
    return get_settings()


@app.put("/api/settings")
async def write_settings(body: dict):
    """Update agent settings."""
    updated = update_settings(body)
    return {"status": "ok", "settings": updated}


# --- Resume Agent ---

@app.post("/api/resume/upload")
async def upload_resume(file: UploadFile = File(...)):
    """Upload and parse a PDF resume. Returns structured resume data."""
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        # Read file bytes
        file_bytes = await file.read()

        # Process resume: extract text -> LLM parse -> save
        resume_data = await process_resume(file_bytes)

        return {
            "status": "ok",
            "message": f"Resume parsed successfully for {resume_data.get('personal_info', {}).get('name', 'Unknown')}",
            "data": resume_data
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[Resume API] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process resume: {str(e)}")


@app.get("/api/resume")
async def get_resume():
    """Get the current saved resume data."""
    resume_data = load_resume()
    if not resume_data:
        raise HTTPException(status_code=404, detail="No resume found. Please upload a resume first.")
    return {"status": "ok", "data": resume_data}


@app.delete("/api/resume")
async def delete_resume():
    """Delete the saved resume."""
    import os
    from .resume_parser import RESUME_FILE

    if not os.path.exists(RESUME_FILE):
        raise HTTPException(status_code=404, detail="No resume found")

    try:
        os.remove(RESUME_FILE)
        print(f"[Resume API] Deleted resume at {RESUME_FILE}")
        return {"status": "ok", "message": "Resume deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete resume: {str(e)}")


# --- Serve Frontend ---

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")


@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


# Mount static files for CSS/JS
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
