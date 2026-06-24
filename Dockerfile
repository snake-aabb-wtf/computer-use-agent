# ── 阶段 1: 依赖安装 ──
FROM python:3.12-slim AS builder

WORKDIR /build

# 系统依赖（用于构建某些 wheel）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libxcb1-dev \
    libxcb-xinerama0-dev \
    libxcb-cursor0-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt pyproject.toml ./
COPY computer_use_agent/ ./computer_use_agent/

# 构建 wheel
RUN pip wheel --no-cache-dir --wheel-dir /wheels .

# ── 阶段 2: 运行时镜像 ──
FROM python:3.12-slim

LABEL org.opencontainers.image.title="computer-use-agent"
LABEL org.opencontainers.image.description="AI-powered desktop automation through screenshots and actions"
LABEL org.opencontainers.image.source="https://github.com/snake-aabb-wtf/computer-use-agent"
LABEL org.opencontainers.image.licenses="MIT"

# Linux 桌面支持
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    xdotool \
    scrot \
    libxcb1 \
    libxcb-xinerama0 \
    libxcb-cursor0 \
    fonts-noto-cjk \
    tini \
    && rm -rf /var/lib/apt/lists/*

# 非 root 用户运行（安全）
RUN useradd -m -u 1000 cua
WORKDIR /home/cua

# 从 builder 阶段复制 wheel
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir \
    /wheels/computer_use_agent-*.whl \
    /wheels/openai-*.whl \
    /wheels/pillow-*.whl \
    /wheels/rich-*.whl \
    /wheels/prompt_toolkit-*.whl \
    /wheels/python_dotenv-*.whl \
    /wheels/pydantic_settings-*.whl \
    /wheels/mss-*.whl \
    /wheels/pyautogui-*.whl \
    && rm -rf /wheels

# 配置目录（用户可挂载）
RUN mkdir -p /home/cua/.config/cua/plugins \
    /home/cua/.cua/plugins \
    /home/cua/.cua/logs \
    /home/cua/.cua/screenshots
ENV CUA_HOME=/home/cua

# 默认环境
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DISPLAY=:99

# 切换到非 root 用户
USER cua
WORKDIR /home/cua

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD cua --help > /dev/null || exit 1

# 入口点：xvfb-run 包装（提供虚拟 X display）
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["xvfb-run", "-a", "-s", "-screen 0 1920x1080x24", "cua"]

# 暴露 HTTP API 端口
EXPOSE 2024
