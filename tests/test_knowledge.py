import pytest

from nexus import knowledge


def test_save_and_load_notes_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(knowledge, "DB", tmp_path / "data" / "knowledge.json")
    knowledge.save_note("  title  ", "  body  ")
    assert knowledge.load_notes() == [{"title": "title", "body": "body"}]


@pytest.mark.parametrize("contents", ["{broken", "{}", '[1, null, {"title": 2, "body": "x"}]'])
def test_load_notes_recovers_from_invalid_or_malformed_data(tmp_path, monkeypatch, contents):
    monkeypatch.setattr(knowledge, "DB", tmp_path / "knowledge.json")
    knowledge.DB.write_text(contents, encoding="utf-8")
    assert knowledge.load_notes() == []


@pytest.mark.parametrize("title,body", [("", "body"), ("title", ""), (None, "body"), ("x" * 201, "body"), ("title", "x" * 20001)])
def test_save_notes_rejects_invalid_or_oversized_input(tmp_path, monkeypatch, title, body):
    monkeypatch.setattr(knowledge, "DB", tmp_path / "knowledge.json")
    with pytest.raises(ValueError):
        knowledge.save_note(title, body)
    assert not knowledge.DB.exists()
