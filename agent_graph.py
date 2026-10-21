from main import (
    SEARCH_KNOWLEDGE_BASE_TOOL,
    SEARCH_LIST_BASE_TOOL,
    search_knowledge_base,
    search_list_base,
)
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
import operator
from openai import OpenAI
from dotenv import load_dotenv
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
from collections import Counter
def  LangGraph_run(question : str,expected_tools_copy : list[str])-> dict:
    MAX_TOOL_CALLS = 4 # 调用的最大工具数


    load_dotenv()#将.env文件中的环境变量加载到系统环境变量中，不会覆盖已经存在的环境变量
    api_key = os.environ.get("DEEPSEEK_KEY")
    if not api_key or not api_key.strip():
        raise RuntimeError(
            "DEEPSEEK_KEY is missing. Add it to the project .env file."
        )
    client = OpenAI(
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

    def agent_node(state: AgentState) -> dict: # agent节点更新历史消息，回答
    
        response = client.chat.completions.create(
            model="deepseek-flash",
            messages=state["messages"],#----------
            tools=[SEARCH_KNOWLEDGE_BASE_TOOL, SEARCH_LIST_BASE_TOOL],
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

    def limit_node(state: AgentState) -> dict:
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

        response = client.chat.completions.create(
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

    def tools_node(state: AgentState) -> dict:
        last_message = state["messages"][-1]
        tool_calls = last_message.get("tool_calls") or []

        messages_to_add = []
        results_to_add = []
        records_to_add = []
        executed_count = 0

        for tool_call in tool_calls:
            call_id = tool_call["id"] # tool的id
            function = tool_call["function"]
            tool_name = function["name"] # 函数名

            try:
                arguments = json.loads(function["arguments"])
            except (TypeError, json.JSONDecodeError) as exc:
                raise ValueError(
                    f"工具 {tool_name} 返回了无效 JSON 参数。"
                ) from exc

            if not isinstance(arguments, dict):
                raise ValueError(f"工具 {tool_name} 的参数必须是 JSON 对象。")

            if state["tool_call_count"] + executed_count >= MAX_TOOL_CALLS:
                tool_result = {
                    "error": f"达到工具调用上限 {MAX_TOOL_CALLS}，本次调用未执行。"
                }
                records_to_add.append(
                    {
                        "tool_call_id": call_id,
                        "name": tool_name,
                        "arguments": arguments,
                        "executed": False,
                        "reason": f"达到工具调用上限 {MAX_TOOL_CALLS}",
                    }
                )
            elif tool_name == "search_knowledge_base":
                if set(arguments) - {"query", "top_k"}:
                    raise ValueError("知识库搜索工具收到不支持的参数。")

                query = arguments.get("query")
                top_k = arguments.get("top_k", 3)

                if not isinstance(query, str) or not query.strip():
                    raise ValueError("知识库搜索工具的 query 不能为空。")
                if type(top_k) is not int or not 1 <= top_k <= 5:
                    raise ValueError("top_k 必须是 1 到 5 之间的整数。")

                tool_result = search_knowledge_base(query=query, top_k=top_k)
                results_to_add.extend(tool_result)
                executed_count += 1

                records_to_add.append( # 工具调用记录
                    {
                        "tool_call_id": call_id,
                        "name": tool_name,
                        "arguments": {
                            "query": query,
                            "top_k": top_k,
                        },
                        "executed": True,
                        "result_chunk_ids": [
                            item["chunk_id"] for item in tool_result
                        ],
                    }
                )
            elif tool_name == "search_list_base":
                if arguments:
                    raise ValueError("目录列表工具不接受参数。")

                tool_result = search_list_base()
                executed_count += 1

                records_to_add.append(
                    {
                        "tool_call_id": call_id,
                        "name": tool_name,
                        "arguments": {},
                        "executed": True,
                        "result_sources": [
                            item["source"] for item in tool_result
                        ],
                    }
                )
            else:
                raise ValueError(f"不支持的工具：{tool_name}")

            messages_to_add.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": json.dumps(tool_result, ensure_ascii=False),
                }
            )

        return {
            "messages": messages_to_add,
            "tool_call_count": state["tool_call_count"] + executed_count,
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
    state = graph.invoke(
        initial_state,
        config={"recursion_limit": 20},
    )
    return state
if __name__ == "__main__":
 pass


