#!/bin/bash
# 生产环境构建脚本

set -e

echo "🏗️  构建 Video Agent 生产环境..."
cd "$(dirname "$0")"

# 构建前端
echo "📦 构建 React 前端..."
cd src/frame
npm install
npm run build
echo "✅ 前端构建完成: src/frame/dist"

# 返回根目录
cd ../..

# 安装 Python 依赖
echo "📦 安装 Python 依赖..."
pip install -e .

echo ""
echo "✅ 构建完成！"
echo ""
echo "启动生产服务器："
echo "  python -m uvicorn gateway.server:app --host 0.0.0.0 --port 8000"
echo ""
echo "或者使用："
echo "  cd src && python -m gateway.server"

