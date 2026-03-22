"""
Lever API Fetcher — fetches job listings from Lever-powered career pages.

Lever is an ATS (Applicant Tracking System) used by many companies.
Their job board API is public and doesn't require authentication.

Usage: Pass in a Lever careers URL like:
  - https://jobs.lever.co/company-name
  - https://company.com/careers (if powered by Lever)

API docs: https://github.com/lever/postings-api
"""

import httpx
import re
from typing import Optional


def extract_lever_company(url: str) -> Optional[str]:
    """
    Extract the company slug from a Lever URL.
    Examples:
      - https://jobs.lever.co/openai -> 'openai'
      - https://jobs.lever.co/stripe -> 'stripe'
    """
    match = re.search(r"jobs\.lever\.co/([^/\s?#]+)", url)
    if match:
        return match.group(1)
    return None


async def fetch_lever_jobs(url: str) -> dict:
    """
    Fetch all open job postings from a Lever company page.
    
    Uses Lever's public Postings API:
    GET https://api.lever.co/v0/postings/{company}?mode=json
    
    Returns structured content with job titles, teams, locations, and links.
    """
    # Step 1: Extract company slug from URL
    company = extract_lever_company(url)
    if not company:
        return {
            "content": "",
            "url": url,
            "status": "error",
            "error": f"Could not extract Lever company from URL: {url}. Expected format: jobs.lever.co/company-name",
        }

    # Step 2: Call Lever's public API
    api_url = f"https://api.lever.co/v0/postings/{company}?mode=json"
    print(f"[Lever] Fetching jobs from: {api_url}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(api_url)
            response.raise_for_status()

        postings = response.json()

        # Step 3: Check if any jobs were returned
        if not postings:
            return {
                "content": "No open positions found.",
                "url": url,
                "jobs_count": 0,
                "status": "success",
            }

        # Step 4: Format each posting into a readable block
        content_lines = [f"# {company.title()} — Open Positions ({len(postings)} jobs)\n"]

        for posting in postings:
            title = posting.get("text", "Unknown Title")
            team = posting.get("categories", {}).get("team", "N/A")
            location = posting.get("categories", {}).get("location", "N/A")
            commitment = posting.get("categories", {}).get("commitment", "")
            apply_url = posting.get("hostedUrl", "")

            content_lines.append(f"## {title}")
            content_lines.append(f"- Company: {company.title()}")
            content_lines.append(f"- Team: {team}")
            content_lines.append(f"- Location: {location}")
            if commitment:
                content_lines.append(f"- Type: {commitment}")
            if apply_url:
                content_lines.append(f"- Apply: {apply_url}")
            content_lines.append("")  # blank line between postings

        content = "\n".join(content_lines)

        # Truncate if too long (token limits)
        if len(content) > 8000:
            content = content[:8000] + "\n\n[Content truncated...]"

        print(f"[Lever] Found {len(postings)} jobs for {company}")
        return {
            "content": content,
            "url": url,
            "jobs_count": len(postings),
            "status": "success",
        }

    except httpx.HTTPStatusError as e:
        # 404 = company not found on Lever
        if e.response.status_code == 404:
            return {
                "content": "",
                "url": url,
                "status": "error",
                "error": f"Company '{company}' not found on Lever. Check the URL.",
            }
        return {
            "content": "",
            "url": url,
            "status": "error",
            "error": f"HTTP {e.response.status_code} from Lever API",
        }
    except Exception as e:
        return {
            "content": "",
            "url": url,
            "status": "error",
            "error": f"Error fetching Lever jobs: {str(e)}",
        }
