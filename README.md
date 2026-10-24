# 本地文档问答与检索 API

一个使用 Python、FastAPI、LangGraph 和 DeepSeek API 构建的本地文档问答示例项目。项目支持读取 TXT/PDF 资料、切分文本、生成向量索引，并通过语义检索为问题提供相关资料和来源。

## 功能特性

- 从 `data/` 读取 UTF-8 TXT 和 PDF 文档，并保留来源文件名、PDF 页码及文本块 ID。
- 使用 `BAAI/bge-small-zh-v1.5` 生成归一化向量，通过余弦相似度检索相关文本。
- 使用 LangGraph 编排 DeepSeek 模型与本地知识库检索工具。
- 提供 FastAPI 健康检查和问答接口，响应中包含引用来源及工具调用记录。
- 通过 MCP stdio 服务提供本地知识库检索和资料列表工具；FastAPI 进程启动时建立客户端连接并在服务期间复用。

## 技术栈

- Python 3.10+
- FastAPI、Uvicorn、Pydantic
- LangGraph、OpenAI Python SDK（通过 DeepSeek 兼容接口调用）
- Sentence Transformers、`BAAI/bge-small-zh-v1.5`
- pypdf

## 环境要求

- Python 3.10 或更高版本
- 用于问答生成的 DeepSeek API Key
- 首次生成向量或启动 API 时可联网下载嵌入模型

## 安装

在项目根目录创建并激活虚拟环境，然后安装依赖。

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## 配置 API Key

复制示例环境变量文件，并在 `.env` 中填写自己的 DeepSeek API Key。

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

macOS / Linux：

```bash
cp .env.example .env
```

编辑 `.env`：

```env
DEEPSEEK_KEY=your-deepseek-api-key
```

请勿将 `.env`、真实 API Key 或其他凭据提交到 Git。调用 DeepSeek API 可能产生费用，请留意服务商账户和计费设置。

## 添加资料并生成向量索引

将 `.txt` 或 `.pdf` 文件放入项目根目录下的 `data/` 文件夹，然后在项目根目录依次执行：

```powershell
python ingest_documents.py
python embed_chunks.py
```

macOS / Linux 使用相同命令。

处理流程：

1. `ingest_documents.py` 读取资料并生成 `chunks.jsonl`。PDF 按页提取文本，TXT 的页码记为 `null`。
2. `embed_chunks.py` 读取文本块并生成 `chunks_with_embeddings.jsonl`，供 MCP 服务启动时加载。

每次添加、删除或修改资料后，都需要重新运行这两个脚本。扫描版 PDF 通常没有可提取文本，请先进行 OCR。生成向量需要下载嵌入模型，首次运行可能需要一些时间。

## 启动 API

请先配置 `.env` 并生成非空的 `chunks_with_embeddings.jsonl`，再运行：

```powershell
python -m uvicorn api:app --reload
```

服务默认地址为 <http://127.0.0.1:8000>，交互式 API 文档为 <http://127.0.0.1:8000/docs>。

## 使用 Docker 启动

需要先安装并启动 Docker。Docker 镜像不包含个人资料、API 密钥或生成的向量索引；启动容器时会从挂载的 `data/` 读取 TXT/PDF，生成文本块和向量索引，再启动 API。首次启动需要联网下载嵌入模型，初始化完成后可访问 <http://127.0.0.1:8000/docs>。

在项目根目录构建镜像：

```powershell
docker build -t aglearn:local .
```

启动前请将至少一个可提取文本的 `.txt` 或 `.pdf` 文件放入 `data/`，并在项目根目录准备好配置了 `DEEPSEEK_KEY` 的 `.env` 文件。

### Windows PowerShell

```powershell
docker run --rm -p 8000:8000 `
  --env-file .env `
  --mount "type=bind,source=$((Resolve-Path .\data).Path),target=/app/data,readonly" `
  --mount "type=volume,source=aglearn-hf-cache,target=/root/.cache/huggingface" `
  aglearn:local
```

### macOS / Linux

```bash
docker run --rm -p 8000:8000 \
  --env-file .env \
  --mount "type=bind,source=$(pwd)/data,target=/app/data,readonly" \
  --mount "type=volume,source=aglearn-hf-cache,target=/root/.cache/huggingface" \
  aglearn:local
```

资料目录以只读方式挂载；生成的索引保存在容器内。每次启动都会根据挂载的资料重新生成索引。Hugging Face 缓存使用 Docker 命名卷保留，避免每次启动都重新下载嵌入模型。资料或 API Key 不会被打包进镜像。

### MCP 服务与客户端

项目使用 MCP 将本地检索能力作为工具提供给 Agent：

- `mcp_server.py` 是 MCP 服务端，以 stdio 方式运行，注册 `search_knowledge_base` 和 `search_list_base` 两个工具。服务端启动时调用 `load_vector_index()`，将向量索引加载到 MCP 子进程中；实际检索也在这个进程中执行。
- `api.py` 是 MCP 客户端的宿主。FastAPI lifespan 启动时会启动 `mcp_server.py` 子进程、建立 MCP 客户端连接，并通过 `list_tools()` 获取工具定义。
- 每个 FastAPI 进程在整个服务运行期间复用同一个 MCP 客户端连接和已获取的工具列表。每次 `/ask` 请求将它们传给 `LangGraph_run`，由 Agent 通过该客户端调用 MCP 工具；不会为每个请求重新启动 MCP 服务或重新连接。
- FastAPI 关闭时，lifespan 退出 MCP 客户端上下文，连接随之关闭，服务端子进程也结束。

因此，向量索引由 MCP 子进程加载，FastAPI API 进程本身不再加载一份向量索引。使用多个 Uvicorn worker 时，每个 worker 都有自己的 MCP 子进程和客户端连接。

### 健康检查

```http
GET /health
```

响应：

```json
{
  "status": "ok"
}
```

### 提交问题

```http
POST /ask
Content-Type: application/json
```

请求示例：

```json
{
  "question": "无人机农村配送面临哪些现实困境？",
  "expected_tools": ["search_knowledge_base"]
}
```

`expected_tools` 是可选字段，用于检查模型实际调用的工具；可用工具名为 `search_knowledge_base` 和 `search_list_base`。不传或设为 `null` 时不进行工具选择匹配检查。

成功响应示例：

```json
{
  "message": "成功获取回答。",
  "answer": "根据检索资料……",
  "sources": [
    {
      "chunk_id": 1,
      "filename": "资料.pdf",
      "page": 2
    }
  ],
  "tool_calls": [
    {
      "tool_call_id": "call_example",
      "name": "search_knowledge_base",
      "arguments": {
        "query": "无人机农村配送",
        "top_k": 3
      },
      "executed": true,
      "result_chunk_ids": [1]
    }
  ],
  "mismatch": false
}
```

`sources` 只列出本次检索得到的文本块；TXT 来源的 `page` 为 `null`。`tool_calls` 记录工具调用情况；`mismatch` 在未传入 `expected_tools` 时为 `null`，传入时表示实际工具调用与预期是否不一致。知识库检索默认返回 3 个文本块，`top_k` 支持 1 至 5。

PowerShell 调用示例：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/ask `
  -ContentType "application/json" `
  -Body '{"question":"无人机农村配送面临哪些现实困境？"}'
```

### 错误响应

- 问题为空或只包含空白字符时，接口返回请求校验错误。
- 向量索引缺失或没有文本块时，API 无法完成启动；请先执行资料处理步骤。
- Agent 或模型调用失败时，`/ask` 返回 HTTP 500，并在 `detail` 中提供错误信息。

## 项目结构

```text
.
├── data/
│   └── README.md                  # 资料目录说明；TXT/PDF 由用户自行添加
├── agent_graph.py                 # LangGraph Agent 与工具调用流程
├── api.py                         # FastAPI 应用与 API 路由
├── Dockerfile                     # Docker 镜像与容器启动配置
├── embed_chunks.py                # 文本块向量化
├── ingest_documents.py            # TXT/PDF 提取、清理与切分
├── mcp_server.py                  # MCP stdio 服务端与本地检索工具
├── vector_search.py               # 加载索引和语义检索
├── requirements.txt               # Python 依赖
├── .env.example                   # 环境变量示例
└── .dockerignore                  # Docker 构建上下文忽略规则
```

`chunks.jsonl`、`chunks_with_embeddings.jsonl` 和 `logs/` 都是运行时生成内容，不需要提交到 Git 或打包进 Docker 镜像。

## 常见问题

### 找不到 `DEEPSEEK_KEY`

确认项目根目录存在 `.env`，且其中配置了有效的 `DEEPSEEK_KEY`。不要将密钥直接写入代码或提交到仓库。

### 找不到向量索引或索引为空

确认 `data/` 中至少有一个包含可提取文本的 TXT/PDF 文件，并依次运行 `python ingest_documents.py` 和 `python embed_chunks.py`。向量索引由 API 启动的 MCP 子进程加载；如果索引缺失或为空，MCP 服务无法正常启动，API lifespan 启动也会失败。

### PDF 未提取到文字

扫描版 PDF 需要先进行 OCR，再将可搜索的 PDF 放入 `data/`。

### 首次运行较慢

Sentence Transformers 首次运行需要下载 `BAAI/bge-small-zh-v1.5` 模型。请确保网络可用，并等待模型下载和加载完成。

## 贡献

欢迎通过 GitHub Issues 报告问题，或提交 Pull Request。提交前请说明改动目的及验证方式；涉及功能变更时，建议同时补充相应测试和文档。

## 许可证

当前仓库未声明开源许可证。添加许可证前，代码的使用、修改和再分发权限应以仓库所有者的授权为准。
