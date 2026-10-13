# Please install OpenAI SDK first: `pip3 install openai`
import os
from pathlib import Path
from KeyWord_Search import search_files
from dotenv import load_dotenv
from openai import (
    APITimeoutError,
    AuthenticationError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)
def main():
    load_dotenv()#将.env文件中的环境变量加载到系统环境变量中，不会覆盖已经存在的环境变量

    api_key = os.environ.get("DEEPSEEK_KEY")
    if not api_key or not api_key.strip():
        raise ValueError("DEEPSEEK_KEY is missing. Add it to the project .env file.")#raise 提出异常，ValueError 是 Python 内置的异常类型之一，表示传入的参数值不合法或不符合预期。
    
    #获取用户的消息，不再是从命令行参数中获取，而是从标准输入中获取
    user_message = input("Your question: ")
    user_message_keyword = input('请输入搜索关键词：').strip()  # 获取用户输入的搜索关键词，并去掉首尾空格
    if not user_message.strip():
        raise SystemExit("输入不能为空，请输入有效消息。")
    if not user_message_keyword.strip():
        raise SystemExit("搜索关键词不能为空，请输入有效的关键词。")

    folderpath = Path(__file__).parent / "data"  # 获取当前脚本所在目录的父目录，并拼接上 "data" 子目录，返回一个 Path 对象
    information = search_files(folderpath, user_message_keyword)  # 调用 search_files 函数，传入文件夹路径和搜索关键词，返回搜索结果
    if information == "无资料":
        raise SystemExit("没有找到相关资料，请尝试其他关键词。")
    user_message=user_message+"上面是问题，下面是找到的资料"+information

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com")

    try:
        response = client.chat.completions.create(
            model="deepseek-flash",
            messages=[
                {"role": "system", "content": "依据提供的资料回答；资料不足时说明不足；不要把没有出现在资料中的内容说成资料结论，并在回答后说明你参考的资料来源。"},
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

if __name__ == '__main__':
    main()
