"""Image analysis module for manipulation detection and context consistency using Gemini Vision."""

import io
from typing import Optional
from PIL import Image

from core.llm import LLMError, generate_structured
from core.schemas import ImageAnalysis

MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_FORMATS = {"JPEG", "JPG", "PNG", "WEBP"}
MAX_DIMENSION = 1280


def validate_and_preprocess_image(image_bytes: bytes) -> Image.Image:
    """Validate image format and size, and resize so longest dimension is <= 1280px."""
    if not image_bytes:
        raise ValueError("Image bytes are empty.")

    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise ValueError(
            f"Image file size ({len(image_bytes) / 1024 / 1024:.1f} MB) exceeds maximum allowed 5 MB."
        )

    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        raise ValueError(f"Unable to read image: {e}") from e

    format_name = (img.format or "").upper()
    if format_name not in ALLOWED_FORMATS:
        raise ValueError(
            f"Unsupported image format: {format_name}. Supported formats: JPG, PNG, WEBP."
        )

    # Convert modes to RGB for consistent model processing
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Resize if largest dimension exceeds 1280px
    width, height = img.size
    longest_side = max(width, height)
    if longest_side > MAX_DIMENSION:
        scale = MAX_DIMENSION / float(longest_side)
        new_width = int(round(width * scale))
        new_height = int(round(height * scale))
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    return img


def analyze_image(
    image_bytes: Optional[bytes], headline: str, body_summary: Optional[str] = None
) -> Optional[ImageAnalysis]:
    """Analyze image against article headline and context for manipulation or mismatch.

    Args:
        image_bytes: Raw bytes of the uploaded image. If None, skips analysis.
        headline: Story headline for context check.
        body_summary: Optional text summary of the story.

    Returns:
        ImageAnalysis result, or None if image_bytes is not provided.
    """
    if not image_bytes:
        return None

    pil_image = validate_and_preprocess_image(image_bytes)

    context_text = f"HEADLINE: {headline.strip()}\n"
    if body_summary and body_summary.strip():
        context_text += f"CONTEXT SUMMARY: {body_summary.strip()[:1000]}\n"

    prompt = f"""You are an expert multimodal news-credibility analyst. Inspect this image and compare it with the claimed news story below:

{context_text}

Evaluate:
1. What does the image depict? Does it plausibly and authentically relate to the reported event, people, and location?
2. Are there indicators of digital manipulation or synthetic generation (e.g., lighting/shadow discrepancies, warped boundaries, AI generation artifacts, unnatural skin/hands, recycled generic stock imagery, misleading text overlays)?

Return ONLY valid JSON matching this schema:
- manipulation_suspicion: integer 0-100 (0 = completely natural/authentic photograph, 100 = blatant manipulation/deepfake)
- context_match: integer 0-100 (100 = image directly matches the headline/story, 0 = completely unrelated or out-of-context)
- verdict: one of "Consistent", "Possible Mismatch", "Likely Manipulated"
- reasoning: 2-3 sentences in plain language. IMPORTANT: State suspicion levels with cautious phrasing (e.g., "appears to show", "possible mismatch", "suggests inconsistencies"), never claiming absolute certainty.
"""

    return generate_structured(
        prompt=prompt,
        schema=ImageAnalysis,
        image=pil_image,
        temperature=0.2,
    )
