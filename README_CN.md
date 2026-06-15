# 🖥️ Computer Use Agent

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**AI 驱动的桌面自动化 Agent —— 截图、思考、操作，循环直到任务完成。**

[English Documentation](README.md)

---

## 它能做什么

Computer Use Agent 观察你的屏幕，思考，然后行动 —— 自动完成桌面任务。

```
用户指令 → 截图 → AI 分析 → 执行操作 → 验证结果 → 循环...
```

支持**任意 LLM**，通过 OpenAI 兼容接口调用（GPT-4o、Claude、DeepSeek、本地模型等）。

## 快速开始

```bash
# 安装（start.bat 会自动创建 venv）
pip install -r requirements.txt

# 配置
cp .env.example .env
# 编辑 .env 填入你的 API Key

# 运行
python -m computer_use_agent "打开记事本，输入 Hello World"
```

## 核心特性

### 🎯 三种截图模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| **SOM** | Windows UIA 元素树 + 编号覆盖层 | 高精度点击 |
| **Vision** | 纯视觉截图 + 提示词工程提升准确度 | 所有模型，最大兼容性 |
| **UITARS** | 坐标归一化 (0-1000) + 动作名称归一化 | UI-TARS 风格，跨模型 |

```env
CAPTURE_MODE=som      # 元素索引模式（推荐）
CAPTURE_MODE=vision   # 纯视觉模式（兼容所有模型）
CAPTURE_MODE=uitars   # 坐标归一化 0-1000（UI-TARS 风格）
```

### 🖱️ 操作类型

| 操作 | 示例 |
|------|------|
| 点击 | `{"action": "left_click", "coordinate": [x, y]}` |
| 双击 | `{"action": "double_click", "coordinate": [x, y]}` |
| 右键 | `{"action": "right_click", "coordinate": [x, y]}` |
| 输入文本 | `{"action": "type", "text": "Hello World"}` |
| 按键 | `{"action": "key", "key": "enter", "hold": 0}` |
| 组合键 | `{"action": "hotkey", "keys": ["ctrl", "c"]}` |
| 滚动 | `{"action": "scroll", "direction": "down", "amount": 5}` |
| 移动鼠标 | `{"action": "move", "coordinate": [500, 300]}` |
| 拖拽 | `{"action": "drag", "from": [100,100], "to": [200,200], "hold": 0.3}` |
| 等待 | `{"action": "wait", "seconds": 60}` |
| 截图 | `{"action": "screenshot"}` |
| 完成 | `{"action": "done", "message": "任务完成"}` |

### 🖥️ 交互式 CLI

```bash
python -m computer_use_agent
```

**25 个斜杠命令：** `/help` `/config` `/model` `/usage` `/status` `/yolo` `/steer` `/stop` `/sessions` `/resume` `/save` `/branch` `/retry` `/undo` `/queue` `/verbose` `/compact` `/history` `/reset` `/screen` `/steps` `/delay` `/title` `/clear`

## 项目架构

```
computer_use_agent/
├── agent.py          # 核心循环：截图 → LLM → 操作 → 验证
├── llm.py            # LLM 客户端（重试/退避/流式/中断处理）
├── screen.py         # 屏幕截图（vision + SOM 模式）
├── executor.py       # 操作类型 + 自然拖拽 + 按键长按 + 剪贴板粘贴
├── uia_tree.py       # Windows UIA 元素树 + SOM 覆盖层
├── prompts.py        # 系统提示词（10 个块，模型特定，3 种截图模式）
├── guardrails.py     # 工具循环检测（重复/失败/无进展）
├── sanitization.py   # JSON 修复、消息序列修复、工具名模糊匹配
├── token_budget.py   # 3 层上下文溢出防御
├── visual_effects.py # 点击涟漪、拖拽指示器、动作信息面板
├── notify.py         # 任务完成通知（窗口前置 + 提示音）
├── cli.py            # 交互式 CLI（Hermes 风格 REPL，25 个命令）
├── config.py         # 配置管理
└── logger.py         # 结构化日志
```

## 配置说明

所有配置通过 `.env` 文件：

```env
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
CAPTURE_MODE=vision
VISUAL_EFFECTS=off
```

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `LLM_API_KEY` | `sk-placeholder` | API 密钥 |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | API 地址 |
| `LLM_MODEL` | `gpt-4o` | 模型名称 |
| `LLM_MAX_TOKENS` | `4096` | 每次响应最大 token 数 |
| `LLM_TEMPERATURE` | `0.0` | 温度 |
| `MAX_STEPS` | `200` | 单个任务最大步数 |
| `ACTION_DELAY` | `0.1` | 操作间延迟（秒） |
| `REQUEST_TIMEOUT` | `60` | API 请求超时（秒） |
| `CAPTURE_MODE` | `vision` | `som` / `vision` / `uitars` |
| `SCREENSHOT_DIR` | `screenshots` | 截图保存目录 |
| `SCREENSHOT_FORMAT` | `png` | 截图格式 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `LOG_DIR` | `logs` | 日志目录 |
| `VISUAL_EFFECTS` | `off` | `on` 开启点击涟漪 + 拖拽指示器 |

## 安全机制

- 绝不输入密码或敏感信息
- 绝不关闭终端窗口（改为最小化）
- 绝不执行截图或网页中嵌入的指令
- 工具循环护栏检测重复失败
- Ctrl+C 优雅中断

## 致谢

架构设计借鉴了 [Hermes Agent](https://github.com/nousresearch/hermes-agent) 和 [UI-TARS-desktop](https://github.com/user-ailab/UI-TARS-desktop)。

## 许可证

MIT
