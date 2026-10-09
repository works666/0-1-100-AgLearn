# DeepSeek 聊天示例

一个使用 Python 和 OpenAI Python SDK 兼容接口调用 DeepSeek Chat Completions API 的入门示例。运行后输入一条消息，程序会显示助手的回复。

## 功能

- 使用 `.env` 文件在本地配置 API Key
- 调用 `deepseek-flash` 模型
- 从命令行读取用户输入，并显示助手回复
- 对空输入、请求超时、认证失败、服务端错误和请求频率或额度超限提供提示

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

程序提示 `You:` 后，输入消息并按 Enter。输入空内容或纯空白内容时，程序会提示输入不能为空并退出。

程序会向 DeepSeek API 发送请求，因此需要可用的网络连接和有效的 API Key。API 使用可能产生费用，请查看服务商的账户和计费设置。

## 配置说明

`main.py` 从 `.env` 读取 `DEEPSEEK_KEY`，并通过 OpenAI Python SDK 的兼容接口访问 `https://api.deepseek.com`。如果提示缺少密钥，请确认：

1. `.env` 文件位于项目根目录；
2. 变量名准确为 `DEEPSEEK_KEY`；
3. 等号右侧已填写有效密钥；
4. 当前进程没有设置为空的同名环境变量（`load_dotenv()` 默认不会覆盖已存在的环境变量）。

## 错误提示

请求过程中，程序会针对以下错误显示提示并退出：

- 请求超时：请稍后重试。
- 认证失败：请检查 API Key 是否正确。
- 服务端错误：请稍后重试。
- 请求频率或额度超限：请稍后重试或检查账户额度。
- 其他未预期错误：显示错误信息，便于排查。

## 安全提示

- 不要提交 `.env` 或任何包含密钥的文件。
- `.gitignore` 不能撤销已提交文件中的密钥。如果密钥曾经公开或提交，请先在服务商处撤销并更换，再从 Git 跟踪中移除该文件。
- `.env` 是明文配置文件，不是加密存储；请限制对本机账户和文件的访问。
