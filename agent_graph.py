'''
agent LangGraph框架的主要代码模块
    agent_node，audit_node，limit_node，三个节点。route_after_agent一个路线选择
    MCP调用，最后返回一个state：
            class AgentState(TypedDict):
                question: str
                messages: Annotated[list[dict], operator.add] # message是历史消息。Annotated是类型注解工具。operator.add当图里的节点返回新的 messages 时，用 operator.add 把新列表追加到已有列表，而不是覆盖原列表。
                tool_call_count: int # tool调用的次数
                results: Annotated[list[dict], operator.add] # 检索知识库得到的结果
                tool_call_records: Annotated[list[dict], operator.add] # tool调用的记录
                expected_tools: list[str] | None # 本次预期tool，用来预测
                answer: str # 得到的回答
                selection_mismatch: bool | None
'''
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
import operator
from openai import AsyncOpenAI
from dotenv import load_dotenv
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
from collections import Counter
from mcp import Client
from mcp.shared.exceptions import MCPError

def extract_text(result) -> str: # 从mcp返回的对象中得到真正tool的数据。
    text_parts = []

    for block in result.content:
        text = getattr(block, "text", None)
        if text is not None:
            text_parts.append(text)

    return "\n".join(text_parts)

def parse_tool_result(result) -> Any:
    structured_content = result.structured_content
    if isinstance(structured_content, dict):
        result_data = structured_content.get("result")
        if isinstance(result_data, list):
            return result_data
    elif isinstance(structured_content, list):
        return structured_content

    response_text = extract_text(result)
    if not response_text:
        return None

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        return None

def to_model_tools(mcp_tools):#动态获取mcp服务中的tool的schema，交给模型注册
    model_tools = []

    for tool in mcp_tools:
        schema = tool.input_schema

        model_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": schema,#字典类型
                },
            }
        )
    return model_tools
async def  LangGraph_run(
    question: str,
    expected_tools_copy: list[str] | None,
    mcp_client: Client,
    mcp_tools: list[Any],
) -> dict:
    MAX_TOOL_CALLS = 4 # 调用的最大工具数
    async def run_graph() -> dict:
        supported_tool_names = {
            "search_knowledge_base",
            "search_list_base",
        }
        supported_mcp_tools = [
            tool for tool in mcp_tools if tool.name in supported_tool_names
        ]
        model_tools = to_model_tools(supported_mcp_tools)
        tools_by_name = {
            tool.name: tool for tool in supported_mcp_tools
        }
        load_dotenv()#将.env文件中的环境变量加载到系统环境变量中，不会覆盖已经存在的环境变量
        api_key = os.environ.get("DEEPSEEK_KEY")
        if not api_key or not api_key.strip():
            raise RuntimeError(
                "DEEPSEEK_KEY is missing. Add it to the project .env file."
            )
        llm = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
            )
        class AgentState(TypedDict):
            question: str
            messages: Annotated[list[dict], operator.add] # message是历史消息。Annotated是类型注解工具。operator.add当图里的节点返回新的 messages 时，用 operator.add 把新列表追加到已有列表，而不是覆盖原列表。
            tool_call_count: int # tool调用的次数
            results: Annotated[list[dict], operator.add] # 检索知识库得到的结果
            tool_call_records: Annotated[list[dict], operator.add] # tool调用的记录
            expected_tools: list[str] | None # 本次预期tool，用来预测
            answer: str # 得到的回答
            selection_mismatch: bool | None

        async def agent_node(state: AgentState) -> dict: # agent节点更新历史消息，回答
            response = await llm.chat.completions.create(
                model="deepseek-flash",
                messages=state["messages"],#----------
                tools=model_tools, # 动态获得的工具列表
                tool_choice="auto",
                stream=False,
                extra_body={"thinking": {"type": "disabled"}},
            )
            message = response.choices[0].message
            message_dict = message.model_dump(exclude_none=True)#-------model_dump把模型对象转换成普通 Python 字典，并省略值为 None 的字段。
            return {
                "messages": [message_dict],
                "answer": message.content or "",
            }

        def route_after_agent(state: AgentState) -> str:
            last_message = state["messages"][-1] # 最新的一条消息
            tool_calls = last_message.get("tool_calls") or []
            if not tool_calls:
                return "audit"
            if state["tool_call_count"] >= MAX_TOOL_CALLS:
                return "limit"
            return "tools"

        def audit_node(state: AgentState) -> dict:#没有请求tool时调用，用来测试和评估，实际调用工具和预测调用工具是否匹配，记录在logs文件中
            expected_tools = state.get("expected_tools")
            if expected_tools is None:
                return {"selection_mismatch": None}
            actual_tools = [
                record["name"]
                for record in state["tool_call_records"]
            ]
            mismatch = Counter(actual_tools) != Counter(expected_tools)
            if mismatch: # 不匹配
                log_path = Path(__file__).resolve().parent / "logs"
                log_path.mkdir(parents=True, exist_ok=True) # mkdir创建文件

                record = { # 不匹配的日志文件
                    "timestamp": datetime.now(timezone.utc).isoformat(),#记录不匹配发生的时间
                    "question": state["question"],
                    "expected_tools": expected_tools,
                    "actual_tool_calls": state["tool_call_records"],
                    "answer": state["answer"],
                }
                with (log_path / "tool_choice_mismatches.jsonl").open(
                    "a",
                    encoding="utf-8",
                ) as log_file:
                    log_file.write(json.dumps(record, ensure_ascii=False) + "\n") 
            return {"selection_mismatch": mismatch}

        async def limit_node(state: AgentState) -> dict:
            last_message = state["messages"][-1]
            tool_calls = last_message.get("tool_calls") or []
            messages_to_add = []
            records_to_add = []
            for tool_call in tool_calls:
                arguments_text = tool_call["function"]["arguments"]
                try:
                    arguments = json.loads(arguments_text)
                except (TypeError, json.JSONDecodeError):
                    arguments = {"raw_arguments": arguments_text}
                if not isinstance(arguments, dict):
                    arguments = {"raw_arguments": arguments}
                messages_to_add.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(
                            {
                                "error": (
                                    f"已达到工具调用上限 {MAX_TOOL_CALLS}，"
                                    "此调用未执行。请依据已有检索结果回答；"
                                    "如果资料不足，请明确说明。"
                                )
                            },
                            ensure_ascii=False,
                        ),
                    }
                )
                records_to_add.append(
                    {
                        "tool_call_id": tool_call["id"],
                        "name": tool_call["function"]["name"],
                        "arguments": arguments,
                        "executed": False,
                        "reason": f"达到工具调用上限 {MAX_TOOL_CALLS}",
                    }
                )
            messages_for_final_answer = state["messages"] + messages_to_add

            response = await llm.chat.completions.create(
                model="deepseek-flash",
                messages=messages_for_final_answer,
                stream=False,
                extra_body={"thinking": {"type": "disabled"}},
            )
            answer = response.choices[0].message.content
            if not answer or not answer.strip():
                raise RuntimeError("达到工具调用上限后，模型没有返回最终回答。")
            return {
                "messages": messages_to_add + [
                    {
                        "role": "assistant",
                        "content": answer,
                    }
                ],
                "tool_call_records": records_to_add,
                "answer": answer,
            }
        async def tools_node(state: AgentState) -> dict:
            last_message = state["messages"][-1]
            tool_calls = last_message.get("tool_calls") or []
            # 得到工具列表
            messages_to_add = []
            results_to_add = []
            records_to_add = []
            attempted_count = 0
            for tool_call in tool_calls:
                call_id = tool_call["id"]
                function = tool_call["function"]
                tool_name = function["name"]
                arguments_text = function.get("arguments", "")
                # Python 字典的安全读取方式，等价于：
                #取出 function 这个字典里的 "arguments" 键的值
                #如果这个键不存在，就返回 ""（空字符串）
                #不会因为键不存在而直接抛 KeyError
                arguments: dict[str, Any] = {}
                result_payload: Any
                record: dict[str, Any] = {
                    "tool_call_id": call_id,
                    "name": tool_name,
                    "arguments": arguments,
                    "executed": False,
                    "succeeded": False,
                }
                try:
                    parsed_arguments = json.loads(arguments_text)
                except (TypeError, json.JSONDecodeError):#出错执行
                    result_payload = {
                        "error": "模型返回的工具参数不是有效 JSON。"
                    }
                    record["reason"] = result_payload["error"]
                else:#没出错执行
                    if not isinstance(parsed_arguments, dict):
                        result_payload = {
                            "error": "工具参数必须是 JSON 对象。"#JSON对象就是字典
                        }
                        record["arguments"] = {#工具调用记录
                            "raw_arguments": parsed_arguments
                        }
                        record["reason"] = result_payload["error"]
                    else:
                        arguments = parsed_arguments
                        record["arguments"] = arguments

                        if tool_name not in tools_by_name:
                            result_payload = {
                                "error": f"MCP 服务没有提供工具：{tool_name}"
                            }
                            record["reason"] = result_payload["error"]
                        else:
                            validation_error = None
                            if tool_name == "search_knowledge_base":
                                if set(arguments) - {"query", "top_k"}:
                                    validation_error = (
                                        "知识库搜索工具只接受 query 和 top_k 参数。"
                                    )
                                else:
                                    query = arguments.get("query")
                                    top_k = arguments.get("top_k", 3)
                                    if (
                                        not isinstance(query, str)
                                        or not query.strip()
                                    ):
                                        validation_error = (
                                            "知识库搜索工具的 query "
                                            "必须是非空字符串。"
                                        )
                                    elif (
                                        type(top_k) is not int
                                        or not 1 <= top_k <= 5
                                    ):
                                        validation_error = (
                                            "top_k 必须是 1 到 5 之间的整数。"
                                        )
                                    else:
                                        arguments = {
                                            "query": query.strip(),
                                            "top_k": top_k,
                                        }
                                        record["arguments"] = arguments
                            elif arguments:
                                validation_error = (
                                    "目录列表工具不接受参数。"
                                )
                            #取出两个函数的参数
                            if validation_error:
                                result_payload = {"error": validation_error}
                                record["reason"] = validation_error
                            elif (
                                state["tool_call_count"] + attempted_count
                                >= MAX_TOOL_CALLS
                            ):
                                result_payload = {
                                    "error": (
                                        f"达到工具调用上限 {MAX_TOOL_CALLS}，"
                                        "本次调用未执行。"
                                    )
                                }
                                record["reason"] = (
                                    f"达到工具调用上限 {MAX_TOOL_CALLS}"
                                )
                            else:
                                attempted_count += 1
                                try:
                                    mcp_result = await mcp_client.call_tool(
                                        tool_name,
                                        arguments,
                                    )
                                except (
                                    MCPError,
                                    OSError,
                                    TimeoutError,
                                    ValueError,
                                ) as exc:
                                    error_text = f"{type(exc).__name__}: {exc}"
                                    result_payload = {
                                        "error": f"调用 MCP 工具 {tool_name} 失败。",
                                        "details": error_text,
                                    }
                                    record.update({
                                        "executed": False,
                                        "reason": error_text,
                                    })
                                else:
                                    response_text = extract_text(mcp_result)
                                    parsed_result = parse_tool_result(mcp_result)

                                    if mcp_result.is_error:
                                        result_payload = {
                                            "error": (
                                                f"MCP 工具 {tool_name} 执行失败。"
                                            ),
                                            "details": (
                                                response_text
                                                or "MCP 未返回错误详情。"
                                            ),
                                        }
                                        record.update({
                                            "executed": True,
                                            "reason": "MCP 返回 is_error=True",
                                        })
                                    elif not isinstance(parsed_result, list) or not all(
                                        isinstance(item, dict)
                                        for item in parsed_result
                                    ):
                                        result_payload = {
                                            "error": (
                                                f"MCP 工具 {tool_name} "
                                                "返回了非预期的数据格式。"
                                            ),
                                            "details": response_text,
                                        }
                                        record.update({
                                            "executed": True,
                                            "reason": result_payload["error"],
                                        })
                                    elif (
                                        tool_name == "search_knowledge_base"
                                        and any(
                                            not {
                                                "chunk_id",
                                                "text",
                                                "source",
                                                "page",
                                            }.issubset(item) # issubset判断前面的keys是否都在item里
                                            for item in parsed_result
                                        )
                                    ):
                                        result_payload = {
                                            "error": (
                                                "知识库搜索结果缺少必要字段。"
                                            ),
                                            "details": response_text,
                                        }
                                        record.update({
                                            "executed": True,
                                            "reason": result_payload["error"],
                                        })
                                    elif (
                                        tool_name == "search_list_base"
                                        and any(
                                            "source" not in item
                                            for item in parsed_result
                                        )
                                    ):
                                        result_payload = {
                                            "error": "目录列表结果缺少 source 字段。",
                                            "details": response_text,
                                        }
                                        record.update({
                                            "executed": True,
                                            "reason": result_payload["error"],
                                        })
                                    else:
                                        result_payload = parsed_result
                                        record.update({
                                            "executed": True,
                                            "succeeded": True,
                                        })
                                        if tool_name == "search_knowledge_base":
                                            results_to_add.extend(parsed_result)
                                            record["result_chunk_ids"] = [
                                                item["chunk_id"]
                                                for item in parsed_result
                                            ]
                                        else:
                                            record["result_sources"] = [
                                                item["source"]
                                                for item in parsed_result
                                            ]
                records_to_add.append(record)
                messages_to_add.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": json.dumps(
                        result_payload,
                        ensure_ascii=False,
                    ),
                })
            return {
                "messages": messages_to_add,
                "tool_call_count": state["tool_call_count"] + attempted_count,
                "results": results_to_add,
                "tool_call_records": records_to_add,
            }

        builder = StateGraph(AgentState)
        builder.add_node("agent", agent_node)
        builder.add_node("tools", tools_node)
        builder.add_node("limit", limit_node)
        builder.add_node("audit", audit_node)
        builder.add_edge(START, "agent")
        builder.add_conditional_edges(
            "agent",
            route_after_agent,
            {
                "tools": "tools",
                "limit": "limit",
                "audit": "audit",
            },
        )
        builder.add_edge("tools", "agent")
        builder.add_edge("limit", "audit")
        builder.add_edge("audit", END)

        graph = builder.compile()
        initial_state = {
            "question": question,
            "messages": [
                {"role": "system", "content": (
                        "你是一个基于本地资料回答问题的助手。"
                        "规则："
                        "不得仅凭模型已有知识回答问题。"
                        "用户询问本地资料中的事实、数据、观点或结论时，必须先调用本地资料检索工具。"
                        "询问本地资料中的具体内容时，调用 search_knowledge_base或者search_list_base；"
                        "只有闲聊、改写、翻译等不需要资料的问题，才可以不调用检索工具。"
                        "如果使用检索资料回答，必须引用对应的 chunk_id;"
                        "不得编造检索结果或引用。"
                        "且一次最多发送4个工具调用请求"
                    )},
                {"role": "user", "content": question},
            ],
            "tool_call_count": 0,
            "results": [],
            "tool_call_records": [],
            "expected_tools": expected_tools_copy,
            "answer": "",
            "selection_mismatch": None,
        }
        state = await graph.ainvoke(
            initial_state,
            config={"recursion_limit": 20},
        )
        return state
    return await run_graph()
if __name__ == "__main__":
 pass
