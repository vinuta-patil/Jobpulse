"""Clear Supabase DB tables and re-add GitHub sources for testing."""
import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))

from backend.database import init_db, _get_client


async def main():
    await init_db()
    client = _get_client()

    # Clear tables in order (foreign key constraints)
    print("Clearing jobs table...")
    resp = client.table("jobs").delete().neq("id", 0).execute()
    print(f"  Deleted {len(resp.data)} rows from jobs")

    print("Clearing scan_history table...")
    resp = client.table("scan_history").delete().neq("id", 0).execute()
    print(f"  Deleted {len(resp.data)} rows from scan_history")

    print("Clearing sources table...")
    resp = client.table("sources").delete().neq("id", 0).execute()
    print(f"  Deleted {len(resp.data)} rows from sources")

    print("\nAll tables cleared!")

    # Re-add the GitHub source
    print("\nRe-adding GitHub source...")
    from backend.database import add_source
    result = await add_source(
        url="https://github.com/SimplifyJobs/New-Grad-Positions",
        source_type="github",
        name="SimplifyJobs New Grad"
    )
    print(f"  Added source: {result}")

    print("\nDone! Now trigger a scan via: curl -X POST http://localhost:8000/api/scan")


asyncio.run(main())
