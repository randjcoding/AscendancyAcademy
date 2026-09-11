"""Read text from page photos with Tesseract when it is installed."""
from __future__ import annotations

import io
import logging
import shutil

log = logging.getLogger("aa.ocr")


def tesseract_available() -> bool:
    if shutil.which("tesseract"):
        return True
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def read_image(data: bytes) -> str:
    if not data:
        return ""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        log.info("pytesseract or Pillow is not installed")
        return ""
    try:
        image = Image.open(io.BytesIO(data))
        if image.mode not in {"L", "RGB"}:
            image = image.convert("RGB")
        text = pytesseract.image_to_string(image) or ""
        return text.strip()
    except Exception:
        log.warning("tesseract failed", exc_info=True)
        return ""


def read_images(blobs: list[bytes]) -> str:
    parts = []
    for i, blob in enumerate(blobs, start=1):
        text = read_image(blob)
        if text:
            parts.append(f"--- photo {i} ---\n{text}")
    return "\n\n".join(parts)
