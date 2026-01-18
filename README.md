# 🎨 Jimeng API MCP Server (即梦 MCP 服务器)

这是一个基于 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) 标准构建的中间件服务器。它将 **即梦 (Jimeng)** 的强大 AI 绘图和视频生成能力封装为标准工具，允许你在 **Cherry Studio**、**Claude Desktop** 或 **n8n** 等支持 MCP 的客户端中直接调用。

---

## ✨ 核心功能

1. **🖼️ 文生图 (Jimeng-4.5)**: 支持 `1k`, `2k` (默认), `4k` 全画质，支持 8 种常用比例。
2. **🎬 文生视频 (Jimeng-Video-3.0)**: 支持文生视频、图生视频（首帧）。
3. **✍️ 智能排版**: 内置“小林漫画”风格文字排版，自动加白边并配文。
4. **🧹 自动维护**: 内置每 12 小时自动清理任务，删除超过 24 小时的临时文件。
5. **🛡️ 安全连接**: 完美适配 SSE 模式，解决 Docker/云服务器下的 Host/Origin 跨域问题。

---

## 🛠️ 部署指南

### 1. 准备工作

确保安装 Python 3.10+。

```bash
# 拉取代码
git clone [https://github.com/Fitterzhou/mcp_jimeng_server.git](https://github.com/Fitterzhou/mcp_jimeng_server.git)
cd mcp_jimeng_server

# 安装依赖
pip install -r requirements.txt

```

### 2. 配置环境变量

新建 `.env` 文件，填入以下内容：

```ini
# 服务配置
SERVER_PORT=9007
# 本地填 127.0.0.1，云服务器填公网 IP
SERVER_HOST_URL=http://127.0.0.1:9007

# API 配置
JIMENG_BASE_URL=
#“即梦接口”或者“你的API代理接口”

JIMENG_API_KEY=“xxxx....."
#“即梦API”,仅字符串

# 字体路径
FONT_PATH=handwriting.ttf
# 任何你想要的字体，改名为handwriting.ttf，上传在mcp_jimeng.py相同目录下
```

### 3. 启动服务

**本地启动：**

```bash
python mcp_jimeng.py

```

**云服务器后台运行：**

```bash
nohup python3 mcp_jimeng.py > output.log 2>&1 &

```
查看日志
tail -f output.log
```
---

## 🔌 客户端连接

### 🍒 Cherry Studio (推荐)

1. 进入 **设置** -> **MCP 服务器** -> **添加**。
2. 类型选择 `Remote (SSE)`。
3. 地址填写：`http://你的IP:9007/sse`。

### 🤖 n8n

使用 **MCP Client** 节点调用（或使用 HTTP Request）：

* **Endpoint**: `http://你的IP:9007/sse`
* **Type**: `Remote (SSE)`
* **Authorization**: `none`

---

## 📐 支持的分辨率列表

支持 `quality` (1k/2k/4k) 和 `ratio` 参数。

| 比例 | 1k 分辨率 | 2k 分辨率 (默认) | 4k 分辨率 |
| --- | --- | --- | --- |
| **1:1** | 1024x1024 | 2048x2048 | 4096x4096 |
| **16:9** | 1024x576 | 2560x1440 | 5120x2880 |
| **9:16** | 576x1024 | 1440x2560 | 2880x5120 |
| **4:3** | 768x1024 | 2304x1728 | 4608x3456 |
| **3:4** | 1024x768 | 1728x2304 | 3456x4608 |

```

```