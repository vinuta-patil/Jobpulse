"""Pydantic models for the Job Source Monitor agent."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class SourceType(str, Enum):
    WEBSITE = "website"
    GITHUB = "github"
    LEVER = "lever"           # Lever ATS career pages (jobs.lever.co/company)
    GREENHOUSE = "greenhouse" # Greenhouse ATS career pages (boards.greenhouse.io/company)
    BROWSER = "browser"       # Login-protected or JS-heavy sites (uses Playwright)


class SourceCreate(BaseModel):
    url: str
    type: SourceType = SourceType.WEBSITE
    name: Optional[str] = None


class Source(BaseModel):
    id: int
    url: str
    type: SourceType
    name: str
    added_at: str
    last_scanned: Optional[str] = None


class JobUpdate(BaseModel):
    id: Optional[int] = None
    source_id: int
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    discovered_at: Optional[str] = None
    content_hash: Optional[str] = None


class ScanResult(BaseModel):
    source_id: int
    source_name: str
    jobs_found: int
    new_jobs: int
    status: str
    error: Optional[str] = None


class ScanStatus(BaseModel):
    is_running: bool
    last_scan_at: Optional[str] = None
    next_scan_at: Optional[str] = None
    interval_minutes: int
    results: list[ScanResult] = []


class ChatMessage(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    updates: list[JobUpdate] = []


class JobSearchQuery(BaseModel):
    """Request model for Agent #2 job search."""
    query: str = Field(..., description="Search keywords (e.g., 'software engineer')")
    location: Optional[str] = Field(None, description="Location (e.g., 'san francisco')")
    date_posted: str = Field("all", description="'all', 'today', '3days', 'week', 'month'")
    remote_only: bool = Field(False, description="Only return remote jobs")
    employment_type: Optional[str] = Field(None, description="FULLTIME, PARTTIME, CONTRACTOR, INTERN")
    country: str = Field("us", description="ISO country code")
