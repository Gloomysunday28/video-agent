# 🎬 Video Agent

视频代理服务 - 同时提供 Python FastAPI 后端和 React 前端，使用同一端口通过 `/api` 区分路由。

## ✨ 特性

- 🚀 **Python FastAPI 后端** - 高性能异步 API 服务
- ⚛️ **React + TypeScript 前端** - 现代化 Web 界面
- 🔄 **统一端口部署** - 生产环境使用同一端口，通过 `/api` 区分
- 🛠️ **开发环境热更新** - 前后端代码修改自动重载
- 📦 **一键启动** - 自动启动前后端开发服务器

## 🚀 快速开始

### 开发环境

```bash
# 一键启动（推荐）
./dev.sh

# 或者手动启动
pip install -e .
python src/gateway/dev.py
```

启动后访问：
- **前端页面**: http://localhost:5173
- **后端 API 文档**: http://127.0.0.1:8000/docs
- **健康检查**: http://127.0.0.1:8000/api/health

### 生产环境

```bash
# 构建前端和安装依赖
./build.sh

# 启动服务
cd src
python -m uvicorn gateway.server:app --host 0.0.0.0 --port 8000
```

生产环境访问：http://your-domain:8000

## 📁 项目结构

```
videoAgent/
├── src/
│   ├── gateway/              # 网关服务
│   │   ├── server.py        # FastAPI 服务器（同时提供 API 和静态文件）
│   │   └── dev.py           # 开发环境启动脚本
│   ├── frame/               # React 前端
│   │   ├── src/
│   │   │   ├── App.tsx      # 主应用组件
│   │   │   └── App.css      # 样式
│   │   ├── vite.config.ts   # Vite 配置（API 代理）
│   │   └── dist/            # 构建产物（生产环境）
│   └── video_agent/         # 视频处理模块
├── dev.sh                   # 开发环境启动脚本
├── build.sh                 # 生产构建脚本
├── DEPLOY.md               # 详细部署文档
└── pyproject.toml          # Python 项目配置
```

## 🏗️ 架构说明

### 开发环境
```
前端: http://localhost:5173 (Vite Dev Server)
  ↓ /api/* 代理
后端: http://127.0.0.1:8000 (FastAPI + uvicorn)
```

### 生产环境
```
浏览器 → http://your-domain:8000
          ├── /api/*     → FastAPI 后端处理
          └── 其他路径    → React 静态文件
```

## 🔧 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/videos` | 获取视频列表 |
| POST | `/api/videos/process` | 处理视频 |
| GET | `/docs` | Swagger API 文档 |

## 📚 更多文档

- [部署指南](./DEPLOY.md) - 详细的部署说明
- [API 文档](http://127.0.0.1:8000/docs) - 启动后端后访问

## 🛠️ 技术栈

**后端:**
- FastAPI - Web 框架
- Uvicorn - ASGI 服务器
- Pydantic - 数据验证

**前端:**
- React 19 - UI 框架
- TypeScript - 类型安全
- Vite - 构建工具

## 📝 开发指南

### 添加新 API

编辑 `src/gateway/server.py`:

```python
@api_router.get("/your-endpoint")
async def your_endpoint():
    return {"data": "your data"}
```

### 修改前端

编辑 `src/frame/src/App.tsx`，Vite 会自动热更新。

## 📄 许可证

MIT
