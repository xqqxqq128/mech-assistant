from collections.abc import AsyncGenerator

import httpx

from backend.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, SYSTEM_PROMPT


class LLMServiceError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


async def ask_llm(question: str) -> str:
    if not LLM_API_KEY:
        raise LLMServiceError("未配置 LLM_API_KEY，请在项目根目录的 .env 文件中设置。", 500)

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        "temperature": 0.4,
        "stream": False,
    }

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    url = f"{LLM_BASE_URL}/chat/completions"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload, headers=headers)
    except httpx.RequestError as exc:
        raise LLMServiceError(f"无法连接到大模型服务：{exc}") from exc

    if response.status_code >= 400:
        detail = response.text.strip() or response.reason_phrase
        raise LLMServiceError(f"大模型 API 返回错误 ({response.status_code})：{detail}", response.status_code)

    data = response.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMServiceError("大模型返回格式异常，无法解析回答。") from exc


async def ask_llm_stream(messages: list[dict]) -> AsyncGenerator[str, None]:
    """流式调用 LLM，逐 token 产出内容。"""
    if not LLM_API_KEY:
        raise LLMServiceError("未配置 LLM_API_KEY，请在项目根目录的 .env 文件中设置。", 500)

    payload = {
        "model": LLM_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, *messages],
        "temperature": 0.4,
        "stream": True,
    }

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    url = f"{LLM_BASE_URL}/chat/completions"

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                if response.status_code >= 400:
                    detail = await response.aread()
                    detail_text = detail.decode().strip() or response.reason_phrase
                    raise LLMServiceError(
                        f"大模型 API 返回错误 ({response.status_code})：{detail_text}",
                        response.status_code,
                    )
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line.removeprefix("data: ").strip()
                    if data_str == "[DONE]":
                        break
                    import json

                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue
    except httpx.RequestError as exc:
        raise LLMServiceError(f"无法连接到大模型服务：{exc}") from exc