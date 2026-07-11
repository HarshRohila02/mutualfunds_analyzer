from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.assistant.agent import run_assistant

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[dict]


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    if not request.messages or request.messages[-1].role != "user":
        raise HTTPException(400, "Last message must be from the user")
    try:
        result = run_assistant([m.model_dump() for m in request.messages])
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    return ChatResponse(reply=result.reply, tool_calls=result.tool_calls)
