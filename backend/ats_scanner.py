"""
ATS Auto-Scanner (Agent #3) — batch-scans Lever & Greenhouse for 1,000+ companies.

Runs every 4 hours (configurable). For each company in companies.json, probes both
the Lever and Greenhouse public APIs concurrently. Deduplicates against existing DB
entries and saves new jobs. Marks companies as inactive on 404 to skip them next time.

No API keys required — both APIs are free and public.
"""

import asyncio
import hashlib
import json
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx

from . import database as db
from .settings import get_settings

# Paths
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
COMPANIES_FILE = os.path.join(DATA_DIR, "companies.json")

# Concurrency limit (polite — 10 simultaneous requests)
MAX_CONCURRENT = 10

# Role keyword filter from settings
def _get_role_keyword() -> str:
    """Get the search role from settings (e.g. 'software engineer')."""
    settings = get_settings()
    return settings.get("search_role", "software engineer").lower().strip()


def _matches_role(title: str, role: str) -> bool:
    """Check if job title matches the role keyword."""
    if not role:
        return True  # no filter = accept all
    title_lower = title.lower()
    # Match any word from the role keyword (e.g. 'software engineer' matches 'Software' or 'Engineer')
    role_words = [w.strip() for w in role.split() if w.strip()]
    return any(w in title_lower for w in role_words)


def _is_recent(date_str: Optional[str], max_days: int = 2) -> bool:
    """Check if a date string (YYYY-MM-DD) is within the last max_days days."""
    if not date_str:
        return True  # if no date, include it (can't filter)
    try:
        posted = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=timezone.utc)
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_days)
        return posted >= cutoff
    except (ValueError, TypeError):
        return True  # can't parse, include it


def _content_hash(title: str, company: str, url: str) -> str:
    raw = f"{title}|{company}|{url}".lower().strip()
    return hashlib.md5(raw.encode()).hexdigest()


def _load_companies() -> list[dict]:
    """Load companies from JSON file."""
    if not os.path.exists(COMPANIES_FILE):
        print("[ATS Scanner] companies.json not found!")
        return []
    with open(COMPANIES_FILE, "r") as f:
        return json.load(f)


def _save_companies(companies: list[dict]):
    """Save updated companies back to JSON (with inactive flags)."""
    with open(COMPANIES_FILE, "w") as f:
        json.dump(companies, f, indent=2)


async def _probe_lever(client: httpx.AsyncClient, slug: str) -> list[dict]:
    """Probe Lever API for a company. Returns list of job dicts."""
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    try:
        resp = await client.get(url)
        if resp.status_code == 404:
            return []  # company not on Lever
        resp.raise_for_status()
        postings = resp.json()
        if not isinstance(postings, list):
            return []

        jobs = []
        for p in postings:
            title = p.get("text", "")
            if not title:
                continue
            location = p.get("categories", {}).get("location", "")
            commitment = p.get("categories", {}).get("commitment", "")
            team = p.get("categories", {}).get("team", "")
            apply_url = p.get("hostedUrl", "")
            created_at = p.get("createdAt", 0)

            # Convert epoch ms to ISO date string
            date_posted = None
            if created_at and isinstance(created_at, (int, float)) and created_at > 0:
                try:
                    dt = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc)
                    date_posted = dt.strftime("%Y-%m-%d")
                except (OSError, ValueError):
                    pass

            # Build description
            desc_parts = []
            if team:
                desc_parts.append(f"Team: {team}")
            if commitment:
                desc_parts.append(f"Type: {commitment}")

            jobs.append({
                "title": title,
                "company": slug.replace("-", " ").title(),
                "location": location,
                "url": apply_url,
                "description": ". ".join(desc_parts) if desc_parts else "",
                "source_api": "lever",
                "created_at": created_at,
                "date_posted": date_posted,
            })
        return jobs
    except Exception:
        return []


async def _probe_greenhouse(client: httpx.AsyncClient, slug: str) -> list[dict]:
    """Probe Greenhouse API for a company. Returns list of job dicts."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    try:
        resp = await client.get(url)
        if resp.status_code == 404:
            return []  # company not on Greenhouse
        resp.raise_for_status()
        data = resp.json()
        job_list = data.get("jobs", [])
        if not isinstance(job_list, list):
            return []

        jobs = []
        for j in job_list:
            title = j.get("title", "")
            if not title:
                continue
            location = j.get("location", {}).get("name", "")
            apply_url = j.get("absolute_url", "")
            updated_at = j.get("updated_at", "")

            # Get department
            depts = j.get("departments", [])
            dept = depts[0].get("name", "") if depts else ""

            desc_parts = []
            if dept:
                desc_parts.append(f"Department: {dept}")

            # Extract date_posted from updated_at
            date_posted = None
            if updated_at:
                date_posted = str(updated_at)[:10]  # YYYY-MM-DD

            jobs.append({
                "title": title,
                "company": slug.replace("-", " ").title(),
                "location": location,
                "url": apply_url,
                "description": ". ".join(desc_parts) if desc_parts else "",
                "source_api": "greenhouse",
                "updated_at": updated_at,
                "date_posted": date_posted,
            })
        return jobs
    except Exception:
        return []


async def _scan_company(
    client: httpx.AsyncClient,
    company: dict,
    semaphore: asyncio.Semaphore,
) -> dict:
    """Scan a single company on both Lever and Greenhouse."""
    slug = company["slug"]
    result = {
        "slug": slug,
        "name": company.get("name", slug),
        "lever_jobs": 0,
        "greenhouse_jobs": 0,
        "lever_active": company.get("lever_active", True),
        "greenhouse_active": company.get("greenhouse_active", True),
        "jobs": [],
    }

    async with semaphore:
        tasks = []
        if result["lever_active"]:
            tasks.append(("lever", _probe_lever(client, slug)))
        if result["greenhouse_active"]:
            tasks.append(("greenhouse", _probe_greenhouse(client, slug)))

        for source, coro in tasks:
            try:
                jobs = await coro
                if source == "lever":
                    if jobs:
                        result["lever_jobs"] = len(jobs)
                        result["jobs"].extend(jobs)
                    else:
                        result["lever_active"] = False
                else:
                    if jobs:
                        result["greenhouse_jobs"] = len(jobs)
                        result["jobs"].extend(jobs)
                    else:
                        result["greenhouse_active"] = False
            except Exception:
                pass

    return result


async def scan_ats_batch() -> dict:
    """
    Main entry point: scan all companies in companies.json.
    Returns summary stats.
    """
    started_at = datetime.now(timezone.utc)
    print(f"[ATS Scanner] Starting batch scan at {started_at.isoformat()}")

    companies = _load_companies()
    if not companies:
        return {
            "status": "error",
            "error": "No companies loaded",
            "scanned": 0,
            "total_jobs": 0,
            "new_jobs": 0,
        }

    role = _get_role_keyword()
    print(f"[ATS Scanner] Role filter: '{role}'")

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    total_jobs = 0
    new_jobs = 0
    active_companies = 0
    errors = []

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        # Process in batches of 50 for progress logging
        batch_size = 50
        for i in range(0, len(companies), batch_size):
            batch = companies[i:i + batch_size]
            tasks = [_scan_company(client, c, semaphore) for c in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for idx, res in enumerate(results):
                if isinstance(res, Exception):
                    errors.append(str(res))
                    continue

                company = batch[idx]
                # Update active flags on the company object
                company["lever_active"] = res["lever_active"]
                company["greenhouse_active"] = res["greenhouse_active"]

                if res["lever_jobs"] > 0 or res["greenhouse_jobs"] > 0:
                    active_companies += 1

            # Save jobs to DB
            valid_jobs = []
            for job in res["jobs"]:
                # Apply role filter
                if not _matches_role(job["title"], role):
                    continue
                # Apply 2-day recency filter
                if not _is_recent(job.get("date_posted"), max_days=2):
                    continue

                total_jobs += 1
                # Add source_name using the API provider (Lever/Greenhouse)
                job["source_name"] = job.get("source_api", "ATS").title()
                valid_jobs.append(job)

            if valid_jobs:
                try:
                    # Save batch (Agent #3)
                    saved, new = await db.save_job_updates(0, valid_jobs, agent_id="agent3")
                    new_jobs += new
                except Exception as e:
                    print(f"[ATS Scanner] Error saving batch: {e}")

            progress = min(i + batch_size, len(companies))
            print(f"[ATS Scanner] Progress: {progress}/{len(companies)} companies scanned")

    # Save updated company flags (inactive markers)
    _save_companies(companies)

    completed_at = datetime.now(timezone.utc)
    duration = (completed_at - started_at).total_seconds()

    summary = {
        "status": "success",
        "scanned": len(companies),
        "active_companies": active_companies,
        "total_jobs": total_jobs,
        "new_jobs": new_jobs,
        "duration_seconds": round(duration, 1),
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "errors": len(errors),
        "role_filter": role or "none",
    }

    print(f"[ATS Scanner] Complete. Scanned {len(companies)} companies, "
          f"found {total_jobs} jobs ({new_jobs} new) in {duration:.1f}s. "
          f"Active companies: {active_companies}")

    return summary
