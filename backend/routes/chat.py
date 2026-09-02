from collections.abc import AsyncGenerator

from pydantic import BaseModel, Field

from backend.config import MAX_QUESTION_LENGTH
from backend.services.llm_service import LLMServiceError, ask_llm, ask_llm_stream
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=MAX_QUESTION_LENGTH)
    messages: list[dict] = Field(default_factory=list, description="历史消息列表")


class ChatResponse(BaseModel):
    answer: str


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空。")

    try:
        answer = await ask_llm(question)
    except LLMServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return ChatResponse(answer=answer)


@router.post("/chat/stream")
async def chat_stream(request: Request) -> StreamingResponse:
    body = await request.json()
    question = body.get("question", "").strip()
    messages = body.get("messages", [])

    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空。")

    if len(question) > MAX_QUESTION_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"问题长度不能超过 {MAX_QUESTION_LENGTH} 个字符。",
        )

    # 将当前问题和历史合并
    full_messages = [*messages, {"role": "user", "content": question}]

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for token in ask_llm_stream(full_messages):
                yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"
        except LLMServiceError as exc:
            yield f"event: error\ndata: {exc}\n\n"
        except Exception:
            yield "event: error\ndata: 服务器内部错误，请稍后重试。\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )