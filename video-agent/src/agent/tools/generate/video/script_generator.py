"""
脚本调用视频生成器
通过直接调用Python脚本来生成视频
"""

import asyncio
import subprocess
import json
import tempfile
import os
import uuid
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ScriptConfig:
    """脚本生成器配置"""
    script_path: str  # Python脚本路径
    python_executable: str = "python3"  # Python解释器路径（默认使用 python3）
    working_directory: Optional[str] = None  # 工作目录
    timeout: int = 900  # 超时时间（秒）
    environment: Optional[Dict[str, str]] = None  # 环境变量


class ScriptVideoGenerator:
    """
    脚本调用视频生成器
    通过执行Python脚本来生成视频
    """
    
    def __init__(self, config: ScriptConfig):
        """
        初始化生成器
        
        Args:
            config: 脚本生成器配置
        """
        self.config = config
        self.script_path = Path(config.script_path)
        
        if not self.script_path.exists():
            raise FileNotFoundError(f"脚本文件不存在: {self.script_path}")
    
    async def generate_video(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        duration: int = 5,
        resolution: str = "720p",
        seed: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        生成视频
        
        Args:
            prompt: 视频描述文本
            aspect_ratio: 宽高比 (16:9, 9:16等)
            duration: 时长（秒）
            resolution: 分辨率 (720p, 1080p)
            seed: 随机种子（可选）
            **kwargs: 其他参数
        
        Returns:
            {
                "success": bool,
                "submit_id": str,      # 提交ID，用于查询状态
                "message": str,
                "video_path": str,     # 生成的视频路径
                "raw_response": dict
            }
        """
        submit_id = str(uuid.uuid4())
        
        # 构建脚本参数
        script_args = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "duration": duration,
            "resolution": resolution,
            "seed": seed,
            "submit_id": submit_id,
            **kwargs
        }
        
        # 创建临时参数文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(script_args, f, ensure_ascii=False, indent=2)
            temp_args_file = f.name
        
        try:
            # 构建命令
            cmd = [
                self.config.python_executable,
                str(self.script_path),
                "--args-file", temp_args_file
            ]
            
            # 设置工作目录
            working_dir = self.config.working_directory or self.script_path.parent
            
            # 设置环境变量
            env = os.environ.copy()
            if self.config.environment:
                env.update(self.config.environment)
            
            print(f"执行脚本命令: {' '.join(cmd)}")
            print(f"工作目录: {working_dir}")
            print(f"参数文件: {temp_args_file}")
            
            # 执行脚本
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=working_dir,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                # 等待脚本完成
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.config.timeout
                )
                
                # 解码输出
                stdout_text = stdout.decode('utf-8') if stdout else ""
                stderr_text = stderr.decode('utf-8') if stderr else ""
                
                print(f"脚本输出: {stdout_text}")
                if stderr_text:
                    print(f"脚本错误: {stderr_text}")
                
                if process.returncode == 0:
                    # 脚本执行成功，解析输出
                    try:
                        result = json.loads(stdout_text.strip())
                        
                        return {
                            "success": True,
                            "submit_id": submit_id,
                            "message": "视频生成成功",
                            "video_path": result.get("video_path", ""),
                            "raw_response": {
                                "script_output": stdout_text,
                                "script_result": result
                            }
                        }
                    except json.JSONDecodeError:
                        # 如果不是JSON格式，返回原始输出
                        return {
                            "success": True,
                            "submit_id": submit_id,
                            "message": "视频生成完成",
                            "video_path": stdout_text.strip(),
                            "raw_response": {
                                "script_output": stdout_text,
                                "script_stderr": stderr_text
                            }
                        }
                else:
                    return {
                        "success": False,
                        "submit_id": submit_id,
                        "message": f"脚本执行失败 (退出码: {process.returncode})",
                        "error": stderr_text or stdout_text,
                        "raw_response": {
                            "script_output": stdout_text,
                            "script_stderr": stderr_text,
                            "return_code": process.returncode
                        }
                    }
                    
            except asyncio.TimeoutError:
                # 超时，终止进程
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                
                return {
                    "success": False,
                    "submit_id": submit_id,
                    "message": f"脚本执行超时 ({self.config.timeout}秒)",
                    "error": "脚本执行超时",
                    "raw_response": {
                        "timeout": self.config.timeout
                    }
                }
                
        except Exception as e:
            return {
                "success": False,
                "submit_id": submit_id,
                "message": f"脚本调用失败: {str(e)}",
                "error": str(e),
                "raw_response": {
                    "exception": str(e)
                }
            }
        finally:
            # 清理临时文件
            try:
                os.unlink(temp_args_file)
            except:
                pass
    
    async def get_video_status(self, submit_id: str) -> Dict[str, Any]:
        """
        查询视频生成状态
        对于脚本生成器，这个功能可能不适用，因为脚本通常是同步执行的
        
        Args:
            submit_id: 提交ID
        
        Returns:
            {
                "success": bool,
                "status": str,         # completed, failed
                "message": str,
                "raw_response": dict
            }
        """
        # 对于脚本生成器，我们假设视频生成是同步的
        # 如果需要异步状态查询，可以在这里实现
        return {
            "success": True,
            "status": "completed",
            "message": "脚本生成器不支持异步状态查询",
            "raw_response": {
                "submit_id": submit_id,
                "note": "脚本生成器通常同步执行"
            }
        }


# 示例脚本模板
def create_example_script(script_path: str):
    """
    创建一个示例视频生成脚本
    
    Args:
        script_path: 脚本保存路径
    """
    script_content = '''#!/usr/bin/env python3
"""
示例视频生成脚本
这个脚本展示了如何接收参数并生成视频
"""

import argparse
import json
import sys
import os
from pathlib import Path


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="视频生成脚本")
    parser.add_argument("--args-file", required=True, help="参数JSON文件路径")
    
    args = parser.parse_args()
    
    # 读取参数
    try:
        with open(args.args_file, 'r', encoding='utf-8') as f:
            params = json.load(f)
    except Exception as e:
        print(f"错误: 无法读取参数文件: {e}", file=sys.stderr)
        sys.exit(1)
    
    # 提取参数
    prompt = params.get("prompt", "")
    aspect_ratio = params.get("aspect_ratio", "16:9")
    duration = params.get("duration", 5)
    resolution = params.get("resolution", "720p")
    seed = params.get("seed")
    submit_id = params.get("submit_id", "")
    
    print(f"开始生成视频:")
    print(f"  描述: {prompt}")
    print(f"  宽高比: {aspect_ratio}")
    print(f"  时长: {duration}秒")
    print(f"  分辨率: {resolution}")
    print(f"  种子: {seed}")
    print(f"  提交ID: {submit_id}")
    
    # 这里应该实现实际的视频生成逻辑
    # 例如调用其他视频生成库或API
    
    # 模拟视频生成过程
    import time
    time.sleep(1)  # 模拟准备时间
    
    # 生成输出视频路径（示例）
    output_dir = Path("generated_videos")
    output_dir.mkdir(exist_ok=True)
    video_filename = f"video_{submit_id}.mp4"
    video_path = output_dir / video_filename
    
    # 生成一个可播放的黑屏示例视频（优先用 moviepy）
    try:
        from moviepy.editor import VideoClip
        import numpy as np
        from PIL import Image, ImageDraw, ImageFont
        width, height = (1280, 720)
        if isinstance(resolution, str):
            if resolution == "1080p":
                width, height = (1920, 1080)
            elif resolution == "720p":
                width, height = (1280, 720)
            elif resolution == "480p":
                width, height = (854, 480)
        dur = float(duration)
        # 文本换行
        def wrap_text(text, max_chars=16):
            lines = []
            line = ''
            for ch in str(prompt):
                if len(line) >= max_chars and ch != ' ':
                    lines.append(line)
                    line = ch
                else:
                    line += ch
            if line:
                lines.append(line)
            return lines[:4]
        lines = wrap_text(prompt)

        # 优先加载系统字体；找不到则用默认字体
        try:
            font = ImageFont.truetype("Arial.ttf", size=36)
        except Exception:
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", size=36)
            except Exception:
                font = ImageFont.load_default()

        def make_frame(t: float):
            # 渐变背景
            bg = np.zeros((height, width, 3), dtype=np.uint8)
            g = int(40 + 60 * np.sin(2 * np.pi * t / max(dur, 0.1)))
            b = int(90 + 100 * np.cos(2 * np.pi * t / max(dur, 0.1)))
            bg[:, :, 1] = g
            bg[:, :, 2] = b

            # 用 PIL 绘制文字
            img = Image.fromarray(bg)
            draw = ImageDraw.Draw(img)
            # 半透明文本底板
            pad = 12
            line_h = font.size + 6
            total_h = line_h * len(lines)
            y0 = height // 2 - total_h // 2
            x0 = width // 10
            # 背板
            draw.rectangle([x0 - pad, y0 - pad, x0 + int(width*0.8), y0 + total_h + pad], fill=(0, 0, 0, 128))
            # 文本
            for i, text in enumerate(lines):
                draw.text((x0, y0 + i * line_h), text, font=font, fill=(255, 255, 255))
            return np.asarray(img)
        clip = VideoClip(make_frame, duration=dur)
        clip.write_videofile(
            str(video_path),
            fps=24,
            codec="libx264",
            audio=False,
            preset="ultrafast",
            verbose=False,
            logger=None
        )
    except Exception:
        # 尝试使用 imageio-ffmpeg 的内置 ffmpeg 生成黑屏视频
        try:
            import subprocess
            import shlex
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            width, height = (1280, 720)
            if isinstance(resolution, str):
                if resolution == "1080p":
                    width, height = (1920, 1080)
                elif resolution == "720p":
                    width, height = (1280, 720)
                elif resolution == "480p":
                    width, height = (854, 480)
            cmd = f'"{ffmpeg_exe}" -y -f lavfi -i color=black:s={width}x{height}:d={float(duration)} -pix_fmt yuv420p "{video_path}"'
            subprocess.run(shlex.split(cmd), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception:
            # 最后兜底：占位文件
            video_path.touch()
    
    # 输出结果（JSON格式）
    result = {
        "success": True,
        "video_path": str(video_path),
        "message": "视频生成成功",
        "metadata": {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "duration": duration,
            "resolution": resolution,
            "seed": seed,
            "submit_id": submit_id
        }
    }
    
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
'''
    
    script_path = Path(script_path)
    script_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    # 设置执行权限
    script_path.chmod(0o755)
    
    print(f"示例脚本已创建: {script_path}")


# 使用示例
if __name__ == "__main__":
    import asyncio
    
    async def test():
        # 创建示例脚本
        example_script = "example_video_generator.py"
        create_example_script(example_script)
        
        # 配置脚本生成器
        config = ScriptConfig(
            script_path=example_script,
            python_executable="python3",
            timeout=60
        )
        
        generator = ScriptVideoGenerator(config)
        
        # 生成视频
        print("开始生成视频...")
        result = await generator.generate_video(
            prompt="一只可爱的小猫在草地上玩耍",
            aspect_ratio="16:9",
            duration=5,
            resolution="720p"
        )
        
        print(f"生成结果: {result}")
    
    asyncio.run(test())
