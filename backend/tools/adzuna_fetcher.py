"""
Adzuna API Fetcher — searches jobs across multiple countries and categories.

Adzuna aggregates job listings and provides search, salary insights, and analytics.
Free tier: 2,500 requests/month.

API docs: https://developer.adzuna.com/
Auth: app_id + app_key as query parameters
"""

import os
import httpx
from typing import Optional


# Adzuna credentials — set in .env
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")

# Adzuna API base URL
ADZUNA_BASE_URL = "https://api.adzuna.com/v1/api/jobs"


async def search_adzuna(
    query: str,
    location: Optional[str] = None,
    page: int = 1,
    results_per_page: int = 20,
    country: str = "us",
    full_time: bool = False,
    salary_min: Optional[int] = None,
) -> dict:
    """
    Search for jobs using Adzuna API.

    Args:
        query: Search keywords (e.g., "python developer")
        location: Location to search in (e.g., "new york")
        page: Page number (starts at 1)
        results_per_page: Number of results per page (max 50)
        country: Country code — "us", "gb", "ca", "au", "de", "fr", etc.
        full_time: If True, only return full-time positions
        salary_min: Minimum annual salary filter

    Returns:
        dict with 'jobs' list and metadata
    """
    # Check if API credentials are configured
    app_id = ADZUNA_APP_ID or os.getenv("ADZUNA_APP_ID", "")
    app_key = ADZUNA_APP_KEY or os.getenv("ADZUNA_APP_KEY", "")

    if not app_id or not app_key:
        return {
            "jobs": [],
            "source": "adzuna",
            "status": "error",
            "error": "ADZUNA_APP_ID and ADZUNA_APP_KEY not set in .env file. Get them at developer.adzuna.com",
        }

    # Build the API URL: /v1/api/jobs/{country}/search/{page}
    url = f"{ADZUNA_BASE_URL}/{country}/search/{page}"
    print(f"[Adzuna] Searching: '{query}' in {country} (page {page})")

    # Build request parameters
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "what": query,
        "results_per_page": str(min(results_per_page, 50)),  # Max 50
        "content-type": "application/json",
    }

    # Add optional filters
    if location:
        params["where"] = location
    if full_time:
        params["full_time"] = "1"
    if salary_min:
        params["salary_min"] = str(salary_min)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()

        data = response.json()
        raw_jobs = data.get("results", [])
        total_count = data.get("count", 0)

        # Transform each job into our standard format
        jobs = []
        for job in raw_jobs:
            # Extract location from Adzuna's nested structure
            location_name = job.get("location", {}).get("display_name", "")

            # Extract salary info
            salary = _format_adzuna_salary(job)

            jobs.append({
                "title": job.get("title", "Unknown"),
                "company": job.get("company", {}).get("display_name", "Unknown"),
                "location": location_name,
                "url": job.get("redirect_url", ""),
                "description": _truncate(job.get("description", ""), 300),
                "salary": salary,
                "employment_type": "Full-time" if full_time else "",
                "is_remote": False,  # Adzuna doesn't provide this field directly
                "posted_at": job.get("created", ""),
                "source_api": "adzuna",
                "source_site": "Adzuna",
                "category": job.get("category", {}).get("label", ""),
            })

        print(f"[Adzuna] Found {len(jobs)} jobs (total: {total_count}) for '{query}'")
        return {
            "jobs": jobs,
            "source": "adzuna",
            "total": total_count,
            "status": "success",
        }

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP {e.response.status_code} from Adzuna API"
        if e.response.status_code == 401:
            error_msg = "Invalid ADZUNA_APP_ID or ADZUNA_APP_KEY"
        elif e.response.status_code == 429:
            error_msg = "Adzuna rate limit exceeded"
        print(f"[Adzuna] Error: {error_msg}")
        return {"jobs": [], "source": "adzuna", "status": "error", "error": error_msg}

    except Exception as e:
        print(f"[Adzuna] Error: {e}")
        return {"jobs": [], "source": "adzuna", "status": "error", "error": str(e)}


def _format_adzuna_salary(job: dict) -> str:
    """Format salary from Adzuna job data."""
    min_sal = job.get("salary_min")
    max_sal = job.get("salary_max")

    if min_sal and max_sal:
        return f"${int(min_sal):,} - ${int(max_sal):,}"
    elif min_sal:
        return f"${int(min_sal):,}+"
    elif max_sal:
        return f"Up to ${int(max_sal):,}"
    return ""


def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max_len characters."""
    if not text:
        return ""
    # Clean up HTML tags that Adzuna sometimes includes
    import re
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\n", " ").strip()
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text
