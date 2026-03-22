"""Agent orchestration — coordinates scraping, LLM parsing, and database storage."""

import asyncio
from datetime import datetime, timezone
from typing import Optional

# Import all scraping tools
from .tools.web_scraper import scrape_url
from .tools.github_fetcher import fetch_github_jobs
from .tools.lever_fetcher import fetch_lever_jobs
from .tools.greenhouse_fetcher import fetch_greenhouse_jobs
from .tools.browser_scraper import scrape_with_browser
from .llm import extract_jobs_from_content
from . import database as db


async def scan_source(source: dict) -> dict:
    """Scan a single source and return results."""
    source_type = source["type"]
    source_url = source["url"]
    source_id = source["id"]
    source_name = source["name"]

    result = {
        "source_id": source_id,
        "source_name": source_name,
        "jobs_found": 0,
        "new_jobs": 0,
        "status": "success",
        "error": None,
    }

    try:
        # Step 1: Fetch content based on source type
        # Each type has its own dedicated fetcher tool
        if source_type == "github":
            fetch_result = await fetch_github_jobs(source_url)
        elif source_type == "lever":
            # Lever ATS — uses their public API (no auth needed)
            fetch_result = await fetch_lever_jobs(source_url)
        elif source_type == "greenhouse":
            # Greenhouse ATS — uses their public API (no auth needed)
            fetch_result = await fetch_greenhouse_jobs(source_url)
        elif source_type == "browser":
            # Browser-based scraping for login-protected or JS-heavy sites
            fetch_result = await scrape_with_browser(source_url)
        else:
            # Default: simple HTTP scraping for generic websites
            fetch_result = await scrape_url(source_url)

        if fetch_result["status"] == "error":
            result["status"] = "error"
            result["error"] = fetch_result.get("error", "Unknown error during fetch")
            return result

        content = fetch_result.get("content", "")
        if not content.strip():
            result["status"] = "warning"
            result["error"] = "No content found at source"
            return result

        # Step 2: Send to LLM for job extraction
        jobs = await extract_jobs_from_content(content, source_url)
        result["jobs_found"] = len(jobs)

        # Step 3: Save to database (with deduplication)
        if jobs:
            total, new = await db.save_job_updates(source_id, jobs, agent_id="agent1")
            result["new_jobs"] = new

        print(f"[Agent] Scanned {source_name}: {result['jobs_found']} found, {result['new_jobs']} new")

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        print(f"[Agent] Error scanning {source_name}: {e}")

    return result


async def scan_all_sources() -> list[dict]:
    """Scan all registered sources and return aggregated results."""
    sources = await db.list_sources()
    if not sources:
        print("[Agent] No sources configured. Skipping scan.")
        return []

    started_at = datetime.now(timezone.utc).isoformat()
    print(f"[Agent] Starting scan of {len(sources)} sources at {started_at}")

    # Scan sources concurrently (with a limit to avoid overwhelming)
    semaphore = asyncio.Semaphore(3)

    async def _scan_with_limit(source):
        async with semaphore:
            return await scan_source(source)

    results = await asyncio.gather(
        *[_scan_with_limit(source) for source in sources],
        return_exceptions=True,
    )

    # Process results
    scan_results = []
    total_found = 0
    total_new = 0
    for r in results:
        if isinstance(r, Exception):
            scan_results.append({
                "source_id": 0,
                "source_name": "Unknown",
                "jobs_found": 0,
                "new_jobs": 0,
                "status": "error",
                "error": str(r),
            })
        else:
            scan_results.append(r)
            total_found += r.get("jobs_found", 0)
            total_new += r.get("new_jobs", 0)

    # Save scan history
    await db.save_scan_history(
        started_at=started_at,
        total_sources=len(sources),
        total_jobs_found=total_found,
        total_new_jobs=total_new,
        status="completed",
        details=str(scan_results),
    )

    print(f"[Agent] Scan complete. {total_found} jobs found, {total_new} new.")
    return scan_results
