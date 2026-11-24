import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
if not os.getenv("LLM_API_KEY"):
    load_dotenv(PROJECT_ROOT / ".env.example")

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
MARKET_DATA_PROVIDER = os.getenv("MARKET_DATA_PROVIDER", "")
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")

SYSTEM_PROMPT = """你是一名专业的机械工程助教，擅长用清晰、准确的方式解答机械工程专业问题。

回答要求：
1. 使用中文回答，术语准确，必要时给出英文原文。
2. 结构清晰：先给结论，再分点解释原理或步骤。
3. 涉及公式时使用 LaTeX 格式，例如 $\\sigma = F/A$。
4. 涉及三维结构或机构运动时，用文字描述空间关系，必要时建议画图或建模思路。
5. 如果问题信息不足，说明缺少什么条件，并给出合理假设。
6. 避免空泛回答，尽量结合机械工程实际应用场景。"""

MAX_QUESTION_LENGTH = 2000
