"""
Search Agent (Agent #2) — searches jobs across multiple aggregator APIs.

Orchestrates JSearch and Adzuna API calls, deduplicates results,
and saves new jobs to the database.
"""

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Optional

from .tools.jsearch_fetcher import search_jsearch
from .tools.adzuna_fetcher import search_adzuna
from . import database as db


async def search_jobs(
    query: str,
    location: Optional[str] = None,
    date_posted: str = "3days",
    remote_only: bool = False,
    employment_type: Optional[str] = None,
    country: str = "us",
) -> dict:
    """
    Search for jobs across both JSearch and Adzuna APIs in parallel.

    Args:
        query: Search keywords (e.g., "software engineer")
        location: Location (e.g., "san francisco")
        date_posted: "all", "today", "3days", "week", "month"
        remote_only: Only return remote jobs
        employment_type: "FULLTIME", "PARTTIME", "CONTRACTOR", "INTERN"
        country: ISO country code (default: "us")

    Returns:
        dict with combined 'jobs' list, source stats, and errors
    """
    started_at = datetime.now(timezone.utc).isoformat()
    print(f"[SearchAgent] Searching '{query}' in '{location or 'anywhere'}' at {started_at}")

    # Step 1: Call both APIs in parallel
    jsearch_task = search_jsearch(
        query=query,
        location=location,
        date_posted=date_posted,
        remote_only=remote_only,
        employment_type=employment_type,
        country=country,
    )
    adzuna_task = search_adzuna(
        query=query,
        location=location,
        country=country,
        full_time=(employment_type == "FULLTIME") if employment_type else False,
    )

    # Run both API calls concurrently
    jsearch_result, adzuna_result = await asyncio.gather(
        jsearch_task, adzuna_task, return_exceptions=True
    )

    # Step 2: Collect results from both APIs
    all_jobs = []
    errors = []

    # Handle JSearch results
    if isinstance(jsearch_result, Exception):
        errors.append(f"JSearch error: {str(jsearch_result)}")
    elif jsearch_result.get("status") == "error":
        errors.append(f"JSearch: {jsearch_result.get('error', 'Unknown error')}")
    else:
        all_jobs.extend(jsearch_result.get("jobs", []))

    # Handle Adzuna results
    if isinstance(adzuna_result, Exception):
        errors.append(f"Adzuna error: {str(adzuna_result)}")
    elif adzuna_result.get("status") == "error":
        errors.append(f"Adzuna: {adzuna_result.get('error', 'Unknown error')}")
    else:
        all_jobs.extend(adzuna_result.get("jobs", []))

    # Step 3: Deduplicate results (same title + company = duplicate)
    seen_hashes = set()
    unique_jobs = []
    for job in all_jobs:
        # Create a hash from title + company to detect duplicates across APIs
        key = f"{job.get('title', '').lower().strip()}|{job.get('company', '').lower().strip()}"
        job_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
        if job_hash not in seen_hashes:
            seen_hashes.add(job_hash)
            job["content_hash"] = job_hash
            # Map posted_at → date_posted for DB storage
            if job.get("posted_at") and not job.get("date_posted"):
                raw = job["posted_at"]
                # Extract just the date portion (YYYY-MM-DD)
                job["date_posted"] = str(raw)[:10] if raw else None
            # Ensure source_name is set for display
            if not job.get("source_name"):
                job["source_name"] = (job.get("source_api") or "search").title()
            unique_jobs.append(job)

    # Step 4: Save results to database (reuse Agent #1's table)
    new_count = 0
    if unique_jobs:
        try:
            # Save batch with agent_id='agent2' (Search)
            total, new = await db.save_job_updates(
                source_id=0,  # 0 = search result
                jobs=unique_jobs,
                agent_id="agent2"
            )
            new_count = new
        except Exception as e:
            print(f"[SearchAgent] Error saving batch: {e}")

    print(f"[SearchAgent] Search complete. {len(unique_jobs)} unique jobs, {new_count} new.")

    return {
        "jobs": unique_jobs,
        "total": len(unique_jobs),
        "new_jobs": new_count,
        "sources": {
            "jsearch": len(jsearch_result.get("jobs", [])) if isinstance(jsearch_result, dict) else 0,
            "adzuna": len(adzuna_result.get("jobs", [])) if isinstance(adzuna_result, dict) else 0,
        },
        "errors": errors,
        "query": query,
        "location": location,
        "searched_at": started_at,
        "status": "success" if not errors else "partial" if unique_jobs else "error",
    }
