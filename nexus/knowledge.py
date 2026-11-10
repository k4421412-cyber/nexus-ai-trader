import json
import os
from pathlib import Path

DB = Path("data/knowledge.json")

def load_notes():
    if not DB.exists():
        return []
    try:
        data = json.loads(DB.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [
        note for note in data
        if isinstance(note, dict)
        and isinstance(note.get("title"), str)
        and isinstance(note.get("body"), str)
    ]

def save_note(title, body):
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Note title must be a non-empty string")
    if not isinstance(body, str) or not body.strip():
        raise ValueError("Note body must be a non-empty string")
    if len(title) > 200 or len(body) > 20000:
        raise ValueError("Note title or body exceeds the allowed length")
    DB.parent.mkdir(parents=True, exist_ok=True)
    notes = load_notes()
    notes.append({"title": title.strip(), "body": body.strip()})
    temporary = DB.with_name(DB.name + ".tmp")
    try:
        temporary.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, DB)
    finally:
        if temporary.exists():
            temporary.unlink()
