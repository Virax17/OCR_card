from __future__ import annotations

from typing import Protocol

from app.models import OCRSideResult


class OCREngine(Protocol):
    name: str

    def available(self) -> bool:
        ...

    def extract(self, image_bytes: bytes, side: str, variant: str) -> OCRSideResult:
        ...

