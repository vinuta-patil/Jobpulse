"""GitHub fetcher tool — fetches job-relevant info from GitHub repos."""

import httpx
import re
import base64
from typing import Optional


def parse_github_url(url: str) -> Optional[tuple[str, str]]:
    """Parse a GitHub URL and return (owner, repo)."""
    patterns = [
        r"github\.com/([^/]+)/([^/\s?#]+)",
        r"github\.com/([^/]+)/([^/\s?#]+)\.git",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1), match.group(2).rstrip("/")
    return None


async def fetch_github_jobs(repo_url: str, github_token: Optional[str] = None) -> dict:
    """
    Fetch job-relevant content from a GitHub repository.
    Looks at: README, issues tagged with job/hiring keywords, and recent activity.
    """
    parsed = parse_github_url(repo_url)
    if not parsed:
        return {
            "content": "",
            "url": repo_url,
            "status": "error",
            "error": f"Could not parse GitHub URL: {repo_url}",
        }

    owner, repo = parsed
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "JobMonitorAgent/1.0",
    }
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    content_parts = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Fetch README
        try:
            readme_resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/readme",
                headers=headers,
            )
            if readme_resp.status_code == 200:
                readme_data = readme_resp.json()
                readme_content = base64.b64decode(readme_data.get("content", "")).decode("utf-8", errors="ignore")
                # Truncate large READMEs
                if len(readme_content) > 50000:
                    readme_content = readme_content[:50000] + "\n\n[README truncated...]"
                content_parts.append(f"## README\n{readme_content}")
        except Exception as e:
            content_parts.append(f"## README\nError fetching README: {str(e)}")

        # 2. Fetch issues with job-related labels/keywords
        try:
            job_keywords = ["job", "hiring", "career", "position", "opening", "role", "opportunity"]
            issues_resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/issues",
                headers=headers,
                params={"state": "open", "per_page": 20, "sort": "updated"},
            )
            if issues_resp.status_code == 200:
                issues = issues_resp.json()
                job_issues = []
                for issue in issues:
                    title_lower = issue.get("title", "").lower()
                    labels = [l.get("name", "").lower() for l in issue.get("labels", [])]
                    body = (issue.get("body") or "")[:500]

                    is_job_related = (
                        any(kw in title_lower for kw in job_keywords)
                        or any(any(kw in label for kw in job_keywords) for label in labels)
                    )
                    if is_job_related:
                        job_issues.append(
                            f"- **{issue['title']}** (#{issue['number']})\n"
                            f"  Labels: {', '.join(labels) if labels else 'none'}\n"
                            f"  URL: {issue['html_url']}\n"
                            f"  {body[:200]}..."
                        )

                if job_issues:
                    content_parts.append(f"## Job-Related Issues\n" + "\n".join(job_issues))
                else:
                    content_parts.append("## Issues\nNo job-related issues found.")
        except Exception as e:
            content_parts.append(f"## Issues\nError fetching issues: {str(e)}")

        # 3. Fetch repo description and metadata
        try:
            repo_resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}",
                headers=headers,
            )
            if repo_resp.status_code == 200:
                repo_data = repo_resp.json()
                meta = (
                    f"## Repository Info\n"
                    f"- **Name:** {repo_data.get('full_name', '')}\n"
                    f"- **Description:** {repo_data.get('description', 'N/A')}\n"
                    f"- **Stars:** {repo_data.get('stargazers_count', 0)}\n"
                    f"- **Last updated:** {repo_data.get('updated_at', 'N/A')}\n"
                    f"- **Topics:** {', '.join(repo_data.get('topics', []))}"
                )
                content_parts.insert(0, meta)
        except Exception:
            pass

    full_content = "\n\n".join(content_parts)
    return {
        "content": full_content,
        "url": repo_url,
        "owner": owner,
        "repo": repo,
        "status": "success",
    }
