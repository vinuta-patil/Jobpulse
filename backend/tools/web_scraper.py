"""Web scraper tool — fetches and extracts clean text from any URL."""

import httpx
from bs4 import BeautifulSoup
from typing import Optional


async def scrape_url(url: str) -> dict:
    """
    Scrape a URL and return clean text content.
    Returns dict with 'content', 'title', and 'status'.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        async with httpx.AsyncClient(
            follow_redirects=True, timeout=30.0
        ) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove non-content elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside",
                         "noscript", "iframe", "svg", "form"]):
            tag.decompose()

        # Extract title
        title = ""
        if soup.title:
            title = soup.title.get_text(strip=True)

        # Extract main content
        # Try to find the main content area first
        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", {"role": "main"})
            or soup.find("div", {"id": "content"})
            or soup.find("div", {"class": "content"})
        )

        if main_content:
            text = main_content.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)

        # Clean up: remove excessive blank lines
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        clean_text = "\n".join(lines)

        # Truncate to avoid token limits (keep first ~8000 chars)
        if len(clean_text) > 8000:
            clean_text = clean_text[:8000] + "\n\n[Content truncated...]"

        return {
            "content": clean_text,
            "title": title,
            "url": url,
            "status": "success",
        }

    except httpx.TimeoutException:
        return {"content": "", "title": "", "url": url, "status": "error", "error": f"Timeout fetching {url}"}
    except httpx.HTTPStatusError as e:
        return {"content": "", "title": "", "url": url, "status": "error", "error": f"HTTP {e.response.status_code} for {url}"}
    except Exception as e:
        return {"content": "", "title": "", "url": url, "status": "error", "error": f"Error scraping {url}: {str(e)}"}
