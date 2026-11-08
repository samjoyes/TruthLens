"""Manual test script to verify Gemini API connection and structured generation."""

import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import BaseModel
from core.llm import LLMError, generate_structured


class Greeting(BaseModel):
    message: str
    language: str


def main():
    print("Testing Gemini structured generation...")
    try:
        result = generate_structured(
            prompt="Say hello in Spanish and name the language.",
            schema=Greeting,
        )
        print("\nSUCCESS! Gemini returned valid structured object:")
        print(f"  Message:  {result.message}")
        print(f"  Language: {result.language}")
    except LLMError as e:
        print(f"\nCaught expected LLMError:\n{e}")
    except Exception as e:
        print(f"\nUnexpected error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
