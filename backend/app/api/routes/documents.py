from fastapi import APIRouter

from app.services.document_service import list_ingested_documents

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("")
async def list_documents():
    return {"documents": await list_ingested_documents()}
