"""
JSearch API Fetcher — searches jobs across LinkedIn, Indeed, Glassdoor, ZipRecruiter, Monster.

Uses the JSearch API via RapidAPI. Aggregates from Google for Jobs.
Free tier: 200 requests/month.

API docs: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
Auth: X-RapidAPI-Key header
"""

import os
import httpx
from typing import Optional


# RapidAPI key — set in .env
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")

# JSearch API base URL and host
JSEARCH_URL = "https://jsearch.p.rapidapi.com/search"
JSEARCH_HOST = "jsearch.p.rapidapi.com"


async def search_jsearch(
    query: str,
    location: Optional[str] = None,
    page: int = 1,
    num_pages: int = 1,
    date_posted: str = "all",
    remote_only: bool = False,
    employment_type: Optional[str] = None,
    country: str = "us",
) -> dict:
    """
    Search for jobs using JSearch API (powered by Google for Jobs).

    Args:
        query: Search query (e.g., "software engineer")
        location: Location to search in (e.g., "san francisco")
        page: Page number (1-50)
        num_pages: Number of pages to return (1-50, each costs 1 credit)
        date_posted: Filter by date — "all", "today", "3days", "week", "month"
        remote_only: If True, only return remote jobs
        employment_type: "FULLTIME", "PARTTIME", "CONTRACTOR", "INTERN" (comma-separated)
        country: ISO country code (default: "us")

    Returns:
        dict with 'jobs' list and metadata
    """
    # Check if API key is configured
    api_key = RAPIDAPI_KEY or os.getenv("RAPIDAPI_KEY", "")
    if not api_key:
        return {
            "jobs": [],
            "source": "jsearch",
            "status": "error",
            "error": "RAPIDAPI_KEY not set in .env file. Get one at rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch",
        }

    # Build the search query — combine query + location if provided
    full_query = f"{query} in {location}" if location else query
    print(f"[JSearch] Searching: '{full_query}' (page {page}, date: {date_posted})")

    # Build request parameters
    params = {
        "query": full_query,
        "page": str(page),
        "num_pages": str(num_pages),
        "date_posted": date_posted,
        "country": country,
    }

    # Add optional filters
    if remote_only:
        params["remote_jobs_only"] = "true"
    if employment_type:
        params["employment_types"] = employment_type

    # Set auth headers for RapidAPI
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": JSEARCH_HOST,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(JSEARCH_URL, headers=headers, params=params)
            response.raise_for_status()

        data = response.json()
        raw_jobs = data.get("data", [])

        # Transform each job into our standard format
        jobs = []
        for job in raw_jobs:
            jobs.append({
                "title": job.get("job_title", "Unknown"),
                "company": job.get("employer_name", "Unknown"),
                "location": job.get("job_city", "") or job.get("job_state", "") or job.get("job_country", ""),
                "url": job.get("job_apply_link", "") or job.get("job_google_link", ""),
                "description": _truncate(job.get("job_description", ""), 300),
                "salary": _format_salary(job),
                "employment_type": job.get("job_employment_type", ""),
                "is_remote": job.get("job_is_remote", False),
                "posted_at": job.get("job_posted_at_datetime_utc", ""),
                "source_api": "jsearch",
                "source_site": job.get("job_publisher", ""),
            })

        print(f"[JSearch] Found {len(jobs)} jobs for '{full_query}'")
        return {
            "jobs": jobs,
            "source": "jsearch",
            "total": len(jobs),
            "status": "success",
        }

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP {e.response.status_code} from JSearch API"
        if e.response.status_code == 403:
            error_msg = "Invalid RAPIDAPI_KEY or subscription expired"
        elif e.response.status_code == 429:
            error_msg = "JSearch rate limit exceeded (200 free req/month)"
        print(f"[JSearch] Error: {error_msg}")
        return {"jobs": [], "source": "jsearch", "status": "error", "error": error_msg}

    except Exception as e:
        print(f"[JSearch] Error: {e}")
        return {"jobs": [], "source": "jsearch", "status": "error", "error": str(e)}


def _format_salary(job: dict) -> str:
    """Format salary range from JSearch job data."""
    min_sal = job.get("job_min_salary")
    max_sal = job.get("job_max_salary")
    period = job.get("job_salary_period", "")

    if min_sal and max_sal:
        return f"${int(min_sal):,} - ${int(max_sal):,} {period}".strip()
    elif min_sal:
        return f"${int(min_sal):,}+ {period}".strip()
    elif max_sal:
        return f"Up to ${int(max_sal):,} {period}".strip()
    return ""


def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max_len characters."""
    if not text:
        return ""
    text = text.replace("\n", " ").strip()
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text
