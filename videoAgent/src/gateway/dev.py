"""
开发环境启动脚本 - 同时运行 Python 后端和 React 前端
"""

import subprocess
import sys
import time
import signal
from pathlib import Path
from typing import List

# 颜色输出
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_colored(message: str, color: str = Colors.GREEN):
    """彩色打印"""
    print(f"{color}{message}{Colors.END}")


class DevServer:
    """开发服务器管理器"""
    
    def __init__(self):
        self.processes: List[subprocess.Popen] = []
        self.project_root = Path(__file__).parent.parent.parent
        self.frontend_dir = self.project_root / "src" / "frame"
        
    def start_backend(self):
        """启动 Python 后端"""
        print_colored("\n🚀 启动 Python 后端服务器...", Colors.CYAN)
        print_colored("   访问地址: http://127.0.0.1:8000", Colors.BLUE)
        print_colored("   API 文档: http://127.0.0.1:8000/docs", Colors.BLUE)
        
        # 启动 FastAPI 服务器
        backend_process = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "gateway.server:app",
                "--host", "127.0.0.1",
                "--port", "8000",
                "--reload"
            ],
            cwd=self.project_root / "src",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        self.processes.append(backend_process)
        return backend_process
    
    def start_frontend(self):
        """启动 React 前端开发服务器"""
        if not self.frontend_dir.exists():
            print_colored(f"\n❌ 前端目录不存在: {self.frontend_dir}", Colors.RED)
            print_colored("   请先创建 React 项目到 src/frame 目录", Colors.YELLOW)
            return None
        
        if not (self.frontend_dir / "node_modules").exists():
            print_colored("\n📦 检测到前端依赖未安装，正在安装...", Colors.YELLOW)
            subprocess.run(["npm", "install"], cwd=self.frontend_dir, check=True)
        
        print_colored("\n🚀 启动 React 前端开发服务器...", Colors.CYAN)
        print_colored("   访问地址: http://localhost:5173", Colors.BLUE)
        print_colored("   API 代理到: http://127.0.0.1:8000/api", Colors.BLUE)
        
        # 启动 Vite 开发服务器
        frontend_process = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=self.frontend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        self.processes.append(frontend_process)
        return frontend_process
    
    def print_output(self, process: subprocess.Popen, prefix: str, color: str):
        """打印进程输出"""
        try:
            for line in process.stdout:
                print(f"{color}[{prefix}]{Colors.END} {line.rstrip()}")
        except Exception as e:
            print_colored(f"[{prefix}] 进程已结束: {e}", Colors.YELLOW)
    
    def cleanup(self, signum=None, frame=None):
        """清理所有子进程"""
        print_colored("\n\n🛑 正在关闭所有服务...", Colors.YELLOW)
        
        for process in self.processes:
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            except Exception as e:
                print_colored(f"关闭进程时出错: {e}", Colors.RED)
        
        print_colored("✅ 所有服务已关闭", Colors.GREEN)
        sys.exit(0)
    
    def run(self):
        """运行开发服务器"""
        # 注册信号处理
        signal.signal(signal.SIGINT, self.cleanup)
        signal.signal(signal.SIGTERM, self.cleanup)
        
        print_colored("=" * 60, Colors.HEADER)
        print_colored("🎬 Video Agent 开发环境", Colors.HEADER + Colors.BOLD)
        print_colored("=" * 60, Colors.HEADER)
        
        # 启动后端
        backend = self.start_backend()
        time.sleep(2)  # 等待后端启动
        
        # 启动前端
        frontend = self.start_frontend()
        
        if not frontend:
            print_colored("\n⚠️  仅后端服务已启动", Colors.YELLOW)
            print_colored("=" * 60, Colors.HEADER)
        else:
            time.sleep(2)
            print_colored("\n" + "=" * 60, Colors.HEADER)
            print_colored("✅ 所有服务已启动！", Colors.GREEN + Colors.BOLD)
            print_colored("=" * 60, Colors.HEADER)
            print_colored("\n📝 开发提示:", Colors.CYAN)
            print_colored("   • 前端访问: http://localhost:5173", Colors.BLUE)
            print_colored("   • 后端 API: http://127.0.0.1:8000/api", Colors.BLUE)
            print_colored("   • API 文档: http://127.0.0.1:8000/docs", Colors.BLUE)
            print_colored("   • 按 Ctrl+C 停止所有服务\n", Colors.YELLOW)
        
        # 等待进程
        try:
            for process in self.processes:
                process.wait()
        except KeyboardInterrupt:
            self.cleanup()


def main():
    """主函数"""
    server = DevServer()
    server.run()


if __name__ == "__main__":
    main()

