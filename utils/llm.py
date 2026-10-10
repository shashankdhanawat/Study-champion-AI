import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

def ask_llm(prompt, system_prompt=None):
    """Generate AI responses using Groq API."""

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        return "Groq API key missing. Please check your .env file."

    messages = []

    if system_prompt:
        messages.append({
            "role": "system",
            "content": system_prompt
        })

    messages.append({
        "role": "user",
        "content": prompt
    })

    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1"
        )

        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=messages,
            temperature=0.3
        )

        return response.choices[0].message.content or ""

    except Exception as exc:
        print(f"Groq API error: {exc}")
        return "AI service is temporarily unavailable. Please try again."
