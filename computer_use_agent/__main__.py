"""CLI 入口 - 支持交互式 REPL、快捷参数模式、HTTP API 模式

修复 C1: 使用 argparse 替代手写参数解析
- 提供标准 --help / --version
- 支持 --task 直接传任务
- 支持 --capture-mode / --verbose / --no-color 覆盖 .env
- 支持 --dry-run 仅生成不执行
- 支持 --mcp 启动 MCP Server（M4 阶段）
"""

import argparse
import sys

from . import __version__


def _build_parser() -> argparse.ArgumentParser:
    """构建参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="cua",
        description="Computer Use Agent - AI-powered desktop automation through screenshots and actions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  cua                                  # 启动交互式 REPL
  cua "open notepad"                   # 单次任务
  cua --serve --port 8080              # 启动 HTTP API
  cua --mcp                            # 启动 MCP Server (stdio)
  cua --task "open browser" --dry-run  # 仅生成不执行
  cua --capture-mode som --verbose     # SOM 模式 + 流式输出
""",
    )

    # 版本
    parser.add_argument(
        "-V", "--version", action="version",
        version=f"cua {__version__}",
    )

    # 任务快捷方式
    parser.add_argument(
        "task", nargs="*",
        help="直接执行的任务（不进入 REPL）",
    )

    # 服务模式
    mode_group = parser.add_argument_group("Service mode")
    mode = mode_group.add_mutually_exclusive_group()
    mode.add_argument(
        "--serve", "--api", dest="serve", action="store_true",
        help="启动 HTTP REST API 服务器",
    )
    mode.add_argument(
        "--mcp", dest="mcp", action="store_true",
        help="启动 MCP (Model Context Protocol) Server (M4 阶段)",
    )
    mode.add_argument(
        "--replay", dest="replay", metavar="FILE",
        help="回放录制的会话 (M4 阶段)",
    )

    # 服务相关
    service_group = parser.add_argument_group("Service options")
    service_group.add_argument(
        "--host", default=None,
        help="API 服务器监听地址（覆盖 API_HOST）",
    )
    service_group.add_argument(
        "--port", "-p", type=int, default=None,
        help="API 服务器监听端口（覆盖 API_PORT）",
    )

    # Agent 配置覆盖
    agent_group = parser.add_argument_group("Agent options")
    agent_group.add_argument(
        "--capture-mode", choices=["som", "vision", "uitars"], default=None,
        help="截图捕获模式（覆盖 CAPTURE_MODE）",
    )
    agent_group.add_argument(
        "--max-steps", type=int, default=None,
        help="单次任务最大步数（覆盖 MAX_STEPS）",
    )
    agent_group.add_argument(
        "--model", default=None,
        help="LLM 模型名（覆盖 LLM_MODEL）",
    )

    # 输出
    output_group = parser.add_argument_group("Output options")
    output_group.add_argument(
        "--verbose", "-v", action="store_true",
        help="详细输出（启用流式 LLM 响应）",
    )
    output_group.add_argument(
        "--no-color", action="store_true",
        help="禁用 ANSI 颜色与 emoji（适合屏幕阅读器/CI）",
    )
    output_group.add_argument(
        "--plain", action="store_true",
        help="纯文本模式（无 Rich TUI）",
    )
    output_group.add_argument(
        "--quiet", "-q", action="store_true",
        help="静默模式（最少输出）",
    )

    # 调试
    debug_group = parser.add_argument_group("Debug options")
    debug_group.add_argument(
        "--dry-run", action="store_true",
        help="仅生成动作不执行（需要 LLM）",
    )
    debug_group.add_argument(
        "--config", default=None,
        help="指定 .env 文件路径",
    )
    debug_group.add_argument(
        "--language", choices=["zh-CN", "en-US"], default=None,
        help="界面语言（覆盖 LANGUAGE）",
    )

    return parser


def _apply_overrides(args: argparse.Namespace) -> None:
    """将 CLI 参数覆盖写入 config 模块（在 cli 启动前生效）。"""
    from . import config
    if args.capture_mode:
        config.CAPTURE_MODE = args.capture_mode
    if args.max_steps is not None:
        config.MAX_STEPS = args.max_steps
    if args.model:
        config.LLM_MODEL = args.model


def main_entry() -> int:
    """主入口；返回退出码。"""
    parser = _build_parser()
    args = parser.parse_args()

    # 应用配置覆盖
    if any([args.capture_mode, args.max_steps is not None, args.model]):
        _apply_overrides(args)

    # MCP Server (M4 占位)
    if args.mcp:
        try:
            from .mcp_server import run_mcp_server
        except ImportError:
            print("MCP Server is not yet implemented (planned for M4).", file=sys.stderr)
            return 1
        return run_mcp_server()

    # Replay (M4 占位)
    if args.replay:
        try:
            from .replay import replay_session
        except ImportError:
            print("Replay is not yet implemented (planned for M4).", file=sys.stderr)
            return 1
        return replay_session(args.replay, dry_run=args.dry_run, verbose=args.verbose)

    # HTTP API 服务
    if args.serve:
        from .api import serve
        host = args.host or "127.0.0.1"
        port = args.port or 2024
        try:
            serve(host=host, port=port)
        except RuntimeError as e:
            print(f"Failed to start API server: {e}", file=sys.stderr)
            return 1
        return 0

    # CLI / REPL
    from .cli import main as cli_main
    task = " ".join(args.task) if args.task else None
    if task:
        # 快捷任务模式：构造 sys.argv 模拟 cli.main 的处理
        # cli.main() 已经会检测 sys.argv
        return cli_main(task_arg=task, verbose=args.verbose, plain=args.plain,
                        no_color=args.no_color, dry_run=args.dry_run)
    return cli_main(verbose=args.verbose, plain=args.plain,
                    no_color=args.no_color, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main_entry())
