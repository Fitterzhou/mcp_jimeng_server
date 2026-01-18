# 🎨 Jimeng API MCP Server (即梦 MCP 服务器)

这是一个基于 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) 标准构建的中间件服务器。它将 **即梦 (Jimeng)** 的强大 AI 绘图和视频生成能力封装为标准工具，允许你在 **Cherry Studio**、**Claude Desktop** 或 **n8n** 等支持 MCP 的客户端中直接调用。

---

## ✨ 核心功能

1.  **🖼️ 文生图 (Jimeng-4.5)**: 支持 `1k`, `2k` (默认), `4k` 全画质，支持 8 种常用比例。
2.  **🎬 文生视频 (Jimeng-Video-3.0)**: 支持文生视频、图生视频（首帧）。
3.  **✍️ 智能排版**: 内置“小林漫画”风格文字排版，自动加白边并配文。
4.  **🧹 自动维护**: 内置每 12 小时自动清理任务，删除超过 24 小时的临时文件。
5.  **🛡️ 安全连接**: 完美适配 SSE 模式，解决 Docker/云服务器下的 Host/Origin 跨域问题。

---

## 🛠️ 部署指南

### 1. 准备工作

确保安装 Python 3.10+。

```bash
# 拉取代码
git clone [https://github.com/你的用户名/mcp_jimeng_server.git](https://github.com/你的用户名/mcp_jimeng_server.git)
cd mcp_jimeng_server

# 安装依赖
pip install -r requirements.txt

### 2. 配置环境变量
新建 .env 文件（不要上传到 GitHub），填入以下内容：

Ini, TOML

# 服务配置
SERVER_PORT=9007
# 本地填 127.0.0.1，云服务器填公网 IP
SERVER_HOST_URL=[http://127.0.0.1:9007](http://127.0.0.1:9007)

# API 配置
JIMENG_BASE_URL=[https://jm.a380.top](https://jm.a380.top)
JIMENG_API_KEY=sk-你的密钥

# 字体路径
FONT_PATH=handwriting.ttf
### 3. 启动服务
Bash

# 本地启动
python mcp_jimeng.py

# 云服务器后台运行
nohup python3 mcp_jimeng.py > output.log 2>&1 &

###🔌 客户端连接
🍒 Cherry Studio (推荐)
设置 -> MCP 服务器 -> 添加。

类型选择 Remote (SSE)。

地址填写：http://你的IP:9007/sse。

### 🤖 n8n
使用 mcp client 节点调用：

Endpoint: http://你的IP:9007/sse。

类型选择 Remote (SSE)。

Authorization: none

### 📐 支持的分辨率列表
支持 quality (1k/2k/4k) 和 ratio 参数。
比例,1k 分辨率,2k 分辨率 (默认),4k 分辨率
1:1,1024x1024,2048x2048,4096x4096
16:9,1024x576,2560x1440,5120x2880
9:16,576x1024,1440x2560,2880x5120
4:3,768x1024,2304x1728,4608x3456