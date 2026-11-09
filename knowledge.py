import json
from pathlib import Path
DB = Path("data/knowledge.json")

def load_notes():
    if not DB.exists():
        return []
    try:
        return json.loads(DB.read_text(encoding="utf-8"))
    except Exception:
        return []

def save_note(title, body):
    DB.parent.mkdir(parents=True, exist_ok=True)
    notes = load_notes()
    notes.append({"title": title, "body": body})
    DB.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
