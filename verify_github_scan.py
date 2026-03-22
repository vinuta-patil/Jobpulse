import asyncio
import os
from dotenv import load_dotenv
from backend.tools.github_fetcher import fetch_github_jobs
from backend.llm import extract_jobs_from_content, client, MODEL
from backend import database as db

# Load env vars
load_dotenv()

async def test_llm_ping():
    print("\n[0] Testing LLM Connectivity...")
    key = os.getenv("NVIDIA_API_KEY")
    if not key:
        print("ERROR: NVIDIA_API_KEY is missing!")
        return False
    print(f"NVIDIA_API_KEY present: {key[:4]}...{key[-4:]}")
    
    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "Hello, are you working?"}],
            max_tokens=10
        )
        print(f"LLM Response: {response.choices[0].message.content}")
        return True
    except Exception as e:
        print(f"LLM Ping Failed: {e}")
        return False

async def test_github_scan(url: str):
    if not await test_llm_ping():
        return

    print(f"\n--- Testing GitHub Scan for: {url} ---")
    
    # 1. Init DB
    await db.init_db()
    
    # 2. Add Source
    print("\n[1] Adding Source to Supabase...")
    try:
        source = await db.add_source(url, "github", "Test GitHub Repo")
        print(f"Success. Source ID: {source['id']}")
        source_id = source['id']
    except Exception as e:
        print(f"Failed to add source (might exist): {e}")
        # Try to find it or just proceed with a dummy ID
        source_id = 999 

    # 3. Fetch Content
    print("\n[2] Fetching Content from GitHub...")
    fetch_result = await fetch_github_jobs(url)
    if fetch_result["status"] == "error":
        print(f"Fetch failed: {fetch_result['error']}")
        return
    
    content = fetch_result["content"]
    print(f"Fetch success. Content length: {len(content)} chars")

    # 4. LLM Extraction
    print("\n[3] Extracting Jobs with LLM...")
    try:
        jobs = await extract_jobs_from_content(content, url)
        print(f"LLM found {len(jobs)} jobs.")
        for j in jobs:
            print(f" - {j.get('title')} @ {j.get('company')}")
    except Exception as e:
        print(f"LLM extraction failed: {e}")
        return

    # 5. Save to DB
    print("\n[4] Saving to Supabase...")
    if jobs:
        try:
            total, new = await db.save_job_updates(source_id, jobs, agent_id="agent1")
            print(f"Saved to DB. Total: {total}, New: {new}")
        except Exception as e:
            print(f"Save failed: {e}")
    else:
        print("No jobs to save.")

if __name__ == "__main__":
    TEST_URL = "https://github.com/SimplifyJobs/New-Grad-Positions" 
    asyncio.run(test_github_scan(TEST_URL))
