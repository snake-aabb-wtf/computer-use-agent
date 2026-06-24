# 🖥️ Computer Use Agent

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version 0.2.0](https://img.shields.io/badge/version-0.2.0-orange.svg)](CHANGELOG.md)
[![CI](https://img.shields.io/badge/CI-passing-brightgreen.svg)](.github/workflows/ci.yml)
[![MCP](https://img.shields.io/badge/MCP-compatible-purple.svg)](https://modelcontextprotocol.io/)

**AI 驱动的桌面自动化 Agent —— 截图、思考、操作，循环直到任务完成。**
驱动任意 OpenAI 兼容的 LLM 来控制鼠标、键盘和屏幕，将自然语言任务转化为
Windows / macOS / Linux 上的自动化操作。

[English Documentation](README.md) · [架构文档](docs/ARCHITECTURE.md) · [API 参考](docs/API.md) · [配置参考](docs/CONFIGURATION.md) · [插件开发](docs/PLUGINS.md) · [更新日志](CHANGELOG.md)

---

## ✨ v0.2.0 新特性

- **🔌 MCP Server** — 通过 [Model Context Protocol](https://modelcontextprotocol.io/)
  把 Claude Desktop、Cursor、Zed 直接连接到 CUA。暴露 5 个工具：
  `cua.run_task` / `cua.stop_task` / `cua.get_status` / `cua.screenshot` / `cua.list_monitors`
- **🧩 插件系统** — 把 Python 文件丢到 `~/.config/cua/plugins/` 即可教 LLM 自定义动作
  （发邮件、查询内部 API 等）
- **🖥️ 多显示器支持** — 通过 `mss` 实现；用 `MONITOR_INDEX` / `CAPTURE_REGION` 配置
- **📡 Webhook 通知** — 异步 POST `done` / `error` / `interrupted` 事件
- **🌐 国际化** — `LANGUAGE=en-US` 切换界面；41 个翻译键
- **📊 结构化 JSON 日志** — `LOG_FORMAT=json` 方便日志聚合
- **🛠️ HTTP API v2** — `GET /tasks` / `GET /stream/<id>` (SSE) / `POST /cancel/<id>` /
  `API_TOKEN` Bearer 鉴权 / `hmac.compare_digest` 防时序攻击
- **🐳 Docker** — `python:3.12-slim` + `xvfb` + `tini` + 非 root 用户
- **🩹 7 个关键 bug 修复** — Windows SIGINT、HTTP `/stop` 真正生效、context% 数学、
  SOM 重复抓屏、JSON 解析错误计数等

完整列表见 [CHANGELOG.md](CHANGELOG.md)。

---

## 🎬 快速开始

### 方式 A：pip / pipx（推荐）

```bash
# 安装
pip install computer-use-agent
# 或者用 pipx（隔离环境）：
pipx install computer-use-agent

# 配置（一次性）
export LLM_API_KEY=sk-...
export LLM_BASE_URL=https://api.openai.com/v1
export LLM_MODEL=gpt-4o

# 使用
cua "打开记事本，输入 Hello World"
```

### 方式 B：Docker

```bash
docker run -it --rm \
  -e LLM_API_KEY=sk-... \
  -e LLM_BASE_URL=https://api.openai.com/v1 \
  -e LLM_MODEL=gpt-4o \
  -p 127.0.0.1:2024:2024 \
  ghcr.io/snake-aabb-wtf/computer-use-agent:0.2.0 \
  cua --serve --host 0.0.0.0
```

### 方式 C：从源码（开发）

```bash
git clone https://github.com/snake-aabb-wtf/computer-use-agent.git
cd computer-use-agent
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

cp .env.example .env       # 然后编辑
python -m computer_use_agent "打开记事本"
```

### 30 秒示例

```bash
# 1. CLI — 单次任务
cua "打开计算器，计算 2+2"

# 2. REPL — 交互式
cua
> /help                    # 列出 26 个命令
> 打开设置，切换到深色模式
> /usage                   # 显示 token 用量
> /quit

# 3. HTTP API — 给其他 Agent 用
cua --serve --port 8080 &
curl -X POST http://127.0.0.1:8080/run \
  -H "Content-Type: application/json" \
  -d '{"task": "打开浏览器，搜索天气"}'

# 4. MCP Server — 给 Claude Desktop / Cursor 用
cua --mcp
# 然后添加到 ~/.config/claude_desktop_config.json（见 docs/API.md）
```

---

## 🎯 三种截图模式

| 模式 | 机制 | 点击方式 | 适用场景 |
|------|------|----------|----------|
| **`som`** *(默认)* | Windows UIA 元素树 + 红色编号覆盖 | `element: 7` | 最高精度，仅 Windows |
| **`vision`** | 纯截图 + 青色坐标网格 | `coordinate: [x, y]` | 跨平台，任意模型 |
| **`uitars`** | 纯截图 + 0-1000 归一化坐标 | `coordinate: [x, y]` (× screen_size/1000) | UI-TARS / Qwen-VL 风格模型 |

```env
# .env 文件中
CAPTURE_MODE=som      # 元素索引模式（Windows）
CAPTURE_MODE=vision   # 纯视觉模式（任意系统，任意模型）
CAPTURE_MODE=uitars   # 0-1000 坐标（UI-TARS 风格）
```

## 🖱️ 操作类型

LLM 输出 JSON 动作；CUA 把 60+ 种名称变体归一化为 12 个标准类型：

| 动作 | JSON | 示例 |
|---|---|---|
| 左键 | `left_click` | `{"action": "left_click", "coordinate": [100, 200]}` |
| 双击 | `double_click` | `{"action": "double_click", "coordinate": [100, 200]}` |
| 右键 | `right_click` | `{"action": "right_click", "coordinate": [100, 200]}` |
| 输入文本 | `type` | `{"action": "type", "text": "你好世界"}`（中文走剪贴板） |
| 按键 | `key` | `{"action": "key", "key": "enter"}` |
| 长按 | `key` | `{"action": "key", "key": "shift", "hold": 2.0}` |
| 组合键 | `hotkey` | `{"action": "hotkey", "keys": ["ctrl", "shift", "p"]}` |
| 滚动 | `scroll` | `{"action": "scroll", "direction": "down", "amount": 5}` |
| 移动鼠标 | `move` | `{"action": "move", "coordinate": [500, 300]}` |
| 拖拽 | `drag` | `{"action": "drag", "from": [100,100], "to": [200,200], "hold": 0.3}` |
| 等待 | `wait` | `{"action": "wait", "seconds": 2}` |
| 重新截图 | `screenshot` | `{"action": "screenshot"}` |
| 完成 | `done` | `{"action": "done", "message": "任务完成"}` |

## 🖥️ 交互式 REPL（26 个斜杠命令）

```bash
cua
> 打开文件管理器
> /help                    # 所有 26 个命令
> /status                  # 显示会话状态
> /steer 关注搜索框         # 任务中途注入指令
> /queue 关闭对话框         # 排队下一个任务
> /stop                    # 停止当前任务
> /compact                 # 手动压缩历史
> /usage                   # token / 成本报告
> /sessions                # 查看历史会话
> /resume 1                # 恢复第 1 个会话
> /save                    # 导出为 JSON
> /branch "变体 A"          # 分叉当前会话
> /model gpt-4o            # 运行时切换模型
> /capture-mode som        # 切换到 SOM 模式
> /steps 50                # 限制步数
> /clear                   # 清屏
> /quit
```

完整命令列表：`/help` `/config` `/model` `/usage` `/status` `/yolo` `/steer`
`/stop` `/sessions` `/resume` `/save` `/branch` `/retry` `/undo` `/queue`
`/verbose` `/compact` `/history` `/reset` `/screen` `/steps` `/delay` `/title` `/clear`

---

## 🔌 HTTP REST API

让其他 Agent（或你自己的脚本）通过 REST 驱动 CUA。零新依赖 —— 纯 Python 标准库。

```bash
# 启动服务器
cua --serve --port 8080
```

```bash
# 提交任务
curl -X POST http://127.0.0.1:8080/run \
  -H "Content-Type: application/json" \
  -d '{"task": "打开计算器，计算 2+2"}'
# → {"id": "a1b2c3d4e5f6", "status": "accepted"}

# 轮询状态
curl http://127.0.0.1:8080/status/a1b2c3d4e5f6
# → {"id": "a1b2c3d4e5f6", "status": "done", "result": "...", "finished_at": ...}

# 实时进度（SSE）
curl -N http://127.0.0.1:8080/stream/a1b2c3d4e5f6

# 取消队列中或正在运行的任务
curl -X POST http://127.0.0.1:8080/cancel/a1b2c3d4e5f6
```

| 端点 | 方法 | 说明 |
|---|---|---|
| `/` | GET | 服务信息 + 端点列表 |
| `/health` | GET | 状态、忙碌/空闲、队列长度 |
| `/tasks` | GET | 列出所有任务（含元数据） |
| `/run` | POST | 提交任务（忙时排队；满了返 429） |
| `/status/<id>` | GET | 任务状态：`queued` → `running` → `done`/`error` |
| `/stream/<id>` | GET | Server-Sent Events（实时进度） |
| `/stop` | POST | 停止当前任务（通过 `Agent.interrupt()` 真正中断） |
| `/cancel/<id>` | POST | 取消指定任务 |

鉴权：设置 `API_TOKEN=...` 要求 Bearer 鉴权。使用 `hmac.compare_digest` 防止
时序攻击。完整参考见 [docs/API.md](docs/API.md)。

---

## 🧠 MCP Server（Model Context Protocol）

让 CUA 对 Claude Desktop、Cursor、Zed、Continue 或任何 MCP 兼容客户端可用：

```bash
# 启动 MCP 服务器（stdio JSON-RPC）
cua --mcp
```

然后添加到 Claude Desktop 配置（`~/Library/Application Support/Claude/claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "cua": {
      "command": "cua-mcp",
      "args": []
    }
  }
}
```

重启 Claude Desktop —— `cua.*` 工具即出现：

- `cua.run_task(task)` → 提交任务
- `cua.stop_task()` → 停止正在运行的任务
- `cua.get_status(task_id)` → 轮询状态
- `cua.screenshot()` → 抓取当前屏幕
- `cua.list_monitors()` → 枚举显示器

## 🧩 插件系统

教 LLM 你自己的自定义动作。把 Python 文件丢到 `~/.config/cua/plugins/`：

```python
# ~/.config/cua/plugins/send_email.py
from computer_use_agent.plugins import ActionRegistry

def register(registry: ActionRegistry):
    @registry.register(
        name="send_email",
        description="通过 SMTP 发送邮件",
        schema={
            "type": "object",
            "properties": {
                "to":      {"type": "string"},
                "subject": {"type": "string"},
                "body":    {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
    )
    def send_email(to: str, subject: str, body: str) -> str:
        # ... 你的实现 ...
        return f"📧 已发送至 {to}: {subject}"
```

CUA 自动发现并注册插件。LLM 现在可以与内置动作一起调用 `send_email`。
完整指南见 [docs/PLUGINS.md](docs/PLUGINS.md)。

## 📡 Webhook 通知

任务完成时获得 POST：

```env
WEBHOOK_URL=https://your-server/webhook
WEBHOOK_EVENTS=done,error,interrupted
```

载荷：
```json
{
  "event": "done",
  "task_id": "agent-1719234567",
  "task": "打开记事本",
  "result": "记事本已打开",
  "duration_seconds": 12.3,
  "stats": {"total_steps": 5, "api_calls": 5, "tokens_in": 1234, "tokens_out": 567}
}
```

## 📼 会话回放

录制会话后回放用于调试 / 审计 / 数据集：

```bash
# 跑完任务后，/save 导出为 JSONL
cua
> 打开记事本，输入 Hello
> /save
Saved to: logs/saved/conversation_20260624_103045.json

# 回放（默认 dry-run）
cua --replay logs/saved/conversation_20260624_103045.json --verbose
```

---

## 🛡️ 安全机制

CUA 默认安全：

- **HTTP API** 默认绑定 `127.0.0.1`；`0.0.0.0` 需要 `API_TOKEN`
- **Bearer 鉴权** 使用 `hmac.compare_digest`（无时序攻击）
- **CORS** 回显请求 `Origin`（无 `*` 通配符）
- **`pyautogui.FAILSAFE`** 通过 `PYAUTOGUI_FAILSAFE=on` 启用（鼠标撞角紧急停止）
- **绝不输入** 密码 / API Key（日志脱敏 12 种密钥模式）
- **绝不关闭** 终端窗口（改为最小化）
- **工具循环护栏** 检测重复失败、无进展循环
- **跨平台中断** 通过 `threading.Event`（无信号处理 hack）
- **Webhook 鉴权** 通过共享密钥

---

## ⚙️ 配置

所有设置通过环境变量（通常在 `.env` 中）。CLI 参数覆盖 `.env` 值，
.env 覆盖内置默认值。

```bash
# 必填
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o

# 可选
CAPTURE_MODE=vision        # som | vision | uitars
MAX_STEPS=200
API_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
LANGUAGE=en-US
LOG_FORMAT=json
WEBHOOK_URL=https://...
```

完整参考（40+ 环境变量及默认值）见 **[docs/CONFIGURATION.md](docs/CONFIGURATION.md)**。

---

## 🏗️ 架构

```
┌─────────────────────────────────────────────────────────────────────┐
│  入口点                                                             │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────────┐                          │
│  │ CLI  │  │ REPL │  │ API  │  │   MCP    │  ← 你在这                │
│  └──┬───┘  └──┬───┘  └──┬───┘  └────┬─────┘                          │
│     └────────┴─────────┴──────────┘                                 │
│                          ▼                                          │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  Agent.run(task)                                              │ │
│  │   for step in 1..MAX_STEPS:                                  │ │
│  │     capture screenshot ──▶ screen.py (mss / ImageGrab)        │ │
│  │     _prepare_messages() ──▶ 3 层 token 预算                 │ │
│  │     chat(screenshot, history) ──▶ llm.py (OpenAI SDK)         │ │
│  │     parse JSON action                                       │ │
│  │     execute(action) ──▶ executor.py (pyautogui / uiautomation)│ │
│  │     guardrail check (loop / no-progress)                      │ │
│  │     append to history                                       │ │
│  │   on done/error/interrupted:                                 │ │
│  │     notify webhook / record replay                          │ │
│  └──────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

深度解析（模块、线程模型、数据流、安全）见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

---

## 📁 项目结构

```
computer-use-agent/
├── computer_use_agent/       # 22 个 Python 模块
│   ├── __main__.py           # argparse CLI 入口
│   ├── agent.py              # 主循环
│   ├── llm.py                # OpenAI 客户端 + 重试 + JSON 解析
│   ├── executor.py           # 12 种动作类型
│   ├── screen.py             # 多显示器截图
│   ├── uia_tree.py           # Windows UIA 元素树
│   ├── api.py                # HTTP REST API
│   ├── cli.py                # 交互式 REPL（26 命令）
│   ├── tui.py                # 实时状态面板
│   ├── mcp_server.py         # MCP 服务器（stdio JSON-RPC）
│   ├── plugins.py            # 插件系统
│   ├── replay.py             # JSONL 会话回放
│   ├── webhook.py            # 异步通知
│   ├── i18n.py               # zh-CN / en-US 翻译
│   ├── logger.py             # 轮转日志 + JSON 格式
│   ├── prompts.py            # 10 块系统提示词
│   ├── sanitization.py       # 5 级 JSON 修复
│   ├── token_budget.py       # 3 层上下文预算
│   ├── guardrails.py         # 循环检测
│   ├── visual_effects.py     # Win32 点击/拖拽覆盖层
│   └── notify.py             # Windows 通知
├── tests/                    # 13 个测试文件
├── docs/                     # ARCHITECTURE / CONFIGURATION / API / PLUGINS
├── .github/workflows/        # CI / Release / CodeQL
├── Dockerfile + docker-compose.yml
├── pyproject.toml            # 4 个 console_scripts
├── CHANGELOG.md              # v0.2.0 更新日志
└── CONTRIBUTING.md
```

---

## 🧪 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 跑测试
pytest tests/ -v

# Lint
ruff check computer_use_agent/
ruff format --check computer_use_agent/

# 类型检查
mypy computer_use_agent/ --ignore-missing-imports

# 安全扫描
bandit -r computer_use_agent/ -ll
```

每次 push 自动跑 CI：

- 3 OS × 3 Python 版本矩阵（Linux / Windows / macOS × 3.10 / 3.11 / 3.12）
- Smoke test（验证所有模块可导入）
- Lint（ruff + bandit）
- CodeQL 安全分析

## 📦 分发渠道

v0.2.0 通过 **GitHub Releases** 分发（不上 PyPI）：

- 📥 **下载**: <https://github.com/snake-aabb-wtf/computer-use-agent/releases/tag/v0.2.0>
- 🐳 **Docker**: `docker pull ghcr.io/snake-aabb-wtf/computer-use-agent:0.2.0`（多架构镜像）
- 📦 **从源码构建**: `pip install -e .`（见[快速开始](#-快速开始)）

PyPI 发布是**可选的**，默认禁用。如需启用：

1. 在 PyPI 设置 [Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
   （一次性手动配置；见 `.github/workflows/release.yml` 注释）。
2. 取消 `publish-pypi` job 的注释 —— 之后每次推 `v*.*.*` tag 就会自动发布。

## 🤝 贡献

欢迎 PR！详见 [CONTRIBUTING.md](CONTRIBUTING.md)：

- 开发环境搭建
- 代码风格（ruff + mypy）
- Conventional Commits
- PR 模板与审核流程

## 📜 许可证

MIT —— 见 [LICENSE](LICENSE)。

## 🙏 致谢

架构借鉴自：

- [Hermes Agent](https://github.com/nousresearch/hermes-agent) — 工程模式
  （重试、退避、历史压缩、护栏）
- [UI-TARS-desktop](https://github.com/user-ailab/UI-TARS-desktop) — 截图模式、
  动作归一化、视觉反馈

使用 [pyautogui](https://github.com/asweigart/pyautogui)、
[mss](https://github.com/BoboTiG/ebook-reader-dict)、
[Rich](https://github.com/Textualize/rich)、
[prompt_toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit) 和
[OpenAI Python SDK](https://github.com/openai/openai-python) 构建。

---

**[⬆ 回到顶部](#-computer-use-agent)**
