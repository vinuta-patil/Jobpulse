# Project Instructions — Multi-Agent Job System

## General Rules

- **Keep the code simple.** Avoid over-engineering. Prefer readable, flat code over clever abstractions.
- **Use comments everywhere.** Every function, every non-obvious block, and every "why" should be commented. The code should be self-explanatory for debugging.
- **No magic.** If something is configured, make it explicit. Avoid hidden defaults.
- **Error handling matters.** Always handle errors gracefully with clear log messages. Never silently swallow exceptions without logging.
- **Print/log progress.** Use `print(f"[Module] message")` format for all log lines so you can trace what's happening at a glance.

## Architecture

- **Backend:** Python + FastAPI, runs on `http://localhost:8000`
- **LLM:** Kimi K2.5 via NVIDIA NIM (OpenAI-compatible API at `integrate.api.nvidia.com/v1`)
- **Database:** SQLite (stored in `backend/job_monitor.db`)
- **Scheduler:** APScheduler (in-process, async)
- **Frontend:** Vanilla HTML/CSS/JS served as static files

## Code Style

- Use `async/await` for all I/O operations (HTTP calls, DB queries)
- Use Pydantic models for all API request/response shapes
- Keep each file focused — one responsibility per file
- Put all scraping tools in `backend/tools/`
- Use type hints on all function signatures
- Use f-strings for string formatting

## Source Types

The agent supports multiple source types. Each has its own fetcher tool:

| Type | File | Description |
|------|------|-------------|
| `website` | `tools/web_scraper.py` | Generic HTTP scraping with BeautifulSoup |
| `github` | `tools/github_fetcher.py` | GitHub API (README, issues, metadata) |
| `lever` | `tools/lever_fetcher.py` | Lever ATS API for company job boards |
| `greenhouse` | `tools/greenhouse_fetcher.py` | Greenhouse ATS API for company job boards |
| `browser` | `tools/browser_scraper.py` | Playwright for login-protected/JS-heavy sites |

## When Adding New Features

1. Add the tool in `backend/tools/`
2. Register it in `backend/agent.py` (the `scan_source` function)
3. Add the source type to `backend/models.py` (`SourceType` enum)
4. Update the frontend dropdown in `frontend/index.html`
5. Add any new dependencies to `backend/requirements.txt`

## Testing

- Always test new tools in isolation first with a simple script
- Then test end-to-end via the dashboard
- Check terminal logs for `[Agent]`, `[LLM]`, `[Scheduler]` prefixed messages

## Environment Variables (.env)

- `NVIDIA_API_KEY` — required for LLM calls
- `SCAN_INTERVAL_MINUTES` — how often the scheduler runs (default: 30)
