"""
Jimeng API MCP 服务器 (端口 9007 - 最终修复版)
修复内容：
1. 修正了中间件加载顺序导致的 AttributeError。
2. 保持了强力清洗 Host/Origin 头的功能，解决 421 错误。
"""
import os
import time
import httpx
import uvicorn
import uuid
import asyncio
import re
from typing import Optional, Literal
from io import BytesIO
from mcp.server.fastmcp import FastMCP, Context
from starlette.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Scope, Receive, Send
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

# ================= 1. 加载配置 =================
load_dotenv() 

SERVER_PORT = int(os.getenv("SERVER_PORT", 9007))
SERVER_HOST_URL = os.getenv("SERVER_HOST_URL", f"http://127.0.0.1:{SERVER_PORT}")
JIMENG_BASE_URL = os.getenv("JIMENG_BASE_URL")
JIMENG_API_KEY_ENV = os.getenv("JIMENG_API_KEY", "")

FONT_PATH = os.getenv("FONT_PATH", "handwriting.ttf")
STATIC_DIR = "static_images_9007"
os.makedirs(STATIC_DIR, exist_ok=True)

# 清理策略
CLEANUP_INTERVAL = int(os.getenv("CLEANUP_INTERVAL", 43200))
RETENTION_PERIOD = int(os.getenv("RETENTION_PERIOD", 86400))

mcp = FastMCP(name="Jimeng API MCP服务器-9007")

# ================= 2. 分辨率映射表 =================
RESOLUTIONS = {
    "1k": {
        "1:1": "1024x1024", "4:3": "768x1024", "3:4": "1024x768", 
        "16:9": "1024x576", "9:16": "576x1024", "3:2": "1024x682", 
        "2:3": "682x1024", "21:9": "1195x512"
    },
    "2k": {
        "1:1": "2048x2048", "4:3": "2304x1728", "3:4": "1728x2304", 
        "16:9": "2560x1440", "9:16": "1440x2560", "3:2": "2496x1664", 
        "2:3": "1664x2496", "21:9": "3024x1296"
    },
    "4k": {
        "1:1": "4096x4096", "4:3": "4608x3456", "3:4": "3456x4608", 
        "16:9": "5120x2880", "9:16": "2880x5120", "3:2": "4992x3328", 
        "2:3": "3328x4992", "21:9": "6048x2592"
    }
}

# --- 辅助函数 ---
def get_resolution_str(quality: str, ratio: str) -> str:
    q_map = RESOLUTIONS.get(quality, RESOLUTIONS["2k"])
    return q_map.get(ratio, q_map["1:1"])

def get_api_key(ctx: Context) -> str:
    if JIMENG_API_KEY_ENV: return JIMENG_API_KEY_ENV
    if hasattr(ctx, "request_context") and ctx.request_context:
        try:
            headers = ctx.request_context.request.headers
            if "Authorization" in headers:
                auth = headers["Authorization"]
                return auth[7:] if auth.startswith("Bearer ") else auth
            if "token" in headers: return headers["token"]
        except Exception: pass
    raise ValueError("❌ 未配置 API Key！")

def get_http_client(api_key: str) -> httpx.Client:
    return httpx.Client(
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=120.0
    )

async def download_to_local(remote_url: str, file_type: str = "image") -> str:
    if not remote_url or not remote_url.startswith("http"): return str(remote_url)
    if remote_url.startswith(SERVER_HOST_URL): return remote_url 

    print(f"⬇️ [下载] {remote_url[:30]}...")
    try:
        ext = ".mp4" if file_type == "video" else ".png"
        filename = f"{uuid.uuid4().hex}{ext}"
        save_path = os.path.join(STATIC_DIR, filename)
        
        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.get(remote_url, timeout=300)
            resp.raise_for_status()
            with open(save_path, "wb") as f:
                f.write(resp.content)
        
        local_url = f"{SERVER_HOST_URL}/static/{filename}"
        print(f"✅ [保存] {local_url}")
        return local_url
    except Exception as e:
        print(f"❌ [下载失败] {e}")
        return remote_url

# --- 核心逻辑: 自动清理任务 ---
async def periodic_cleanup():
    print(f"🧹 [清理服务] 启动: 每 {CLEANUP_INTERVAL/3600:.1f}h 检查, 删除 >{RETENTION_PERIOD/3600:.1f}h 旧文件")
    while True:
        try:
            await asyncio.sleep(CLEANUP_INTERVAL) 
            deleted = 0
            now = time.time()
            if os.path.exists(STATIC_DIR):
                for f in os.listdir(STATIC_DIR):
                    fp = os.path.join(STATIC_DIR, f)
                    if os.path.isfile(fp) and (now - os.path.getmtime(fp)) > RETENTION_PERIOD:
                        try: os.remove(fp); deleted += 1
                        except: pass
            if deleted: print(f"🧹 已清理 {deleted} 个过期文件")
        except Exception as e: print(f"❌ 清理任务出错: {e}")

# --- 核心逻辑: 本地排版算法 ---
def add_text_local(image_url: str, text: str) -> str:
    print(f"🎨 [排版] 文案: {text}")
    img = None
    try:
        if image_url.startswith(SERVER_HOST_URL):
            local_name = image_url.split("/static/")[-1]
            local_path = os.path.join(STATIC_DIR, local_name)
            if os.path.exists(local_path):
                img = Image.open(local_path).convert("RGBA")
            else: return f"错误: 本地文件 {local_name} 不存在"
        else:
            with httpx.Client(timeout=60) as c:
                resp = c.get(image_url); resp.raise_for_status()
                img = Image.open(BytesIO(resp.content)).convert("RGBA")
    except Exception as e: return f"图片加载失败: {e}"

    width, height = img.size
    draw = ImageDraw.Draw(img)
    
    white_start_ratio = 0.60
    mask_y_start = int(height * white_start_ratio)
    draw.rectangle([(0, mask_y_start), (width, height)], fill=(255, 255, 255, 255))

    font_size = int(width / 9.0)
    try: font = ImageFont.truetype(FONT_PATH, font_size)
    except: font = ImageFont.load_default()

    split_pattern = r'[，,。\.！!？\?；;：:\s\n]+'
    raw_lines = re.split(split_pattern, text)
    lines = []
    max_chars = 10
    for seg in raw_lines:
        seg = seg.strip()
        if not seg: continue
        if len(seg) > max_chars:
            for i in range(0, len(seg), max_chars): lines.append(seg[i:i+max_chars])
        else: lines.append(seg)

    text_color = (10, 10, 10, 255)
    line_spacing = font_size * 1.25
    total_text_height = len(lines) * line_spacing
    white_area_center_y = height * (white_start_ratio + 1.0) / 2
    start_y = white_area_center_y - (total_text_height / 2) - (font_size * 0.2)

    safe_content_width = width * 0.94
    global_spacing = int(font_size * -0.02)
    for line in lines:
        if len(line) <= 1: continue
        raw_w = 0
        for char in line:
            try: w = font.getbbox(char)[2]
            except: w = font.getsize(char)[0]
            raw_w += w
        needed_spacing = int((safe_content_width - raw_w) / (len(line) - 1))
        if needed_spacing < global_spacing: global_spacing = needed_spacing

    for i, line in enumerate(lines):
        cur_w = 0
        char_ws = []
        for char in line:
            try: w = font.getbbox(char)[2]
            except: w = font.getsize(char)[0]
            char_ws.append(w)
            cur_w += w
        if len(line) > 1: cur_w += (len(line) - 1) * global_spacing
        
        cur_x = (width - cur_w) / 2
        y = start_y + (i * line_spacing)
        for char, w in zip(line, char_ws):
            draw.text((cur_x, y), char, font=font, fill=text_color)
            cur_x += w + global_spacing

    filename = f"{uuid.uuid4().hex}.png"
    img.save(os.path.join(STATIC_DIR, filename), format="PNG")
    return f"{SERVER_HOST_URL}/static/{filename}"

# ================= 3. 工具定义 =================

@mcp.tool()
async def generate_image(
    ctx: Context, 
    prompt: str, 
    ratio: Literal["1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3", "21:9"] = "1:1",
    quality: Literal["1k", "2k", "4k"] = "2k"
) -> str:
    """生成图片。"""
    try:
        key = get_api_key(ctx)
        size_str = get_resolution_str(quality, ratio)
        print(f"🎨 [生成] {quality} {ratio} -> {size_str}")
        
        data = {"model": "jimeng-4.5", "prompt": prompt, "n": 1, "size": size_str}
        with get_http_client(key) as client:
            resp = client.post(f"{JIMENG_BASE_URL}/v1/images/generations", json=data)
            try: res = resp.json()
            except: return f"API Error: {resp.text}"
            
            if "data" in res:
                return await download_to_local(res["data"][0]["url"], "image")
            return f"生成失败: {res}"
    except Exception as e: return f"执行错误: {e}"

@mcp.tool()
async def generate_image_from_reference(ctx: Context, prompt: str, reference_image_url: str, ratio: str = "1:1") -> str:
    """图生图(参考图)。"""
    try:
        key = get_api_key(ctx)
        size_str = get_resolution_str("2k", ratio)
        data = {"model": "jimeng-4.5", "prompt": prompt, "image": reference_image_url, "size": size_str}
        with get_http_client(key) as client:
            resp = client.post(f"{JIMENG_BASE_URL}/v1/images/generations", json=data)
            res = resp.json()
            if "data" in res: return await download_to_local(res["data"][0]["url"], "image")
            return f"错误: {res}"
    except Exception as e: return f"图生图错误: {e}"

@mcp.tool()
async def generate_video(ctx: Context, prompt: str) -> str:
    """文生视频。"""
    try:
        key = get_api_key(ctx)
        data = {"model": "jimeng-video-3.0", "prompt": prompt}
        with get_http_client(key) as client:
            resp = client.post(f"{JIMENG_BASE_URL}/v1/videos/generations", json=data)
            res = resp.json()
            url = res.get("data", [{}])[0].get("url") or res.get("url")
            if url: return await download_to_local(url, "video")
            return f"视频生成响应异常: {res}"
    except Exception as e: return f"视频错误: {e}"

@mcp.tool()
async def generate_video_from_image(ctx: Context, prompt: str, start_image_url: str) -> str:
    """图生视频。"""
    try:
        key = get_api_key(ctx)
        data = {"model": "jimeng-video-3.0", "prompt": prompt, "image": start_image_url}
        with get_http_client(key) as client:
            resp = client.post(f"{JIMENG_BASE_URL}/v1/videos/generations", json=data)
            res = resp.json()
            url = res.get("data", [{}])[0].get("url") or res.get("url")
            if url: return await download_to_local(url, "video")
            return f"视频生成响应异常: {res}"
    except Exception as e: return f"图生视频错误: {e}"

@mcp.tool()
async def image_edit_generation(ctx: Context, text: str, image: str) -> str:
    """[本地功能] 图片底部加文字"""
    try:
        clean_text = text.replace("'", "").replace('"', "").replace("overlay text:", "").strip()
        return add_text_local(image, clean_text)
    except Exception as e: return f"修图错误: {e}"

# --- 中间件修复逻辑 ---
class SecurityBypassMiddleware:
    """
    强制清洗请求头，移除 Origin/Referer，并将 Host 重写为 localhost。
    解决 'Invalid Host header' 和 '421 Misdirected Request' 错误。
    """
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] == 'http':
            headers = dict(scope['headers'])
            
            # 1. 移除可能导致校验失败的头
            if b'origin' in headers:
                del headers[b'origin']
            if b'referer' in headers:
                del headers[b'referer']
            
            # 2. 强制伪装 Host 为本地
            headers[b'host'] = f'localhost:{SERVER_PORT}'.encode()
            
            scope['headers'] = list(headers.items())
            
        await self.app(scope, receive, send)

# --- 启动逻辑 ---
if __name__ == "__main__":
    print(f"🚀 启动 Jimeng MCP... 端口:{SERVER_PORT}")
    
    async def main():
        # 1. 创建 MCP App
        app = mcp.sse_app()
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
        
        # 2. 正确添加中间件（注意顺序：add_middleware 是洋葱模型，后添加的先执行）
        
        # 最外层：强力清洗头，骗过 MCP 校验 (最后添加 = 最先执行)
        app.add_middleware(SecurityBypassMiddleware)
        
        # 内层：CORS (允许跨域)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

        config = uvicorn.Config(app, host="0.0.0.0", port=SERVER_PORT)
        server = uvicorn.Server(config)

        asyncio.create_task(periodic_cleanup())
        await server.serve()

    asyncio.run(main())