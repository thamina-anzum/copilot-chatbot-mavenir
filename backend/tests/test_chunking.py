from app.ingestion.chunker import chunk_section
from app.ingestion.pdf_parser import TextLine
from app.ingestion.section_parser import SectionNode, build_sections


def _line(text: str, page: int, font: str, size: float, y0: float = 120) -> TextLine:
    return TextLine(text=text, page=page, font=font, size=size, flags=0, y0=y0, is_header_footer=False)


def test_split_heading_number_and_title():
    lines = [
        _line("1", 23, "Helvetica", 18),
        _line("Scope", 23, "Helvetica", 18),
        _line("The present document defines the Stage 2 system architecture for the 5G System.", 23, "Times-Roman", 10),
        _line("6.2.1", 520, "Helvetica", 14),
        _line("AMF", 520, "Helvetica", 14),
        _line("The Access and Mobility Management function (AMF) includes the following functionality.", 520, "Times-Roman", 10),
    ]
    sections = build_sections(lines)
    assert sections[0].number == "1" and sections[0].title == "Scope"
    assert any(s.number == "6.2.1" and s.title == "AMF" for s in sections)


def test_skips_toc_and_starts_at_scope():
    lines = [
        _line("ETSI TS 123 501 V18.10.0 (2025-07)", 1, "Helvetica-Bold", 9, y0=20),
        _line("Contents", 4, "Helvetica", 18),
        _line("1 Scope ................................ 23", 4, "Times-Roman", 10),
        _line("6.2.1 AMF ............................. 520", 10, "Times-Roman", 10),
        _line("Foreword", 22, "Helvetica", 18),
        _line("This Technical Specification has been produced by 3GPP.", 22, "Times-Roman", 10),
        _line("1 Scope", 23, "Helvetica", 18),
        _line("The present document defines the Stage 2 system architecture for the 5G System.", 23, "Times-Roman", 10),
        _line("6.2.1 AMF", 520, "Helvetica", 14),
        _line("The Access and Mobility Management function (AMF) includes the following functionality.", 520, "Times-Roman", 10),
    ]
    sections = build_sections(lines)
    assert sections[0].number == "1"
    assert sections[0].title.lower().startswith("scope")
    assert any(s.number == "6.2.1" and s.title == "AMF" for s in sections)
    assert not any("........" in ln.text for s in sections for ln in s.lines)


def test_table_stays_atomic():
    section = SectionNode(number="5.1", title="Numerology", page=41, lines=[
        _line("Prose before the table.", 41, "Times-Roman", 10),
        _line("Table 5.1-1: Supported transmission numerologies", 41, "Times-Roman", 10),
        _line("µ  Δf  CP", 41, "Times-Roman", 10),
        _line("0  15 kHz  Normal", 41, "Times-Roman", 10),
        _line("1  30 kHz  Normal", 41, "Times-Roman", 10),
        _line("After the table the prose continues with enough text to be a separate chunk.", 41, "Times-Roman", 10),
    ])
    chunks = chunk_section(section, "38.300", "18", "18.10.0", "ts_138300.pdf", 1400, 50)
    tables = [c for c in chunks if c.chunk_type == "table"]
    assert len(tables) == 1
    assert "Table 5.1-1" in tables[0].text
    assert "15 kHz" in tables[0].text


def test_figure_keeps_caption_only():
    section = SectionNode(number="4.4.2.1", title="Architecture", page=86, lines=[
        _line("AMF", 86, "Helvetica", 10),
        _line("N1", 86, "Helvetica", 10),
        _line("SMSF", 86, "Helvetica", 10),
        _line("Figure 4.4.2.1-1: Non-roaming System Architecture for SMS over NAS", 86, "Times-Roman", 10),
        _line("NOTE 1: SMS Function (SMSF) may be connected to the SMS-GMSC.", 86, "Times-Roman", 10),
    ])
    chunks = chunk_section(section, "23.501", "18", "18.10.0", "ts_123501.pdf", 1400, 50)
    figures = [c for c in chunks if c.chunk_type == "figure"]
    assert len(figures) == 1
    assert figures[0].text.startswith("Figure 4.4.2.1-1")
    assert "AMF" not in figures[0].text or "Architecture" in figures[0].text
    assert figures[0].has_diagram is True


def test_numbered_procedure_not_split():
    steps = [
        _line("The registration procedure is as follows.", 100, "Times-Roman", 10),
        _line("0. UE is in RM-DEREGISTERED.", 100, "Times-Roman", 10),
        _line("1. UE sends a Registration Request to the AMF.", 100, "Times-Roman", 10),
        _line("2. AMF performs identity request if needed.", 100, "Times-Roman", 10),
        _line("3. AMF accepts the registration and sends Registration Accept.", 100, "Times-Roman", 10),
    ]
    section = SectionNode(number="4.2.2.2", title="Registration", page=100, lines=steps)
    chunks = chunk_section(section, "23.502", "18", "18.10.0", "ts_123502.pdf", 120, 20)
    proc = [c for c in chunks if "Registration Request" in c.text and "Registration Accept" in c.text]
    assert proc, "procedure steps should remain in one chunk"
