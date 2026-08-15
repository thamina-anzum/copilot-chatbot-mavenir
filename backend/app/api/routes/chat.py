from fastapi import APIRouter, HTTPException

from app.models.chat import ChatMessageRequest, ChatMessageResponse
from app.services import chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=ChatMessageResponse)
async def post_message(body: ChatMessageRequest) -> ChatMessageResponse:
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Query must not be empty.")
    return await chat_service.send_message(query, body.conversation_id)


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    detail = await chat_service.get_conversation_detail(conversation_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return detail
