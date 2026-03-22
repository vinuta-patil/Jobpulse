"""Resume Parser — Extract structured data from PDF resumes using LLM."""

import os
import json
import pdfplumber
from io import BytesIO

from .llm import client, MODEL

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
RESUME_FILE = os.path.join(DATA_DIR, "resume.json")

RESUME_PROMPT = """\
You are a resume parser. Given the raw text extracted from a PDF resume, \
parse it into a structured JSON object with the following schema:

{
  "personal_info": {
    "name": "Full name",
    "email": "Email address or null",
    "phone": "Phone number or null",
    "location": "City, State or null",
    "linkedin": "LinkedIn URL or null",
    "github": "GitHub URL or null",
    "website": "Personal website URL or null"
  },
  "education": [
    {
      "school": "University name",
      "degree": "Degree type (e.g. Master of Science)",
      "field": "Field of study",
      "gpa": "GPA or null",
      "location": "City, State/Country",
      "start_date": "e.g. Aug 2024",
      "end_date": "e.g. May 2026 or Present",
      "coursework": ["course1", "course2"],
      "achievements": ["achievement1"]
    }
  ],
  "experience": [
    {
      "company": "Company name",
      "title": "Job title",
      "location": "City, State or Remote",
      "start_date": "e.g. Jun 2023",
      "end_date": "e.g. Aug 2024 or Present",
      "highlights": ["bullet point 1", "bullet point 2"]
    }
  ],
  "skills": {
    "languages": ["Python", "Java"],
    "frameworks": ["React", "FastAPI"],
    "tools": ["Docker", "Git"],
    "other": ["Machine Learning", "Agile"]
  },
  "projects": [
    {
      "name": "Project name",
      "highlights": ["achievement or feature 1", "achievement or feature 2", "achievement or feature 3"],
      "technologies": ["tech1", "tech2"],
      "url": "URL or null"
    }
  ],
  "certifications": [
    {
      "name": "Certification name",
      "issuer": "Issuing organization",
      "date": "Date obtained or null"
    }
  ]
}

Rules:
- Extract ALL information from the resume text, do not skip anything.
- If a section is not present in the resume, use an empty array [] or null.
- For dates, keep them in the original format (e.g. "Aug 2024", "2024").
- For GPA, include the scale if mentioned (e.g. "3.8/4.0" or just "3.8").
- For skills, categorize them as best you can. If unsure, put in "other".
- For experience highlights: Each bullet point from the resume should be a SEPARATE array item. If a bullet point contains multiple achievements, split them into separate items.
- For project highlights: Extract key features, achievements, or technical accomplishments as separate array items (at least 3-6 highlights per project).
- Keep each highlight focused and concise (one specific achievement per item).
- Return ONLY the JSON object, no other text."""


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text content from a PDF file."""
    text_parts = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n\n".join(text_parts)


async def parse_resume_with_llm(text: str) -> dict:
    """Send resume text to LLM for structured extraction."""
    print(f"[Resume] Sending {len(text)} chars to LLM for parsing...")

    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": RESUME_PROMPT},
            {
                "role": "user",
                "content": f"Parse this resume:\n\n{text}",
            },
        ],
        temperature=0.1,
        max_tokens=4096,
    )

    content = response.choices[0].message.content
    if not content:
        raise ValueError("Empty response from LLM")

    # Strip markdown code fences if present
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1]).strip()

    parsed = json.loads(content)
    print(f"[Resume] Successfully parsed resume for: {parsed.get('personal_info', {}).get('name', 'Unknown')}")
    return parsed


async def process_resume(file_bytes: bytes) -> dict:
    """Full pipeline: PDF → text → LLM → structured data → save."""
    text = extract_text_from_pdf(file_bytes)
    if not text.strip():
        raise ValueError("Could not extract text from PDF. Is the file a valid PDF?")

    print(f"[Resume] Extracted {len(text)} chars from PDF")
    data = await parse_resume_with_llm(text)

    # Save to file
    save_resume(data)
    return data


def save_resume(data: dict) -> None:
    """Save parsed resume data to JSON file."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(RESUME_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[Resume] Saved to {RESUME_FILE}")


def load_resume() -> dict | None:
    """Load saved resume data. Returns None if no resume is saved."""
    if not os.path.exists(RESUME_FILE):
        return None
    with open(RESUME_FILE, "r") as f:
        return json.load(f)


def update_resume(data: dict) -> dict:
    """Update resume data (for manual edits)."""
    existing = load_resume() or {}
    existing.update(data)
    save_resume(existing)
    return existing
