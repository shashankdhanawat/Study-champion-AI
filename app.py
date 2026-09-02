import os
import json
import re
import textwrap
from pathlib import Path
import base64
import random
import sqlite3
import hashlib
from datetime import date, timedelta

import streamlit as st

from utils.pdf_reader import read_pdf
from utils.pdf_cleaning import clean_text
from utils.text_chuncker import chunk_text

from services.rag_pipeline import answer_question
from utils.llm import ask_llm


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Study Champion AI",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# COLORS
# ============================================================

NAVY = "#0B1F3A"
NAVY_LIGHT = "#236ABA"
BLUE = "#1E5AA8"
WHITE = "#FFFFFF"
LIGHT = "#F5F8FC"
TEXT = "#0B1F3A"
MUTED = "#52647A"
BORDER = "#DCE6F2"
GREEN = "#176B35"
RED = "#B42318"


# ============================================================
# SESSION STATE
# ============================================================

DEFAULT_STATE = {
    "logged_in": False,
    "user_id": None,
    "username": "",
    "page": "landing",
    "chunks": [],
    "cleaned_text": "",
    "file_name": "",
    "document_loaded": False,
    "messages": [],
    "topics": [],
    "quiz_questions": [],
    "quiz_score": 0,
    "quiz_attempted": 0,
    "correct_answers": 0,
    "wrong_answers": 0,
    "flashcards": [],
    "flashcards_reviewed": 0,
    "study_minutes": 0,
    "selected_topic": None,
    "study_plan": [],
    "adaptive_recommendations": [],
    "quiz_generated": False,
    "flashcards_generated": False,
    "topics_generated": False,
    "planner_created": False,
    "quiz_submitted": False,
    "study_streak": 0,
    "ai_summary": "",
   
}


for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


DB_PATH = "study_champion.db"


def init_auth_database():
    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS study_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            study_date TEXT NOT NULL,
            UNIQUE(user_id, study_date)
        )
        """
    )
    conn.commit()
    conn.close()
init_auth_database()

# ============================================================
# HTML RENDER HELPER
# ============================================================

def render_html(html):
    """
    Safely render HTML using textwrap.dedent.

    IMPORTANT:
    All custom HTML in this application goes through this function.
    """

    cleaned_html = textwrap.dedent(html).strip()

    try:
        # Modern Streamlit HTML renderer
        st.html(cleaned_html)
    except AttributeError:
        # Compatibility fallback for older Streamlit versions
        st.markdown(
            cleaned_html,
            unsafe_allow_html=True,
        )


# ============================================================
# BACKGROUND
# ============================================================

def set_background(image_path):
    """
    Set landing page background if image exists.
    """

    image_path = Path(image_path)

    if not image_path.exists():
        return

    try:
        image_data = base64.b64encode(
            image_path.read_bytes()
        ).decode("utf-8")

        render_html(
            f"""
            <style>
                [data-testid="stAppViewContainer"] {{
                    background:
                        linear-gradient(
                            rgba(11, 31, 58, 0.88),
                            rgba(11, 31, 58, 0.94)
                        ),
                        url("data:image/jpeg;base64,{image_data}");

                    background-size: cover;
                    background-position: center;
                    background-attachment: fixed;
                }}

                [data-testid="stHeader"] {{
                    background: transparent;
                }}
            </style>
            """
        )

    except Exception:
        pass


# ============================================================
# GLOBAL CSS
# ============================================================

def common_css():

    render_html(
        f"""
        <style>

        /* ================================================
           MAIN
        ================================================ */

        [data-testid="stMainBlockContainer"] {{
            max-width: 1250px;
            padding-top: 25px;
            padding-bottom: 70px;
        }}


        /* ================================================
           SIDEBAR
        ================================================ */

        [data-testid="stSidebar"] {{
            background: {NAVY};
        }}

        [data-testid="stSidebar"] * {{
            color: white;
        }}

        [data-testid="stSidebar"] div.stButton {{
            width: 100%;
            margin-bottom: 9px;
        }}

        [data-testid="stSidebar"] div.stButton > button {{
            width: 100%;
            min-height: 48px;
            border-radius: 12px;

            background: {NAVY_LIGHT};
            color: white;

            border: 1px solid rgba(255,255,255,0.15);

            font-size: 15px;
            font-weight: 700;

            transition: all 0.2s ease;
        }}

        [data-testid="stSidebar"] div.stButton > button:hover {{
            background: white;
            color: {NAVY};
            transform: translateX(4px);
        }}


        /* ================================================
           NORMAL BUTTONS
        ================================================ */

        div.stButton > button {{
            border-radius: 12px;

            background: white;
            color: {NAVY};

            border: 1px solid {BORDER};

            font-weight: 700;

            min-height: 44px;

            transition: all 0.2s ease;
        }}

        div.stButton > button:hover {{
            background: {NAVY};
            color: white;

            border-color: {NAVY};

            transform: translateY(-2px);
        }}


        /* ================================================
           LANDING
        ================================================ */

        .landing {{
            text-align: center;
            padding: 80px 25px;
        }}

        .badge {{
            display: inline-block;

            padding: 10px 22px;

            border-radius: 30px;

            background: rgba(255,255,255,0.12);

            border: 1px solid rgba(255,255,255,0.20);

            color: white;

            font-weight: 800;

            letter-spacing: 1px;
        }}

        .landing-title {{
            color: white;

            font-size: clamp(45px, 7vw, 78px);

            font-weight: 900;

            margin-top: 25px;

            letter-spacing: -3px;
        }}

        .landing-subtitle {{
            color: rgba(255,255,255,0.88);

            font-size: 20px;

            max-width: 800px;

            margin: auto;

            line-height: 1.7;
        }}

        .chips {{
            margin-top: 35px;
        }}

        .chip {{
            display: inline-block;

            padding: 12px 20px;

            margin: 7px;

            border-radius: 30px;

            background: rgba(255,255,255,0.12);

            border: 1px solid rgba(255,255,255,0.15);

            color: white;
        }}


        /* ================================================
           HERO
        ================================================ */

        .hero {{
            background: white;

            padding: 40px;

            border-radius: 25px;

            text-align: center;

            border: 1px solid {BORDER};

            box-shadow:
                0 12px 35px rgba(11,31,58,0.08);
        }}

        .hero h1 {{
            color: {NAVY};

            font-size: 48px;

            margin: 0;
        }}

        .hero p {{
            color: {MUTED};

            font-size: 18px;

            margin-bottom: 0;
        }}


        /* ================================================
           SECTION TITLE
        ================================================ */

        .section-title {{
            color: white;

            font-size: 28px;

            font-weight: 900;

            margin-top: 30px;

            margin-bottom: 18px;
        }}


        /* ================================================
           FEATURE CARDS
        ================================================ */

        .feature-card {{
            background: {NAVY};

            padding: 30px;

            border-radius: 20px;

            text-align: center;

            color: white;

            min-height: 210px;

            display: flex;

            flex-direction: column;

            justify-content: center;

            box-shadow:
                0 10px 25px rgba(11,31,58,0.15);
        }}

        .feature-icon {{
            font-size: 45px;
        }}

        .feature-card h2 {{
            color: white;

            margin: 10px 0;
        }}

        .feature-card p {{
            color: #DDE6F2;

            margin: 0;
        }}


        /* ================================================
           STAT CARDS
        ================================================ */

        .stat-card {{
            background: white;

            border: 1px solid {BORDER};

            border-radius: 16px;

            padding: 22px;

            text-align: center;

            min-height: 115px;

            box-shadow:
                0 8px 25px rgba(11,31,58,0.05);
        }}

        .stat-number {{
            color: {NAVY};

            font-size: 30px;

            font-weight: 900;
        }}

        .stat-label {{
            color: #69798C;

            font-size: 13px;

            margin-top: 5px;
        }}


        /* ================================================
           INFO CARDS
        ================================================ */

        .info-card {{
            background: white;

            border: 1px solid {BORDER};

            border-left: 5px solid {NAVY};

            border-radius: 15px;

            padding: 20px;

            margin: 12px 0;

            box-shadow:
                0 6px 20px rgba(11,31,58,0.05);
        }}

        .info-card h3 {{
            color: {NAVY};

            margin-top: 0;
        }}

        .info-card p {{
            color: {MUTED};
        }}


        /* ================================================
           UPLOAD
        ================================================ */

        .upload-box {{
            background:
                linear-gradient(
                    135deg,
                    {NAVY},
                    {NAVY_LIGHT}
                );

            padding: 40px;

            border-radius: 25px;

            text-align: center;

            margin-top: 30px;

            color: white;
        }}

        .upload-box h1 {{
            color: white;
        }}

        .upload-box p {{
            color: rgba(255,255,255,0.80);
        }}


        /* ================================================
           QUIZ
        ================================================ */

        .quiz-card {{
            background: white;

            border: 1px solid {BORDER};

            border-radius: 18px;

            padding: 25px;

            margin-bottom: 18px;

            box-shadow:
                0 7px 20px rgba(11,31,58,0.05);
        }}

        .question-number {{
            color: {BLUE};

            font-weight: 800;

            font-size: 14px;
        }}

        .question-text {{
            color: {NAVY};

            font-size: 19px;

            font-weight: 800;

            margin-top: 8px;
        }}


        /* ================================================
           FLASHCARD
        ================================================ */

        .flashcard {{
            background:
                linear-gradient(
                    135deg,
                    {NAVY},
                    {NAVY_LIGHT}
                );

            color: white;

            padding: 45px;

            border-radius: 22px;

            text-align: center;

            margin: 15px 0;

            min-height: 180px;

            display: flex;

            flex-direction: column;

            justify-content: center;
        }}

        .flashcard-label {{
            color: #BBD4F0;

            font-size: 13px;

            font-weight: 800;

            text-transform: uppercase;

            letter-spacing: 1px;
        }}

        .flashcard-question {{
            color: white;

            font-size: 23px;

            font-weight: 800;

            margin-top: 12px;
        }}

        .answer-box {{
            background: #F5F8FC;

            border: 1px solid {BORDER};

            padding: 25px;

            border-radius: 16px;

            color: {TEXT};

            margin-top: 10px;
        }}


        /* ================================================
           PLAN
        ================================================ */

        .plan-day {{
            background: white;

            border: 1px solid {BORDER};

            border-radius: 15px;

            padding: 20px;

            margin-bottom: 12px;
        }}

        .plan-day h3 {{
            color: {NAVY};
        }}

        .plan-day p {{
            color: {MUTED};
        }}


        /* ================================================
           SIDEBAR BRAND
        ================================================ */

        .sidebar-brand {{
            text-align: center;

            padding: 10px 5px 18px 5px;
        }}

        .sidebar-brand-icon {{
            font-size: 45px;
        }}

        .sidebar-brand-title {{
            color: white;

            font-size: 21px;

            font-weight: 900;

            margin-top: 5px;
        }}

        .sidebar-brand-subtitle {{
            color: rgba(255,255,255,0.65);

            font-size: 12px;

            margin-top: 4px;
        }}

        </style>
        """
    )


# ============================================================
# RESET DOCUMENT DATA
# ============================================================

def reset_document_data():

    st.session_state.chunks = []
    st.session_state.cleaned_text = ""
    st.session_state.file_name = ""
    st.session_state.document_loaded = False

    st.session_state.messages = []

    st.session_state.topics = []
    st.session_state.quiz_questions = []
    st.session_state.flashcards = []

    st.session_state.selected_topic = None

    st.session_state.quiz_generated = False
    st.session_state.flashcards_generated = False
    st.session_state.topics_generated = False


# ============================================================
# PDF PROCESSING
# ============================================================

def process_pdf(uploaded_file):

    if uploaded_file is None:
        return False

    temp_path = Path(
        f"temp_{uploaded_file.name}"
    )

    try:

        with open(temp_path, "wb") as file:

            file.write(
                uploaded_file.getbuffer()
            )

        with st.spinner(
            "Processing your PDF..."
        ):

            raw_text = read_pdf(
                str(temp_path)
            )

            if not raw_text or not raw_text.strip():

                st.error(
                    "Could not extract text from this PDF."
                )

                return False

            cleaned = clean_text(
                raw_text
            )

            if not cleaned or not cleaned.strip():

                st.error(
                    "The PDF does not contain usable study text."
                )

                return False

            chunks = chunk_text(
                cleaned
            )

            chunks = [
                str(chunk).strip()
                for chunk in chunks
                if chunk and str(chunk).strip()
            ]

            if not chunks:

                st.error(
                    "No study chunks were created."
                )

                return False

        reset_document_data()

        st.session_state.cleaned_text = cleaned

        st.session_state.chunks = chunks

        st.session_state.file_name = (
            uploaded_file.name
        )

        st.session_state.document_loaded = True
        record_study_activity()

        st.success(
            f"PDF processed successfully: {uploaded_file.name}"
        )

        return True

    except Exception as exc:

        st.error(
            f"Error processing PDF: {exc}"
        )

        return False

    finally:

        if temp_path.exists():

            try:
                temp_path.unlink()
            except Exception:
                pass


# ============================================================
# MISTRAL HELPER
# ============================================================

def ai_generate(prompt, system_prompt=None):


    try:

        result = ask_llm(
            prompt,
            system_prompt=system_prompt
        )

        if not result:
            return ""

        return str(result).strip()

    except TypeError:

        # Compatibility with older ask_llm(prompt)
        try:

            result = ask_llm(prompt)

            return str(result).strip()

        except Exception:

            return ""

    except Exception:

        return ""
    
def generate_ai_summary():

    if not st.session_state.document_loaded:
        return ""

    material = st.session_state.cleaned_text[:20000]

    prompt = f"""
You are Study Champion AI.

Create a clear and useful study summary from the supplied
study material.

Use ONLY the supplied material.

Create the summary in this structure:

# Study Summary

## Overview
Give a short overview of the material.

## Key Concepts
List the most important concepts.

## Important Points
Explain the major points in simple language.

## Exam Notes
Give concise exam-oriented notes.

## Quick Revision
Give a short bullet-point revision section.

Rules:
- Do not invent information.
- Do not add information not present in the material.
- Keep the explanation student-friendly.
- Use clear headings and bullet points.
- Make it useful for exam revision.

STUDY MATERIAL:
{material}
"""

    response = ai_generate(
        prompt,
        system_prompt=(
            "Create accurate study summaries using only "
            "the supplied educational material."
        )
    )

    return response.strip() if response else ""

# ============================================================
# JSON EXTRACTION
# ============================================================

def extract_json(text):

    if not text:
        return None

    cleaned = text.strip()

    # Remove markdown fences
    cleaned = re.sub(
        r"```json",
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    cleaned = re.sub(
        r"```",
        "",
        cleaned
    ).strip()

    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # Try object
    object_match = re.search(
        r"\{.*\}",
        cleaned,
        flags=re.DOTALL
    )

    if object_match:

        try:
            return json.loads(
                object_match.group(0)
            )
        except Exception:
            pass

    # Try array
    array_match = re.search(
        r"\[.*\]",
        cleaned,
        flags=re.DOTALL
    )

    if array_match:

        try:
            return json.loads(
                array_match.group(0)
            )
        except Exception:
            pass

    return None


# ============================================================
# TOPIC GENERATOR
# ============================================================

def generate_topics():

    if not st.session_state.document_loaded:
        return []

    material = st.session_state.cleaned_text[:12000]

    prompt = f"""
You are an educational AI.

Analyze ONLY the supplied study material.

Extract the main study topics.

Return ONLY valid JSON in this exact format:

[
  "Topic 1",
  "Topic 2",
  "Topic 3"
]

Rules:
- Return 5 to 10 useful topics.
- Do not invent topics.
- Do not add explanations.
- Use short topic names.

STUDY MATERIAL:
{material}
"""

    response = ai_generate(
        prompt,
        system_prompt=(
            "You extract study topics accurately "
            "from supplied educational material."
        )
    )

    parsed = extract_json(response)

    if isinstance(parsed, list):

        topics = []

        for item in parsed:

            if isinstance(item, str):

                item = item.strip()

                if item and item not in topics:
                    topics.append(item)

        return topics[:10]

    # Fallback
    return detect_topics_locally()


def detect_topics_locally():

    text = st.session_state.cleaned_text

    topics = []

    for line in text.splitlines():

        line = line.strip()

        if not line:
            continue

        cleaned = re.sub(
            r"^[#\d\.\-\)\s]+",
            "",
            line
        ).strip()

        if (
            3 <= len(cleaned) <= 90
            and len(cleaned.split()) <= 12
        ):

            if cleaned not in topics:
                topics.append(cleaned)

    if not topics:

        topics = [
            "General Study Material"
        ]

    return topics[:10]


# ============================================================
# QUIZ GENERATOR
# ============================================================

def generate_quiz(topic=None, number_of_questions=5):

    if not st.session_state.document_loaded:
        return []

    material = st.session_state.cleaned_text[:16000]

    topic_instruction = ""

    if topic:

        topic_instruction = f"""
Focus primarily on this topic:
{topic}
"""

    prompt = f"""
You are an AI quiz generator for Study Champion AI.

Create {number_of_questions} multiple-choice questions.

{topic_instruction}

Use ONLY the supplied study material.

Return ONLY valid JSON in this exact format:

[
  {{
    "question": "Question text",
    "options": [
      "Option A",
      "Option B",
      "Option C",
      "Option D"
    ],
    "answer": "Option A",
    "explanation": "Short explanation"
  }}
]

Rules:
- Exactly 4 options per question.
- The answer must exactly match one option.
- Questions must be answerable from the material.
- Do not invent information.
- No markdown.
- No text outside JSON.

STUDY MATERIAL:
{material}
"""

    response = ai_generate(
        prompt,
        system_prompt=(
            "Generate accurate educational MCQs "
            "using only supplied study material."
        )
    )

    parsed = extract_json(response)

    if not isinstance(parsed, list):
        return []

    valid_questions = []

    for item in parsed:

        if not isinstance(item, dict):
            continue

        question = str(
            item.get("question", "")
        ).strip()

        options = item.get(
            "options",
            []
        )

        answer = str(
            item.get("answer", "")
        ).strip()

        explanation = str(
            item.get("explanation", "")
        ).strip()

        if (
            not question
            or not isinstance(options, list)
            or len(options) != 4
            or not answer
        ):
            continue

        options = [
            str(option).strip()
            for option in options
        ]

        if answer not in options:
            continue

        valid_questions.append(
            {
                "question": question,
                "options": options,
                "answer": answer,
                "explanation": explanation,
            }
        )
    for question in valid_questions:
        random.shuffle(question["options"])
    return valid_questions[:number_of_questions]


# ============================================================
# FLASHCARD GENERATOR
# ============================================================

def generate_flashcards(topic=None, number_of_cards=8):

    if not st.session_state.document_loaded:
        return []

    material = st.session_state.cleaned_text[:16000]

    topic_instruction = ""

    if topic:

        topic_instruction = f"""
Focus primarily on this topic:
{topic}
"""

    prompt = f"""
You are an AI flashcard generator.

Create {number_of_cards} useful study flashcards.

{topic_instruction}

Use ONLY the supplied study material.

Return ONLY valid JSON:

[
  {{
    "question": "Question",
    "answer": "Answer"
  }}
]

Rules:
- Questions should test understanding.
- Answers should be concise but useful.
- Do not invent information.
- No markdown.
- No text outside JSON.

STUDY MATERIAL:
{material}
"""

    response = ai_generate(
        prompt,
        system_prompt=(
            "Create accurate educational flashcards "
            "from supplied material."
        )
    )

    parsed = extract_json(response)

    if not isinstance(parsed, list):
        return []

    cards = []

    for item in parsed:

        if not isinstance(item, dict):
            continue

        question = str(
            item.get("question", "")
        ).strip()

        answer = str(
            item.get("answer", "")
        ).strip()

        if question and answer:

            cards.append(
                {
                    "question": question,
                    "answer": answer,
                }
            )

    return cards[:number_of_cards]


# ============================================================
# ADAPTIVE LEARNING
# ============================================================

def generate_adaptive_recommendations():

    accuracy = 0

    if st.session_state.quiz_attempted > 0:

        accuracy = round(
            (
                st.session_state.correct_answers
                / st.session_state.quiz_attempted
            ) * 100
        )

    recommendations = []

    if accuracy < 50:

        recommendations.append(
            "Focus on basic concepts before attempting advanced questions."
        )

        recommendations.append(
            "Review your flashcards and retry the quiz."
        )

    elif accuracy < 75:

        recommendations.append(
            "You have a developing understanding. Practice weak concepts."
        )

        recommendations.append(
            "Use topic-specific quizzes for targeted revision."
        )

    else:

        recommendations.append(
            "Your performance is strong. Try harder questions."
        )

        recommendations.append(
            "Use flashcards for spaced revision."
        )

    if st.session_state.flashcards_reviewed == 0:

        recommendations.append(
            "Start reviewing flashcards to strengthen memory."
        )

    if not recommendations:

        recommendations.append(
            "Upload study material and complete a quiz to receive adaptive recommendations."
        )

    return recommendations

# ============================================================
# AUTHENTICATION
# ============================================================

DB_PATH = "study_champion.db"


def init_auth_database():
    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()


def hash_password(password):
    return hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()


def register_user(username, password):
    username = username.strip()

    if not username or not password:
        return False, "Username and password are required."

    if len(password) < 6:
        return False, "Password must contain at least 6 characters."

    password_hash = hash_password(password)

    try:
        conn = sqlite3.connect(DB_PATH)

        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO users (username, password_hash)
            VALUES (?, ?)
            """,
            (username, password_hash),
        )

        conn.commit()
        conn.close()

        return True, "Account created successfully."

    except sqlite3.IntegrityError:
        return False, "Username already exists."

    except Exception as exc:
        return False, f"Registration failed: {exc}"


def login_user(username, password):
    username = username.strip()

    password_hash = hash_password(password)

    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, username
        FROM users
        WHERE username = ?
        AND password_hash = ?
        """,
        (username, password_hash),
    )

    user = cursor.fetchone()

    conn.close()

    if user:
        return True, user[0], user[1]

    return False, None, None

def record_study_activity():
    user_id = st.session_state.get("user_id")

    if not user_id:
        return

    today = date.today().isoformat()

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR IGNORE INTO study_activity
            (user_id, study_date)
            VALUES (?, ?)
            """,
            (user_id, today),
        )

        conn.commit()

        cursor.execute(
            """
            SELECT study_date
            FROM study_activity
            WHERE user_id = ?
            ORDER BY study_date DESC
            """,
            (user_id,),
        )

        activity_dates = [
            row[0]
            for row in cursor.fetchall()
        ]

        conn.close()

        streak = 0
        expected_date = date.today()

        for activity_date in activity_dates:

            current_date = date.fromisoformat(
                activity_date
            )

            if current_date == expected_date:
                streak += 1
                expected_date -= timedelta(days=1)

            else:
                break

        st.session_state.study_streak = streak

    except Exception:
        pass


def get_study_streak(user_id):
    if not user_id:
        return 0

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT study_date
            FROM study_activity
            WHERE user_id = ?
            ORDER BY study_date DESC
            """,
            (user_id,),
        )

        activity_dates = [
            row[0]
            for row in cursor.fetchall()
        ]

        conn.close()

        streak = 0
        expected_date = date.today()

        for activity_date in activity_dates:

            current_date = date.fromisoformat(
                activity_date
            )

            if current_date == expected_date:
                streak += 1
                expected_date -= timedelta(days=1)

            else:
                break

        return streak

    except Exception:
        return 0
def logout_user():
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.username = ""
    st.session_state.page = "login"

    reset_document_data()

# ============================================================
# SIDEBAR
# ============================================================

def render_sidebar():

    with st.sidebar:

        render_html(
            """
            <div class="sidebar-brand">

                <div class="sidebar-brand-icon">
                    🏆
                </div>

                <div class="sidebar-brand-title">
                    STUDY CHAMPION
                </div>

                <div class="sidebar-brand-subtitle">
                    Your AI Study Companion
                </div>

            </div>
            """
        )

        st.divider()

        # Dashboard
        if st.button(
            "🏠  Dashboard",
            use_container_width=True,
            key="nav_dashboard",
        ):

            st.session_state.page = "home"
            st.rerun()

        # Topics
        if st.button(
            "📚  Topics",
            use_container_width=True,
            key="nav_topics",
        ):

            st.session_state.page = "topics"
            st.rerun()

        if st.button(
          "📝  AI Summary",
          use_container_width=True,
          key="nav_summary",
       ):

         st.session_state.page = "summary"
         st.rerun()

        # Quiz
        if st.button(
            "🧠  Quiz",
            use_container_width=True,
            key="nav_quiz",
        ):

            st.session_state.page = "quiz"
            st.rerun()

        # Flashcards
        if st.button(
            "🃏  Flashcards",
            use_container_width=True,
            key="nav_flashcards",
        ):

            st.session_state.page = "flashcards"
            st.rerun()

        # Planner
        if st.button(
            "📅  Study Planner",
            use_container_width=True,
            key="nav_planner",
        ):

            st.session_state.page = "planner"
            st.rerun()

        # Adaptive
        if st.button(
            "🤖  Adaptive Learning",
            use_container_width=True,
            key="nav_adaptive",
        ):

            st.session_state.page = "adaptive"
            st.rerun()

        # Progress
        if st.button(
            "🎯  Progress",
            use_container_width=True,
            key="nav_progress",
        ):

            st.session_state.page = "progress"
            st.rerun()

        st.divider()

        if st.session_state.document_loaded:

            file_name = st.session_state.file_name

            render_html(
                f"""
                <div style="
                    background:rgba(255,255,255,0.08);
                    border-radius:12px;
                    padding:12px;
                    margin-bottom:12px;
                ">

                    <div style="
                        font-size:11px;
                        color:rgba(255,255,255,0.60);
                    ">
                        CURRENT DOCUMENT
                    </div>

                    <div style="
                        font-size:13px;
                        color:white;
                        font-weight:700;
                        margin-top:5px;
                        word-break:break-word;
                    ">
                        📄 {file_name}
                    </div>

                </div>
                """
            )

        # Reset
        if st.button(
            "🔄  Reset Study Session",
            use_container_width=True,
            key="reset_session",
        ):

            reset_document_data()

            st.session_state.quiz_score = 0
            st.session_state.quiz_attempted = 0
            st.session_state.correct_answers = 0
            st.session_state.wrong_answers = 0
            st.session_state.flashcards_reviewed = 0
            st.session_state.study_minutes = 0
            st.session_state.study_plan = []
            st.session_state.adaptive_recommendations = []

            st.session_state.page = "home"

            st.rerun()
        st.divider()

        render_html(
            f"""
            <div style="
                color:rgba(255,255,255,0.75);
                text-align:center;
                font-size:13px;
                margin-bottom:10px;
            ">
                👤 Logged in as
                <strong>{st.session_state.username}</strong>
            </div>
            """
        )

        if st.button(
            "🚪 Logout",
            use_container_width=True,
            key="logout_button",
        ):

            logout_user()
            st.rerun()

        if st.button(
            "←  Back to Welcome",
            use_container_width=True,
            key="back_welcome",
        ):

            st.session_state.page = "landing"
            st.rerun()

        render_html(
            """
            <div style="
                color:rgba(255,255,255,0.40);
                font-size:11px;
                text-align:center;
                margin-top:20px;
            ">
                Study Champion AI • v3.0
            </div>
            """
        )





# ============================================================
# LOGIN PAGE
# ============================================================

def render_login():

    render_html(
        """
        <div style="
            max-width:650px;
            margin:70px auto 30px auto;
            background:white;
            padding:45px;
            border-radius:25px;
            text-align:center;
            border:1px solid #DCE6F2;
            box-shadow:0 15px 40px rgba(11,31,58,0.12);
        ">

            <div style="font-size:55px;">
                🏆
            </div>

            <h1 style="
                color:#0B1F3A;
                margin-bottom:8px;
            ">
                Study Champion AI
            </h1>

            <p style="
                color:#52647A;
                font-size:16px;
            ">
                Your personal AI-powered study companion
            </p>

        </div>
        """
    )

    login_tab, register_tab = st.tabs(
        ["🔐 Login", "📝 Create Account"]
    )

    with login_tab:

        st.subheader("Welcome Back")

        username = st.text_input(
            "Username",
            key="login_username",
        )

        password = st.text_input(
            "Password",
            type="password",
            key="login_password",
        )

        if st.button(
            "🔐 Login",
            use_container_width=True,
            key="login_button",
        ):

            success, user_id, logged_username = login_user(
                username,
                password,
            )

            if success:

                st.session_state.logged_in = True
                st.session_state.user_id = user_id
                st.session_state.username = logged_username
                st.session_state.page = "landing"
                st.session_state.study_streak = get_study_streak(user_id)

                st.success(
                    f"Welcome back, {logged_username}! 🎉"
                )

                st.rerun()

            else:

                st.error(
                    "Invalid username or password."
                )

    with register_tab:

        st.subheader("Create Your Account")

        new_username = st.text_input(
            "Choose a username",
            key="register_username",
        )

        new_password = st.text_input(
            "Create password",
            type="password",
            key="register_password",
        )

        confirm_password = st.text_input(
            "Confirm password",
            type="password",
            key="register_confirm_password",
        )

        if st.button(
            "📝 Create Account",
            use_container_width=True,
            key="register_button",
        ):

            if new_password != confirm_password:

                st.error(
                    "Passwords do not match."
                )

            else:

                success, message = register_user(
                    new_username,
                    new_password,
                )

                if success:

                    st.success(
                        "Account created successfully! "
                        "You can now login."
                    )

                else:

                    st.error(message)

# ============================================================
# LANDING
# ============================================================

def render_landing():

    set_background(
        Path("assets/background.jpg")
    )

    render_html(
        """
        <div class="landing">

            <div class="badge">
                ✦ AI POWERED LEARNING ✦
            </div>

            <div class="landing-title">
                STUDY CHAMPION 🏆
            </div>

            <div class="landing-subtitle">
                Your personal AI study companion designed
                to transform study material into a smarter,
                simpler and interactive learning experience.
            </div>

            <div class="chips">

                <span class="chip">
                    📚 Smart Learning
                </span>

                <span class="chip">
                    🧠 AI Assistance
                </span>

                <span class="chip">
                    🎯 Progress Tracking
                </span>

                <span class="chip">
                    🃏 Flashcards
                </span>

                <span class="chip">
                    📝 AI Quiz
                </span>

                <span class="chip">
                    📅 Study Planning
                </span>

                <span class="chip">
                    🤖 Adaptive Learning
                </span>

            </div>

        </div>
        """
    )

    st.divider()

    col1, col2, col3 = st.columns(
        [1, 2, 1]
    )

    with col2:

        if st.button(
            "START LEARNING →",
            use_container_width=True,
            key="start_learning",
        ):

            st.session_state.page = "home"
            st.rerun()


# ============================================================
# DASHBOARD
# ============================================================

def render_dashboard():

    render_html(
        """
        <div class="hero">

            <h1>
                STUDY CHAMPION AI
            </h1>

            <p>
                Learn smarter. Stay organized.
                Turn your study material into
                intelligent learning content.
            </p>

        </div>
        """
    )

    st.markdown(
        "### 🚀 Your AI Learning Toolkit"
    )

    col1, col2, col3, col4, col5 = st.columns(5)

    cards = [
        ("📚", "TOPICS", "Organize your study material."),
        ("🧠", "QUIZ", "Test your knowledge with AI."),
        ("🃏", "FLASHCARDS", "Review concepts quickly."),
        ("🤖", "ADAPTIVE", "Get personalized learning."),
    ]

    for column, card in zip(
        [col1, col2, col3, col4, col5],
        cards
    ):

        with column:

            icon, title, description = card

            render_html(
                f"""
                <div class="feature-card">

                    <div class="feature-icon">
                        {icon}
                    </div>

                    <h2>
                        {title}
                    </h2>

                    <p>
                        {description}
                    </p>

                </div>
                """
            )

    render_html(
        """
        <div class="section-title">
            📊 Your Learning Workspace
        </div>
        """
    )

    stat1, stat2, stat3, stat4, stat5 = st.columns(5)

    attempted = st.session_state.quiz_attempted

    accuracy = 0

    if attempted > 0:

        accuracy = round(
            (
                st.session_state.correct_answers
                / attempted
            ) * 100
        )

    stats = [
        (
            len(st.session_state.chunks),
            "Study Chunks"
        ),
        (
            attempted,
            "Questions Attempted"
        ),
        (
            f"{accuracy}%",
            "Quiz Accuracy"
        ),
        (
            st.session_state.flashcards_reviewed,
            "Cards Reviewed"
        ),
        (
          f"🔥 {st.session_state.study_streak}",
           "Study Streak"
      ),
    ]

    for column, stat in zip(
        [stat1, stat2, stat3, stat4 , stat5],
        stats
    ):

        with column:

            number, label = stat

            render_html(
                f"""
                <div class="stat-card">

                    <div class="stat-number">
                        {number}
                    </div>

                    <div class="stat-label">
                        {label}
                    </div>

                </div>
                """
            )

    # ========================================================
    # UPLOAD
    # ========================================================

    render_html(
        """
        <div class="upload-box">

            <h1>
                📚 Upload Your Study Material
            </h1>

            <p>
                Upload a PDF and unlock AI-powered
                learning tools.
            </p>

        </div>
        """
    )

    uploaded_file = st.file_uploader(
        "Upload your study material",
        type=["pdf"],
        help="Upload a PDF study material.",
        key="pdf_uploader",
    )

    if uploaded_file is not None:

        if (
            not st.session_state.document_loaded
            or st.session_state.file_name
            != uploaded_file.name
        ):

            process_pdf(
                uploaded_file
            )

    # ========================================================
    # DOCUMENT INFORMATION
    # ========================================================

    if st.session_state.document_loaded:

        render_html(
            """
            <div class="section-title">
                📄 Document Information
            </div>
            """
        )

        c1, c2, c3 = st.columns(3)

        with c1:

            st.metric(
                "Characters",
                f"{len(st.session_state.cleaned_text):,}"
            )

        with c2:

            st.metric(
                "Chunks",
                len(st.session_state.chunks)
            )

        with c3:

            st.metric(
                "Document",
                st.session_state.file_name
            )

        render_html(
            """
            <div class="section-title">
                📖 Generated Study Content
            </div>
            """
        )

        for i, chunk in enumerate(
            st.session_state.chunks[:10]
        ):

            with st.expander(
                f"Chunk {i + 1}"
            ):

                st.write(chunk)

        if len(st.session_state.chunks) > 10:

            st.info(
                f"{len(st.session_state.chunks) - 10} "
                "additional chunks are available for AI processing."
            )


# ============================================================
# TOPICS
# ============================================================

def render_topics():

    render_html(
        """
        <div class="section-title">
            📚 Study Topics
        </div>
        """
    )

    if not st.session_state.document_loaded:

        st.info(
            "Upload a PDF from Dashboard first."
        )

        return

    st.write(
        f"Current document: **{st.session_state.file_name}**"
    )

    if st.button(
        "✨ Generate AI Topics",
        use_container_width=True,
        key="generate_topics",
    ):

        with st.spinner(
            "AI is analyzing your study material..."
        ):

            topics = generate_topics()

        if topics:

            st.session_state.topics = topics

            st.session_state.topics_generated = True

            st.success(
                f"{len(topics)} topics generated successfully."
            )

        else:

            st.error(
                "Could not generate topics. Please try again."
            )

    if st.session_state.topics:

        render_html(
            """
            <div class="section-title">
                🎯 Detected Topics
            </div>
            """
        )

        for i, topic in enumerate(
            st.session_state.topics
        ):

            col1, col2 = st.columns(
                [4, 1]
            )

            with col1:

                render_html(
                    f"""
                    <div class="info-card">

                        <h3>
                            📘 {topic}
                        </h3>

                        <p>
                            Topic {i + 1} from your
                            uploaded study material.
                        </p>

                    </div>
                    """
                )

            with col2:

                if st.button(
                    "Study",
                    key=f"study_topic_{i}",
                    use_container_width=True,
                ):

                    st.session_state.selected_topic = topic

                    st.session_state.page = "quiz"

                    st.rerun()

    else:

        st.info(
            "Click 'Generate AI Topics' to analyze your PDF."
        )


# ============================================================
# QUIZ
# ============================================================

def render_quiz():

    render_html(
        """
        <div class="section-title">
            🧠 AI Quiz Center
        </div>
        """
    )

    if not st.session_state.document_loaded:

        st.info(
            "Upload a PDF from Dashboard first."
        )

        return

    topics = st.session_state.topics

    topic_options = [
        "All Topics"
    ]

    topic_options.extend(topics)

    selected = st.selectbox(
        "Quiz topic",
        topic_options,
        index=0,
        key="quiz_topic_select",
    )

    selected_topic = (
        None
        if selected == "All Topics"
        else selected
    )

    number_of_questions = st.slider(
        "Number of questions",
        min_value=3,
        max_value=10,
        value=5,
        key="quiz_question_count",
    )

    if st.button(
        "🧠 Generate Quiz",
        use_container_width=True,
        key="generate_quiz",
    ):

        with st.spinner(
            "Generating your AI quiz..."
        ):

            questions = generate_quiz(
                selected_topic,
                number_of_questions
            )

        if questions:

            st.session_state.quiz_questions = questions

            st.session_state.quiz_score = 0

            st.session_state.quiz_submitted = False

            st.session_state.quiz_generated = True

            st.success(
                f"{len(questions)} questions generated."
            )

        else:

            st.error(
                "Quiz generation failed. Please try again."
            )

    questions = st.session_state.quiz_questions

    if not questions:
        return

    render_html(
        """
        <div class="section-title">
            📝 Test Your Knowledge
        </div>
        """
    )

    answers = {}

    for i, question in enumerate(
        questions
    ):

        render_html(
            f"""
            <div class="quiz-card">

                <div class="question-number">
                    QUESTION {i + 1}
                </div>

                <div class="question-text">
                    {question["question"]}
                </div>

            </div>
            """
        )

        answers[i] = st.radio(
            f"Choose your answer for Question {i + 1}",
            question["options"],
            key=f"quiz_answer_{i}",
        )

    if st.button(
        "✅ Submit Quiz",
        use_container_width=True,
        key="submit_quiz",
    ):

        score = 0

        for i, question in enumerate(
            questions
        ):

            if answers.get(i) == question["answer"]:
                score += 1

        total = len(questions)

        st.session_state.quiz_score = score

        st.session_state.quiz_attempted += total

        st.session_state.correct_answers += score

        st.session_state.wrong_answers += (
            total - score
        )

        st.session_state.quiz_submitted = True
        record_study_activity()

        st.success(
            f"Quiz completed! Score: {score}/{total}"
        )

    if st.session_state.quiz_submitted:

        score = st.session_state.quiz_score

        total = len(questions)

        percentage = round(
            (score / total) * 100
        )

        st.progress(
            percentage / 100
        )

        st.write(
            f"### Score: {score}/{total} ({percentage}%)"
        )

        for i, question in enumerate(
            questions
        ):

            with st.expander(
                f"Question {i + 1} Explanation"
            ):

                st.write(
                    f"**Correct answer:** "
                    f"{question['answer']}"
                )

                if question.get(
                    "explanation"
                ):

                    st.write(
                        question["explanation"]
                    )


# ============================================================
# FLASHCARDS
# ============================================================

def render_flashcards():

    render_html(
        """
        <div class="section-title">
            🃏 Flashcard Generator
        </div>
        """
    )

    if not st.session_state.document_loaded:

        st.info(
            "Upload a PDF from Dashboard first."
        )

        return

    topics = st.session_state.topics

    options = [
        "All Topics"
    ]

    options.extend(topics)

    selected = st.selectbox(
        "Flashcard topic",
        options,
        key="flashcard_topic_select",
    )

    selected_topic = (
        None
        if selected == "All Topics"
        else selected
    )

    card_count = st.slider(
        "Number of flashcards",
        min_value=5,
        max_value=15,
        value=8,
        key="flashcard_count",
    )

    if st.button(
        "🃏 Generate Flashcards",
        use_container_width=True,
        key="generate_flashcards",
    ):

        with st.spinner(
            "Creating your flashcards..."
        ):

            cards = generate_flashcards(
                selected_topic,
                card_count
            )

        if cards:

            st.session_state.flashcards = cards

            st.session_state.flashcards_generated = True

            st.success(
                f"{len(cards)} flashcards generated."
            )

        else:

            st.error(
                "Flashcard generation failed. Please try again."
            )

    cards = st.session_state.flashcards

    if not cards:
        return

    render_html(
        """
        <div class="section-title">
            📖 Review Your Flashcards
        </div>
        """
    )

    for i, card in enumerate(
        cards
    ):

        with st.container():

            render_html(
                f"""
                <div class="flashcard">

                    <div class="flashcard-label">
                        Flashcard {i + 1}
                    </div>

                    <div class="flashcard-question">
                        {card["question"]}
                    </div>

                </div>
                """
            )

            if st.toggle(
                "Show Answer",
                key=f"show_card_{i}",
            ):

                render_html(
                    f"""
                    <div class="answer-box">

                        <strong>
                            Answer:
                        </strong>

                        <br><br>

                        {card["answer"]}

                    </div>
                    """
                )

                if st.button(
                    "✓ Mark Reviewed",
                    key=f"review_card_{i}",
                ):

                    review_key = (
                        f"reviewed_{i}"
                    )

                    if not st.session_state.get(
                        review_key,
                        False
                    ):

                        st.session_state[
                            "flashcards_reviewed"
                        ] += 1
                        record_study_activity()

                        st.session_state[
                            review_key
                        ] = True

                        st.success(
                            "Flashcard marked as reviewed."
                        )


# ============================================================
# STUDY PLANNER
# ============================================================

def render_planner():

    render_html(
        """
        <div class="section-title">
            📅 Personalized Study Planner
        </div>
        """
    )

    st.write(
        "Create a practical study schedule based on your available time."
    )

    col1, col2 = st.columns(2)

    with col1:

        days = st.number_input(
            "Days available",
            min_value=1,
            max_value=30,
            value=7,
            step=1,
            key="planner_days",
        )

    with col2:

        hours = st.number_input(
            "Study hours per day",
            min_value=0.5,
            max_value=12.0,
            value=2.0,
            step=0.5,
            key="planner_hours",
        )

    focus = st.text_input(
        "Main study goal",
        value="Complete my study material",
        key="planner_goal",
    )

    if st.button(
        "📅 Create Study Plan",
        use_container_width=True,
        key="create_plan",
    ):

        plan = []

        total_chunks = len(
            st.session_state.chunks
        )

        for day in range(
            1,
            int(days) + 1
        ):

            if total_chunks > 0:

                start = int(
                    (day - 1)
                    * total_chunks
                    / days
                )

                end = int(
                    day
                    * total_chunks
                    / days
                )

                chunk_text_label = (
                    f"Chunks {start + 1}-{max(start + 1, end)}"
                )

            else:

                chunk_text_label = (
                    "General revision"
                )

            plan.append(
                {
                    "day": day,
                    "hours": hours,
                    "goal": focus,
                    "material": chunk_text_label,
                }
            )

        st.session_state.study_plan = plan

        st.session_state.planner_created = True

        st.success(
            "Study plan created successfully!"
        )

    if st.session_state.study_plan:

        render_html(
            """
            <div class="section-title">
                🗓️ Your Study Schedule
            </div>
            """
        )

        for item in (
            st.session_state.study_plan
        ):

            render_html(
                f"""
                <div class="plan-day">

                    <h3>
                        Day {item["day"]}
                    </h3>

                    <p>
                        ⏱️ {item["hours"]} hours
                    </p>

                    <p>
                        🎯 {item["goal"]}
                    </p>

                    <p>
                        📚 {item["material"]}
                    </p>

                </div>
                """
            )

        total_hours = sum(
            float(item["hours"])
            for item in st.session_state.study_plan
        )

        st.metric(
            "Total Planned Study Time",
            f"{total_hours:g} hours"
        )

        if st.button(
            "✅ Mark 30 Minutes Studied",
            use_container_width=True,
            key="mark_study_time",
        ):

            st.session_state.study_minutes += 30
            record_study_activity()

            st.success(
                "30 minutes added to your progress."
            )


# ============================================================
# ADAPTIVE LEARNING
# ============================================================

def render_adaptive():

    render_html(
        """
        <div class="section-title">
            🤖 Adaptive Learning
        </div>
        """
    )

    attempted = (
        st.session_state.quiz_attempted
    )

    correct = (
        st.session_state.correct_answers
    )

    if attempted > 0:

        accuracy = round(
            (correct / attempted) * 100
        )

    else:

        accuracy = 0

    render_html(
        f"""
        <div class="info-card">

            <h3>
                🧠 Your Current Learning Level
            </h3>

            <p>
                Quiz Accuracy:
                <strong>{accuracy}%</strong>
            </p>

            <p>
                Questions Attempted:
                <strong>{attempted}</strong>
            </p>

            <p>
                Flashcards Reviewed:
                <strong>
                    {st.session_state.flashcards_reviewed}
                </strong>
            </p>

        </div>
        """
    )

    if st.button(
        "🤖 Analyze My Learning",
        use_container_width=True,
        key="analyze_learning",
    ):

        recommendations = (
            generate_adaptive_recommendations()
        )

        st.session_state.adaptive_recommendations = (
            recommendations
        )

    if st.session_state.adaptive_recommendations:

        render_html(
            """
            <div class="section-title">
                🎯 Personalized Recommendations
            </div>
            """
        )

        for recommendation in (
            st.session_state.adaptive_recommendations
        ):

            st.success(
                recommendation
            )

    else:

        st.info(
            "Complete a quiz or review flashcards, "
            "then click Analyze My Learning."
        )

def render_summary():

    render_html(
        """
        <div class="section-title">
            📝 AI Study Summary
        </div>
        """
    )

    if not st.session_state.document_loaded:

        st.info(
            "Upload a PDF from Dashboard first."
        )

        return

    st.write(
        f"Current document: "
        f"**{st.session_state.file_name}**"
    )

    if st.button(
        "✨ Generate AI Summary",
        use_container_width=True,
        key="generate_ai_summary",
    ):

        with st.spinner(
            "AI is creating your study summary..."
        ):

            summary = generate_ai_summary()

        if summary:

            st.session_state.ai_summary = summary

            record_study_activity()

            st.success(
                "AI summary generated successfully! 🎉"
            )

        else:

            st.error(
                "Could not generate the summary. "
                "Please try again."
            )

    if st.session_state.ai_summary:

        render_html(
            """
            <div class="section-title">
                📖 Your AI Summary
            </div>
            """
        )

        st.markdown(
            st.session_state.ai_summary
        )

        st.divider()

        st.subheader(
            "📥 Download Summary Notes"
        )

        st.download_button(
            label="📄 Download as TXT",
            data=st.session_state.ai_summary,
            file_name="study_champion_summary.txt",
            mime="text/plain",
            use_container_width=True,
            key="download_summary_txt",
        )

        st.download_button(
            label="📝 Download as Markdown",
            data=st.session_state.ai_summary,
            file_name="study_champion_summary.md",
            mime="text/markdown",
            use_container_width=True,
            key="download_summary_md",
        )
# ============================================================
# PROGRESS
# ============================================================

def render_progress():

    render_html(
        """
        <div class="section-title">
            🎯 Progress Dashboard
        </div>
        """
    )

    attempted = (
        st.session_state.quiz_attempted
    )

    correct = (
        st.session_state.correct_answers
    )

    wrong = (
        st.session_state.wrong_answers
    )

    if attempted > 0:

        accuracy = round(
            (correct / attempted) * 100
        )

    else:

        accuracy = 0

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Questions Attempted",
            attempted
        )

    with col2:

        st.metric(
            "Correct",
            correct
        )

    with col3:

        st.metric(
            "Wrong",
            wrong
        )

    with col4:

        st.metric(
            "Accuracy",
            f"{accuracy}%"
        )

    render_html(
        """
        <div class="section-title">
            📈 Learning Activity
        </div>
        """
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            "Flashcards Reviewed",
            st.session_state.flashcards_reviewed
        )

    with c2:

        st.metric(
            "Study Time",
            f"{st.session_state.study_minutes} min"
        )

    with c3:

        st.metric(
            "Topics",
            len(st.session_state.topics)
        )

    if attempted > 0:

        st.progress(
            accuracy / 100
        )

        st.write(
            f"### Overall Quiz Accuracy: {accuracy}%"
        )

        if accuracy >= 80:

            st.success(
                "Excellent performance! Keep going. 🏆"
            )

        elif accuracy >= 60:

            st.info(
                "Good progress. Keep practicing. 💪"
            )

        else:

            st.warning(
                "Review your material and try another quiz. 📚"
            )

    else:

        st.info(
            "Complete a quiz to start tracking your performance."
        )

    render_html(
        """
        <div class="section-title">
            📊 Study Summary
        </div>
        """
    )

    st.write(
        f"**Current document:** "
        f"{st.session_state.file_name or 'No document uploaded'}"
    )

    st.write(
        f"**Study chunks:** "
        f"{len(st.session_state.chunks)}"
    )

    st.write(
        f"**Generated topics:** "
        f"{len(st.session_state.topics)}"
    )

    st.write(
        f"**Generated flashcards:** "
        f"{len(st.session_state.flashcards)}"
    )


# ============================================================
# AI STUDY CHAT
# ============================================================

def render_ai_chat():

    render_html(
        """
        <div class="section-title">
            💬 AI Study Chat
        </div>
        """
    )

    if not st.session_state.document_loaded:

        st.info(
            "Upload a PDF first to start asking questions."
        )

        return

    for message in (
        st.session_state.messages
    ):

        role = message.get(
            "role",
            "assistant"
        )

        content = message.get(
            "content",
            ""
        )

        with st.chat_message(role):

            st.write(content)

    question = st.chat_input(
        "Ask something from your document..."
    )

    if question:

        st.session_state.messages.append(
            {
                "role": "user",
                "content": question,
            }
        )

        with st.chat_message("user"):

            st.write(question)

        with st.chat_message("assistant"):

            with st.spinner(
                "AI is thinking..."
            ):

                try:

                    answer = answer_question(
                        st.session_state.chunks,
                        question,
                    )

                except Exception as exc:

                    answer = (
                        "I could not generate an answer "
                        "right now.\n\n"
                        f"Error: {exc}"
                    )

                st.write(answer)

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": answer,
            }
        )




common_css()

# ============================================================
# APPLICATION ROUTING
# ============================================================

if not st.session_state.logged_in:

    st.session_state.page = "login"

    render_login()

else:

    if st.session_state.page == "login":

        st.session_state.page = "landing"
        st.rerun()

    elif st.session_state.page == "landing":

        render_landing()

    else:

        render_sidebar()

        if st.session_state.page == "home":

            render_dashboard()

            st.divider()

            render_ai_chat()

        elif st.session_state.page == "topics":

            render_topics()

        elif st.session_state.page == "summary":

         render_summary()
         
        elif st.session_state.page == "quiz":

            render_quiz()

        elif st.session_state.page == "flashcards":

            render_flashcards()

        elif st.session_state.page == "planner":

            render_planner()

        elif st.session_state.page == "adaptive":

            render_adaptive()

        elif st.session_state.page == "progress":

            render_progress()

        else:

            st.session_state.page = "home"
            st.rerun()