from __future__ import annotations

from io import BytesIO

try:
    from PIL import Image, ImageEnhance, ImageOps
except Exception:  # pragma: no cover - dependency checked at runtime
    Image = None
    ImageEnhance = None
    ImageOps = None


def preprocess_image(file_bytes: bytes) -> tuple[bytes, int | None, int | None, str, list[str]]:
    if Image is None:
        return file_bytes, None, None, "Unknown", ["Pillow is not installed; image preprocessing skipped"]

    warnings: list[str] = []
    with Image.open(BytesIO(file_bytes)) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        width, height = img.size
        if width < 600 or height < 300:
            warnings.append("low_resolution")
        if width > 2000 or height > 2000:
            img.thumbnail((2000, 2000))
            width, height = img.size
        gray = ImageOps.grayscale(img)
        brightness = sum(gray.histogram()[i] * i for i in range(256)) / max(1, width * height)
        if brightness < 55:
            warnings.append("dark_image")
        if brightness > 220:
            warnings.append("overexposed_image")
        img = ImageEnhance.Contrast(img).enhance(1.25)
        output = BytesIO()
        img.save(output, format="JPEG", quality=92)

    quality = "Low" if warnings else "High"
    return output.getvalue(), width, height, quality, warnings

