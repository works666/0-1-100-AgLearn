# Please install OpenAI SDK first: `pip3 install openai`
import json
from vector_search import retrieve
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


def generate_response(user_message, information, api_key):
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com")
    user_message=user_message+"上面是问题，下面是找到的资料"+information
   # try:
    response = client.chat.completions.create(
        model="deepseek-flash",
        messages=[
            {"role": "system", "content": "依据提供的资料回答；资料不足时说明不足；不要把没有出现在资料中的内容说成资料结论，在每一条的回答中提出根据哪一个chunk_id得到的，也就是来源是什么。"},
            {"role": "user", "content": user_message},
        ],
        stream=False,
        reasoning_effort="low",
        #extra_body={"thinking": {"type": "enabled"}}
    )
    # except APITimeoutError:
    #   raise SystemExit("请求超时，请稍后重试。")
    # except AuthenticationError:
    #    raise SystemExit("认证失败，请检查 API 密钥是否正确。")
    # except InternalServerError:
    #    raise SystemExit("服务端发生错误，请稍后重试。")
    # except RateLimitError:
    #    raise SystemExit("请求频率或额度超限，请稍后重试或检查账户额度。")
    # except Exception as e:
    #    raise SystemExit(f"发生未知错误: {e}")

    return(response.choices[0].message.content)

SEARCH_KNOWLEDGE_BASE_TOOL = { #工具的定义，告诉模型可以调用这个工具
    "type": "function",
    "function": {
        "name": "search_knowledge_base",
        "description": "根据用户问题检索知识库，返回相关文本块及其来源。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "用于搜索知识库的关键词或短语",
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回的相关文本块数量，1 到 5 之间，默认 3",
                    "minimum": 1,
                    "maximum": 5,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
}
SEARCH_LIST_BASE_TOOL = {
    "type":"function",
    "function":{
        "name":"search_list_base",
        "description":"检索知识库，返回本地知识库的所有来源文件列表。",
        "parameters":{
            #无参数
            "type":"object",
            "properties":{},
            "required":[],
            "additionalProperties": False,
        },
    },

}

def search_knowledge_base(query: str, top_k: int = 3) -> list[dict]:
    """执行知识库检索，返回文本块和引用来源。"""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query 不能为空。")

    if type(top_k) is not int or not 1 <= top_k <= 5:
        raise ValueError("top_k 必须是 1 到 5 之间的整数。")

    results = retrieve(query.strip(), top_k=top_k)

    return [
        {
            "chunk_id": item["chunk_id"],
            "text": item["text"],
            "source": item["source"],
            "page": item["page"],
        }
        for item in results
    ]

def search_list_base() -> list[dict]:
    """检索知识库，返回本地知识库的所有来源文件列表。"""
    #得到data文件夹下的所有文件列表
    folderpath = Path(__file__).parent / "data"
    files = sorted(
        (
            file
            for file in folderpath.iterdir()
            if file.is_file() and file.suffix.lower() in {".txt", ".pdf"}
        ),
        key=lambda file: file.name.casefold(),
    )

    return [{"source": file.name} for file in files]

def generate_rag_response(question: str, api_key: str) -> tuple[str, list[dict],list[dict]]:
    """让模型调用知识库检索工具，再根据检索结果生成回答。"""
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
    )

    messages = [
        {
            "role": "system",
            "content": (
                "你是一个基于本地资料回答问题的助手。"
                "规则："
                "不得仅凭模型已有知识回答问题。"
                "用户询问本地资料中的事实、数据、观点或结论时，必须先调用本地资料检索工具。"
                "询问本地资料中的具体内容时，调用 search_knowledge_base或者search_list_base；"
                "只有闲聊、改写、翻译等不需要资料的问题，才可以不调用检索工具。"
                "如果使用检索资料回答，必须引用对应的 chunk_id；"
                "不得编造检索结果或引用。"
                "且一次最多发送两个工具调用请求"
            ),
        },
        {
            "role": "user",
            "content": question,
        },
    ]

    # 第一次请求：模型观察是否提出一次知识库检索工具调用。
    first_response = client.chat.completions.create(
        model="deepseek-flash",
        messages=messages,
        tools=[SEARCH_KNOWLEDGE_BASE_TOOL, SEARCH_LIST_BASE_TOOL],#注册一个tool，告诉模型可以调用这个工具
        tool_choice='auto',#告诉模型可以选择调用这个工具
        # tool_choice={        #这次回答可以选择调用的工具，若有多个tool，模型可以选择调用其中一个或两个
        #     "type": "function",
        #     "function": {"name": "search_knowledge_base"},
        # },
        stream=False,
        extra_body={"thinking": {"type": "disabled"}},#关闭deepseek思考模式
    )

    assistant_message = first_response.choices[0].message#第一次回答的结果，可能包含tool调用请求，也可能没有
    tool_calls = assistant_message.tool_calls or []#工具调用请求,在assistant_message.tool_calls中，可能有多次。
    
    if not tool_calls:#模型没有调用工具，直接返回回答。
        if not assistant_message.content:
            raise RuntimeError("模型没有返回回答。")
        return assistant_message.content, [], []  # 模型没有调用工具，直接返回回答。
    
    for call in tool_calls:
        print(call.function.name, call.function.arguments)

    if not len(tool_calls) <= 2:
        raise RuntimeError(
            f"若模型调用tools,必须调用小于等于2 次，实际调用 {len(tool_calls)} 次。"
    )

    messages.append(assistant_message.model_dump(exclude_none=True))
    all_results = []
    list_results = []
    tool_call_records = []#调用日志记录

    for tool_call in tool_calls:
        if tool_call.function.name == "search_knowledge_base":
            # 处理 search_knowledge_base 工具调用
            pass
        elif tool_call.function.name == "search_list_base":
            # 处理 search_list_base 工具调用
            pass
        else:
            raise RuntimeError(f"不支持的工具：{tool_call.function.name}")

        try:
            arguments = json.loads(tool_call.function.arguments)#得到模型调用工具的参数，json.loads()将字符串转换为Python对象
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("模型返回的工具参数不是有效 JSON。") from exc

        if not isinstance(arguments, dict):
            raise ValueError("模型返回的工具参数必须是 JSON 对象。")
        
        if tool_call.function.name == "search_knowledge_base":
            if set(arguments) - {"query", "top_k"}:
                raise ValueError("模型返回了不支持的工具参数。")
            
            query = arguments.get("query")#若模型返回空参数，query为None
            top_k = arguments.get("top_k", 3)
            if not isinstance(query, str) or not query.strip():
                raise ValueError("知识库搜索工具的 query 不能为空。")
            if type(top_k) is not int or not 1 <= top_k <= 5:
                raise ValueError("top_k 必须是 1 到 5 之间的整数。")

            print(f"模型调用chunks检索工具，query={query}, top_k={top_k}")
            results = search_knowledge_base(query=query, top_k=top_k)#返回检索chunks结果

            # 将模型的工具调用和程序检索出的资料放进对话历史。
            all_results.extend(results)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(results, ensure_ascii=False),
                }
            )
            tool_call_records.append(
                {
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "arguments": {
                        "query": query,
                        "top_k": top_k,
                    },
                    "result_chunk_ids": [
                        item["chunk_id"] for item in results
                    ],
                }
            )
        if tool_call.function.name == "search_list_base":
            if arguments:
                raise ValueError("目录列表工具不接受参数。")
            print(f"模型调用目录检索工具，返回本地知识库的所有来源文件列表。")
            if not list_results:
                list_results: list[dict] = search_list_base()#返回检索列表结果
            # 将模型的工具调用和程序检索出的资料放进对话历史。
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(list_results, ensure_ascii=False),
                }
            )
            tool_call_records.append(
                {
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "arguments": {},
                    "list_results": [
                        item["source"] for item in list_results
                    ],
                }
            )
    # 第二次请求：模型根据检索资料生成最终回答。没有设置tools参数，模型不能再调用工具。
    final_response = client.chat.completions.create(
        model="deepseek-flash",
        messages=messages,
        stream=False,
        extra_body={"thinking": {"type": "disabled"}},#关闭deepseek思考模式
    )

    answer = final_response.choices[0].message.content
    if not answer:
        raise RuntimeError("模型没有返回最终回答。")

    return answer, all_results,tool_call_records

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
    try:
        response = generate_response(user_message, information, api_key)
    except Exception as e:
        raise SystemExit(f"模型请求回答发生错误: {e}")
    print("AI Response:", response)


if __name__ == '__main__':
    main()
