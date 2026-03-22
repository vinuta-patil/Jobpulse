"""LLM client — meta/llama-3.3-70b-instruct via NVIDIA NIM (OpenAI-compatible)."""

import os
import json
import re
from openai import AsyncOpenAI
from dotenv import load_dotenv
import httpx

load_dotenv()

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL = "meta/llama-3.3-70b-instruct"

# 5-minute timeout — large README content (50K+) can take a while to process
client = AsyncOpenAI(
    base_url=BASE_URL,
    api_key=NVIDIA_API_KEY,
    timeout=httpx.Timeout(300.0, connect=15.0),
)

SYSTEM_PROMPT = """\
You are a Job Source Monitor agent. Your task is to analyze content from websites \
and GitHub repositories to extract job-related information.

When given raw content from a source, you should:
1. Identify job listings, openings, career opportunities, or hiring-related information
2. Extract structured data for each job found: title, company, location, URL, date posted, and a brief description
3. If the content is a curated list (like "hiring-without-whiteboards"), extract the company names and any relevant details

Return your findings as a JSON array of job objects. Each object should have:
- "title": the job title or company name if specific title not available
- "company": the company name
- "location": the location (or "Remote" / "Various" / "Not specified")
- "url": direct link to the job or company careers page if available
- "date_posted": the date the job was posted in YYYY-MM-DD format (e.g. "2026-02-11"). Extract this from the source content. If no date is found, use null.
- "description": a 1-2 sentence summary

If no job-related content is found, return an empty array [].
Always respond with ONLY the JSON array, no other text."""

# Tool definitions for function-calling
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "scrape_website",
            "description": "Scrape a website URL to extract its text content. Use this for career pages, job boards, or any web URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full URL to scrape",
                    }
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_github_repo",
            "description": "Fetch job-related information from a GitHub repository. Retrieves README, job-tagged issues, and repo metadata.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_url": {
                        "type": "string",
                        "description": "The GitHub repository URL",
                    }
                },
                "required": ["repo_url"],
            },
        },
    },
]


def _parse_jobs_json(text: str) -> list[dict] | None:
    """Try to parse a JSON job array from LLM response text. Returns None on failure."""
    text = text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (```json and ```)
        text = "\n".join(lines[1:-1]).strip()

    # Direct parse
    try:
        obj = json.loads(text)
        if isinstance(obj, list):
            return obj
    except json.JSONDecodeError:
        pass

    # Regex fallback — find JSON array embedded in text
    for m in re.finditer(r'\[[\s\S]*?\]', text):
        try:
            obj = json.loads(m.group())
            if isinstance(obj, list) and obj:
                return obj
        except json.JSONDecodeError:
            continue

    # Truncated JSON recovery — if max_tokens cut off the response,
    # the closing ] may be missing. Find all complete {...} objects.
    objects = []
    for m in re.finditer(r'\{[^{}]*\}', text):
        try:
            obj = json.loads(m.group())
            if isinstance(obj, dict) and "title" in obj:
                objects.append(obj)
        except json.JSONDecodeError:
            continue
    if objects:
        return objects

    return None


async def extract_jobs_from_content(content: str, source_url: str, max_retries: int = 2) -> list[dict]:
    """Send scraped content to LLM to extract job listings.

    Llama 3.3 70B has a 128K context window so we can send the full
    content in one shot — no chunking needed.  Retries on timeout.
    """
    import asyncio as _aio

    for attempt in range(1, max_retries + 1):
        try:
            print(f"[LLM] Attempt {attempt}/{max_retries}: sending {len(content)} chars to {MODEL}...")
            response = await client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Analyze this content from {source_url} and extract "
                            f"all job-related information:\n\n{content}"
                        ),
                    },
                ],
                temperature=0.1,
                max_tokens=16384,
            )

            resp_content = response.choices[0].message.content
            if not resp_content:
                print(f"[LLM] Warning: empty response from {MODEL}")
                return []

            print(f"[LLM] Response received ({len(resp_content)} chars).")

            jobs = _parse_jobs_json(resp_content)
            if jobs is not None:
                print(f"[LLM] Extracted {len(jobs)} jobs.")
                return jobs

            print(f"[LLM] Could not parse JSON. Raw response (first 300):")
            print(f"  {resp_content[:300]}")
            return []

        except Exception as e:
            print(f"[LLM] Error on attempt {attempt}: {e}")
            if attempt < max_retries:
                print(f"[LLM] Retrying in 10 seconds...")
                await _aio.sleep(10)

    print(f"[LLM] All {max_retries} attempts failed for {source_url}")
    return []


async def chat_with_agent(message: str, context: str = "") -> str:
    """General chat with the agent for user queries about job updates."""
    try:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful Job Monitor assistant. You help users track job openings "
                    "from their configured sources. Answer questions about job updates, provide "
                    "summaries, and help configure monitoring. Be concise and informative."
                ),
            },
        ]
        if context:
            messages.append({"role": "system", "content": f"Current job data:\n{context}"})
        messages.append({"role": "user", "content": message})

        response = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=2048,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Sorry, I encountered an error: {str(e)}"
