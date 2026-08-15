from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    chunk_id: str
    text: str
    chunk_type: str = Field(description="prose | table | figure")
    specification: str
    release: str
    version: str
    section: str
    section_title: str
    parent_section: str
    page: int
    source_filename: str
    has_diagram: bool = False


class DocumentMeta(BaseModel):
    specification: str
    title: str
    release: str
    version: str
    source_filename: str
    page_count: int
    chunk_count: int = 0
