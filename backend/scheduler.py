"""APScheduler background job for periodic source scanning."""

import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timezone
import os

scheduler = AsyncIOScheduler()

# Track scan state — Agent #1 (source monitor)
_scan_state = {
    "is_running": False,
    "last_scan_at": None,
    "last_results": [],
}

# Track scan state — Agent #3 (ATS auto-scanner)
_ats_scan_state = {
    "is_running": False,
    "last_scan_at": None,
    "last_results": {},
}


def get_scan_state() -> dict:
    return _scan_state.copy()


def get_ats_scan_state() -> dict:
    return _ats_scan_state.copy()


async def _run_scan():
    """The scheduled scan job."""
    from .agent import scan_all_sources

    if _scan_state["is_running"]:
        print("[Scheduler] Scan already in progress, skipping.")
        return

    _scan_state["is_running"] = True
    try:
        results = await scan_all_sources()
        _scan_state["last_scan_at"] = datetime.now(timezone.utc).isoformat()
        _scan_state["last_results"] = results
    except Exception as e:
        print(f"[Scheduler] Scan error: {e}")
    finally:
        _scan_state["is_running"] = False


async def _run_ats_scan():
    """The scheduled ATS batch scan job (Agent #3)."""
    from .ats_scanner import scan_ats_batch

    if _ats_scan_state["is_running"]:
        print("[Scheduler] ATS scan already in progress, skipping.")
        return

    _ats_scan_state["is_running"] = True
    try:
        results = await scan_ats_batch()
        _ats_scan_state["last_scan_at"] = datetime.now(timezone.utc).isoformat()
        _ats_scan_state["last_results"] = results
    except Exception as e:
        print(f"[Scheduler] ATS scan error: {e}")
    finally:
        _ats_scan_state["is_running"] = False


def start_scheduler(interval_minutes: int = 30):
    """Start the background scheduler."""
    interval = int(os.getenv("SCAN_INTERVAL_MINUTES", str(interval_minutes)))
    ats_interval_hours = int(os.getenv("ATS_SCAN_INTERVAL_HOURS", "4"))

    # Agent #1: source monitor
    scheduler.add_job(
        _run_scan,
        trigger=IntervalTrigger(minutes=interval),
        id="job_scan",
        name="Periodic Job Source Scan",
        replace_existing=True,
    )

    # Agent #3: ATS auto-scanner
    scheduler.add_job(
        _run_ats_scan,
        trigger=IntervalTrigger(hours=ats_interval_hours),
        id="ats_scan",
        name="ATS Batch Scanner",
        replace_existing=True,
    )

    scheduler.start()
    print(f"[Scheduler] Started. Source scan every {interval}min, ATS scan every {ats_interval_hours}h.")


def stop_scheduler():
    """Stop the background scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("[Scheduler] Stopped.")


async def trigger_manual_scan() -> list[dict]:
    """Trigger an immediate scan (manual)."""
    if _scan_state["is_running"]:
        return [{"status": "error", "error": "Scan already in progress"}]

    await _run_scan()
    return _scan_state["last_results"]


async def trigger_ats_scan() -> dict:
    """Trigger an immediate ATS batch scan (manual)."""
    if _ats_scan_state["is_running"]:
        return {"status": "error", "error": "ATS scan already in progress"}

    await _run_ats_scan()
    return _ats_scan_state["last_results"]

