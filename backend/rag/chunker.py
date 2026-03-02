import json
import re
from pathlib import Path

from config import CHUNK_SIZE, CHUNK_OVERLAP, DATA_DIR


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks by token-approximate character count."""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk.strip())
        start += chunk_size - overlap
    return chunks


def _chunk_markdown(filepath: Path) -> list[dict]:
    """Split a markdown file by headers, then into sized chunks."""
    text = filepath.read_text(encoding="utf-8")
    sections = re.split(r"\n(?=##?\s)", text)
    chunks = []
    for section in sections:
        lines = section.strip().split("\n")
        header = lines[0].strip("# ").strip() if lines else ""
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else lines[0]
        if not body:
            continue
        for piece in _split_text(body, CHUNK_SIZE, CHUNK_OVERLAP):
            chunks.append({
                "text": piece,
                "source": filepath.name,
                "section": header,
            })
    return chunks


def _chunk_resume(filepath: Path) -> list[dict]:
    """Extract structured chunks from resume JSON."""
    data = json.loads(filepath.read_text(encoding="utf-8"))
    chunks = []

    basic = f"{data['name']} is based in {data['location']['current']}, originally from {data['location']['hometown']}."
    chunks.append({"text": basic, "source": "resume.json", "section": "basic_info"})

    for edu in data.get("education", []):
        text = f"Education: {edu['degree']} at {edu['school']}, {edu['location']}. Graduated {edu['graduation']}."
        if "focus" in edu:
            text += f" Focus: {edu['focus']}."
        if "coursework" in edu:
            text += f" Coursework: {', '.join(edu['coursework'])}."
        chunks.append({"text": text, "source": "resume.json", "section": "education"})

    skills = data.get("skills", {})
    skills_text = (
        f"Technical skills — Languages: {', '.join(skills.get('languages', []))}. "
        f"Frameworks & tools: {', '.join(skills.get('frameworks_and_tools', []))}. "
        f"Infrastructure: {', '.join(skills.get('infrastructure', []))}."
    )
    chunks.append({"text": skills_text, "source": "resume.json", "section": "skills"})

    for exp in data.get("experience", []):
        header = f"{exp['role']} at {exp['company']}, {exp['location']} ({exp['dates']})"
        highlights = " ".join(exp.get("highlights", []))
        full = f"{header}. {highlights}"
        for piece in _split_text(full, CHUNK_SIZE, CHUNK_OVERLAP):
            chunks.append({"text": piece, "source": "resume.json", "section": f"experience_{exp['company']}"})

    return chunks


def _chunk_qa_pairs(filepath: Path) -> list[dict]:
    """Each Q&A pair becomes its own chunk."""
    pairs = json.loads(filepath.read_text(encoding="utf-8"))
    chunks = []
    for pair in pairs:
        text = f"Q: {pair['question']}\nA: {pair['answer']}"
        chunks.append({
            "text": text,
            "source": "qa_pairs.json",
            "section": "qa",
        })
    return chunks


def load_all_chunks() -> list[dict]:
    """Load and chunk all data files."""
    chunks = []

    for md_file in DATA_DIR.glob("*.md"):
        chunks.extend(_chunk_markdown(md_file))

    resume_path = DATA_DIR / "resume.json"
    if resume_path.exists():
        chunks.extend(_chunk_resume(resume_path))

    qa_path = DATA_DIR / "qa_pairs.json"
    if qa_path.exists():
        chunks.extend(_chunk_qa_pairs(qa_path))

    return chunks
