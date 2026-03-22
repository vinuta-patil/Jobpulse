"""
Browser Scraper — uses Playwright to scrape login-protected or JS-heavy sites.

This tool launches a real Chromium browser, so it can:
  - Render JavaScript-heavy pages (SPAs, React apps, etc.)
  - Handle login flows (using stored cookies or credentials)
  - Navigate through paginated content

Usage: For sites that can't be scraped with simple httpx + BeautifulSoup.

Dependencies: playwright (install with: pip install playwright && playwright install chromium)
"""

import os
import json
import asyncio
from typing import Optional

# Try to import playwright — it's an optional dependency
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("[Browser] Playwright not installed. Run: pip install playwright && playwright install chromium")


# Directory to store session cookies for persistent login
COOKIES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cookies")


async def scrape_with_browser(
    url: str,
    wait_for_selector: Optional[str] = None,
    cookies_file: Optional[str] = None,
    wait_seconds: int = 3,
) -> dict:
    """
    Scrape a page using a real browser (Playwright + Chromium).

    Args:
        url: The URL to scrape
        wait_for_selector: Optional CSS selector to wait for before extracting content
                          (e.g., '.job-listing' to wait for job cards to load)
        cookies_file: Optional path to a JSON file with cookies for authentication
                     (export from browser using a cookie export extension)
        wait_seconds: How many seconds to wait for the page to fully load (default: 3)

    Returns:
        dict with 'content', 'title', 'url', and 'status'
    """
    # Step 0: Check if playwright is available
    if not PLAYWRIGHT_AVAILABLE:
        return {
            "content": "",
            "title": "",
            "url": url,
            "status": "error",
            "error": "Playwright is not installed. Run: pip install playwright && playwright install chromium",
        }

    print(f"[Browser] Launching browser for: {url}")

    try:
        async with async_playwright() as p:
            # Step 1: Launch headless Chromium
            browser = await p.chromium.launch(headless=True)

            # Create a browser context (isolated session)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )

            # Step 2: Load cookies if provided (for authenticated sessions)
            if cookies_file and os.path.exists(cookies_file):
                print(f"[Browser] Loading cookies from: {cookies_file}")
                with open(cookies_file, "r") as f:
                    cookies = json.load(f)
                await context.add_cookies(cookies)

            # Step 3: Navigate to the page
            page = await context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # Step 4: Wait for dynamic content to load
            if wait_for_selector:
                # Wait for a specific element to appear (e.g., job listing cards)
                try:
                    await page.wait_for_selector(wait_for_selector, timeout=10000)
                    print(f"[Browser] Found selector: {wait_for_selector}")
                except Exception:
                    print(f"[Browser] Selector '{wait_for_selector}' not found, continuing anyway")
            else:
                # Generic wait for JavaScript to finish rendering
                await asyncio.sleep(wait_seconds)

            # Step 5: Extract the page title
            title = await page.title()

            # Step 6: Extract the main text content
            # Try to get the main content area first, fall back to body
            content = await page.evaluate("""
                () => {
                    // Remove non-content elements
                    const removeSelectors = ['script', 'style', 'nav', 'footer', 'header', 
                                            'aside', 'noscript', 'iframe', 'svg'];
                    removeSelectors.forEach(sel => {
                        document.querySelectorAll(sel).forEach(el => el.remove());
                    });
                    
                    // Try to find the main content area
                    const main = document.querySelector('main') 
                              || document.querySelector('article')
                              || document.querySelector('[role="main"]')
                              || document.querySelector('#content')
                              || document.querySelector('.content')
                              || document.body;
                    
                    return main.innerText;
                }
            """)

            # Step 7: Clean up the text
            lines = [line.strip() for line in content.split("\n") if line.strip()]
            clean_content = "\n".join(lines)

            # Truncate to avoid token limits
            if len(clean_content) > 8000:
                clean_content = clean_content[:8000] + "\n\n[Content truncated...]"

            # Step 8: Save cookies for future use (if logged in)
            # This lets us reuse the session next time
            cookies_save_path = os.path.join(COOKIES_DIR, f"{_url_to_filename(url)}.json")
            os.makedirs(COOKIES_DIR, exist_ok=True)
            current_cookies = await context.cookies()
            with open(cookies_save_path, "w") as f:
                json.dump(current_cookies, f)

            # Clean up
            await browser.close()

            print(f"[Browser] Successfully scraped: {title}")
            return {
                "content": clean_content,
                "title": title,
                "url": url,
                "status": "success",
            }

    except Exception as e:
        print(f"[Browser] Error scraping {url}: {e}")
        return {
            "content": "",
            "title": "",
            "url": url,
            "status": "error",
            "error": f"Browser scraping error: {str(e)}",
        }


def _url_to_filename(url: str) -> str:
    """Convert a URL to a safe filename (for cookie storage)."""
    # Strip protocol and replace special chars
    name = url.replace("https://", "").replace("http://", "")
    name = name.replace("/", "_").replace(".", "_").replace("?", "_")
    return name[:50]  # Limit length
