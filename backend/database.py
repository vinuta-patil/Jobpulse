import os
import asyncio
from datetime import datetime, timezone
from typing import Optional
from supabase import create_client, Client
from dotenv import load_dotenv

# Load .env from project root (parent directory of backend/)
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(env_path)

supabase: Optional[Client] = None

async def init_db():
    """Initialize Supabase client."""
    global supabase

    # Read env vars inside the function to ensure .env is loaded
    url: str = os.getenv("SUPABASE_URL", "")
    key: str = os.getenv("SUPABASE_KEY", "")

    print(f"[DB] Initializing... URL: {url[:30]}... KEY: {'*' * 20 if key else 'MISSING'}")

    if not url or not key:
        print("[DB] ERROR: SUPABASE_URL or SUPABASE_KEY missing. Database operations will fail.")
        print(f"[DB] URL present: {bool(url)}, KEY present: {bool(key)}")
        return

    try:
        supabase = create_client(url, key)
        print("[DB] ✓ Supabase client initialized successfully.")
    except Exception as e:
        print(f"[DB] ✗ Failed to init Supabase: {e}")

def _get_client() -> Client:
    if not supabase:
        raise Exception("Supabase client not initialized. Check .env")
    return supabase

# --- Sources ---

async def add_source(url: str, source_type: str, name: str) -> dict:
    client = _get_client()
    now = datetime.now(timezone.utc).isoformat()
    data = {
        "url": url,
        "type": source_type,
        "name": name,
        "added_at": now,
        "enabled": True  # Default to enabled
    }
    # Supabase insert returns data
    resp = await asyncio.to_thread(
        lambda: client.table("sources").insert(data).execute()
    )
    return resp.data[0]

async def list_sources() -> list[dict]:
    client = _get_client()
    resp = await asyncio.to_thread(
        lambda: client.table("sources").select("*").order("added_at", desc=True).execute()
    )
    return resp.data

async def delete_source(source_id: int) -> bool:
    client = _get_client()
    resp = await asyncio.to_thread(
        lambda: client.table("sources").delete().eq("id", source_id).execute()
    )
    return len(resp.data) > 0

async def toggle_source(source_id: int, enabled: bool) -> dict:
    """Toggle a source enabled/disabled."""
    client = _get_client()
    resp = await asyncio.to_thread(
        lambda: client.table("sources").update({"enabled": enabled}).eq("id", source_id).execute()
    )
    if not resp.data or len(resp.data) == 0:
        raise Exception(f"Source {source_id} not found")
    return resp.data[0]

async def update_source_scan_result(source_id: int, jobs_found: int, error: Optional[str] = None):
    """Update source with scan results."""
    client = _get_client()
    now = datetime.now(timezone.utc).isoformat()
    data = {
        "last_scanned": now,
        "jobs_found_last_scan": jobs_found
    }
    if error:
        data["last_error"] = error
    else:
        data["last_error"] = None  # Clear error on successful scan

    await asyncio.to_thread(
        lambda: client.table("sources").update(data).eq("id", source_id).execute()
    )

# --- Jobs ---

async def save_job_updates(source_id: int, jobs: list[dict], agent_id: str = "agent1") -> tuple[int, int]:
    """
    Save job updates to Supabase 'jobs' table.
    - agent_id: 'agent1' (Monitor), 'agent2' (Search), 'agent3' (ATS)
    - source_id: Linked to sources table for Agent 1. 0 or None for others.
    """
    client = _get_client()
    now = datetime.now(timezone.utc).isoformat()
    new_jobs = 0
    
    # Prepare data
    records = []
    for job in jobs:
        # Create a content hash for dedup (Supabase needs unique constraint on this col)
        # We can also use upsert based on content_hash if configured in Supabase
        import hashlib
        hash_input = f"{job.get('title', '')}{job.get('company', '')}{job.get('url', '')}"
        content_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        
        record = {
            "source_id": source_id if source_id > 0 else None,
            "agent_id": agent_id,
            "title": job.get("title", "Unknown"),
            "company": job.get("company"),
            "location": job.get("location"),
            "url": job.get("url"),
            "description": job.get("description"),
            "date_posted": job.get("date_posted"),  # actual posting date from source
            "discovered_at": now,
            "content_hash": content_hash,
            # For Agent 2/3, we might want to store source metadata if needed
            "source_url": job.get("source_url") or "",  # Optional extra field
            "source_name": job.get("source_name") or "" # Optional extra field
        }
        records.append(record)

    if not records:
        return 0, 0

    # Upsert logic: rely on unique 'content_hash' constraint in Supabase
    # on_conflict='content_hash'
    try:
        resp = await asyncio.to_thread(
            lambda: client.table("jobs").upsert(records, on_conflict="content_hash", ignore_duplicates=True).execute()
        )
        # Count actually inserted? Supabase upsert response might not distinguish easily without `count` param
        # But ignore_duplicates=True returns empty for duplicates usually? 
        # Actually `ignore_duplicates=True` means "DO NOTHING" on conflict.
        # So returned data should be only new rows?
        # Let's assume len(resp.data) is the number of new rows if we use default behavior, 
        # but with ignore_duplicates request creates no data return for dupes?
        # We'll just estimate or return len(records) if not critical. 
        # Ideally we want 'new' count.
        new_jobs = len(resp.data)
        
        # Update source last_scanned if Agent 1
        if source_id > 0:
            await asyncio.to_thread(
                lambda: client.table("sources").update({"last_scanned": now}).eq("id", source_id).execute()
            )
            
        return len(records), new_jobs
    except Exception as e:
        print(f"[DB] Upsert failed: {e}")
        return len(records), 0

async def get_updates(limit: int = 50, offset: int = 0, source_id: Optional[int] = None, agent_id: Optional[str] = None, date_from: Optional[str] = None, include_hidden: bool = False) -> list[dict]:
    client = _get_client()

    query = client.table("jobs").select("*, sources(name, url)").order("date_posted", desc=True).order("discovered_at", desc=True).order("id", desc=True).range(offset, offset + limit - 1)

    # Filter out hidden jobs by default
    if not include_hidden:
        query = query.eq("hidden", False)

    if source_id:
        # If source_id is provided, filter by it (Agent 1 specific)
        query = query.eq("source_id", source_id)

    if agent_id:
        query = query.eq("agent_id", agent_id)

    if date_from:
        query = query.gte("date_posted", date_from)

    resp = await asyncio.to_thread(lambda: query.execute())
    
    # Map result to flatten sources if needed, or frontend can handle it
    # We'll return dicts. Supabase returns list of dicts.
    # Note: `sources` will be a nested dict or list.
    # We mimic the old SQL join output: `source_name`, `source_url`
    
    results = []
    for row in resp.data:
        # Flatten sources join
        src = row.get("sources")
        if src and isinstance(src, dict):
            row["source_name"] = src.get("name")
            row["source_url"] = src.get("url")
        elif src and isinstance(src, list) and len(src) > 0: # Should be dict for single foreign key
             row["source_name"] = src[0].get("name")
             row["source_url"] = src[0].get("url")
        
        # If no source join (Agent 2/3), leave as is (maybe stored in fields or inferred)
        # Agent 3: company is the sourceish.
        results.append(row)
        
    return results

# --- History ---

async def save_scan_history(started_at: str, total_sources: int, total_jobs_found: int, total_new_jobs: int, status: str, details: str = ""):
    client = _get_client()
    now = datetime.now(timezone.utc).isoformat()
    data = {
        "started_at": started_at,
        "completed_at": now,
        "total_sources": total_sources,
        "total_jobs_found": total_jobs_found,
        "total_new_jobs": total_new_jobs,
        "status": status,
        "details": details
    }
    await asyncio.to_thread(
        lambda: client.table("scan_history").insert(data).execute()
    )

async def get_last_scan() -> Optional[dict]:
    client = _get_client()
    resp = await asyncio.to_thread(
        lambda: client.table("scan_history").select("*").order("started_at", desc=True).limit(1).execute()
    )
    if resp.data:
        return resp.data[0]
    return None

# --- Job Hiding ---

async def hide_job(job_id: int) -> dict:
    """Hide a job from view."""
    client = _get_client()
    now = datetime.now(timezone.utc).isoformat()
    resp = await asyncio.to_thread(
        lambda: client.table("jobs").update({"hidden": True, "hidden_at": now}).eq("id", job_id).execute()
    )
    if not resp.data or len(resp.data) == 0:
        raise Exception(f"Job {job_id} not found")
    return resp.data[0]

async def unhide_job(job_id: int) -> dict:
    """Unhide a previously hidden job."""
    client = _get_client()
    resp = await asyncio.to_thread(
        lambda: client.table("jobs").update({"hidden": False, "hidden_at": None}).eq("id", job_id).execute()
    )
    if not resp.data or len(resp.data) == 0:
        raise Exception(f"Job {job_id} not found")
    return resp.data[0]
