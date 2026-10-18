# 文档问答与检索 API

本项目使用 Python、FastAPI、Sentence Transformers 和 DeepSeek API 构建基于本地资料的问答服务。服务将 TXT/PDF 文档切分为文本块、生成向量；收到问题后检索相关文本块，再将检索内容交给 DeepSeek 生成回答，并返回来源信息。

## 功能

- 从 `data` 目录读取 TXT 和 PDF 文档，并按文本块保存文件名、页码和 `chunk_id`。
- 使用 `BAAI/bge-small-zh-v1.5` 生成文本向量，并进行向量相似度检索。
- 通过 FastAPI 提供健康检查和问答接口。
- 问答响应将 `chunk_id`、文件名和页码作为独立来源字段返回。
- 保留 `main.py` 的命令行关键词搜索问答入口。

## 环境要求

- Python 3.10 或更高版本
- DeepSeek API Key（调用问答接口时需要）
- 首次生成向量或启动 API 时，需要联网下载 `BAAI/bge-small-zh-v1.5` 模型

## 安装与配置

在项目根目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

macOS/Linux 可使用以下虚拟环境激活命令：

```bash
source .venv/bin/activate
```

将 `.env.example` 复制为 `.env`，并在 `.env` 中填写自己的密钥：

```env
DEEPSEEK_KEY=your-deepseek-api-key
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

macOS/Linux：

```bash
cp .env.example .env
```

不要将 `.env` 或真实 API Key 提交到 Git。调用 DeepSeek API 可能产生费用，请留意服务商账户和计费设置。

## 添加资料与构建检索数据

将 `.txt` 或 `.pdf` 文件放入项目根目录下的 `data` 文件夹。然后按顺序执行：

```powershell
python ingest_documents.py
python embed_chunks.py
```

第一步生成 `chunks.jsonl`，包含每个文本块的 `chunk_id`、文本、来源文件名和页码；TXT 的页码为 `null`。第二步生成 `chunks_with_embeddings.jsonl`，供 API 启动时加载和检索。

PDF 使用文本提取方式处理。扫描版 PDF 若没有可提取文本，需要先进行 OCR。每次增删或修改资料后，重新执行上述两个命令以更新检索数据。

## 启动 API 服务

确保已配置 `.env` 并生成 `chunks_with_embeddings.jsonl`，然后在项目根目录运行：

```powershell
python -m uvicorn api:app --reload
```

服务默认运行在 `http://127.0.0.1:8000`。交互式 API 文档位于 `http://127.0.0.1:8000/docs`。

### 健康检查

```http
GET /health
```

成功响应：

```json
{
  "status": "ok"
}
```

### 提问

```http
POST /ask
Content-Type: application/json
```

请求示例：

```json
{
  "question": "低空经济中无人机农村配送面临哪些现实困境？"
}
```

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
  ]
}
```

`sources` 中每个来源是一个对象，包含 `chunk_id`、`filename` 和 `page`；TXT 来源的 `page` 为 `null`。问题不能为空。API 当前按相似度检索最多 3 个文本块。

也可以在 PowerShell 中调用：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/ask `
  -ContentType "application/json" `
  -Body '{"question":"低空经济中无人机农村配送面临哪些现实困境？"}'
```

## 命令行入口

`main.py` 仍提供基于关键词的命令行问答功能：

```powershell
python main.py
```

按提示输入问题和搜索关键词。该入口使用 `KeyWord_Search.py` 在 `data` 目录的 TXT 文件中查找关键词，再将搜索结果发送给 DeepSeek。

## 主要文件

| 文件 | 说明 |
| --- | --- |
| `api.py` | FastAPI 应用、健康检查和问答接口 |
| `vector_search.py` | 加载向量索引并检索相关文本块 |
| `ingest_documents.py` | 提取 TXT/PDF 文本并切分文本块 |
| `embed_chunks.py` | 为文本块生成向量 |
| `main.py` | DeepSeek 调用及命令行问答入口 |
| `KeyWord_Search.py` | 命令行入口使用的 TXT 关键词搜索 |
| `data/` | 待处理的 TXT/PDF 资料 |
| `chunks.jsonl` | 文本切分结果 |
| `chunks_with_embeddings.jsonl` | 带向量的检索索引数据 |

## 注意事项

- API 启动时会加载向量索引和嵌入模型；如果索引文件缺失或为空，服务启动会失败。
- `chunks_with_embeddings.jsonl` 可能较大。若不提交该生成文件，部署前需先运行文档切分和向量生成步骤。
- `.env` 含有密钥，不应提交、公开或分享。
