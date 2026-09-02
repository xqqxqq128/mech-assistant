# 机械工程问答助手

本地运行的机械工程专业问答网页：输入问题，通过 Python 后端调用大模型 API 返回答案。

## 环境要求

- Python 3.10+
- 已配置 `.env`（可参考 `.env.example`）

## 快速开始

1. 在项目根目录创建或确认 `.env` 文件：

```env
LLM_API_KEY=你的密钥
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
```

2. 安装依赖并启动：

```powershell
pip install -r backend\requirements.txt
python -m uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

3. 浏览器打开：<http://127.0.0.1:8000>

## 项目结构

```
mech-assistant/
├── backend/          # FastAPI 后端
│   ├── app.py        # 主入口，挂载路由、CORS、静态文件
│   ├── config.py     # 环境变量配置 + System Prompt
│   ├── requirements.txt
│   ├── routes/
│   │   └── chat.py   # POST /api/chat（非流式）、POST /api/chat/stream（流式）
│   └── services/
│       └── llm_service.py  # LLM API 调用（非流式 + 流式）
├── frontend/         # 静态网页
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
├── .env              # API 配置（本地，不提交）
└── .env.example      # 配置示例
```

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/chat` | 非流式问答，请求体：`{"question": "..."}` |
| POST | `/api/chat/stream` | 流式问答（SSE），请求体：`{"question": "...", "messages": [...]}` |
| GET | `/` | 前端页面 |

## 功能特性

- **流式输出**：AI 回答逐字显示，无需等待完整响应
- **对话历史**：支持多轮上下文，保持对话连贯性
- **LaTeX 公式渲染**：使用 KaTeX 渲染数学公式
- **代码高亮**：使用 highlight.js 高亮代码块
- **快捷键**：`Ctrl+Enter` 快速发送
- **清空对话**：一键清空对话历史