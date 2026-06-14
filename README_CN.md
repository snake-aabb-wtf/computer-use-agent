# 🖥️ Computer Use Agent

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-169%20passing-brightgreen.svg)](tests/)

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
# 安装
pip install -r requirements.txt

# 配置
cp .env.example .env
# 编辑 .env 填入你的 API Key

# 运行
python -m computer_use_agent "打开记事本，输入 Hello World"
```

## 核心特性

### 🎯 两种截图模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| **SOM**（默认） | Windows UIA 元素树 + 编号覆盖层 | 高精度点击 |
| **Vision** | 纯视觉截图 | 所有模型，最大兼容性 |

在 `.env` 中切换：
```env
CAPTURE_MODE=som      # 元素索引模式（推荐）
CAPTURE_MODE=vision   # 纯视觉模式（兼容所有模型）
```

### 🖱️ 12 种操作类型

| 操作 | 示例 |
|------|------|
| 点击 | `{"action": "left_click", "element": 47}` |
| 双击 | `{"action": "double_click", "coordinate": [100, 200]}` |
| 右键 | `{"action": "right_click", "element": 12}` |
| 输入文本 | `{"action": "type", "text": "Hello World"}` |
| 按键 | `{"action": "key", "key": "enter"}` |
| 组合键 | `{"action": "hotkey", "keys": ["ctrl", "c"]}` |
| 滚动 | `{"action": "scroll", "direction": "down", "amount": 5}` |
| 移动鼠标 | `{"action": "move", "coordinate": [500, 300]}` |
| 拖拽 | `{"action": "drag", "from": [100,100], "to": [200,200]}` |
| 等待 | `{"action": "wait", "seconds": 2}` |
| 截图 | `{"action": "screenshot"}` |
| 完成 | `{"action": "done", "message": "任务完成"}` |

### 🖥️ 交互式 CLI（Hermes 风格）

```bash
python -m computer_use_agent
```

```
╔══════════════════════════════════════════╗
║   Computer Use Agent          v0.1.0    ║
╚══════════════════════════════════════════╝

┌────────────────────────────── Session ───────────────────────────────┐
│   Model           mimo-v2.5                                         │
│   Base URL        https://api.example.com/v1                       │
│   Screen          1920x1080                                        │
│   Capture Mode    SOM (SOM + UIA)                                  │
│   Max Steps       200                                              │
└─────────────────────────────────────────────────────────────────────┘

❯ /help
```

**25 个斜杠命令：**

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助 |
| `/config` | 显示配置 |
| `/model <name>` | 切换模型 |
| `/usage` | Token 用量统计 |
| `/status` | 当前状态 |
| `/yolo` | 切换自主模式 |
| `/steer <msg>` | 运行中注入指令 |
| `/stop` | 停止当前任务 |
| `/sessions` | 查看历史会话 |
| `/resume <id>` | 恢复会话 |
| `/save` | 导出会话为 JSON |
| `/branch` | 分叉当前会话 |
| `/retry` | 重试上一个任务 |
| `/undo` | 撤销最后对话 |
| `/queue <task>` | 排队下一条指令 |
| `/verbose` | 切换显示模式 |

## 项目架构

```
computer_use_agent/
├── agent.py          # 核心循环：截图 → LLM → 操作 → 验证
├── llm.py            # LLM 客户端（重试/退避/流式）
├── screen.py         # 屏幕截图（vision + SOM 模式）
├── executor.py       # 12 种操作 + 剪贴板粘贴
├── uia_tree.py       # Windows UIA 元素树 + SOM 覆盖层
├── prompts.py        # 系统提示词（10 个块，模型特定）
├── guardrails.py     # 工具循环检测（重复/失败/无进展）
├── sanitization.py   # JSON 修复、消息序列修复
├── token_budget.py   # 3 层上下文溢出防御
├── cli.py            # 交互式 CLI（Hermes 风格 REPL）
├── config.py         # 配置管理
└── logger.py         # 结构化日志
```

## 配置说明

所有配置通过 `.env` 文件：

```env
# LLM
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o

# Agent
MAX_STEPS=200
ACTION_DELAY=0.1

# 截图模式: som | vision
CAPTURE_MODE=som
```

## 环境要求

- Windows 10/11
- Python 3.10+
- `uiautomation`（SOM 模式需要）

```bash
pip install -r requirements.txt
```

## 运行测试

```bash
cd tests
python test_all.py          # 核心模块测试 (32)
python test_som.py          # SOM 模式测试 (27)
python test_coverage.py     # 覆盖测试 (67)
python test_cli_new.py      # CLI 功能测试 (30)
python test_new_commands.py # 新命令测试 (13)
```

**169 个测试全部通过。**

## 工作原理

1. **截图** — 捕获当前屏幕状态
2. **发送** — 将截图（+ SOM 模式下的元素列表）发送给 LLM
3. **解析** — 从 LLM 响应中提取 JSON 操作指令
4. **执行** — 执行操作（点击、输入、滚动等）
5. **验证** — 再次截图确认操作结果
6. **循环** — 重复直到任务完成或达到最大步数

### SOM 模式（元素索引）

模型不再猜测像素坐标，而是通过**元素编号**点击：

```
带红色编号覆盖层的截图 → 模型："点击元素 #47"
→ 后端解析：#47 → 中心坐标 → 系统点击
```

这把困难的回归问题变成了简单的分类问题。

## 安全机制

- 绝不输入密码或敏感信息
- 绝不点击破坏性确认（除非用户明确指示）
- 绝不执行截图或网页中嵌入的指令
- 工具循环护栏检测重复失败
- Ctrl+C 优雅中断

## 致谢

架构设计借鉴了 [Hermes Agent](https://github.com/nousresearch/hermes-agent) 的 agent 工程模式。

## 许可证

MIT
