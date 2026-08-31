"""Small local JSON persistence layer for learning progress."""
import json
from datetime import date
from pathlib import Path

DATA_FILE = Path("data/student_progress.json")
DEFAULT = {"pdfs": [], "questions": 0, "flashcards_reviewed": 0, "flashcards_hard": 0, "quizzes": [], "study_hours": 0.0, "tasks": [], "weak_topics": {}, "activity": {}}


def load_progress():
    DATA_FILE.parent.mkdir(exist_ok=True)
    if not DATA_FILE.exists():
        save_progress(DEFAULT.copy())
    try:
        return {**DEFAULT, **json.loads(DATA_FILE.read_text())}
    except (ValueError, OSError):
        return DEFAULT.copy()


def save_progress(progress):
    DATA_FILE.parent.mkdir(exist_ok=True)
    DATA_FILE.write_text(json.dumps(progress, indent=2))


def record_activity(kind, amount=1):
    progress = load_progress()
    today = date.today().isoformat()
    progress["activity"][today] = progress["activity"].get(today, 0) + amount
    if kind in progress:
        progress[kind] += amount
    save_progress(progress)
    return progress


def record_quiz(score, total, topics):
    progress = load_progress()
    progress["quizzes"].append({"date": date.today().isoformat(), "score": score, "total": total})
    for topic, is_correct in topics:
        if not is_correct:
            progress["weak_topics"][topic] = progress["weak_topics"].get(topic, 0) + 1
    save_progress(progress)
