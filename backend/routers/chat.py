"""챗봇 API — Solar + LEGAL_DB + 웹 검색."""

from fastapi import APIRouter, HTTPException

from backend.models.schemas import (
    ChatPromptResponse,
    ChatPromptUpdate,
    ChatRequest,
    ChatResponse,
)
from backend.services.chatbot import answer_chat
from backend.services.prompts import load_chatbot_prompt, save_chatbot_prompt

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    message = body.message.strip()
    if not message:
        raise HTTPException(400, "메시지를 입력하세요.")
    return await answer_chat(message, history=body.history, page_context=body.page_context)


@router.post("/documents/{doc_id}", response_model=ChatResponse)
async def chat_with_document(doc_id: str, body: ChatRequest) -> ChatResponse:
    message = body.message.strip()
    if not message:
        raise HTTPException(400, "메시지를 입력하세요.")
    return await answer_chat(
        message,
        doc_id=doc_id,
        history=body.history,
        page_context=body.page_context,
    )


@router.get("/prompt", response_model=ChatPromptResponse)
async def get_chat_prompt() -> ChatPromptResponse:
    return ChatPromptResponse(system_prompt=load_chatbot_prompt())


@router.patch("/prompt", response_model=ChatPromptResponse)
async def update_chat_prompt(body: ChatPromptUpdate) -> ChatPromptResponse:
    prompt = body.system_prompt.strip()
    if not prompt:
        raise HTTPException(400, "system_prompt가 비어 있습니다.")
    save_chatbot_prompt(prompt)
    return ChatPromptResponse(system_prompt=prompt)
