"""Quick test: fetch GitHub content and send to LLM to extract jobs."""
import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))

from backend.tools.github_fetcher import fetch_github_jobs
from backend.llm import extract_jobs_from_content


async def main():
    test_url = "https://github.com/SimplifyJobs/New-Grad-Positions"
    
    print("=" * 60)
    print(f"Step 1: Fetching from GitHub: {test_url}")
    print("=" * 60)
    result = await fetch_github_jobs(test_url)
    
    print(f"Status: {result['status']}")
    if result['status'] == 'error':
        print(f"Error: {result.get('error')}")
        return
    
    content = result.get('content', '')
    print(f"Content length: {len(content)}")
    print(f"Content preview (first 300 chars):\n{content[:300]}")
    print("=" * 60)
    
    print()
    print("=" * 60)
    print("Step 2: Sending to LLM for job extraction")
    print("=" * 60)
    
    jobs = await extract_jobs_from_content(content, test_url)
    print(f"\n{'='*60}")
    print(f"RESULT: {len(jobs)} jobs extracted")
    print(f"{'='*60}")
    
    if jobs:
        for i, job in enumerate(jobs[:5]):
            print(f"\n  Job {i+1}:")
            print(f"    Title: {job.get('title')}")
            print(f"    Company: {job.get('company')}")
            print(f"    URL: {job.get('url')}")
            print(f"    Location: {job.get('location')}")
    else:
        print("NO JOBS EXTRACTED - something is still wrong")


asyncio.run(main())
