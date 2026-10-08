# DeepSeek 聊天示例

一个使用 Python 和 OpenAI Python SDK 兼容接口调用 DeepSeek Chat Completions API 的入门示例。程序发送一条简单的问候消息，并打印完整响应和助手回复。

## 功能

- 使用 `.env` 文件在本地配置 API Key
- 调用 `deepseek-flash` 模型
- 展示完整 API 响应及回复正文

## 环境要求

- Python 3
- DeepSeek API Key

## 安装与运行

### 1. 克隆项目

```bash
git clone <仓库地址>
cd <仓库目录>
```

### 2. 创建并激活虚拟环境

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS / Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 安装依赖

```bash
python -m pip install -r requirements.txt
```

### 4. 配置 API Key

将示例文件复制为本地 `.env` 文件：

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

macOS / Linux：

```bash
cp .env.example .env
```

编辑 `.env`，填入你自己的 DeepSeek API Key：

```env
DEEPSEEK_KEY=your-deepseek-api-key
```

不要把真实 API Key 写进代码、提交到 Git，或分享 `.env` 文件。`.env` 已加入 `.gitignore`；`.env.example` 只用于说明变量名称，不应包含真实密钥。

### 5. 运行

```bash
python main.py
```

程序会向 DeepSeek API 发送请求，因此需要可用的网络连接和有效的 API Key。API 使用可能产生费用，请查看服务商的账户和计费设置。

## 配置说明

`main.py` 从 `.env` 读取 `DEEPSEEK_KEY`，并通过 OpenAI Python SDK 的兼容接口访问 `https://api.deepseek.com`。如果提示缺少密钥，请确认：

1. `.env` 文件位于项目根目录；
2. 变量名准确为 `DEEPSEEK_KEY`；
3. 等号右侧已填写有效密钥；
4. 当前进程没有设置为空的同名环境变量（`load_dotenv()` 默认不会覆盖已存在的环境变量）。

## 安全提示

- 不要提交 `.env` 或任何包含密钥的文件。
- `.gitignore` 不能撤销已提交文件中的密钥。如果密钥曾经公开或提交，请先在服务商处撤销并更换，再从 Git 跟踪中移除该文件。
- `.env` 是明文配置文件，不是加密存储；请限制对本机账户和文件的访问。
