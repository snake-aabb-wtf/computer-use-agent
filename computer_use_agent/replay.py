"""Replay - 会话录制与回放 (修复 F4)

JSONL 格式:
    {"type": "header", "model": "...", "task": "...", "saved_at": "..."}
    {"type": "step", "step": 1, "thought": "...", "action": {...}, "result": "..."}
    {"type": "footer", "finished_at": "...", "total_steps": N, "result": "..."}

录制:
    在 agent.run() 中通过 RecordSink 写入 JSONL
    CLI: /save 增强支持 .jsonl 格式

回放:
    replay_session(file)  ——  按时间顺序打印动作
    replay_session(file, dry_run=True)  ——  仅打印不执行
"""

import json
import time
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, TextIO

from . import config
from .logger import setup_logger

logger = setup_logger()


# ── 录制器 ──

class RecordSink:
    """将会话步骤写入 JSONL 文件。

    用法:
        sink = RecordSink("session.jsonl")
        sink.write_header(model, task)
        # ... agent 跑 ...
        sink.write_step(1, thought, action, result)
        sink.write_footer("done", "Task completed", 10)
        sink.close()
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        self._fp: TextIO = open(file_path, "w", encoding="utf-8")
        self._closed = False
        self._step_count = 0
        self._start_time = time.time()

    def write_header(self, model: str = "", task: str = "") -> None:
        self._write({
            "type": "header",
            "model": model,
            "task": task,
            "capture_mode": getattr(config, "CAPTURE_MODE", "vision"),
            "saved_at": datetime.now().isoformat(),
        })

    def write_step(self, step: int, thought: str, action: dict, result: str) -> None:
        """记录一步。"""
        # 移除内部字段（_tokens_in 等），只保留干净的动作
        clean_action = {k: v for k, v in action.items() if not k.startswith("_")}
        self._write({
            "type": "step",
            "step": step,
            "thought": thought,
            "action": clean_action,
            "result": result,
            "elapsed": action.get("_elapsed", 0),
            "ts": time.time() - self._start_time,
        })
        self._step_count += 1

    def write_footer(self, status: str, result: str, total_steps: int) -> None:
        self._write({
            "type": "footer",
            "status": status,
            "result": result,
            "total_steps": total_steps,
            "finished_at": datetime.now().isoformat(),
            "duration": time.time() - self._start_time,
        })

    def _write(self, obj: dict) -> None:
        if self._closed:
            return
        try:
            self._fp.write(json.dumps(obj, ensure_ascii=False) + "\n")
            self._fp.flush()
        except Exception as e:
            logger.warning(f"RecordSink write failed: {e}")

    def close(self) -> None:
        if not self._closed:
            try:
                self._fp.close()
            except Exception:
                pass
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ── 回放器 ──

def replay_session(file_path: str, dry_run: bool = True, verbose: bool = False) -> int:
    """回放一个会话记录。

    Args:
        file_path: JSONL 记录文件
        dry_run: True=仅打印动作不执行；False=实际执行（需谨慎）
        verbose: 打印每步的完整 JSON

    Returns:
        退出码: 0=成功, 1=错误
    """
    if not os.path.exists(file_path):
        print(f"Replay file not found: {file_path}", file=sys.stderr)
        return 1

    print(f"📼 Replay: {file_path}")
    if dry_run:
        print("   Mode: DRY RUN (no actions will be executed)")
    else:
        print("   ⚠ Mode: LIVE (actions will be executed!)")

    step_count = 0
    header = None
    actions_to_replay = []

    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"  ⚠ Line {line_num} parse error: {e}")
                continue

            entry_type = entry.get("type")

            if entry_type == "header":
                header = entry
                print(f"\n  Task: {entry.get('task', '?')}")
                print(f"  Model: {entry.get('model', '?')}")
                print(f"  Saved: {entry.get('saved_at', '?')}")
                print()
            elif entry_type == "step":
                step_count += 1
                step_num = entry.get("step", step_count)
                thought = entry.get("thought", "")
                action = entry.get("action", {})
                result = entry.get("result", "")
                elapsed = entry.get("elapsed", 0)
                ts = entry.get("ts", 0)

                act_name = action.get("action", "?")
                coord = action.get("coordinate", "")
                text = action.get("text", "")
                key = action.get("key", "")

                desc = act_name
                if coord:
                    desc += f" @ {coord}"
                if text:
                    desc += f' text="{text[:50]}"'
                if key:
                    desc += f" key={key}"

                print(f"  [{step_num:03d}] {ts:6.1f}s | {elapsed:4.1f}s | {desc}")
                if verbose and thought:
                    print(f"         💭 {thought[:150]}")
                if verbose:
                    print(f"         action: {json.dumps(action, ensure_ascii=False)}")
                    print(f"         result: {result[:150]}")

                actions_to_replay.append((step_num, action))

            elif entry_type == "footer":
                print()
                print(f"  ── Footer ──")
                print(f"  Status:     {entry.get('status', '?')}")
                print(f"  Steps:      {entry.get('total_steps', '?')}")
                print(f"  Duration:   {entry.get('duration', 0):.1f}s")
                print(f"  Result:     {entry.get('result', '?')[:200]}")

    if not dry_run and actions_to_replay:
        print(f"\n  ⚠ LIVE MODE not yet fully implemented. Use dry_run=True.")
        return 1

    print(f"\n  ✅ Replayed {step_count} steps")
    return 0


# ── 工具：检查文件格式 ──

def detect_format(file_path: str) -> str:
    """检测会话文件格式：jsonl (replay) 或 json (legacy save)。"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
            if first_line.startswith("{"):
                try:
                    obj = json.loads(first_line)
                    if obj.get("type") == "header":
                        return "jsonl"
                except Exception:
                    pass
            # 尝试解析为单一 JSON
            f.seek(0)
            content = f.read()
            obj = json.loads(content)
            if "messages" in obj:
                return "json"
    except Exception:
        pass
    return "unknown"


import sys  # 在最后 import 避免循环
