from pathlib import Path
import sys

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types


PROMPT = (
    "Create a grounded presentation visual for a slide about small business "
    "automation: a tidy desk with a laptop, calendar, and organized workflow "
    "materials in a real office setting. Clean modern deck style, 16:9, no text."
)
OUTPUT_FILE = Path("generated_test_image.png")


def load_api_key() -> str:
    # Try the repo root .env first, then backend/.env for convenience.
    load_dotenv(".env")
    load_dotenv(Path("backend") / ".env")

    api_key = (__import__("os").getenv("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError(
            "Missing GEMINI_API_KEY. Add it to .env or backend/.env before running this test."
        )
    return api_key


def classify_api_error(exc: errors.APIError) -> tuple[str, str]:
    code = getattr(exc, "code", None)
    message = (getattr(exc, "message", None) or str(exc) or "").strip()
    lower = message.lower()

    if code == 429 or "quota" in lower or "resource_exhausted" in lower:
        return "quota", "Quota exceeded or request rate is too high."
    if code in {401, 403} and ("api key" in lower or "permission" in lower or "auth" in lower):
        return "api key/project", "Invalid API key or the key is not allowed for this project."
    if code in {401, 403} and ("model" in lower or "access" in lower or "not allowed" in lower):
        return "billing/access issue", "The project does not have access to this model."
    if code == 404 or "model" in lower and "not found" in lower:
        return "wrong model name", "The model name is wrong or not available on this API."
    if code == 400:
        return "sdk usage", "The request shape is invalid for the SDK or API."
    return "billing/access issue", "Gemini rejected the request, likely due to access or project setup."


def extract_image_bytes(response) -> bytes | None:
    parts = list(getattr(response, "parts", None) or [])
    if not parts:
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            parts = list(getattr(candidates[0].content, "parts", []) or [])

    for part in parts:
        inline_data = getattr(part, "inline_data", None)
        if inline_data and getattr(inline_data, "data", None):
            data = inline_data.data
            return data if isinstance(data, bytes) else bytes(data)
    return None


def main() -> int:
    print("Gemini image test starting...")
    print(f"Output file: {OUTPUT_FILE.resolve()}")

    try:
        api_key = load_api_key()
        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=PROMPT,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
                image_config=types.ImageConfig(aspect_ratio="16:9", image_size="1K"),
            ),
        )

        image_bytes = extract_image_bytes(response)
        print("Request succeeded: yes")
        print(f"Image data returned: {'yes' if image_bytes else 'no'}")

        if not image_bytes:
            print("Failure category: sdk usage")
            print("Reason: The request completed but no image bytes were returned.")
            return 1

        OUTPUT_FILE.write_bytes(image_bytes)
        print(f"Saved image: {OUTPUT_FILE.resolve()}")
        return 0

    except RuntimeError as exc:
        print("Request succeeded: no")
        print("Failure category: api key/project")
        print(f"Error: {exc}")
        return 1
    except errors.APIError as exc:
        category, meaning = classify_api_error(exc)
        print("Request succeeded: no")
        print(f"Failure category: {category}")
        print(f"Gemini error code: {getattr(exc, 'code', 'unknown')}")
        print(f"Gemini error message: {getattr(exc, 'message', str(exc))}")
        print(f"What it means: {meaning}")
        return 1
    except Exception as exc:
        lower = str(exc).lower()
        print("Request succeeded: no")
        if any(token in lower for token in ["connection", "timed out", "dns", "ssl", "network"]):
            print("Failure category: network errors")
            print("What it means: The request could not reach Gemini reliably.")
        else:
            print("Failure category: sdk usage")
            print("What it means: The Python code or local environment likely needs adjustment.")
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
