const chatEl = document.getElementById("chat");
const formEl = document.getElementById("chat-form");
const questionEl = document.getElementById("question");
const submitBtn = document.getElementById("submit-btn");
const clearBtn = document.getElementById("clear-btn");
const charCountEl = document.getElementById("char-count");

const MAX_LENGTH = 2000;

// 会话历史：[{ role: "user"|"assistant", content: string }]
let messages = [];

function updateCharCount() {
  const length = questionEl.value.length;
  charCountEl.textContent = `${length} / ${MAX_LENGTH}`;
}

function renderEmptyState() {
  chatEl.innerHTML = `
    <div class="empty-state">
      还没有对话。试试问：<br />
      "什么是莫尔圆？" 或 "齿轮传动比怎么计算？"
    </div>
  `;
}

function createMessage(role, content, options = {}) {
  const message = document.createElement("article");
  message.className = `message message-${role}`;

  const label = document.createElement("div");
  label.className = "message-label";
  label.textContent = role === "user" ? "你的问题" : "AI 回答";

  const body = document.createElement("div");
  body.className = "message-content";

  if (options.loading) {
    body.innerHTML = '<div class="loading">正在思考...</div>';
  } else if (options.error) {
    body.innerHTML = `<p class="error-text">${escapeHtml(content)}</p>`;
  } else if (role === "assistant") {
    body.innerHTML = marked.parse(content);
    renderMath();
    highlightCode();
  } else {
    body.textContent = content;
  }

  message.append(label, body);
  return message;
}

function escapeHtml(text) {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function removeEmptyState() {
  const empty = chatEl.querySelector(".empty-state");
  if (empty) empty.remove();
}

function renderMath() {
  if (typeof renderMathInElement === "function") {
    try {
      renderMathInElement(chatEl, {
        delimiters: [
          { left: "$$", right: "$$", display: true },
          { left: "$", right: "$", display: false },
        ],
        throwOnError: false,
      });
    } catch {
      // 忽略 KaTeX 渲染错误
    }
  }
}

function highlightCode() {
  if (typeof hljs === "object") {
    chatEl.querySelectorAll("pre code").forEach((block) => {
      hljs.highlightElement(block);
    });
  }
}

// 流式提交
async function submitQuestionStream(question) {
  removeEmptyState();

  // 添加用户消息
  chatEl.appendChild(createMessage("user", question));
  messages.push({ role: "user", content: question });

  // 创建 AI 消息占位
  const assistantMessage = createMessage("assistant", "", { loading: true });
  chatEl.appendChild(assistantMessage);
  chatEl.scrollTop = chatEl.scrollHeight;

  submitBtn.disabled = true;
  let accumulatedContent = "";

  try {
    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, messages }),
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      const detail = data.detail || "请求失败，请稍后重试。";
      assistantMessage.replaceWith(
        createMessage("assistant", detail, { error: true })
      );
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    // 替换 loading 为可更新的内容容器
    const body = assistantMessage.querySelector(".message-content");
    body.innerHTML = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || ""; // 保留未完成的行

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const data = line.slice(6).trim();

        if (data === "[DONE]") continue;
        if (data.startsWith("event: error")) continue;

        accumulatedContent += data;
        body.innerHTML = marked.parse(accumulatedContent);
        renderMath();
        highlightCode();
      }
      chatEl.scrollTop = chatEl.scrollHeight;
    }

    // 处理 buffer 中的剩余数据
    if (buffer.startsWith("data: ")) {
      const data = buffer.slice(6).trim();
      if (data && data !== "[DONE]") {
        accumulatedContent += data;
        body.innerHTML = marked.parse(accumulatedContent);
        renderMath();
        highlightCode();
      }
    }

    // 保存 AI 回答到历史
    messages.push({ role: "assistant", content: accumulatedContent });
  } catch (error) {
    assistantMessage.replaceWith(
      createMessage("assistant", "网络异常，请确认后端服务已启动。", {
        error: true,
      })
    );
  } finally {
    submitBtn.disabled = false;
    chatEl.scrollTop = chatEl.scrollHeight;
  }
}

// 非流式提交（降级方案）
async function submitQuestionLegacy(question) {
  removeEmptyState();

  chatEl.appendChild(createMessage("user", question));
  messages.push({ role: "user", content: question });

  const assistantMessage = createMessage("assistant", "", { loading: true });
  chatEl.appendChild(assistantMessage);
  chatEl.scrollTop = chatEl.scrollHeight;

  submitBtn.disabled = true;

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, messages }),
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      const detail = data.detail || "请求失败，请稍后重试。";
      assistantMessage.replaceWith(
        createMessage("assistant", detail, { error: true })
      );
      return;
    }

    assistantMessage.replaceWith(createMessage("assistant", data.answer));
    messages.push({ role: "assistant", content: data.answer });
  } catch (error) {
    assistantMessage.replaceWith(
      createMessage("assistant", "网络异常，请确认后端服务已启动。", {
        error: true,
      })
    );
  } finally {
    submitBtn.disabled = false;
    chatEl.scrollTop = chatEl.scrollHeight;
  }
}

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();

  const question = questionEl.value.trim();
  if (!question) return;

  questionEl.value = "";
  updateCharCount();

  // 优先使用流式 API
  await submitQuestionStream(question);
});

questionEl.addEventListener("input", updateCharCount);

clearBtn.addEventListener("click", () => {
  messages = [];
  chatEl.innerHTML = "";
  renderEmptyState();
});

// Ctrl+Enter 快捷键发送
questionEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    formEl.dispatchEvent(new Event("submit"));
  }
});

renderEmptyState();
updateCharCount();