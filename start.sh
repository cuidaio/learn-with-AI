#!/usr/bin/env bash
# learn-with-AI 启动助手（macOS / Linux）
# 用法：chmod +x start.sh && ./start.sh

set -e

COMPOSE_PROJECT_NAME="learn-with-ai"

echo "============================================"
echo "       learn-with-AI  启动助手"
echo "============================================"
echo

# ── 1. 检查 .env ──
if [ ! -f ".env" ]; then
    echo "[提示] 未找到 .env，正在从模板复制..."
    cp .env.example .env
    echo
    echo "[重要] 请用编辑器打开 .env，填入你自己的："
    echo "       - EMBEDDING_BASE_URL / EMBEDDING_API_KEY / EMBEDDING_MODEL"
    echo "       - LLM_BASE_URL       / LLM_API_KEY       / LLM_MODEL"
    echo
    echo "填好后重新运行本脚本。"
    exit 1
fi

# ── 2. 检查 Docker CLI 是否安装 ──
if ! command -v docker >/dev/null 2>&1; then
    echo "[ERROR] Docker not installed. Download Docker Desktop first:"
    echo "        https://www.docker.com/products/docker-compose/"
    exit 1
fi

# ── 3. 检查 Docker daemon 是否运行 ──
if ! docker version >/dev/null 2>&1; then
    echo "[ERROR] Docker is installed but not running."
    echo "        Please start Docker Desktop, wait until it says \"Docker is running\", then re-run this script."
    exit 1
fi

# ── 3. 自动选择 compose 命令（v2 优先，回退 v1） ──
if docker compose version >/dev/null 2>&1; then
    COMPOSE="docker compose"
elif docker-compose version >/dev/null 2>&1; then
    COMPOSE="docker-compose"
else
    echo "[错误] 未检测到 docker compose 插件。"
    exit 1
fi

echo "[启动] 正在拉取镜像并构建（首次约数分钟）..."
$COMPOSE up -d || {
    echo
    echo "[错误] 启动失败，请检查上方日志。常见原因："
    echo "       - .env 中的 API Key 无效"
    echo "       - 端口 5173 / 7480 / 5432 / 6379 被占用"
    exit 1
}

echo
echo "============================================"
echo " 启动完成！请在浏览器打开："
echo
echo "   前端 : http://localhost:5173"
echo "   后端 : http://localhost:7480"
echo "   文档 : http://localhost:7480/docs"
echo "============================================"
echo
echo "查看日志：$COMPOSE logs -f backend"
echo "停止服务：$COMPOSE down"
