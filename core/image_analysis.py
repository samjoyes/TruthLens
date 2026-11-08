"""Image analysis module for manipulation detection and context consistency using Gemini Vision."""

import io
from typing import Optional
from PIL import Image

from core.llm import generate_structured
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
    image_bytes: Optional[bytes],
    headline: Optional[str] = None,
    body_summary: Optional[str] = None,
) -> Optional[ImageAnalysis]:
    """Analyze image for authenticity, manipulation, and reverse-search query formulation.

    Args:
        image_bytes: Raw bytes of the uploaded image. If None, skips analysis.
        headline: Optional story headline for context check.
        body_summary: Optional text summary of the story.

    Returns:
        ImageAnalysis result with reverse search queries and origin context, or None.
    """
    if not image_bytes:
        return None

    pil_image = validate_and_preprocess_image(image_bytes)

    clean_headline = (headline or "").strip()
    if clean_headline:
        context_block = f"CLAIMED HEADLINE: {clean_headline}\n"
        if body_summary and body_summary.strip():
            context_block += f"CONTEXT SUMMARY: {body_summary.strip()[:1000]}\n"
        context_instruction = (
            "Determine if the image authentically matches this claimed headline, or if it is "
            "recycled, out-of-context, or synthetically generated."
        )
    else:
        context_block = "CONTEXT: No headline was provided. Perform an autonomous deep-dive visual investigation."
        context_instruction = (
            "Analyze what this image depicts, determine its real-world origin, date/location, "
            "and identify key entities to perform a deep-dive reverse search."
        )

    prompt = f"""You are an expert multimodal forensic visual analyst and fact-checker. Inspect this image thoroughly:

{context_block}

{context_instruction}

Tasks:
1. Visually identify what the image shows: key public figures, landmarks, objects, visible signs/text, uniforms, terrain, or logos.
2. Check for indicators of digital manipulation or generative AI creation (e.g., warped perspective, surreal textures, abnormal hands/limbs, lighting mismatches, watermarks, deepfake artifacts).
3. Generate 2 to 3 high-precision web search queries (reverse-search style keywords) to find the original source, photographer, or news event for this picture.
4. Summarize the likely real-world origin, event, or context of this image.

Return ONLY valid JSON matching this schema:
- manipulation_suspicion: integer 0-100 (0 = authentic real photograph, 100 = blatant deepfake/manipulation)
- context_match: integer 0-100 (100 = image fits the story or authentic real capture, 0 = completely unrelated)
- verdict: one of "Consistent", "Possible Mismatch", "Likely Manipulated"
- reasoning: 2-3 plain language sentences explaining the visual assessment. Never claim absolute certainty; use cautious phrasing ("appears to show", "possible inconsistency").
- detected_entities: list of key entities, people, locations, or objects identified
- reverse_search_queries: list of 2-3 specific search queries to locate this image/event on the web
- origin_context: 1-2 sentences describing the identified origin, historical setting, or event
"""

    return generate_structured(
        prompt=prompt,
        schema=ImageAnalysis,
        image=pil_image,
        temperature=0.2,
    )
