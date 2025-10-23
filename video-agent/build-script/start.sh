#!/bin/bash
# 同端口启动脚本 - 8000端口同时服务前端和后端

echo "🚀 启动 Video Agent - 统一端口模式"

# 进入项目根目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "📁 项目目录: $PROJECT_ROOT"

# 确保依赖已安装
echo "📦 安装 Python 依赖..."
python3.13 -m pip install -e . -q

# 在后台启动 Vite 开发服务器
echo "🎨 启动前端开发服务器（端口 5173）..."
cd src/frame
npm run dev > /tmp/vite.log 2>&1 &
VITE_PID=$!
cd "$PROJECT_ROOT"

# 等待 Vite 启动
echo "⏳ 等待前端服务器启动..."
sleep 3

# 启动后端服务器（会代理前端请求）
echo ""
echo "🌐 启动后端服务器（端口 8000）..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ 统一访问地址: http://127.0.0.1:8000"
echo "  📡 API 端点: http://127.0.0.1:8000/api/*"
echo "  📄 API 文档: http://127.0.0.1:8000/docs"
echo "  🎨 前端页面: http://127.0.0.1:8000/"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  按 Ctrl+C 停止所有服务"
echo ""

# 捕获退出信号，清理进程
cleanup() {
    echo ""
    echo "🛑 正在停止所有服务..."
    kill $VITE_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# 启动后端
cd src
DEV_MODE=true python3.13 -m uvicorn gateway.server:app --host 127.0.0.1 --port 8000 --reload

