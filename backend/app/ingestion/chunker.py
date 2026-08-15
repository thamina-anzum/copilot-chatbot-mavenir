"""Structure-aware chunking: prose, tables, figures, atomic procedures."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

from app.core.config import get_settings
from app.core.logging import get_logger
from app.ingestion.pdf_parser import TextLine
from app.ingestion.section_parser import SectionNode, build_sections
from app.models.document import DocumentChunk

logger = get_logger(__name__)

TABLE_RE = re.compile(r"^Table\s+[\dA-Z]+(?:\.[\dA-Z]+)*-\d+\s*:", re.I)
FIGURE_RE = re.compile(r"^Figure\s+[\dA-Z]+(?:\.[\dA-Z]+)*-\d+\s*:", re.I)
STEP_RE = re.compile(r"^(\d{1,2})\.\s+\S")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _stable_id(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _join_lines(lines: Iterable[TextLine]) -> str:
    texts: list[str] = []
    for ln in lines:
        t = ln.text.strip()
        if not t:
            continue
        if texts and texts[-1].endswith("-") and t[:1].islower():
            texts[-1] = texts[-1][:-1] + t
        else:
            texts.append(t)
    return "\n".join(texts).strip()


def _is_diagram_noise(line: TextLine) -> bool:
    text = line.text.strip()
    if TABLE_RE.match(text) or FIGURE_RE.match(text):
        return False
    if text.startswith("NOTE") or text.startswith("- "):
        return False
    words = text.split()
    if len(text) <= 48 and len(words) <= 6 and not text.endswith("."):
        return True
    return False


def _split_prose(text: str, chunk_size: int, overlap: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text] if text.strip() else []
    sentences = SENTENCE_SPLIT_RE.split(text)
    chunks: list[str] = []
    buf = ""
    for sent in sentences:
        candidate = (buf + " " + sent).strip() if buf else sent
        if len(candidate) <= chunk_size:
            buf = candidate
            continue
        if buf:
            chunks.append(buf)
        if len(sent) > chunk_size:
            for i in range(0, len(sent), chunk_size - overlap):
                piece = sent[i : i + chunk_size].strip()
                if piece:
                    chunks.append(piece)
            buf = ""
        else:
            overlap_text = chunks[-1][-overlap:] if chunks and overlap else ""
            buf = (overlap_text + " " + sent).strip() if overlap_text else sent
    if buf:
        chunks.append(buf)
    return chunks


def _procedure_blocks(lines: list[TextLine]) -> list[tuple[str, list[TextLine]]]:
    """Group consecutive numbered steps so they are never split mid-list."""
    blocks: list[tuple[str, list[TextLine]]] = []
    i = 0
    while i < len(lines):
        m = STEP_RE.match(lines[i].text.strip())
        if m and int(m.group(1)) <= 1:
            proc = [lines[i]]
            expected = int(m.group(1)) + 1
            j = i + 1
            while j < len(lines):
                nxt = lines[j].text.strip()
                if TABLE_RE.match(nxt) or FIGURE_RE.match(nxt):
                    break
                sm = STEP_RE.match(nxt)
                if sm and int(sm.group(1)) == expected:
                    proc.append(lines[j])
                    expected += 1
                    j += 1
                    continue
                if sm and int(sm.group(1)) == 0:
                    break
                # Continuation of current step
                if sm and int(sm.group(1)) != expected:
                    break
                proc.append(lines[j])
                j += 1
            if expected >= 3:
                blocks.append(("procedure", proc))
                i = j
                continue
        i += 1
    return blocks


def chunk_section(
    section: SectionNode,
    spec: str,
    release: str,
    version: str,
    source_filename: str,
    chunk_size: int,
    overlap: int,
) -> list[DocumentChunk]:
    lines = section.lines
    chunks: list[DocumentChunk] = []
    buffer: list[TextLine] = []
    i = 0

    def flush_prose(buf: list[TextLine]) -> None:
        text = _join_lines(buf)
        if not text:
            return
        page = buf[0].page if buf else section.page
        for part in _split_prose(text, chunk_size, overlap):
            chunks.append(
                _make_chunk(
                    part,
                    "prose",
                    spec,
                    release,
                    version,
                    section,
                    page,
                    source_filename,
                    False,
                )
            )

    while i < len(lines):
        text = lines[i].text.strip()

        if FIGURE_RE.match(text):
            flush_prose(buffer)
            buffer = []
            caption = text
            # Drop nearby diagram-fragment lines
            j = i + 1
            while j < len(lines) and _is_diagram_noise(lines[j]):
                j += 1
            # Also drop noise immediately before caption already in buffer — already flushed
            chunks.append(
                _make_chunk(
                    caption,
                    "figure",
                    spec,
                    release,
                    version,
                    section,
                    lines[i].page,
                    source_filename,
                    True,
                )
            )
            i = j
            continue

        if TABLE_RE.match(text):
            flush_prose(buffer)
            buffer = []
            table_lines = [lines[i]]
            j = i + 1
            while j < len(lines):
                nxt = lines[j].text.strip()
                if FIGURE_RE.match(nxt) or TABLE_RE.match(nxt):
                    break
                if lines[j].is_heading_font and re.match(r"^\d+(?:\.\d+)*\s+", nxt):
                    break
                table_lines.append(lines[j])
                j += 1
            chunks.append(
                _make_chunk(
                    _join_lines(table_lines),
                    "table",
                    spec,
                    release,
                    version,
                    section,
                    lines[i].page,
                    source_filename,
                    False,
                )
            )
            i = j
            continue

        # Drop diagram noise that sits just above a forthcoming figure caption
        lookahead = lines[i + 1].text.strip() if i + 1 < len(lines) else ""
        if _is_diagram_noise(lines[i]) and FIGURE_RE.match(lookahead):
            i += 1
            continue

        buffer.append(lines[i])
        i += 1

    flush_prose(buffer)

    # Re-merge numbered procedures that were split across prose chunks is hard;
    # instead, detect procedure blocks on original lines and replace overlapping prose.
    # For atomicity we scan original lines and emit procedure chunks, removing
    # duplicate prose that is a subset. Simpler: second pass on section lines.
    proc_chunks: list[DocumentChunk] = []
    consumed_texts: set[str] = set()
    for _kind, proc_lines in _procedure_blocks(lines):
        ptext = _join_lines(proc_lines)
        if len(ptext) < 80:
            continue
        proc_chunks.append(
            _make_chunk(
                ptext,
                "prose",
                spec,
                release,
                version,
                section,
                proc_lines[0].page,
                source_filename,
                False,
            )
        )
        consumed_texts.add(ptext)

    if proc_chunks:
        # Keep non-overlapping prose/table/figure plus atomic procedures
        kept = [
            c
            for c in chunks
            if c.chunk_type != "prose" or not any(c.text in p or p in c.text for p in consumed_texts)
        ]
        # Avoid dropping unique surrounding prose: only drop if fully contained
        kept = []
        for c in chunks:
            if c.chunk_type != "prose":
                kept.append(c)
                continue
            if any(c.text.strip() in p for p in consumed_texts):
                continue
            kept.append(c)
        chunks = kept + proc_chunks

    return [c for c in chunks if c.text.strip()]


def _make_chunk(
    text: str,
    chunk_type: str,
    spec: str,
    release: str,
    version: str,
    section: SectionNode,
    page: int,
    source_filename: str,
    has_diagram: bool,
) -> DocumentChunk:
    cid = _stable_id(spec, section.number, str(page), chunk_type, text[:160], str(len(text)))
    return DocumentChunk(
        chunk_id=cid,
        text=text.strip(),
        chunk_type=chunk_type,
        specification=spec,
        release=release,
        version=version,
        section=section.number,
        section_title=section.title,
        parent_section=section.parent_section,
        page=page,
        source_filename=source_filename,
        has_diagram=has_diagram,
    )


def chunk_document(doc: dict, chunk_size: int | None = None, overlap: int | None = None) -> list[DocumentChunk]:
    settings = get_settings()
    chunk_size = chunk_size or settings.chunk_size
    overlap = overlap or settings.chunk_overlap
    sections = build_sections(doc["lines"])
    out: list[DocumentChunk] = []
    for section in sections:
        out.extend(
            chunk_section(
                section,
                spec=doc["specification"],
                release=doc["release"],
                version=doc["version"],
                source_filename=doc["source_filename"],
                chunk_size=chunk_size,
                overlap=overlap,
            )
        )
    logger.info(
        "%s: %s chunks (prose=%s table=%s figure=%s)",
        doc["source_filename"],
        len(out),
        sum(1 for c in out if c.chunk_type == "prose"),
        sum(1 for c in out if c.chunk_type == "table"),
        sum(1 for c in out if c.chunk_type == "figure"),
    )
    return out
