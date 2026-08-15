"""Detect 3GPP headings and skip cover, legal boilerplate, and Table of Contents."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.ingestion.pdf_parser import TextLine

logger = get_logger(__name__)

HEADING_NUM_RE = re.compile(
    r"^(?P<num>\d+(?:\.\d+)*|[A-Z]\d*(?:\.\d+)*)(?:\s+|$)(?P<title>.*)$"
)
ANNEX_RE = re.compile(r"^Annex\s+([A-Z])\s*(?:\(([^)]+)\))?:?\s*(.*)$", re.I)
TOC_DOTS_RE = re.compile(r"\.{4,}\s*\d+\s*$")
CLAUSE_REF_RE = re.compile(r"\b(clause|see|as described in|refer to)\b", re.I)
SKIP_TITLES = {"change history", "history"}


@dataclass
class SectionNode:
    number: str
    title: str
    page: int
    lines: list[TextLine] = field(default_factory=list)

    @property
    def parent_section(self) -> str:
        if "." not in self.number:
            return ""
        return self.number.rsplit(".", 1)[0]


def _is_toc_line(text: str) -> bool:
    if TOC_DOTS_RE.search(text):
        return True
    if re.search(r"\s{8,}\d{1,3}\s*$", text) and HEADING_NUM_RE.match(text.strip()):
        return True
    return False


def _looks_like_heading(line: TextLine) -> bool:
    if not line.is_heading_font:
        return False
    text = line.text.strip()
    if not text or _is_toc_line(text):
        return False
    if CLAUSE_REF_RE.search(text) and line.is_times:
        return False
    if ANNEX_RE.match(text):
        return True
    if HEADING_NUM_RE.match(text):
        return True
    return bool(text) and line.size >= 12 and line.is_helvetica and len(text) < 120


def _parse_heading(text: str) -> tuple[str, str] | None:
    annex = ANNEX_RE.match(text)
    if annex:
        letter, rest = annex.group(1), annex.group(3)
        title = rest.strip() or f"Annex {letter}"
        return letter, title
    match = HEADING_NUM_RE.match(text)
    if not match:
        return None
    return match.group("num"), match.group("title").strip()


def _read_heading(lines: list[TextLine], i: int) -> tuple[str, str, int] | None:
    """Return (number, title, lines_consumed) for a heading at index i.

    3GPP often splits '6.2.1' and 'AMF' onto two Helvetica lines.
    """
    if i >= len(lines):
        return None
    line = lines[i]
    if not _looks_like_heading(line):
        return None
    text = line.text.strip()
    parsed = _parse_heading(text)
    if parsed and parsed[1]:
        return parsed[0], parsed[1], 1
    if parsed and not parsed[1]:
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if nxt and nxt.is_heading_font and not _is_toc_line(nxt.text.strip()):
            nxt_parsed = _parse_heading(nxt.text.strip())
            # Title-only next line (e.g. "Scope", "AMF") — not itself a numbered heading
            if nxt_parsed is None:
                return parsed[0], nxt.text.strip(), 2
            if nxt_parsed[0] and nxt_parsed[1] == "" and nxt_parsed[0] != parsed[0]:
                # Next line is another number-only heading; current has empty title
                return parsed[0], "", 1
        return parsed[0], "", 1
    return None


def build_sections(lines: list[TextLine]) -> list[SectionNode]:
    """Skip cover/legal/ToC; emit body sections starting at clause 1 Scope."""
    started = False
    sections: list[SectionNode] = []
    current: SectionNode | None = None
    i = 0
    n = len(lines)
    while i < n:
        if not started:
            heading = _read_heading(lines, i)
            if heading and heading[0] == "1" and heading[1].lower().startswith("scope"):
                started = True
            else:
                i += 1
                continue

        heading = _read_heading(lines, i)
        if heading:
            number, title, consumed = heading
            if title.lower() in SKIP_TITLES:
                break
            current = SectionNode(number=number, title=title, page=lines[i].page)
            sections.append(current)
            i += consumed
            continue

        if current is not None:
            current.lines.append(lines[i])
        i += 1

    logger.info("Built %s sections after ToC/legal skip", len(sections))
    return sections
