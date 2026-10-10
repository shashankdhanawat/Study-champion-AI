import json
import math
import re
import textwrap
import base64
import random
import sqlite3
import hashlib
import html as html_lib
from pathlib import Path
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
# DESIGN TOKENS
# ------------------------------------------------------------
# Highlighter-and-notebook look:
#   ink indigo  -> structure
#   blue        -> actions
#   highlighter -> "you are here" / "this matters"
# ============================================================

PALETTES = {
    "light": {
        "ink": "#0F2A3F",        # dark surfaces: sidebar, banners
        "blue": "#0B6E99",       # buttons and fills
        "blue_text": "#0B6E99",  # accent text
        "blue_soft": "#E3F1F8",
        "hl": "#FFC93C",         # highlighter
        "on_hl": "#0F2A3F",      # text on the highlighter
        "paper": "#F5F8FA",
        "card": "#FFFFFF",
        "line": "#DCE6EC",
        "text": "#12222F",
        "heading": "#0F2A3F",
        "muted": "#526979",
        "good": "#13855E",
        "good_soft": "#E1F5EC",
        "bad": "#D6384A",
        "bad_soft": "#FDE9EC",
        "edge": "#0F2A3F",       # hard "pressed" shadows
        "landing": "#0F2A3F",
    },
    "dark": {
        "ink": "#13354F",
        "blue": "#0F7DAE",
        "blue_text": "#7CCBF0",
        "blue_soft": "#17394F",
        "hl": "#FFC93C",
        "on_hl": "#0F2A3F",
        "paper": "#0B1722",
        "card": "#102536",
        "line": "#24455C",
        "text": "#E3ECF2",
        "heading": "#F1F6F9",
        "muted": "#9DB3C2",
        "good": "#34B27F",
        "good_soft": "#103426",
        "bad": "#F26B78",
        "bad_soft": "#3A1C25",
        "edge": "#050D14",
        "landing": "#07111A",
    },
}

DB_PATH = "study_champion.db"


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
    "quiz_id": 0,
    "flashcard_id": 0,
    "fc_index": 0,
    "fc_show": False,
    "dark_mode": False,
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# SMALL HELPERS
# ============================================================

def esc(value):
    """Escape any text (user or AI generated) before placing it in HTML."""
    return html_lib.escape(str(value))


def render_html(html):
    """Render custom HTML through one place (dedented, trimmed)."""
    cleaned_html = textwrap.dedent(html).strip()

    try:
        st.html(cleaned_html)
    except AttributeError:
        st.markdown(cleaned_html, unsafe_allow_html=True)


def go(page, **state):
    """Navigate to a page, optionally setting session values first."""
    for key, value in state.items():
        st.session_state[key] = value
    st.session_state.page = page
    st.rerun()


def page_header(icon, title, subtitle=""):
    sub = f'<p class="page-sub">{esc(subtitle)}</p>' if subtitle else ""
    render_html(
        f"""
        <div class="page-head">
            <div class="page-head-icon">{icon}</div>
            <div>
                <h1 class="page-title">{esc(title)}</h1>
                {sub}
            </div>
        </div>
        """
    )


def section_title(text):
    render_html(f'<h2 class="section-title">{text}</h2>')


def need_document():
    """Shared empty state for pages that need a PDF."""
    render_html(
        """
        <div class="empty">
            <div class="empty-icon">📄</div>
            <h3>No study material yet</h3>
            <p>Upload a PDF on the Dashboard and this page will
            fill up with content from it.</p>
        </div>
        """
    )
    if st.button(
        "Go to Dashboard",
        key=f"empty_go_{st.session_state.page}",
        type="primary",
    ):
        go("home")


def accuracy_percent():
    attempted = st.session_state.quiz_attempted
    if attempted <= 0:
        return 0
    return round((st.session_state.correct_answers / attempted) * 100)


def ring_svg(percent, size=150):
    """Circular progress ring as inline SVG (colours follow the theme)."""
    radius = 52
    circumference = 2 * math.pi * radius
    dash = circumference * max(0, min(percent, 100)) / 100

    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 120 120"
         role="img" aria-label="{percent} percent">
        <circle cx="60" cy="60" r="{radius}" fill="none"
                style="stroke: var(--line)" stroke-width="12"/>
        <circle cx="60" cy="60" r="{radius}" fill="none"
                style="stroke: var(--blue-text)" stroke-width="12"
                stroke-linecap="round"
                stroke-dasharray="{dash:.1f} {circumference:.1f}"
                transform="rotate(-90 60 60)"/>
        <text x="60" y="68" text-anchor="middle"
              font-family="Bricolage Grotesque, sans-serif"
              font-weight="800" font-size="28"
              style="fill: var(--heading)">{percent}%</text>
    </svg>
    """


def learning_level():
    """Return (label, one-line description) from quiz accuracy."""
    if st.session_state.quiz_attempted == 0:
        return "Not started", "Take a quiz to find out where you stand."

    accuracy = accuracy_percent()

    if accuracy >= 75:
        return "Strong", "You know this material well. Try harder questions."
    if accuracy >= 50:
        return "Developing", "You're getting there. Keep practicing weak spots."
    return "Building basics", "Start with the fundamentals, then retry the quiz."


# ============================================================
# DATABASE / AUTH
# ============================================================

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


def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def register_user(username, password):
    username = username.strip()

    if not username or not password:
        return False, "Username and password are required."

    if len(password) < 6:
        return False, "Password must contain at least 6 characters."

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, hash_password(password)),
        )
        conn.commit()
        conn.close()
        return True, "Account created successfully."

    except sqlite3.IntegrityError:
        return False, "That username is already taken."

    except Exception as exc:
        return False, f"Registration failed: {exc}"


def login_user(username, password):
    username = username.strip()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, username
        FROM users
        WHERE username = ? AND password_hash = ?
        """,
        (username, hash_password(password)),
    )
    user = cursor.fetchone()
    conn.close()

    if user:
        return True, user[0], user[1]

    return False, None, None


def _activity_dates(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT study_date FROM study_activity
        WHERE user_id = ? ORDER BY study_date DESC
        """,
        (user_id,),
    )
    dates = [row[0] for row in cursor.fetchall()]
    conn.close()
    return dates


def _calculate_streak(user_id):
    streak = 0
    expected_date = date.today()

    for activity_date in _activity_dates(user_id):
        if date.fromisoformat(activity_date) == expected_date:
            streak += 1
            expected_date -= timedelta(days=1)
        else:
            break

    return streak


def record_study_activity():
    user_id = st.session_state.get("user_id")
    if not user_id:
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO study_activity (user_id, study_date)
            VALUES (?, ?)
            """,
            (user_id, date.today().isoformat()),
        )
        conn.commit()
        conn.close()

        st.session_state.study_streak = _calculate_streak(user_id)

    except Exception:
        pass


def get_study_streak(user_id):
    if not user_id:
        return 0
    try:
        return _calculate_streak(user_id)
    except Exception:
        return 0


def get_week_activity(user_id):
    """Return a set of ISO dates studied in the last 7 days."""
    if not user_id:
        return set()
    try:
        cutoff = (date.today() - timedelta(days=6)).isoformat()
        return {d for d in _activity_dates(user_id) if d >= cutoff}
    except Exception:
        return set()


def logout_user():
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.username = ""
    st.session_state.page = "login"
    reset_document_data()


# ============================================================
# GLOBAL CSS
# ============================================================

DARK_EXTRA_CSS = """
    /* ---------- Dark mode: native Streamlit widgets ---------- */
    [data-testid="stApp"] { color: var(--text); }

    [data-testid="stHeader"] button,
    [data-testid="stHeader"] svg { color: var(--text) !important; }

    [data-baseweb="input"], [data-baseweb="base-input"],
    [data-baseweb="select"] > div, [data-baseweb="textarea"] {
        background: var(--card) !important;
        border-color: var(--line) !important;
    }
    input, textarea {
        background: var(--card) !important;
        color: var(--text) !important;
        -webkit-text-fill-color: var(--text) !important;
    }
    [data-baseweb="select"] * { color: var(--text) !important; }
    [data-baseweb="select"] svg { fill: var(--muted) !important; }

    [data-baseweb="popover"] > div,
    [data-baseweb="menu"],
    ul[role="listbox"] {
        background: var(--card) !important;
        color: var(--text) !important;
    }
    li[role="option"] { color: var(--text) !important; }
    li[role="option"]:hover { background: var(--blue-soft) !important; }

    [data-testid="stAlert"] {
        background: var(--card) !important;
        border: 1.5px solid var(--line);
        border-radius: 12px;
    }
    [data-testid="stAlert"] * { color: var(--text) !important; }

    [data-testid="stMetricLabel"] * { color: var(--muted) !important; }

    [data-testid="stExpander"] details,
    [data-testid="stExpander"] summary { background: var(--card); }
    [data-testid="stExpander"] summary * { color: var(--text) !important; }

    [data-testid="stVerticalBlockBorderWrapper"] { border-color: var(--line); }

    [data-testid="stFileUploaderDropzone"] { background: var(--card); }
    [data-testid="stFileUploaderDropzone"] *,
    [data-testid="stFileUploaderFile"] * { color: var(--text); }

    [data-testid="stTabs"] [role="tab"] { color: var(--muted); }
    [data-testid="stTabs"] [role="tab"][aria-selected="true"] { color: var(--blue-text); }

    [data-testid="stBottom"],
    [data-testid="stBottomBlockContainer"] { background: var(--paper) !important; }
    [data-testid="stChatInput"] { background: var(--card) !important; }

    [data-testid="stCaptionContainer"] * { color: var(--muted) !important; }
    [data-testid="stMainBlockContainer"] hr { border-color: var(--line); }
    code { background: var(--blue-soft) !important; color: var(--text) !important; }
"""


def _sync_theme():
    st.session_state.dark_mode = st.session_state.dark_toggle


def render_theme_toggle():
    """Light / dark switch. Rendered once per page."""
    st.toggle(
        "🌙 Dark mode",
        value=st.session_state.dark_mode,
        key="dark_toggle",
        on_change=_sync_theme,
    )


def common_css():
    dark = bool(st.session_state.get("dark_mode", False))
    palette = PALETTES["dark" if dark else "light"]

    variables = "\n".join(
        f"        --{name.replace('_', '-')}: {value};"
        for name, value in palette.items()
    )

    tokens = f"""
    :root {{
{variables}
        color-scheme: {"dark" if dark else "light"};
    }}
    """

    css = """
    @import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700;12..96,800&family=Figtree:wght@400;500;600;700&display=swap');

    /* ---------- Base ---------- */
    html, body, [data-testid="stApp"], .stApp {
        font-family: 'Figtree', system-ui, sans-serif;
    }

    /* flat paper background */
    [data-testid="stAppViewContainer"] {
        background: var(--paper);
    }

    [data-testid="stHeader"] { background: transparent; }

    [data-testid="stMainBlockContainer"] {
        max-width: 1180px;
        padding-top: 28px;
        padding-bottom: 80px;
    }

    [data-testid="stMainBlockContainer"] p,
    [data-testid="stMainBlockContainer"] li,
    [data-testid="stMainBlockContainer"] label,
    [data-testid="stMainBlockContainer"] span {
        color: var(--text);
    }

    [data-testid="stMainBlockContainer"] h1,
    [data-testid="stMainBlockContainer"] h2,
    [data-testid="stMainBlockContainer"] h3 {
        font-family: 'Bricolage Grotesque', 'Figtree', sans-serif;
        color: var(--heading);
        letter-spacing: -0.02em;
    }

    /* ---------- Sidebar ---------- */
    [data-testid="stSidebar"] {
        background: var(--ink);
        border-right: none;
    }

    [data-testid="stSidebar"] * { color: #E8F0F5; }

    [data-testid="stSidebar"] hr {
        border-color: rgba(255,255,255,0.12);
        margin: 14px 0;
    }

    [data-testid="stSidebar"] div.stButton { margin-bottom: 2px; }

    [data-testid="stSidebar"] div.stButton > button {
        width: 100%;
        min-height: 44px;
        justify-content: flex-start;
        padding: 0 14px;
        border-radius: 10px;
        background: transparent;
        border: 1px solid transparent;
        font-weight: 600;
        font-size: 15px;
        box-shadow: none;
        transform: none;
    }

    [data-testid="stSidebar"] div.stButton > button:hover {
        background: rgba(255,255,255,0.09);
        border-color: transparent;
        color: #fff;
    }

    /* active page = highlighter swipe */
    [data-testid="stSidebar"] button[kind="primary"],
    [data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {
        background: var(--hl) !important;
        border-color: var(--hl) !important;
        box-shadow: none !important;
    }
    [data-testid="stSidebar"] button[kind="primary"] *,
    [data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] * {
        color: var(--on-hl) !important;
        font-weight: 700;
    }

    .brand { display: flex; align-items: center; gap: 12px; padding: 6px 4px 4px 4px; }
    .brand-mark {
        width: 44px; height: 44px; border-radius: 12px;
        background: var(--hl);
        display: grid; place-items: center; font-size: 24px;
    }
    .brand-name {
        font-family: 'Bricolage Grotesque', sans-serif;
        font-weight: 800; font-size: 19px; line-height: 1.1; color: #fff;
    }
    .brand-tag { font-size: 12.5px; color: #9DB6C7; }

    .doc-chip {
        background: rgba(255,255,255,0.08);
        border-radius: 10px; padding: 11px 13px; margin: 4px 0 12px 0;
    }
    .doc-chip small { color: #9DB6C7; font-size: 12px; }
    .doc-chip div { color: #fff; font-weight: 600; font-size: 14px; word-break: break-word; margin-top: 2px; }

    .user-line { text-align: center; font-size: 13.5px; color: #C3D4E0; margin: 4px 0 10px 0; }
    .user-line strong { color: #fff; }
    .version { text-align: center; font-size: 12px; color: #7F99AB; margin-top: 16px; }

    /* ---------- Buttons ---------- */
    div.stButton > button,
    div.stDownloadButton > button {
        border-radius: 10px;
        min-height: 46px;
        font-weight: 700;
        background: var(--card);
        color: var(--heading);
        border: 1.5px solid var(--line);
        transition: background .15s ease, border-color .15s ease, transform .08s ease;
    }
    div.stButton > button:hover,
    div.stDownloadButton > button:hover {
        border-color: var(--blue);
        color: var(--blue-text);
        background: var(--blue-soft);
    }
    div.stButton > button:focus-visible,
    div.stDownloadButton > button:focus-visible {
        outline: 3px solid var(--hl);
        outline-offset: 2px;
    }
    div.stButton > button:disabled { opacity: .45; }

    /* primary = blue with a hard ink underline, like a pressed key */
    [data-testid="stMainBlockContainer"] button[kind="primary"],
    [data-testid="stMainBlockContainer"] button[data-testid="stBaseButton-primary"] {
        background: var(--blue);
        border-color: var(--edge);
        box-shadow: 0 3px 0 var(--edge);
    }
    [data-testid="stMainBlockContainer"] button[kind="primary"] *,
    [data-testid="stMainBlockContainer"] button[data-testid="stBaseButton-primary"] * {
        color: #fff !important;
    }
    [data-testid="stMainBlockContainer"] button[kind="primary"]:hover,
    [data-testid="stMainBlockContainer"] button[data-testid="stBaseButton-primary"]:hover {
        background: var(--ink);
    }
    [data-testid="stMainBlockContainer"] button[kind="primary"]:active,
    [data-testid="stMainBlockContainer"] button[data-testid="stBaseButton-primary"]:active {
        transform: translateY(2px);
        box-shadow: 0 1px 0 var(--edge);
    }

    /* ---------- Inputs ---------- */
    [data-baseweb="input"], [data-baseweb="select"] > div, textarea {
        border-radius: 10px !important;
    }
    [data-testid="stFileUploaderDropzone"] {
        background: var(--card);
        border: 2px dashed var(--blue);
        border-radius: 0 0 14px 14px;
    }

    /* ---------- Page header ---------- */
    .page-head {
        display: flex; align-items: center; gap: 16px;
        margin-bottom: 26px; padding-bottom: 18px;
        border-bottom: 2px solid var(--heading);
    }
    .page-head-icon {
        width: 54px; height: 54px; border-radius: 14px;
        background: var(--hl);
        display: grid; place-items: center; font-size: 28px; flex: none;
        box-shadow: 3px 3px 0 var(--edge);
    }
    .page-title {
        font-family: 'Bricolage Grotesque', sans-serif;
        font-size: 34px; font-weight: 800; color: var(--heading);
        margin: 0; line-height: 1.1; letter-spacing: -0.02em;
    }
    .page-sub { margin: 4px 0 0 0; color: var(--muted); font-size: 16px; }

    .section-title {
        font-family: 'Bricolage Grotesque', sans-serif;
        font-size: 22px; font-weight: 700; color: var(--heading);
        margin: 34px 0 14px 0; letter-spacing: -0.01em;
    }

    /* ---------- Dashboard banner ---------- */
    .banner {
        background: var(--ink);
        border-radius: 18px; padding: 34px 38px;
        display: flex; justify-content: space-between;
        align-items: center; gap: 24px; flex-wrap: wrap;
        box-shadow: 6px 6px 0 var(--hl);
    }
    .banner h1 {
        font-family: 'Bricolage Grotesque', sans-serif;
        color: #fff !important; font-size: 36px; font-weight: 800;
        margin: 0 0 8px 0; letter-spacing: -0.02em;
    }
    .banner p { color: #C3D4E0 !important; margin: 0; font-size: 16.5px; max-width: 560px; line-height: 1.55; }
    .streak {
        background: var(--hl); border-radius: 14px; padding: 14px 22px;
        text-align: center; min-width: 130px;
    }
    .streak b {
        display: block; font-family: 'Bricolage Grotesque', sans-serif;
        font-size: 34px; line-height: 1; color: var(--on-hl);
    }
    .streak span { font-size: 13.5px; font-weight: 600; color: var(--on-hl) !important; }

    /* ---------- Stats strip ---------- */
    .strip {
        display: grid; grid-template-columns: repeat(5, 1fr);
        background: var(--card); border: 1.5px solid var(--line);
        border-radius: 14px; margin-top: 28px; overflow: hidden;
    }
    .strip-item { padding: 20px 22px; border-right: 1.5px solid var(--line); }
    .strip-item:last-child { border-right: none; }
    .strip-num {
        font-family: 'Bricolage Grotesque', sans-serif;
        font-size: 32px; font-weight: 800; color: var(--heading); line-height: 1.05;
    }
    .strip-label { font-size: 14px; color: var(--muted); margin-top: 4px; }
    @media (max-width: 800px) {
        .strip { grid-template-columns: repeat(2, 1fr); }
        .strip-item { border-bottom: 1.5px solid var(--line); }
    }

    /* ---------- Guided path ---------- */
    .steps { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }
    .step {
        background: var(--card); border: 1.5px solid var(--line);
        border-radius: 12px; padding: 16px;
    }
    .step-dot {
        width: 30px; height: 30px; border-radius: 50%;
        background: var(--blue-soft); color: var(--blue-text) !important;
        font-weight: 800; display: grid; place-items: center; margin-bottom: 10px;
    }
    .step-name { font-weight: 700; color: var(--heading); font-size: 15px; line-height: 1.3; }
    .step-state { font-size: 13px; color: var(--muted) !important; margin-top: 3px; }
    .step.done { background: var(--good-soft); border-color: var(--good); }
    .step.done .step-dot { background: var(--good); color: #fff !important; }
    .step.next { border: 2px solid var(--heading); box-shadow: 4px 4px 0 var(--hl); }
    .step.next .step-dot { background: var(--blue); color: #fff !important; }
    @media (max-width: 900px) { .steps { grid-template-columns: repeat(2, 1fr); } }

    /* ---------- Toolkit ---------- */
    .tool {
        background: var(--card); border: 1.5px solid var(--line);
        border-radius: 14px; padding: 20px; min-height: 150px;
    }
    .tool-icon {
        width: 42px; height: 42px; border-radius: 10px; background: var(--blue-soft);
        display: grid; place-items: center; font-size: 22px;
    }
    .tool h3 { font-size: 18px; margin: 14px 0 4px 0; }
    .tool p { color: var(--muted) !important; margin: 0; font-size: 14.5px; line-height: 1.5; }

    /* ---------- Upload ---------- */
    .upload-intro {
        background: var(--blue); border-radius: 14px 14px 0 0;
        padding: 24px 28px; margin-top: 34px;
    }
    .upload-intro h2 {
        color: #fff !important; margin: 0 0 4px 0; font-size: 24px;
        font-family: 'Bricolage Grotesque', sans-serif;
    }
    .upload-intro p { color: #D7ECF6 !important; margin: 0; }

    /* ---------- Document card ---------- */
    .doc-card {
        background: var(--card); border: 1.5px solid var(--line);
        border-left: 6px solid var(--hl); border-radius: 12px;
        padding: 18px 22px; display: flex; gap: 30px; flex-wrap: wrap; align-items: center;
    }
    .doc-card .doc-name { font-weight: 700; font-size: 17px; color: var(--heading); word-break: break-word; flex: 1 1 260px; }
    .doc-card .doc-stat b { font-family: 'Bricolage Grotesque', sans-serif; font-size: 24px; color: var(--heading); display: block; line-height: 1.1; }
    .doc-card .doc-stat span { font-size: 13.5px; color: var(--muted) !important; }

    /* ---------- Landing ---------- */
    .landing-grid {
        max-width: 1080px; margin: 0 auto; padding: 56px 10px 10px 10px;
        display: grid; grid-template-columns: 1.15fr 1fr; gap: 40px; align-items: center;
    }
    @media (max-width: 900px) { .landing-grid { grid-template-columns: 1fr; } .mock { display: none; } }
    .landing-pill {
        display: inline-block; background: var(--hl); color: var(--on-hl);
        font-weight: 700; font-size: 14.5px; padding: 8px 16px; border-radius: 999px;
    }
    .landing-title {
        font-family: 'Bricolage Grotesque', sans-serif;
        font-size: clamp(46px, 7vw, 82px); font-weight: 800; color: #fff;
        line-height: 0.98; letter-spacing: -0.035em; margin: 24px 0 20px 0;
    }
    .landing-sub { color: #CEDDE7; font-size: 19px; line-height: 1.6; max-width: 560px; }
    .landing-list { margin: 30px 0 6px 0; display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px 24px; max-width: 520px; }
    .landing-list div { color: #fff; font-size: 16.5px; font-weight: 500; }
    .landing-list span { color: var(--hl); margin-right: 8px; }

    .mock { position: relative; min-height: 420px; }
    .mock-q {
        position: absolute; top: 10px; left: 0; right: 30px;
        background: #fff; border-radius: 16px; padding: 24px;
        box-shadow: 8px 8px 0 rgba(255,225,77,.9); transform: rotate(-2deg);
    }
    .mock-q small { color: var(--blue); font-weight: 700; }
    .mock-q b { display: block; color: var(--ink); font-size: 18px; margin: 6px 0 14px 0; line-height: 1.4; font-family: 'Bricolage Grotesque', sans-serif; }
    .mock-opt { border: 1.5px solid var(--line); border-radius: 8px; padding: 9px 12px; margin-top: 8px; font-size: 15px; color: var(--text); }
    .mock-opt.on { border-color: var(--good); background: var(--good-soft); font-weight: 700; }
    .mock-card {
        position: absolute; bottom: 0; right: 0; width: 76%;
        background: var(--blue); border-radius: 16px; padding: 22px 24px;
        transform: rotate(3deg); box-shadow: 6px 6px 0 rgba(0,0,0,.25);
    }
    .mock-card small { color: #D0E8F4; font-weight: 600; }
    .mock-card b { display: block; color: #fff; font-size: 18px; margin-top: 6px; line-height: 1.4; font-family: 'Bricolage Grotesque', sans-serif; }

    /* ---------- Login ---------- */
    .login-brand {
        background: var(--ink); border-radius: 20px; padding: 44px 40px;
        min-height: 540px; display: flex; flex-direction: column; justify-content: space-between;
        box-shadow: 6px 6px 0 var(--hl);
    }
    .login-brand .mark {
        width: 58px; height: 58px; border-radius: 16px; background: var(--hl);
        display: grid; place-items: center; font-size: 30px;
    }
    .login-brand h1 {
        font-family: 'Bricolage Grotesque', sans-serif;
        color: #fff !important; font-size: 44px; line-height: 1.04;
        letter-spacing: -0.03em; margin: 26px 0 14px 0;
    }
    .login-brand p { color: #C3D4E0 !important; font-size: 17px; line-height: 1.6; margin: 0; }
    .login-brand ul { list-style: none; padding: 0; margin: 28px 0 0 0; }
    .login-brand li { color: #fff !important; padding: 7px 0; font-size: 16px; }
    .login-brand li span { color: var(--hl) !important; margin-right: 10px; }

    /* ---------- Topics ---------- */
    .topic-card {
        background: var(--card); border: 1.5px solid var(--line);
        border-radius: 12px; padding: 16px 20px;
        display: flex; align-items: center; gap: 16px; min-height: 60px;
    }
    .topic-num {
        width: 34px; height: 34px; border-radius: 8px;
        background: var(--blue-soft); color: var(--blue-text) !important;
        font-weight: 800; display: grid; place-items: center; flex: none;
    }
    .topic-name { font-weight: 700; font-size: 17px; color: var(--heading); }

    /* ---------- Quiz ---------- */
    .q-card {
        background: var(--card); border: 1.5px solid var(--line);
        border-radius: 12px; padding: 20px 24px 14px 24px; margin: 20px 0 6px 0;
    }
    .q-index { color: var(--blue-text) !important; font-weight: 700; font-size: 14px; }
    .q-text { color: var(--heading); font-size: 19px; font-weight: 700; margin-top: 4px; line-height: 1.45; }

    .score-card {
        background: var(--ink); border-radius: 16px; padding: 28px 32px;
        display: flex; align-items: center; gap: 26px; flex-wrap: wrap;
        margin: 26px 0 10px 0; box-shadow: 6px 6px 0 var(--hl);
    }
    .score-big { font-family: 'Bricolage Grotesque', sans-serif; font-size: 60px; font-weight: 800; color: var(--hl); line-height: 1; }
    .score-card p { color: #fff !important; margin: 0; font-size: 18px; font-weight: 600; }
    .score-card small { color: #BCD0DD; font-size: 14.5px; }

    .review { border-radius: 10px; padding: 14px 18px; margin: 8px 0; border-left: 5px solid; }
    .review.good { background: var(--good-soft); border-color: var(--good); }
    .review.bad { background: var(--bad-soft); border-color: var(--bad); }
    .review b, .review div { color: var(--text) !important; }
    .review .why { color: var(--muted) !important; margin-top: 6px; font-size: 14.5px; }

    /* ---------- Flashcards ---------- */
    .flash {
        background: var(--blue); border-radius: 18px;
        padding: 40px 42px; min-height: 230px; margin: 18px 0 10px 0;
        display: flex; flex-direction: column; justify-content: center;
        box-shadow: 8px 8px 0 var(--edge);
    }
    .flash small { color: #D0E8F4 !important; font-weight: 600; font-size: 14px; }
    .flash .flash-text { color: #fff !important; font-size: 28px; font-weight: 700; margin-top: 10px; line-height: 1.35; font-family: 'Bricolage Grotesque', sans-serif; }
    .flash.back { background: var(--hl); }
    .flash.back small { color: var(--on-hl) !important; }
    .flash.back .flash-text { color: var(--on-hl) !important; font-size: 22px; font-family: 'Figtree', sans-serif; font-weight: 600; }
    .flash-q { margin-top: 14px; font-size: 14.5px; color: var(--on-hl) !important; opacity: .7; }

    /* ---------- Planner ---------- */
    .plan-day {
        display: flex; gap: 18px; align-items: stretch;
        background: var(--card); border: 1.5px solid var(--line);
        border-radius: 12px; margin-bottom: 10px; overflow: hidden;
    }
    .plan-badge {
        background: var(--hl); color: var(--on-hl) !important;
        padding: 14px 20px; min-width: 92px; text-align: center;
        display: flex; flex-direction: column; justify-content: center;
    }
    .plan-badge small { color: var(--on-hl) !important; font-weight: 600; }
    .plan-badge b { font-family: 'Bricolage Grotesque', sans-serif; font-size: 30px; line-height: 1; color: var(--on-hl) !important; }
    .plan-body { padding: 14px 18px 14px 0; flex: 1; }
    .plan-body .goal { font-weight: 700; font-size: 17px; color: var(--heading); }
    .plan-body .meta { color: var(--muted) !important; font-size: 14.5px; margin-top: 4px; }

    /* ---------- Progress / adaptive ---------- */
    .panel {
        background: var(--card); border: 1.5px solid var(--line);
        border-radius: 16px; padding: 26px; height: 100%;
    }
    .panel h3 { margin: 0 0 14px 0; font-size: 18px; }
    .ring-wrap { display: flex; align-items: center; gap: 22px; flex-wrap: wrap; }
    .level {
        display: inline-block; background: var(--hl); color: var(--on-hl) !important;
        font-weight: 800; padding: 5px 12px; border-radius: 999px; font-size: 14px;
    }
    .level-text { color: var(--muted) !important; margin: 10px 0 0 0; max-width: 240px; line-height: 1.5; }

    .bar-row { display: grid; grid-template-columns: 76px 1fr 36px; gap: 12px; align-items: center; margin: 12px 0; }
    .bar-row span { color: var(--muted) !important; font-size: 14.5px; }
    .bar-row b { color: var(--heading); text-align: right; }
    .bar { height: 14px; background: var(--blue-soft); border-radius: 999px; overflow: hidden; }
    .bar i { display: block; height: 100%; border-radius: 999px; }

    .week { display: flex; gap: 10px; flex-wrap: wrap; }
    .day { text-align: center; }
    .day .dot {
        width: 40px; height: 40px; border-radius: 50%;
        border: 2px solid var(--line); display: grid; place-items: center;
        font-size: 16px; color: var(--muted);
    }
    .day.on .dot { background: var(--hl); border-color: var(--on-hl); color: var(--on-hl); }
    .day.today .dot { border-color: var(--blue); }
    .day small { color: var(--muted) !important; font-size: 12.5px; display: block; margin-top: 4px; }

    .insight {
        background: var(--card); border: 1.5px solid var(--line);
        border-left: 6px solid var(--blue); border-radius: 10px;
        padding: 16px 20px; margin: 10px 0; font-size: 16.5px;
        color: var(--text) !important; font-weight: 500;
    }

    .empty {
        background: var(--card); border: 2px dashed var(--line);
        border-radius: 16px; padding: 44px 24px; text-align: center; margin: 10px 0 14px 0;
    }
    .empty-icon { font-size: 40px; }
    .empty h3 { margin: 10px 0 6px 0; }
    .empty p { color: var(--muted) !important; max-width: 420px; margin: 0 auto; }

    /* ---------- Streamlit widgets ---------- */
    [data-testid="stMetric"] {
        background: var(--card); border: 1.5px solid var(--line);
        border-radius: 12px; padding: 16px 18px;
    }
    [data-testid="stMetricValue"] { font-family: 'Bricolage Grotesque', sans-serif; font-weight: 800; color: var(--heading); }
    [data-testid="stExpander"] { background: var(--card); border: 1.5px solid var(--line) !important; border-radius: 12px; }
    [data-testid="stProgress"] > div > div > div > div { background-color: var(--blue); }
    [data-testid="stTabs"] [role="tab"] { font-weight: 700; font-size: 16px; }
    [data-baseweb="tab-highlight"] { background-color: var(--blue) !important; }
    [data-testid="stProgress"] > div > div { background-color: var(--blue-soft); }
    [data-testid="stChatMessage"] { background: var(--card); border: 1.5px solid var(--line); border-radius: 12px; }

    @media (prefers-reduced-motion: reduce) {
        * { transition: none !important; }
    }
    """

    extra = DARK_EXTRA_CSS if dark else ""
    render_html(f"<style>{tokens}{css}{extra}</style>")


def landing_background(image_path=None):
    """Flat dark landing backdrop (no gradients)."""
    render_html(
        """
        <style>
            [data-testid="stAppViewContainer"] { background: var(--landing); }
            [data-testid="stMainBlockContainer"] label,
            [data-testid="stMainBlockContainer"] label * { color: #FFFFFF !important; }
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
    st.session_state.ai_summary = ""

    st.session_state.selected_topic = None

    st.session_state.quiz_generated = False
    st.session_state.quiz_submitted = False
    st.session_state.flashcards_generated = False
    st.session_state.topics_generated = False

    st.session_state.fc_index = 0
    st.session_state.fc_show = False

    st.session_state.quiz_id += 1
    st.session_state.flashcard_id += 1


# ============================================================
# PDF PROCESSING
# ============================================================

def process_pdf(uploaded_file):
    if uploaded_file is None:
        return False

    temp_path = Path(f"temp_{uploaded_file.name}")

    try:
        with open(temp_path, "wb") as file:
            file.write(uploaded_file.getbuffer())

        with st.spinner("Reading your PDF..."):
            raw_text = read_pdf(str(temp_path))

            if not raw_text or not raw_text.strip():
                st.error(
                    "We couldn't read any text from this PDF. "
                    "If it's a scan, try a version with selectable text."
                )
                return False

            cleaned = clean_text(raw_text)

            if not cleaned or not cleaned.strip():
                st.error("This PDF doesn't contain usable study text.")
                return False

            chunks = chunk_text(cleaned)
            chunks = [
                str(chunk).strip()
                for chunk in chunks
                if chunk and str(chunk).strip()
            ]

            if not chunks:
                st.error("No study sections could be created from this PDF.")
                return False

        reset_document_data()

        st.session_state.cleaned_text = cleaned
        st.session_state.chunks = chunks
        st.session_state.file_name = uploaded_file.name
        st.session_state.document_loaded = True
        record_study_activity()

        st.success(f"Loaded {uploaded_file.name}")
        return True

    except Exception as exc:
        st.error(f"Couldn't process this PDF: {exc}")
        return False

    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass


# ============================================================
# AI HELPERS
# ============================================================

def ai_generate(prompt, system_prompt=None):
    try:
        result = ask_llm(prompt, system_prompt=system_prompt)

        if not result:
            print("AI GENERATION ERROR: Empty response from ask_llm()")
            return ""

        result = str(result).strip()

        if result.startswith("AI service is temporarily unavailable"):
            print(f"AI GENERATION ERROR: {result}")
            return ""

        return result

    except Exception as e:
        print(f"AI GENERATION ERROR: {type(e).__name__}: {e}")
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
        ),
    )

    return response.strip() if response else ""


def extract_json(text):
    if not text:
        return None

    cleaned = text.strip()
    cleaned = re.sub(r"```json", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"```", "", cleaned).strip()

    try:
        return json.loads(cleaned)
    except Exception:
        pass

    object_match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if object_match:
        try:
            return json.loads(object_match.group(0))
        except Exception:
            pass

    array_match = re.search(r"\[.*\]", cleaned, flags=re.DOTALL)
    if array_match:
        try:
            return json.loads(array_match.group(0))
        except Exception:
            pass

    return None


def detect_topics_locally():
    text = st.session_state.cleaned_text
    topics = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        cleaned = re.sub(r"^[#\d\.\-\)\s]+", "", line).strip()

        if 3 <= len(cleaned) <= 90 and len(cleaned.split()) <= 12:
            if cleaned not in topics:
                topics.append(cleaned)

    if not topics:
        topics = ["General Study Material"]

    return topics[:10]


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
        ),
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

    return detect_topics_locally()


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
        ),
    )

    parsed = extract_json(response)

    if not isinstance(parsed, list):
        return []

    valid_questions = []

    for item in parsed:
        if not isinstance(item, dict):
            continue

        question = str(item.get("question", "")).strip()
        options = item.get("options", [])
        answer = str(item.get("answer", "")).strip()
        explanation = str(item.get("explanation", "")).strip()

        if (
            not question
            or not isinstance(options, list)
            or len(options) != 4
            or not answer
        ):
            continue

        options = [str(option).strip() for option in options]

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
        ),
    )

    parsed = extract_json(response)

    if not isinstance(parsed, list):
        return []

    cards = []

    for item in parsed:
        if not isinstance(item, dict):
            continue

        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()

        if question and answer:
            cards.append({"question": question, "answer": answer})

    return cards[:number_of_cards]


def generate_adaptive_recommendations():
    accuracy = accuracy_percent()
    recommendations = []

    if accuracy < 50:
        recommendations.append(
            "Focus on basic concepts before attempting advanced questions."
        )
        recommendations.append("Review your flashcards and retry the quiz.")

    elif accuracy < 75:
        recommendations.append(
            "You have a developing understanding. Practice weak concepts."
        )
        recommendations.append(
            "Use topic-specific quizzes for targeted revision."
        )

    else:
        recommendations.append("Your performance is strong. Try harder questions.")
        recommendations.append("Use flashcards for spaced revision.")

    if st.session_state.flashcards_reviewed == 0:
        recommendations.append("Start reviewing flashcards to strengthen memory.")

    return recommendations


# ============================================================
# SIDEBAR
# ============================================================

NAV_ITEMS = [
    ("home", "🏠", "Dashboard"),
    ("topics", "📚", "Topics"),
    ("summary", "📝", "AI Summary"),
    ("quiz", "🧠", "Quiz"),
    ("flashcards", "🃏", "Flashcards"),
    ("planner", "📅", "Study Planner"),
    ("adaptive", "🤖", "Adaptive Learning"),
    ("progress", "🎯", "Progress"),
]


def render_sidebar():
    with st.sidebar:
        render_html(
            """
            <div class="brand">
                <div class="brand-mark">🏆</div>
                <div>
                    <div class="brand-name">Study Champion</div>
                    <div class="brand-tag">Your AI study companion</div>
                </div>
            </div>
            """
        )

        st.divider()

        for page_key, icon, label in NAV_ITEMS:
            is_active = st.session_state.page == page_key

            if st.button(
                f"{icon}  {label}",
                use_container_width=True,
                key=f"nav_{page_key}",
                type="primary" if is_active else "secondary",
            ):
                go(page_key)

        st.divider()

        render_theme_toggle()

        if st.session_state.document_loaded:
            render_html(
                f"""
                <div class="doc-chip">
                    <small>Current document</small>
                    <div>📄 {esc(st.session_state.file_name)}</div>
                </div>
                """
            )

        if st.button(
            "🔄  Reset study session",
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

            go("home")

        st.divider()

        render_html(
            f"""
            <div class="user-line">
                Signed in as <strong>{esc(st.session_state.username)}</strong>
            </div>
            """
        )

        if st.button("🚪  Log out", use_container_width=True, key="logout_button"):
            logout_user()
            st.rerun()

        if st.button(
            "←  Back to welcome",
            use_container_width=True,
            key="back_welcome",
        ):
            go("landing")

        render_html('<div class="version">Study Champion AI · v5.0</div>')


# ============================================================
# LOGIN PAGE
# ============================================================

def render_login():
    _, toggle_col = st.columns([5, 1])
    with toggle_col:
        render_theme_toggle()

    left, right = st.columns([1, 1], gap="large")

    with left:
        render_html(
            """
            <div class="login-brand">
                <div>
                    <div class="mark">🏆</div>
                    <h1>Turn any PDF into a study plan that sticks.</h1>
                    <p>Upload your notes or textbook. Study Champion builds
                    the summary, quizzes and flashcards for you.</p>
                </div>
                <ul>
                    <li><span>✓</span>Summaries written from your own material</li>
                    <li><span>✓</span>Quizzes that track what you get wrong</li>
                    <li><span>✓</span>Daily streaks to keep you going</li>
                </ul>
            </div>
            """
        )

    with right:
        login_tab, register_tab = st.tabs(["Log in", "Create account"])

        with login_tab:
            st.subheader("Welcome back")

            username = st.text_input("Username", key="login_username")
            password = st.text_input(
                "Password", type="password", key="login_password"
            )

            if st.button(
                "Log in",
                use_container_width=True,
                key="login_button",
                type="primary",
            ):
                success, user_id, logged_username = login_user(username, password)

                if success:
                    st.session_state.logged_in = True
                    st.session_state.user_id = user_id
                    st.session_state.username = logged_username
                    st.session_state.page = "landing"
                    st.session_state.study_streak = get_study_streak(user_id)
                    st.rerun()
                else:
                    st.error("Wrong username or password. Check both and try again.")

        with register_tab:
            st.subheader("Create your account")

            new_username = st.text_input("Choose a username", key="register_username")
            new_password = st.text_input(
                "Create a password (6+ characters)",
                type="password",
                key="register_password",
            )
            confirm_password = st.text_input(
                "Confirm password",
                type="password",
                key="register_confirm_password",
            )

            if st.button(
                "Create account",
                use_container_width=True,
                key="register_button",
                type="primary",
            ):
                if new_password != confirm_password:
                    st.error("The two passwords don't match.")
                else:
                    success, message = register_user(new_username, new_password)

                    if success:
                        st.success("Account created. You can log in now.")
                    else:
                        st.error(message)


# ============================================================
# LANDING
# ============================================================

def render_landing():
    landing_background()

    _, toggle_col = st.columns([5, 1])
    with toggle_col:
        render_theme_toggle()

    render_html(
        """
        <div class="landing-grid">
            <div>
                <span class="landing-pill">AI-powered learning</span>

                <div class="landing-title">Study Champion 🏆</div>

                <div class="landing-sub">
                    Your personal study companion. Drop in a PDF and get
                    summaries, quizzes, flashcards and a plan to finish it.
                </div>

                <div class="landing-list">
                    <div><span>●</span>Smart topics</div>
                    <div><span>●</span>AI summaries</div>
                    <div><span>●</span>Quizzes with feedback</div>
                    <div><span>●</span>Flashcards</div>
                    <div><span>●</span>Study planner</div>
                    <div><span>●</span>Adaptive learning</div>
                </div>
            </div>

            <div class="mock" aria-hidden="true">
                <div class="mock-q">
                    <small>Question 1 of 5</small>
                    <b>Which organelle produces most of the cell's ATP?</b>
                    <div class="mock-opt">Ribosome</div>
                    <div class="mock-opt on">✓ Mitochondria</div>
                    <div class="mock-opt">Golgi apparatus</div>
                </div>
                <div class="mock-card">
                    <small>Flashcard 3 of 8</small>
                    <b>What does chlorophyll do?</b>
                </div>
            </div>
        </div>
        """
    )

    _, middle, _ = st.columns([1, 2, 1])

    with middle:
        if st.button(
            "Start learning →",
            use_container_width=True,
            key="start_learning",
            type="primary",
        ):
            go("home")


# ============================================================
# DASHBOARD
# ============================================================

def render_guided_path():
    """Five-step path that shows what to do next."""
    state = st.session_state

    steps = [
        ("Upload a PDF", state.document_loaded, "home", "Add your material"),
        ("Find topics", bool(state.topics), "topics", "Spot the key ideas"),
        ("Read the summary", bool(state.ai_summary), "summary", "Get exam notes"),
        ("Take a quiz", state.quiz_attempted > 0, "quiz", "Test yourself"),
        ("Review flashcards", state.flashcards_reviewed > 0, "flashcards", "Lock it in"),
    ]

    next_index = next((i for i, step in enumerate(steps) if not step[1]), None)

    cells = []
    for i, (name, done, _, hint) in enumerate(steps):
        if done:
            css, dot, label = "done", "✓", "Done"
        elif i == next_index:
            css, dot, label = "next", str(i + 1), "Up next"
        else:
            css, dot, label = "", str(i + 1), hint

        cells.append(
            f"""
            <div class="step {css}">
                <div class="step-dot">{dot}</div>
                <div class="step-name">{esc(name)}</div>
                <div class="step-state">{esc(label)}</div>
            </div>
            """
        )

    section_title("Your study path")
    render_html(f'<div class="steps">{"".join(cells)}</div>')

    if next_index is None:
        st.success("You've completed every step. Keep your streak alive tomorrow! 🔥")

    elif next_index > 0:
        name, _, page, _ = steps[next_index]

        st.write("")
        if st.button(
            f"Continue: {name} →",
            key="continue_path",
            type="primary",
        ):
            go(page)


def render_dashboard():
    render_html(
        f"""
        <div class="banner">
            <div>
                <h1>Hi {esc(st.session_state.username)}, ready to study?</h1>
                <p>Upload your material, follow the path below, and test
                yourself until it sticks.</p>
            </div>
            <div class="streak">
                <b>🔥 {st.session_state.study_streak}</b>
                <span>day streak</span>
            </div>
        </div>
        """
    )

    render_html(
        f"""
        <div class="strip">
            <div class="strip-item">
                <div class="strip-num">{len(st.session_state.chunks)}</div>
                <div class="strip-label">Study chunks</div>
            </div>
            <div class="strip-item">
                <div class="strip-num">{st.session_state.quiz_attempted}</div>
                <div class="strip-label">Questions attempted</div>
            </div>
            <div class="strip-item">
                <div class="strip-num">{accuracy_percent()}%</div>
                <div class="strip-label">Quiz accuracy</div>
            </div>
            <div class="strip-item">
                <div class="strip-num">{st.session_state.flashcards_reviewed}</div>
                <div class="strip-label">Cards reviewed</div>
            </div>
            <div class="strip-item">
                <div class="strip-num">{st.session_state.study_streak}</div>
                <div class="strip-label">Day streak</div>
            </div>
        </div>
        """
    )

    render_guided_path()

    # ---------------- Upload ----------------
    render_html(
        """
        <div class="upload-intro">
            <h2>Upload your study material</h2>
            <p>Add a PDF to unlock topics, summaries, quizzes and flashcards.</p>
        </div>
        """
    )

    uploaded_file = st.file_uploader(
        "Upload your study material",
        type=["pdf"],
        help="Upload a PDF study material.",
        key="pdf_uploader",
        label_visibility="collapsed",
    )

    if uploaded_file is not None:
        if (
            not st.session_state.document_loaded
            or st.session_state.file_name != uploaded_file.name
        ):
            if process_pdf(uploaded_file):
                st.rerun()

    # ---------------- Document info ----------------
    if st.session_state.document_loaded:
        section_title("📄 Your document")

        render_html(
            f"""
            <div class="doc-card">
                <div class="doc-name">{esc(st.session_state.file_name)}</div>
                <div class="doc-stat">
                    <b>{len(st.session_state.cleaned_text):,}</b>
                    <span>characters</span>
                </div>
                <div class="doc-stat">
                    <b>{len(st.session_state.chunks)}</b>
                    <span>chunks</span>
                </div>
            </div>
            """
        )

        with st.expander("Browse study chunks"):
            for i, chunk in enumerate(st.session_state.chunks[:10]):
                st.markdown(f"**Chunk {i + 1}**")
                st.write(chunk)
                st.divider()

            if len(st.session_state.chunks) > 10:
                st.info(
                    f"{len(st.session_state.chunks) - 10} more chunks are "
                    "available to the AI but not shown here."
                )

    # ---------------- Toolkit ----------------
    section_title("Your toolkit")

    tools = [
        ("📚", "Topics", "Find the main ideas in your material.", "topics"),
        ("📝", "AI Summary", "Get exam-ready notes you can download.", "summary"),
        ("🧠", "Quiz", "Test yourself on any topic.", "quiz"),
        ("🃏", "Flashcards", "Review key concepts quickly.", "flashcards"),
    ]

    for column, (icon, title, description, page) in zip(st.columns(4), tools):
        with column:
            render_html(
                f"""
                <div class="tool">
                    <div class="tool-icon">{icon}</div>
                    <h3>{title}</h3>
                    <p>{description}</p>
                </div>
                """
            )
            if st.button(
                f"Open {title}",
                key=f"tool_{page}",
                use_container_width=True,
            ):
                go(page)


# ============================================================
# TOPICS
# ============================================================

def render_topics():
    page_header("📚", "Study topics", "The main ideas found in your material.")

    if not st.session_state.document_loaded:
        need_document()
        return

    st.write(f"Current document: **{st.session_state.file_name}**")

    if st.button(
        "✨ Find topics with AI",
        use_container_width=True,
        key="generate_topics",
        type="primary",
    ):
        with st.spinner("Reading through your material..."):
            topics = generate_topics()

        if topics:
            st.session_state.topics = topics
            st.session_state.topics_generated = True
            st.success(f"Found {len(topics)} topics.")
        else:
            st.error("We couldn't find topics this time. Please try again.")

    if st.session_state.topics:
        section_title("Detected topics")

        for i, topic in enumerate(st.session_state.topics):
            col1, col2, col3 = st.columns([5, 1.2, 1.4], vertical_alignment="center")

            with col1:
                render_html(
                    f"""
                    <div class="topic-card">
                        <div class="topic-num">{i + 1}</div>
                        <div class="topic-name">{esc(topic)}</div>
                    </div>
                    """
                )

            with col2:
                if st.button("Quiz me", key=f"quiz_topic_{i}", use_container_width=True):
                    go("quiz", quiz_topic_select=topic, selected_topic=topic)

            with col3:
                if st.button("Flashcards", key=f"cards_topic_{i}", use_container_width=True):
                    go("flashcards", flashcard_topic_select=topic, selected_topic=topic)
    else:
        st.info("Select “Find topics with AI” to analyze your PDF.")


# ============================================================
# SUMMARY
# ============================================================

def render_summary():
    page_header("📝", "AI summary", "Exam-ready notes written from your material.")

    if not st.session_state.document_loaded:
        need_document()
        return

    st.write(f"Current document: **{st.session_state.file_name}**")

    if st.button(
        "✨ Write my summary",
        use_container_width=True,
        key="generate_ai_summary",
        type="primary",
    ):
        with st.spinner("Writing your study summary..."):
            summary = generate_ai_summary()

        if summary:
            st.session_state.ai_summary = summary
            record_study_activity()
            st.success("Your summary is ready.")
        else:
            st.error("We couldn't write the summary this time. Please try again.")

    if st.session_state.ai_summary:
        section_title("Your summary")

        with st.container(border=True):
            st.markdown(st.session_state.ai_summary)

        section_title("Download your notes")

        d1, d2 = st.columns(2)

        with d1:
            st.download_button(
                label="📄 Download as TXT",
                data=st.session_state.ai_summary,
                file_name="study_champion_summary.txt",
                mime="text/plain",
                use_container_width=True,
                key="download_summary_txt",
            )

        with d2:
            st.download_button(
                label="📝 Download as Markdown",
                data=st.session_state.ai_summary,
                file_name="study_champion_summary.md",
                mime="text/markdown",
                use_container_width=True,
                key="download_summary_md",
            )


# ============================================================
# QUIZ
# ============================================================

def render_quiz():
    page_header("🧠", "Quiz", "Test what you know, then see where to improve.")

    if not st.session_state.document_loaded:
        need_document()
        return

    topic_options = ["All Topics"] + list(st.session_state.topics)

    # keep a stale selection (e.g. after a reset) from breaking the selectbox
    if st.session_state.get("quiz_topic_select") not in topic_options:
        st.session_state["quiz_topic_select"] = "All Topics"

    col1, col2 = st.columns([3, 2])

    with col1:
        selected = st.selectbox("Quiz topic", topic_options, key="quiz_topic_select")

    with col2:
        number_of_questions = st.slider(
            "Number of questions",
            min_value=3,
            max_value=10,
            value=5,
            key="quiz_question_count",
        )

    selected_topic = None if selected == "All Topics" else selected

    if st.button(
        "🧠 Generate quiz",
        use_container_width=True,
        key="generate_quiz",
        type="primary",
    ):
        with st.spinner("Writing your questions..."):
            questions = generate_quiz(selected_topic, number_of_questions)

        if questions:
            st.session_state.quiz_questions = questions
            st.session_state.quiz_score = 0
            st.session_state.quiz_submitted = False
            st.session_state.quiz_generated = True
            st.session_state.quiz_id += 1
            st.rerun()
        else:
            st.error("Quiz generation failed. Please try again.")

    questions = st.session_state.quiz_questions

    if not questions:
        return

    quiz_id = st.session_state.quiz_id
    submitted = st.session_state.quiz_submitted
    total = len(questions)

    answered = sum(
        1
        for i in range(total)
        if st.session_state.get(f"quiz_answer_{quiz_id}_{i}") is not None
    )

    # ---------------- Results ----------------
    if submitted:
        score = st.session_state.quiz_score
        percentage = round((score / total) * 100)

        if percentage >= 80:
            verdict = "Excellent work. You know this material."
        elif percentage >= 60:
            verdict = "Good progress. A bit more practice will lock it in."
        else:
            verdict = "Review the material below and try another quiz."

        render_html(
            f"""
            <div class="score-card">
                <div class="score-big">{score}/{total}</div>
                <div>
                    <p>{percentage}% correct</p>
                    <small>{verdict}</small>
                </div>
            </div>
            """
        )

        section_title("Review your answers")

        for i, question in enumerate(questions):
            given = st.session_state.get(f"quiz_answer_{quiz_id}_{i}")
            is_right = given == question["answer"]
            css_class = "good" if is_right else "bad"
            mark = "✓ Correct" if is_right else "✗ Not quite"

            explanation = (
                f'<div class="why">{esc(question["explanation"])}</div>'
                if question.get("explanation")
                else ""
            )
            your_answer = "" if is_right else f"<div>Your answer: {esc(given)}</div>"

            render_html(
                f"""
                <div class="review {css_class}">
                    <b>{i + 1}. {mark}</b>
                    <div>{esc(question["question"])}</div>
                    {your_answer}
                    <div>Correct answer: <b>{esc(question["answer"])}</b></div>
                    {explanation}
                </div>
                """
            )

        st.write("")
        if st.button("Try another quiz", key="another_quiz", type="primary"):
            st.session_state.quiz_questions = []
            st.session_state.quiz_submitted = False
            st.rerun()

        return

    # ---------------- Taking the quiz ----------------
    section_title("Answer the questions")
    st.progress(answered / total, text=f"{answered} of {total} answered")

    for i, question in enumerate(questions):
        render_html(
            f"""
            <div class="q-card">
                <div class="q-index">Question {i + 1} of {total}</div>
                <div class="q-text">{esc(question["question"])}</div>
            </div>
            """
        )

        st.radio(
            f"Answer for question {i + 1}",
            question["options"],
            index=None,
            key=f"quiz_answer_{quiz_id}_{i}",
            label_visibility="collapsed",
        )

    st.write("")

    if st.button(
        "✅ Submit quiz",
        use_container_width=True,
        key="submit_quiz",
        type="primary",
    ):
        answers = [
            st.session_state.get(f"quiz_answer_{quiz_id}_{i}")
            for i in range(total)
        ]

        if any(answer is None for answer in answers):
            st.warning("Answer every question before submitting.")
        else:
            score = sum(
                1
                for answer, question in zip(answers, questions)
                if answer == question["answer"]
            )

            st.session_state.quiz_score = score
            st.session_state.quiz_attempted += total
            st.session_state.correct_answers += score
            st.session_state.wrong_answers += total - score
            st.session_state.quiz_submitted = True
            record_study_activity()
            st.rerun()


# ============================================================
# FLASHCARDS (one card at a time)
# ============================================================

def render_flashcards():
    page_header("🃏", "Flashcards", "Flip through key ideas and mark what you've learned.")

    if not st.session_state.document_loaded:
        need_document()
        return

    options = ["All Topics"] + list(st.session_state.topics)

    if st.session_state.get("flashcard_topic_select") not in options:
        st.session_state["flashcard_topic_select"] = "All Topics"

    col1, col2 = st.columns([3, 2])

    with col1:
        selected = st.selectbox("Flashcard topic", options, key="flashcard_topic_select")

    with col2:
        card_count = st.slider(
            "Number of flashcards",
            min_value=5,
            max_value=15,
            value=8,
            key="flashcard_count",
        )

    selected_topic = None if selected == "All Topics" else selected

    if st.button(
        "🃏 Generate flashcards",
        use_container_width=True,
        key="generate_flashcards",
        type="primary",
    ):
        with st.spinner("Creating your flashcards..."):
            cards = generate_flashcards(selected_topic, card_count)

        if cards:
            st.session_state.flashcards = cards
            st.session_state.flashcards_generated = True
            st.session_state.flashcard_id += 1
            st.session_state.fc_index = 0
            st.session_state.fc_show = False
            st.rerun()
        else:
            st.error("Flashcard generation failed. Please try again.")

    cards = st.session_state.flashcards

    if not cards:
        return

    card_set = st.session_state.flashcard_id
    total = len(cards)
    index = max(0, min(st.session_state.fc_index, total - 1))
    st.session_state.fc_index = index
    card = cards[index]
    showing_answer = st.session_state.fc_show

    reviewed_count = sum(
        1 for i in range(total) if st.session_state.get(f"reviewed_{card_set}_{i}", False)
    )

    section_title(f"Card {index + 1} of {total}")
    st.progress(reviewed_count / total, text=f"{reviewed_count} of {total} reviewed")

    if showing_answer:
        render_html(
            f"""
            <div class="flash back">
                <small>Answer</small>
                <div class="flash-text">{esc(card["answer"])}</div>
                <div class="flash-q">Q: {esc(card["question"])}</div>
            </div>
            """
        )
    else:
        render_html(
            f"""
            <div class="flash">
                <small>Question</small>
                <div class="flash-text">{esc(card["question"])}</div>
            </div>
            """
        )

    prev_col, flip_col, next_col = st.columns([1, 2, 1])

    with prev_col:
        if st.button(
            "← Previous",
            key="fc_prev",
            use_container_width=True,
            disabled=index == 0,
        ):
            st.session_state.fc_index = index - 1
            st.session_state.fc_show = False
            st.rerun()

    with flip_col:
        if st.button(
            "Hide answer" if showing_answer else "Show answer",
            key="fc_flip",
            use_container_width=True,
            type="primary",
        ):
            st.session_state.fc_show = not showing_answer
            st.rerun()

    with next_col:
        if st.button(
            "Next →",
            key="fc_next",
            use_container_width=True,
            disabled=index == total - 1,
        ):
            st.session_state.fc_index = index + 1
            st.session_state.fc_show = False
            st.rerun()

    review_key = f"reviewed_{card_set}_{index}"

    if st.session_state.get(review_key, False):
        st.success("You've reviewed this card ✓")

    elif showing_answer:
        if st.button("✓ Mark as reviewed", key=f"review_card_{card_set}_{index}"):
            st.session_state["flashcards_reviewed"] += 1
            st.session_state[review_key] = True
            record_study_activity()
            st.rerun()

    else:
        st.caption("Think of your answer first, then reveal it.")


# ============================================================
# STUDY PLANNER
# ============================================================

def render_planner():
    page_header("📅", "Study planner", "Spread your material across the days you have.")

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
        "📅 Create study plan",
        use_container_width=True,
        key="create_plan",
        type="primary",
    ):
        plan = []
        total_chunks = len(st.session_state.chunks)

        for day in range(1, int(days) + 1):
            if total_chunks > 0:
                start = int((day - 1) * total_chunks / days)
                end = int(day * total_chunks / days)
                material_label = f"Chunks {start + 1}–{max(start + 1, end)}"
            else:
                material_label = "General revision"

            plan.append(
                {
                    "day": day,
                    "hours": hours,
                    "goal": focus,
                    "material": material_label,
                }
            )

        st.session_state.study_plan = plan
        st.session_state.planner_created = True
        st.success("Your study plan is ready.")

    if st.session_state.study_plan:
        section_title("Your schedule")

        for item in st.session_state.study_plan:
            render_html(
                f"""
                <div class="plan-day">
                    <div class="plan-badge">
                        <small>Day</small>
                        <b>{item["day"]}</b>
                    </div>
                    <div class="plan-body">
                        <div class="goal">{esc(item["goal"])}</div>
                        <div class="meta">
                            ⏱️ {item["hours"]:g} hours · 📚 {esc(item["material"])}
                        </div>
                    </div>
                </div>
                """
            )

        total_hours = sum(float(item["hours"]) for item in st.session_state.study_plan)

        m1, m2 = st.columns(2)

        with m1:
            st.metric("Total planned study time", f"{total_hours:g} hours")

        with m2:
            st.metric("Logged so far", f"{st.session_state.study_minutes} min")

        if st.button(
            "✅ Log 30 minutes studied",
            use_container_width=True,
            key="mark_study_time",
        ):
            st.session_state.study_minutes += 30
            record_study_activity()
            st.success("Added 30 minutes to your progress.")
            st.rerun()


# ============================================================
# ADAPTIVE LEARNING
# ============================================================

def render_adaptive():
    page_header("🤖", "Adaptive learning", "Advice based on how you're actually doing.")

    level, level_text = learning_level()

    left, right = st.columns([1, 1.4], gap="large")

    with left:
        render_html(
            f"""
            <div class="panel">
                <h3>Your current level</h3>
                <div class="ring-wrap">
                    {ring_svg(accuracy_percent())}
                    <div>
                        <span class="level">{esc(level)}</span>
                        <p class="level-text">{esc(level_text)}</p>
                    </div>
                </div>
            </div>
            """
        )

    with right:
        c1, c2 = st.columns(2)

        with c1:
            st.metric("Questions attempted", st.session_state.quiz_attempted)

        with c2:
            st.metric("Flashcards reviewed", st.session_state.flashcards_reviewed)

        st.write("")

        if st.button(
            "🤖 Analyze my learning",
            use_container_width=True,
            key="analyze_learning",
            type="primary",
        ):
            st.session_state.adaptive_recommendations = (
                generate_adaptive_recommendations()
            )

    if st.session_state.adaptive_recommendations:
        section_title("Recommended next steps")

        for recommendation in st.session_state.adaptive_recommendations:
            render_html(f'<div class="insight">{esc(recommendation)}</div>')
    else:
        st.write("")
        st.info(
            "Finish a quiz or review some flashcards, "
            "then select “Analyze my learning”."
        )


# ============================================================
# PROGRESS
# ============================================================

def render_week_dots():
    active_days = get_week_activity(st.session_state.user_id)
    today = date.today()
    cells = []

    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        classes = ["day"]

        if day.isoformat() in active_days:
            classes.append("on")
        if day == today:
            classes.append("today")

        mark = "✓" if day.isoformat() in active_days else ""
        cells.append(
            f"""
            <div class="{' '.join(classes)}">
                <div class="dot">{mark}</div>
                <small>{day.strftime('%a')}</small>
            </div>
            """
        )

    return f'<div class="week">{"".join(cells)}</div>'


def render_progress():
    page_header("🎯", "Progress", "See how your studying is adding up.")

    attempted = st.session_state.quiz_attempted
    correct = st.session_state.correct_answers
    wrong = st.session_state.wrong_answers
    accuracy = accuracy_percent()
    level, level_text = learning_level()

    correct_pct = round(correct / attempted * 100) if attempted else 0
    wrong_pct = round(wrong / attempted * 100) if attempted else 0

    left, right = st.columns(2, gap="large")

    with left:
        render_html(
            f"""
            <div class="panel">
                <h3>Quiz accuracy</h3>
                <div class="ring-wrap">
                    {ring_svg(accuracy)}
                    <div>
                        <span class="level">{esc(level)}</span>
                        <p class="level-text">{esc(level_text)}</p>
                    </div>
                </div>
            </div>
            """
        )

    with right:
        render_html(
            f"""
            <div class="panel">
                <h3>Answers breakdown</h3>
                <div class="bar-row">
                    <span>Correct</span>
                    <div class="bar"><i style="width:{correct_pct}%;background:var(--good)"></i></div>
                    <b>{correct}</b>
                </div>
                <div class="bar-row">
                    <span>Wrong</span>
                    <div class="bar"><i style="width:{wrong_pct}%;background:var(--bad)"></i></div>
                    <b>{wrong}</b>
                </div>
                <h3 style="margin-top:26px">Last 7 days</h3>
                {render_week_dots()}
            </div>
            """
        )

    section_title("Learning activity")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("Questions attempted", attempted)

    with c2:
        st.metric("Flashcards reviewed", st.session_state.flashcards_reviewed)

    with c3:
        st.metric("Study time", f"{st.session_state.study_minutes} min")

    with c4:
        st.metric("Day streak", f"🔥 {st.session_state.study_streak}")

    if attempted > 0:
        if accuracy >= 80:
            st.success("Excellent performance. Keep going. 🏆")
        elif accuracy >= 60:
            st.info("Good progress. Keep practicing. 💪")
        else:
            st.warning("Review your material and try another quiz. 📚")
    else:
        st.info("Complete a quiz to start tracking your performance.")

    section_title("Session summary")

    with st.container(border=True):
        st.write(
            f"**Current document:** "
            f"{st.session_state.file_name or 'No document uploaded'}"
        )
        st.write(f"**Study chunks:** {len(st.session_state.chunks)}")
        st.write(f"**Generated topics:** {len(st.session_state.topics)}")
        st.write(f"**Generated flashcards:** {len(st.session_state.flashcards)}")


# ============================================================
# AI STUDY CHAT
# ============================================================

def render_ai_chat():
    section_title("💬 Ask your document")

    if not st.session_state.document_loaded:
        st.info("Upload a PDF first, then ask questions about it here.")
        return

    for message in st.session_state.messages:
        role = message.get("role", "assistant")
        content = message.get("content", "")

        with st.chat_message(role):
            st.write(content)

    question = st.chat_input("Ask something from your document...")

    if question:
        st.session_state.messages.append({"role": "user", "content": question})

        with st.chat_message("user"):
            st.write(question)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    answer = answer_question(st.session_state.chunks, question)
                except Exception as exc:
                    answer = (
                        "I couldn't answer that right now.\n\n"
                        f"Error: {exc}"
                    )

                st.write(answer)

        st.session_state.messages.append({"role": "assistant", "content": answer})


# ============================================================
# APPLICATION ROUTING
# ============================================================

common_css()

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

        page = st.session_state.page

        if page == "home":
            render_dashboard()
            st.divider()
            render_ai_chat()

        elif page == "topics":
            render_topics()

        elif page == "summary":
            render_summary()

        elif page == "quiz":
            render_quiz()

        elif page == "flashcards":
            render_flashcards()

        elif page == "planner":
            render_planner()

        elif page == "adaptive":
            render_adaptive()

        elif page == "progress":
            render_progress()

        else:
            st.session_state.page = "home"
            st.rerun()