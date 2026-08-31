"""AI-powered learning-content generators."""
import json
import re
from utils.llm import ask_llm


def _json_from_llm(prompt, fallback):
    response = ask_llm(prompt)
    try:
        match = re.search(r"\{.*\}|\[.*\]", response, re.DOTALL)
        return json.loads(match.group(0) if match else response)
    except (ValueError, AttributeError):
        return fallback


def generate_flashcards(chunks, language="English", count=10):
    source = "\n".join(chunks[:6])
    return _json_from_llm(
        f"Create {count} concise study flashcards from this material in {language}. "
        "Return only JSON list: [{\"front\": \"question\", \"back\": \"answer\", \"topic\": \"topic\"}].\n" + source, [],
    )


def generate_quiz(chunks, language, count, difficulty):
    source = "\n".join(chunks[:6])
    return _json_from_llm(
        f"Create {count} {difficulty} study quiz questions from this material in {language}. "
        "Return only JSON list. Every item needs question, options (four strings), answer (exact option), explanation, and topic.\n" + source, [],
    )


def create_plan(exam_date, topics, hours, confidence, preferred_time, language):
    return ask_llm(
        f"Create a practical day-by-day study plan in {language}. Exam date: {exam_date}. "
        f"Topics: {topics}. Available daily hours: {hours}. Confidence by topic: {confidence}. "
        f"Preferred time: {preferred_time}. Include revision, flashcards, adaptive quizzes, rest breaks, and weak-topic priority."
    )
