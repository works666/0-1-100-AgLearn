from typing import TypedDict
from langgraph.graph import StateGraph, START, END

from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph


class AgentState(TypedDict):
    messages: list[str]
    tool_call_count: int


def decide_node(state: AgentState) -> dict:
    print("判断节点收到：", state)
    return {}


def tool_node(state: AgentState) -> dict:
    print("进入工具节点")
    return {
        "messages": state["messages"] + ["工具：找到了 3 条资料"],
        "tool_call_count": state["tool_call_count"] + 1,
    }


def answer_node(state: AgentState) -> dict:
    print("进入回答节点")
    return {
        "messages": state["messages"] + ["回答：这里是根据资料整理的回答。"],
    }


def route_by_count(state: AgentState) -> Literal["tool_node", "answer_node"]:#判断函数
    if state["tool_call_count"] == 0:
        return "tool_node"
    return "answer_node"


builder = StateGraph(AgentState)
builder.add_node("decide_node", decide_node)
builder.add_node("tool_node", tool_node)
builder.add_node("answer_node", answer_node)

builder.add_edge(START, "decide_node")
builder.add_conditional_edges(
    "decide_node",
    route_by_count,
    {
        "tool_node": "tool_node",
        "answer_node": "answer_node",
    },
)
builder.add_edge("tool_node", "answer_node")
builder.add_edge("answer_node", END)

graph = builder.compile()

initial_state: AgentState = {
    "messages": ["用户：无人机发展面临哪些问题？"],
    "tool_call_count": 0,
}

result = graph.invoke(initial_state)
print("最终状态：", result)



#-----------------------------------------------




# class AgentState(TypedDict):#定义一个类型，表示智能体的状态
#     messages: list[str]
#     tool_call_count: int


# def start_node(state: AgentState) -> dict:
#     print("开始节点收到：", state)
#     return {"tool_call_count": 1,"messages": ["ai:无人机发展很好"]}#不操作状态


# def end_node(state: AgentState) -> dict:
#     print("结束节点收到：", state)
#     return {"tool_call_count": 3}#不操作状态


# builder = StateGraph(AgentState)
# builder.add_node("start_node", start_node)
# builder.add_node("end_node", end_node)

# builder.add_edge(START, "start_node")
# builder.add_edge("start_node", "end_node")
# builder.add_edge("end_node", END)

# graph = builder.compile()

# initial_state: AgentState = {
#     "messages": ["用户：无人机发展面临哪些问题？"],
#     "tool_call_count": 0,
# }

# graph.invoke(initial_state)
