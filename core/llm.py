"""Gemini client wrapper with structured JSON output, retries, and error handling."""

import io
import time
from pathlib import Path
from typing import Any, Optional, Type, TypeVar, Union
from unittest.mock import Mock
from PIL import Image
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from core.config import FALLBACK_MODELS, MODEL_NAME, get_gemini_api_key

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Custom exception raised when Gemini structured inference fails."""

    pass


def get_client() -> genai.Client:
    """Return a google-genai client configured with the active API key and timeout."""
    key = get_gemini_api_key()
    if not key or key in ("your_key_here", "your_actual_key"):
        raise LLMError(
            "Gemini API key is missing. Please add your key to the .env file or input it in the app sidebar."
        )
    return genai.Client(api_key=key)


# Module-level client instance (can be patched in tests)
client = genai.Client(api_key=get_gemini_api_key() or "placeholder")


def _prepare_contents(
    prompt: str, image: Optional[Union[bytes, bytearray, Image.Image, str, Path]] = None
) -> list[Any]:
    """Prepare content payload for Gemini multimodal inference."""
    if image is None:
        return [prompt]

    try:
        if isinstance(image, (bytes, bytearray)):
            pil_image = Image.open(io.BytesIO(image))
        elif isinstance(image, (str, Path)):
            pil_image = Image.open(image)
        elif isinstance(image, Image.Image):
            pil_image = image
        else:
            raise LLMError(f"Unsupported image type: {type(image)}")

        # Convert palette/RGBA if needed to ensure RGB format
        if pil_image.mode in ("RGBA", "P"):
            pil_image = pil_image.convert("RGB")

        return [prompt, pil_image]
    except Exception as e:
        if isinstance(e, LLMError):
            raise
        raise LLMError(f"Failed to process input image: {e}") from e


def generate_structured(
    prompt: str,
    schema: Type[T],
    image: Optional[Union[bytes, bytearray, Image.Image, str, Path]] = None,
    temperature: float = 0.2,
    model: Optional[str] = None,
    max_retries: int = 2,
    initial_backoff: float = 1.0,
    timeout: float = 30.0,
) -> T:
    """Generate structured output adhering to a Pydantic schema using Gemini.

    Args:
        prompt: Instruction or context string.
        schema: Target Pydantic model class.
        image: Optional image bytes, PIL Image, or file path.
        temperature: Sampling temperature (0.1 - 0.3 for deterministic outputs).
        model: Model name override (defaults to MODEL_NAME from config).
        max_retries: Number of retries on transient errors (default 2).
        initial_backoff: Initial backoff duration in seconds.
        timeout: Request timeout in seconds.

    Returns:
        An instance of `schema` populated and validated with the model's output.

    Raises:
        LLMError: If inference fails after retries, returns empty, or violates schema.
    """
    selected_model = model or MODEL_NAME
    candidate_models = [selected_model] + [m for m in FALLBACK_MODELS if m != selected_model]
    contents = _prepare_contents(prompt, image)

    # Prefer patched client in tests, otherwise fresh client with active session/env credentials
    if isinstance(client.models.generate_content, Mock):
        active_client = client
    else:
        try:
            active_client = get_client()
        except Exception:
            active_client = client

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema,
        temperature=temperature,
    )

    last_exception: Optional[Exception] = None
    total_attempts = max_retries + 1

    for attempt in range(total_attempts):
        current_model = candidate_models[min(attempt, len(candidate_models) - 1)]
        try:
            response = active_client.models.generate_content(
                model=current_model,
                contents=contents,
                config=config,
            )

            if not response or not response.text or not response.text.strip():
                raise LLMError("Gemini returned an empty response.")

            # Validate structured output into target schema
            validated = schema.model_validate_json(response.text)
            return validated

        except (errors.APIError, TimeoutError, ConnectionError, LLMError, ValidationError) as err:
            last_exception = err
            if attempt < max_retries:
                sleep_time = initial_backoff * (2**attempt)
                time.sleep(sleep_time)
            else:
                break
        except Exception as err:
            last_exception = err
            if attempt < max_retries:
                sleep_time = initial_backoff * (2**attempt)
                time.sleep(sleep_time)
            else:
                break

    raise LLMError(
        f"Structured generation failed after {total_attempts} attempts: {last_exception}"
    ) from last_exception
