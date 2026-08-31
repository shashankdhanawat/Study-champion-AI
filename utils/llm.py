import os
from dotenv import load_dotenv
from mistralai.client import Mistral

load_dotenv()


def ask_llm(prompt, system_prompt=None):
    """Send a request to Mistral without crashing the Streamlit UI."""
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        return "Mistral is not configured. Add MISTRAL_API_KEY to your .env file."
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    try:
        response = Mistral(api_key=api_key).chat.complete(
            model="mistral-small-latest", messages=messages
        )
        return response.choices[0].message.content
    except Exception as exc:
        return f"I could not reach Mistral right now. Please try again. ({exc})"
