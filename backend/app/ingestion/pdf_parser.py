"""PyMuPDF page parser with header/footer stripping and font metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass

import pymupdf

from app.core.logging import get_logger

logger = get_logger(__name__)

HEADER_RE = re.compile(
    r"^(ETSI|ETSI TS \d{3} \d{3} V[\d.]+ \(\d{4}-\d{2}\)|"
    r"3GPP TS \d{2}\.\d{3} version [\d.]+ Release \d+)$",
    re.I,
)
PAGE_NUM_RE = re.compile(r"^\d{1,4}$")
SPEC_HEADER_RE = re.compile(
    r"3GPP TS (\d{2}\.\d{3}) version ([\d.]+) Release (\d+)",
    re.I,
)


@dataclass
class TextLine:
    text: str
    page: int
    font: str
    size: float
    flags: int
    y0: float
    is_header_footer: bool = False

    @property
    def is_helvetica(self) -> bool:
        return "helvetica" in self.font.lower()

    @property
    def is_times(self) -> bool:
        return "times" in self.font.lower()

    @property
    def is_heading_font(self) -> bool:
        return self.is_helvetica and self.size >= 11.0 and not self.is_header_footer


def _is_header_footer(text: str, font: str, size: float, y0: float, page_height: float) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    in_band = y0 < 72 or y0 > page_height - 56
    helv_small = "helvetica" in font.lower() and size <= 9.5
    if helv_small and HEADER_RE.match(stripped):
        return True
    if helv_small and PAGE_NUM_RE.match(stripped) and in_band:
        return True
    if in_band and helv_small and stripped.upper() == "ETSI":
        return True
    return False


def extract_spec_header(text: str) -> tuple[str, str, str] | None:
    match = SPEC_HEADER_RE.search(text)
    if not match:
        return None
    return match.group(1), match.group(2), match.group(3)


def parse_pdf(path: str) -> tuple[list[TextLine], dict[str, str], int]:
    """Return stripped body lines, document metadata, and page count."""
    doc = pymupdf.open(path)
    lines: list[TextLine] = []
    spec, version, release = "", "", ""
    try:
        for page_index, page in enumerate(doc):
            page_height = float(page.rect.height)
            raw = page.get_text("dict")
            page_text_for_meta = page.get_text("text")
            if not spec:
                header = extract_spec_header(page_text_for_meta)
                if header:
                    spec, version, release = header
            for block in raw.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    spans = line.get("spans") or []
                    if not spans:
                        continue
                    text = "".join(s.get("text", "") for s in spans).strip()
                    if not text:
                        continue
                    dominant = max(spans, key=lambda s: len(s.get("text", "")))
                    font = dominant.get("font", "")
                    size = float(dominant.get("size", 0))
                    flags = int(dominant.get("flags", 0))
                    y0 = float(line.get("bbox", [0, 0, 0, 0])[1])
                    hf = _is_header_footer(text, font, size, y0, page_height)
                    lines.append(
                        TextLine(
                            text=text,
                            page=page_index + 1,
                            font=font,
                            size=size,
                            flags=flags,
                            y0=y0,
                            is_header_footer=hf,
                        )
                    )
    finally:
        doc.close()

    body = [ln for ln in lines if not ln.is_header_footer]
    meta = {
        "specification": spec,
        "version": version,
        "release": release,
    }
    logger.info(
        "Parsed %s: %s pages, %s body lines, spec=%s v%s Rel-%s",
        path,
        page_index + 1 if lines else 0,
        len(body),
        spec,
        version,
        release,
    )
    return body, meta, (page_index + 1 if lines else 0)
