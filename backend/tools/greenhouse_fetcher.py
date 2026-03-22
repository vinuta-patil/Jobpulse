"""
Greenhouse API Fetcher — fetches job listings from Greenhouse-powered career pages.

Greenhouse is one of the most popular ATS platforms.
Their job board API is public and doesn't require authentication.

Usage: Pass in a Greenhouse careers URL like:
  - https://boards.greenhouse.io/company-name
  - https://company.com/careers (if powered by Greenhouse)

API docs: https://developers.greenhouse.io/job-board.html
"""

import httpx
import re
from typing import Optional


def extract_greenhouse_company(url: str) -> Optional[str]:
    """
    Extract the company slug (board token) from a Greenhouse URL.
    Examples:
      - https://boards.greenhouse.io/airbnb -> 'airbnb'
      - https://boards.greenhouse.io/embed/job_board?for=airbnb -> 'airbnb'
    """
    # Pattern 1: boards.greenhouse.io/company
    match = re.search(r"boards\.greenhouse\.io/([^/\s?#]+)", url)
    if match and match.group(1) != "embed":
        return match.group(1)

    # Pattern 2: boards.greenhouse.io/embed/job_board?for=company
    match = re.search(r"[?&]for=([^&\s#]+)", url)
    if match:
        return match.group(1)

    return None


async def fetch_greenhouse_jobs(url: str) -> dict:
    """
    Fetch all open job postings from a Greenhouse company board.
    
    Uses Greenhouse's public Job Board API:
    GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs
    
    Returns structured content with job titles, departments, locations, and links.
    """
    # Step 1: Extract company/board token from URL
    company = extract_greenhouse_company(url)
    if not company:
        return {
            "content": "",
            "url": url,
            "status": "error",
            "error": f"Could not extract Greenhouse company from URL: {url}. Expected format: boards.greenhouse.io/company-name",
        }

    # Step 2: Call Greenhouse's public Job Board API
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
    print(f"[Greenhouse] Fetching jobs from: {api_url}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(api_url)
            response.raise_for_status()

        data = response.json()
        jobs = data.get("jobs", [])

        # Step 3: Check if any jobs were returned
        if not jobs:
            return {
                "content": "No open positions found.",
                "url": url,
                "jobs_count": 0,
                "status": "success",
            }

        # Step 4: Format each job into a readable block
        content_lines = [f"# {company.title()} — Open Positions ({len(jobs)} jobs)\n"]

        for job in jobs:
            title = job.get("title", "Unknown Title")
            location = job.get("location", {}).get("name", "N/A")
            job_url = job.get("absolute_url", "")
            updated_at = job.get("updated_at", "")

            # Get department info (nested in the response)
            departments = job.get("departments", [])
            dept_name = departments[0].get("name", "N/A") if departments else "N/A"

            content_lines.append(f"## {title}")
            content_lines.append(f"- Company: {company.title()}")
            content_lines.append(f"- Department: {dept_name}")
            content_lines.append(f"- Location: {location}")
            if updated_at:
                content_lines.append(f"- Updated: {updated_at[:10]}")
            if job_url:
                content_lines.append(f"- Apply: {job_url}")
            content_lines.append("")  # blank line between jobs

        content = "\n".join(content_lines)

        # Truncate if too long (token limits)
        if len(content) > 8000:
            content = content[:8000] + "\n\n[Content truncated...]"

        print(f"[Greenhouse] Found {len(jobs)} jobs for {company}")
        return {
            "content": content,
            "url": url,
            "jobs_count": len(jobs),
            "status": "success",
        }

    except httpx.HTTPStatusError as e:
        # 404 = company not found on Greenhouse
        if e.response.status_code == 404:
            return {
                "content": "",
                "url": url,
                "status": "error",
                "error": f"Company '{company}' not found on Greenhouse. Check the URL.",
            }
        return {
            "content": "",
            "url": url,
            "status": "error",
            "error": f"HTTP {e.response.status_code} from Greenhouse API",
        }
    except Exception as e:
        return {
            "content": "",
            "url": url,
            "status": "error",
            "error": f"Error fetching Greenhouse jobs: {str(e)}",
        }
