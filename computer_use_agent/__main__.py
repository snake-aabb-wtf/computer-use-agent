"""CLI 入口 - 支持交互式 REPL、快捷参数模式、HTTP API 模式"""

import sys
from .cli import main

if __name__ == "__main__":
    args = sys.argv[1:]

    # --serve / --api 启动 HTTP API 服务器
    if any(a in ("--serve", "--api") for a in args):
        from .api import serve
        host = "127.0.0.1"
        port = 2024
        for i, a in enumerate(args):
            if a in ("--host", "-h") and i + 1 < len(args):
                host = args[i + 1]
            if a in ("--port", "-p") and i + 1 < len(args):
                port = int(args[i + 1])
        serve(host=host, port=port)
    else:
        main()
