"""
FastAPI 服务器 - 同时提供 API 和静态前端文件
开发环境通过反向代理到前端开发服务器
"""

from pathlib import Path
from fastapi import FastAPI, APIRouter, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import httpx
import os

# 创建 FastAPI 应用
app = FastAPI(
    title="Video Agent API",
    description="视频代理服务 - API 和前端",
    version="0.1.0"
)

# CORS 配置（开发环境需要）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React 开发服务器
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 创建 API 路由
api_router = APIRouter(prefix="/api")


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


@api_router.post("/videos/process")
async def process_video(video_id: int):
    """处理视频"""
    return {
        "video_id": video_id,
        "status": "processing",
        "message": "视频处理已开始"
    }


# 注册 API 路由
app.include_router(api_router)

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 前端静态文件目录
FRONTEND_BUILD_DIR = PROJECT_ROOT / "src" / "frame" / "dist"

# 检查是否为开发模式（环境变量或前端构建目录不存在）
DEV_MODE = os.getenv("DEV_MODE", "true").lower() == "true" or not FRONTEND_BUILD_DIR.exists()
VITE_DEV_SERVER = "http://localhost:5173"

# HTTP 客户端（用于代理，禁用系统代理以访问本地 Vite 服务器）
http_client = httpx.AsyncClient(trust_env=False)


if DEV_MODE:
    # 开发模式：代理到 Vite 开发服务器
    @app.get("/{full_path:path}")
    async def proxy_to_vite(request: Request, full_path: str):
        """
        开发模式：代理所有非 /api 请求到 Vite 开发服务器
        """
        # 构建目标 URL
        target_url = f"{VITE_DEV_SERVER}/{full_path}"
        if request.url.query:
            target_url = f"{target_url}?{request.url.query}"
        
        try:
            # 转发请求到 Vite 开发服务器
            response = await http_client.request(
                method=request.method,
                url=target_url,
                headers={
                    key: value for key, value in request.headers.items()
                    if key.lower() not in ["host", "connection"]
                },
                content=await request.body() if request.method in ["POST", "PUT", "PATCH"] else None,
            )
            
            # 返回响应
            return StreamingResponse(
                response.aiter_bytes(),
                status_code=response.status_code,
                headers={
                    key: value for key, value in response.headers.items()
                    if key.lower() not in ["content-encoding", "content-length", "transfer-encoding", "connection"]
                },
            )
        except Exception as e:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "前端开发服务器未启动",
                    "message": f"无法连接到 {VITE_DEV_SERVER}",
                    "detail": str(e),
                    "hint": "请在另一个终端运行: cd src/frame && npm run dev"
                }
            )
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
        log_level="info"
    )


if __name__ == "__main__":
    start_server(host="127.0.0.1", port=8000, reload=True)

