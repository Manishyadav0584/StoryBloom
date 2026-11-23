
import os
from pathlib import Path

import httpx

# Load local .env when python-dotenv is installed.
# Render will use environment variables configured in its dashboard.
try:
    from dotenv import load_dotenv

    PROJECT_ROOT = Path(__file__).resolve().parents[3]
    ENV_FILE = PROJECT_ROOT / "backend" / ".env"

    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
except ImportError:
    pass


GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def generate_text(prompt: str) -> dict:
    """
    Generate text using Groq.

    Returns the same dictionary structure as the previous
    Gemini/Ollama gateway to preserve existing service compatibility.
    """

    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is missing. Configure it in your environment."
        )

    if not prompt or not prompt.strip():
        raise ValueError("The generation prompt cannot be empty.")

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are StoryBloom, a creative and thoughtful "
                    "children's storytelling assistant. Write original, "
                    "age-appropriate, engaging content."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "max_tokens": 6000,
    }

    timeout = httpx.Timeout(
        connect=15.0,
        read=90.0,
        write=15.0,
        pool=15.0,
    )

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                GROQ_API_URL,
                headers=headers,
                json=payload,
            )

        if response.status_code == 429:
            raise RuntimeError(
                "Groq rate limit reached. Please wait before trying again."
            )

        if response.status_code == 401:
            raise RuntimeError(
                "Groq authentication failed. Check your GROQ_API_KEY."
            )

        response.raise_for_status()

        data = response.json()

        result = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        if not result or not result.strip():
            raise RuntimeError("Groq returned an empty response.")

        return {
            "text": result.strip(),
            "provider": "groq",
        }

    except httpx.TimeoutException as error:
        raise RuntimeError(
            "Groq request timed out. Please try again."
        ) from error

    except httpx.HTTPStatusError as error:
        details = error.response.text[:500]
        raise RuntimeError(
            f"Groq API error ({error.response.status_code}): {details}"
        ) from error

    except httpx.RequestError as error:
        raise RuntimeError(
            f"Could not connect to Groq: {error}"
        ) from error
