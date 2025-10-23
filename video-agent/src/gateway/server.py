"""
FastAPI 服务器 - 同时提供 API 和静态前端文件
开发环境通过反向代理到前端开发服务器
"""

from pathlib import Path
from fastapi import FastAPI, APIRouter, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
import json
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import httpx
import os
import asyncio

# 创建 FastAPI 应用
app = FastAPI(
    title="Video Agent API",
    description="视频代理服务 - API 和前端",
    version="0.1.0"
)

# CORS 配置（开发环境需要）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # React 开发服务器
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 创建 API 路由
api_router = APIRouter(prefix="/api")

# 导入API路由
from agent.api import chat, video_analysis, video_generate
from agent.api.sse import register_connection, unregister_connection

# 注意：各模块路由已自带 "/api/..." 前缀，避免重复挂载到 api_router('/api') 下
# 仅在此文件中直接把这些路由挂到 app（见下方 app.include_router(...)）

# 连接在每次请求内注册

@api_router.get("/events/{session_id}")
async def stream_events(session_id: str):
    """SSE事件流端点"""
    
    async def event_generator():
        # 注册一个新的连接队列
        connection_queue = register_connection(session_id)
        
        try:
            # 发送连接确认
            yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"
            
            # 保持连接活跃，发送心跳
            while True:
                try:
                    # 等待消息或超时
                    message = await asyncio.wait_for(connection_queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(message)}\n\n"
                except asyncio.TimeoutError:
                    # 发送心跳
                    yield f"data: {json.dumps({'type': 'ping', 'timestamp': asyncio.get_event_loop().time()})}\n\n"
                except Exception as e:
                    print(f"SSE连接错误: {e}")
                    break
                    
        finally:
            # 清理连接
            unregister_connection(session_id, connection_queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


@api_router.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "ok", "message": "Video Agent API is running"}


@api_router.get("/videos")
async def list_videos():
    """获取视频列表"""
    return {
        "videos": [
            {"id": 1, "title": "示例视频1", "duration": "2:30"},
            {"id": 2, "title": "示例视频2", "duration": "1:45"},
        ]
    }

@api_router.get("/generated_videos/{filename}")
async def get_generated_video(filename: str):
    """获取生成的视频文件"""
    project_root = Path(__file__).parent.parent.parent
    video_path = project_root / "src" / "agent" / "tools" / "generate" / "generated_videos" / filename
    
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="视频文件不存在")
    
    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=filename
    )



@api_router.post("/videos/process")
async def process_video(video_id: int):
    """处理视频"""
    return {
        "video_id": video_id,
        "status": "processing",
        "message": "视频处理已开始"
    }


# 注册 API 路由（仅注册此文件中定义的 /api 子路由）
app.include_router(api_router)

# 导入并注册视频生成 API（模块内已带 /api 前缀，直接挂载到 app）
try:
    from agent.api.video_generate import router as video_generate_router
    app.include_router(video_generate_router)
    print("✅ 视频生成 API 已注册")
except ImportError as e:
    print(f"⚠️  警告: 无法导入视频生成 API: {e}")

# 导入并注册视频识别 API（模块内已带 /api 前缀，直接挂载到 app）
try:
    from agent.api.video_analysis import router as video_analysis_router
    app.include_router(video_analysis_router)
    print("✅ 视频识别 API 已注册")
except ImportError as e:
    print(f"⚠️  警告: 无法导入视频识别 API: {e}")

# 导入并注册聊天 API（模块内已带 /api 前缀，直接挂载到 app）
try:
    from agent.api.chat import router as chat_router
    app.include_router(chat_router)
    print("✅ 聊天 API 已注册")
except ImportError as e:
    print(f"⚠️  警告: 无法导入聊天 API: {e}")

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 前端静态文件目录
FRONTEND_BUILD_DIR = PROJECT_ROOT / "src" / "frame" / "dist"

# 检查是否为开发模式（环境变量或前端构建目录不存在）
DEV_MODE = os.getenv("DEV_MODE", "true").lower() == "true" or not FRONTEND_BUILD_DIR.exists()
VITE_DEV_SERVER = "http://localhost:5173"

# HTTP 客户端（用于代理，禁用系统代理以访问本地 Vite 服务器）
http_client = httpx.AsyncClient(trust_env=False)

# 上下文清理器任务
cleaner_task = None


@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    import logging
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 设置特定模块的日志级别
    logging.getLogger('agent.tools.vision.video_analyzer').setLevel(logging.INFO)
    logging.getLogger('agent.api.video_analysis').setLevel(logging.INFO)
    logging.getLogger('agent.core.scheduler').setLevel(logging.INFO)
    logging.getLogger('agent.tools.generate').setLevel(logging.INFO)
    
    global cleaner_task
    
    print("🚀 启动 Video Agent 服务...")
    
    # 启动上下文清理器（30天清理，每24小时检查一次）
    try:
        from agent.context.cleaner import get_cleaner
        cleaner = get_cleaner(max_age_days=30, cleanup_interval_hours=24)
        
        # 启动定期清理任务
        cleaner_task = asyncio.create_task(cleaner.run_periodic_cleanup())
        print("✅ 上下文清理器已启动 (30天清理策略)")
    except Exception as e:
        print(f"⚠️  警告: 上下文清理器启动失败: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时执行"""
    global cleaner_task
    
    print("👋 关闭 Video Agent 服务...")
    
    # 关闭清理器任务
    if cleaner_task:
        cleaner_task.cancel()
        try:
            await cleaner_task
        except asyncio.CancelledError:
            pass
        print("✅ 上下文清理器已关闭")
    
    # 关闭HTTP客户端
    await http_client.aclose()


if DEV_MODE:
    # 开发模式：作为反向代理转发到 Vite 开发服务器（不重定向，端口保持 8000）
    @app.api_route("/{full_path:path}", methods=["GET"])
    async def proxy_to_vite(request: Request, full_path: str):
        """
        开发模式：所有非 /api 请求通过网关转发到 Vite 开发服务器
        - 不使用 3xx 重定向，保持在 8000 端口访问前端
        - 仅处理 GET 静态资源与页面请求
        """
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")

        target_url = f"{VITE_DEV_SERVER}/{full_path}" if full_path else VITE_DEV_SERVER
        if request.url.query:
            target_url = f"{target_url}?{request.url.query}"

        try:
            # 透传 headers 中与缓存/类型相关的关键头
            headers = {k: v for k, v in request.headers.items() if k.lower() in [
                "accept", "accept-encoding", "user-agent", "cache-control"
            ]}

            resp = await http_client.get(target_url, headers=headers)

            # 读取响应内容为字节，避免二次消费导致的 StreamConsumed
            content_bytes = await resp.aread()

            # 过滤不应透传的头
            excluded = {"content-encoding", "transfer-encoding", "connection"}
            response_headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}

            from fastapi.responses import Response
            return Response(
                content=content_bytes,
                status_code=resp.status_code,
                headers=response_headers,
                media_type=resp.headers.get("content-type")
            )
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Proxy to Vite failed: {e}")
else:
    # 生产模式：提供静态文件
    # 挂载静态资源（JS, CSS, 图片等）
    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_BUILD_DIR / "assets"),
        name="assets"
    )
    
    # 所有非 API 路径返回 index.html（用于 React Router）
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """
        生产模式：服务前端静态文件
        - /api/* 路径已经被 API 路由处理
        - 其他所有路径返回 index.html（支持 React Router）
        """
        # 如果请求的是具体文件（如 favicon.ico）
        file_path = FRONTEND_BUILD_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        
        # 否则返回 index.html
        return FileResponse(FRONTEND_BUILD_DIR / "index.html")


def start_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """启动服务器"""
    uvicorn.run(
        "gateway.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
        # 增加URL长度限制
        limit_max_requests=1000,
        limit_concurrency=1000,
        # 增加请求体大小限制
        limit_request_line=8192,  # 默认4096，增加到8192
        limit_request_fields=100,
        limit_request_field_size=8192
    )


if __name__ == "__main__":
    start_server(host="127.0.0.1", port=8000, reload=True)

