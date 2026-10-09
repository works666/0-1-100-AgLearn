# Please install OpenAI SDK first: `pip3 install openai`
import os
from dotenv import load_dotenv
from openai import (
    APITimeoutError,
    AuthenticationError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)

load_dotenv()#将.env文件中的环境变量加载到系统环境变量中，不会覆盖已经存在的环境变量

api_key = os.environ.get("DEEPSEEK_KEY")
if not api_key or not api_key.strip():
    raise ValueError("DEEPSEEK_KEY is missing. Add it to the project .env file.")#raise 提出异常，ValueError 是 Python 内置的异常类型之一，表示传入的参数值不合法或不符合预期。
 
#获取用户的消息，不再是从命令行参数中获取，而是从标准输入中获取
user_message = input("You: ")
if not user_message.strip():
    raise SystemExit("输入不能为空，请输入有效消息。")


client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com")

try:
    response = client.chat.completions.create(
        model="deepseek-flash",
        messages=[
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": user_message},
        ],
        stream=False,
        reasoning_effort="low",
        #extra_body={"thinking": {"type": "enabled"}}
    )
except APITimeoutError:
    raise SystemExit("请求超时，请稍后重试。")
except AuthenticationError:
    raise SystemExit("认证失败，请检查 API 密钥是否正确。")
except InternalServerError:
    raise SystemExit("服务端发生错误，请稍后重试。")
except RateLimitError:
    raise SystemExit("请求频率或额度超限，请稍后重试或检查账户额度。")
except Exception as e:
    raise SystemExit(f"发生未知错误: {e}")

print(response.choices[0].message.content)
