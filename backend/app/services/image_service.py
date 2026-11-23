
import os
import base64
import json
import httpx

from pathlib import Path
from dotenv import load_dotenv


# Load environment variables
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / "backend" / ".env"

load_dotenv(ENV_FILE)

CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")

MODEL = "@cf/black-forest-labs/flux-1-schnell"


async def generate_story_image(prompt: str) -> str:

    if not CLOUDFLARE_API_TOKEN or not CLOUDFLARE_ACCOUNT_ID:
        raise RuntimeError("Cloudflare credentials are not configured.")

    if not prompt or not prompt.strip():
        raise ValueError("Image prompt cannot be empty.")

    url = (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{CLOUDFLARE_ACCOUNT_ID}/ai/run/{MODEL}"
    )

    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "prompt": prompt.strip()[:2048],
        "steps": 4
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            url,
            headers=headers,
            json=payload
        )

    if response.status_code == 429:
        raise RuntimeError(
            "Cloudflare rate or usage limit reached. "
            "Please try again later."
        )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Cloudflare API returned HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    content_type = response.headers.get("content-type", "")

    # Handle direct binary image responses
    if content_type.startswith("image/"):
        image_base64 = base64.b64encode(
            response.content
        ).decode("utf-8")

        return f"data:{content_type};base64,{image_base64}"

    # Handle JSON image responses
    try:
        data = response.json()
    except (ValueError, json.JSONDecodeError):
        raise RuntimeError(
            f"Unexpected Cloudflare response type: {content_type}"
        )

    # Support both possible JSON structures
    image_base64 = data.get("image")

    if not image_base64 and isinstance(data.get("result"), dict):
        image_base64 = data["result"].get("image")

    if isinstance(image_base64, str) and image_base64:
        return f"data:image/jpeg;base64,{image_base64}"

    # Show useful diagnostics without exposing credentials
    errors = data.get("errors", [])
    error_message = str(errors)[:500] if errors else "No image field found."

    print("Cloudflare response keys:", list(data.keys()))
    print("Cloudflare response errors:", error_message)

    raise RuntimeError(
        f"Cloudflare did not return an image. {error_message}"
    )
