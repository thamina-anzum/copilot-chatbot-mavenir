"""Extract specification identity from filename and recurring header string."""

from __future__ import annotations

import re
from pathlib import Path

from app.ingestion.pdf_parser import parse_pdf

FILENAME_RE = re.compile(r"ts_1(\d{2})(\d{3})v", re.I)

# Common 3GPP titles when cover-page extraction is noisy
KNOWN_TITLES = {
    "23.501": "System architecture for the 5G System (5GS)",
    "23.502": "Procedures for the 5G System (5GS)",
    "24.501": "Non-Access-Stratum (NAS) protocol for 5GS",
    "38.300": "NR and NG-RAN Overall Description",
}


def spec_from_filename(filename: str) -> str | None:
    match = FILENAME_RE.search(filename)
    if not match:
        return None
    return f"{match.group(1)}.{match.group(2)}"


def extract_title_from_cover(path: str) -> str:
    import pymupdf

    doc = pymupdf.open(path)
    try:
        text = doc[0].get_text("text")
    finally:
        doc.close()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    skip = {"technical specification", "etsi"}
    candidates = [ln for ln in lines if ln.lower() not in skip and not ln.lower().startswith("etsi")]
    # Prefer a long descriptive line that is not the 3GPP TS version string
    for ln in candidates:
        if "3GPP TS" in ln or ln.startswith("ETSI TS"):
            continue
        if len(ln) > 20:
            return ln
    return candidates[1] if len(candidates) > 1 else (candidates[0] if candidates else Path(path).stem)


def process_document(path: str) -> dict:
    filename = Path(path).name
    lines, header_meta, page_count = parse_pdf(path)
    spec = header_meta.get("specification") or spec_from_filename(filename) or "unknown"
    version = header_meta.get("version") or ""
    release = header_meta.get("release") or ""
    title = KNOWN_TITLES.get(spec) or extract_title_from_cover(path)
    return {
        "path": path,
        "source_filename": filename,
        "specification": spec,
        "version": version,
        "release": release,
        "title": title,
        "page_count": page_count,
        "lines": lines,
    }
