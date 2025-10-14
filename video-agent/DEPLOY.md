# 部署指南

## 开发环境

### 快速启动

```bash
# 方式1: 使用启动脚本（推荐）
chmod +x dev.sh
./dev.sh

# 方式2: 手动启动
# 1. 安装 Python 依赖
pip install -e .

# 2. 运行开发服务器
python src/gateway/dev.py
```

这会同时启动：
- **Python 后端**: http://127.0.0.1:8000
  - API 文档: http://127.0.0.1:8000/docs
  - 健康检查: http://127.0.0.1:8000/api/health
  
- **React 前端**: http://localhost:5173
  - 开发服务器，支持热更新
  - 自动代理 `/api` 请求到后端

### 架构说明

```
┌─────────────────────────────────────┐
│  浏览器访问: http://localhost:5173  │
└────────────┬────────────────────────┘
             │
             ▼
    ┌────────────────┐
    │  Vite Dev Server │ (端口 5173)
    │  React 前端      │
    └────────┬───────┘
             │
             │ /api/* 请求代理
             ▼
    ┌────────────────┐
    │  FastAPI Server │ (端口 8000)
    │  Python 后端    │
    └────────────────┘
```

## 生产环境

### 构建

```bash
# 使用构建脚本
chmod +x build.sh
./build.sh

# 或手动构建
cd src/frame
npm install
npm run build
cd ../..
pip install -e .
```

### 启动生产服务器

```bash
# 从 src 目录启动
cd src
python -m uvicorn gateway.server:app --host 0.0.0.0 --port 8000

# 或使用 gunicorn (推荐用于生产)
pip install gunicorn
cd src
gunicorn gateway.server:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### 生产环境架构

```
┌─────────────────────────────────────┐
│  浏览器访问: http://your-domain.com │
└────────────┬────────────────────────┘
             │
             ▼
    ┌────────────────────┐
    │  Nginx (可选)       │  反向代理 & SSL
    └────────┬───────────┘
             │
             ▼
    ┌────────────────────┐
    │  FastAPI Server    │  (端口 8000)
    │  ┌──────────────┐  │
    │  │ /api/*       │──┼──> Python API
    │  │ 其他路径     │──┼──> React 静态文件 (src/frame/dist)
    │  └──────────────┘  │
    └────────────────────┘
```

### Nginx 配置示例（可选）

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 可选：单独处理静态文件
    location /assets {
        alias /path/to/videoAgent/src/frame/dist/assets;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

## Docker 部署（推荐）

### Dockerfile 示例

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# 安装 Node.js (用于构建前端)
RUN apt-get update && apt-get install -y nodejs npm

# 复制项目文件
COPY . .

# 构建前端
WORKDIR /app/src/frame
RUN npm install && npm run build

# 安装 Python 依赖
WORKDIR /app
RUN pip install --no-cache-dir -e .

# 暴露端口
EXPOSE 8000

# 启动服务
WORKDIR /app/src
CMD ["uvicorn", "gateway.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 构建和运行 Docker

```bash
# 构建镜像
docker build -t video-agent .

# 运行容器
docker run -p 8000:8000 video-agent
```

## 环境变量

创建 `.env` 文件：

```bash
# 应用配置
DEBUG=False
LOG_LEVEL=INFO

# API 配置
API_HOST=0.0.0.0
API_PORT=8000

# 其他配置...
```

## 监控和日志

### 查看日志

```bash
# 开发环境
# 日志直接输出到控制台

# 生产环境（使用 systemd）
sudo journalctl -u video-agent -f
```

### 性能监控

推荐使用：
- **Prometheus + Grafana** - 指标监控
- **Sentry** - 错误追踪
- **ELK Stack** - 日志分析

## 故障排查

### 前端无法访问

1. 检查前端是否已构建：`ls -la src/frame/dist`
2. 检查后端配置：确认 `FRONTEND_BUILD_DIR` 路径正确
3. 查看后端日志

### API 请求失败

1. 访问 http://127.0.0.1:8000/docs 查看 API 文档
2. 检查 CORS 配置
3. 确认 API 路由是否正确注册

### 端口被占用

```bash
# 查找占用端口的进程
lsof -i :8000
lsof -i :5173

# 杀死进程
kill -9 <PID>
```

## 安全建议

1. **使用 HTTPS**: 配置 SSL 证书
2. **设置防火墙**: 只开放必要端口
3. **环境变量**: 敏感信息不要硬编码
4. **定期更新**: 保持依赖包最新
5. **日志审计**: 记录重要操作

