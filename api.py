'''
构建开启fastapi服务，终端运行
.\.venv\Scripts\python.exe api.py
.\.venv\Scripts\python.exe -m uvicorn api:app --reload
加载完成后可访问http://127.0.0.1:8000/docs
通过ask，delete模块使用
'''
from contextlib import asynccontextmanager
import os
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from pydantic import BaseModel,field_validator
from agent_graph import create_agent_graph
from uuid import uuid4
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Overwrite
from dotenv import load_dotenv
from openai import AsyncOpenAI

@asynccontextmanager
async def lifespan(app: FastAPI):
    project_dir = Path(__file__).resolve().parent
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(project_dir / "mcp_server.py")],
    )

    load_dotenv()
    api_key = os.environ.get("DEEPSEEK_KEY")
    if not api_key or not api_key.strip():
        raise RuntimeError("DEEPSEEK_KEY is missing. Add it to the project .env file.")

    llm = AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
    )
    try:
        async with Client(server_params) as client:
            tool_result = await client.list_tools()
            checkpoint_path = Path(
                os.environ.get(
                    "CHECKPOINT_DB_PATH",
                    str(project_dir / "checkpoints.sqlite"),
                )
            )
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            async with AsyncSqliteSaver.from_conn_string(
                str(checkpoint_path)
            ) as checkpointer:
                app.state.checkpointer = checkpointer
                app.state.agent_graph = create_agent_graph(
                    client,
                    tool_result.tools,
                    llm,
                    checkpointer,
                )
                yield
    finally:
        await llm.close()

app = FastAPI(lifespan=lifespan)

class AskRequest(BaseModel):
    question: str
    expected_tools: list[str] | None = None #传入数据为 ["search_knowledge_base"]或者["search_list_base"]，不传参默认为None，不进行tool匹配确认
    conversation_id: str | None = None

    @field_validator('question')#要检验的值，自动调用下面的函数
    @classmethod
    def not_empty(cls, value):#检查输入是否为空，如果为空则抛出 ValueError 异常

        if not value or not value.strip():
            raise ValueError("输入不能为空，请输入有效内容。")
        return value

    @field_validator("conversation_id")
    @classmethod
    def conversation_id_not_empty(cls, value):
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("conversation_id 不能为空字符串。")
        return value

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/ask")
async def ask(request: Request, body: AskRequest):
    conversation_id = body.conversation_id or str(uuid4())
    input_state = {
        "question": body.question,
        "messages": [{"role": "user", "content": body.question}],
        "tool_call_count": 0,
        "results": Overwrite([]),
        "tool_call_records": Overwrite([]),
        "expected_tools": body.expected_tools,
        "answer": "",
        "selection_mismatch": None,
    }

    try:
        state = await request.app.state.agent_graph.ainvoke(
            input_state,
            config={
                "configurable": {"thread_id": conversation_id},
                "recursion_limit": 20,
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Agent运行失败: {exc}",
        ) from exc

    results = state["results"]
    sources = [
        {
            "chunk_id": item["chunk_id"],
            "filename": item["source"],
            "page": item["page"],
        }
        for item in results
    ]
    return {
        "message": "成功获取回答。",
        "conversation_id": conversation_id,
        "answer": state["answer"],
        "sources": sources,
        "tool_calls": state["tool_call_records"],
        "mismatch" : state["selection_mismatch"],
    }

@app.delete("/conversations/{conversation_id}")
async def delete_conversation(request: Request, conversation_id: str):
    try:
        await request.app.state.checkpointer.adelete_thread(conversation_id)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"删除会话失败: {exc}",
        ) from exc

    return {
        "message": "会话已删除。",
        "conversation_id": conversation_id,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
