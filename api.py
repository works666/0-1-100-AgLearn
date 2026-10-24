'''
构建开启fastapi服务，终端运行
.\.venv\Scripts\python.exe api.py
.\.venv\Scripts\python.exe -m uvicorn api:app --reload
加载完成后可访问http://127.0.0.1:8000/docs
通过ask模块使用
'''
from contextlib import asynccontextmanager
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from pydantic import BaseModel,field_validator
from agent_graph import LangGraph_run

@asynccontextmanager
async def lifespan(app: FastAPI):
    project_dir = Path(__file__).resolve().parent
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(project_dir / "mcp_server.py")],
    )

    async with Client(server_params) as client:
        tool_result = await client.list_tools()
        app.state.mcp_client = client
        app.state.mcp_tools = tool_result.tools
        yield

app = FastAPI(lifespan=lifespan)  

class AskRequest(BaseModel):
    question: str
    expected_tools: list[str] | None = None #传入数据为 ["search_knowledge_base"]或者["search_list_base"]，不传参默认为None，不进行tool匹配确认

    @field_validator('question')#要检验的值，自动调用下面的函数
    @classmethod
    def not_empty(cls, value):#检查输入是否为空，如果为空则抛出 ValueError 异常
      
        if not value or not value.strip():
            raise ValueError("输入不能为空，请输入有效内容。")
        return value
    
@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/ask")
async def ask(request: Request, body: AskRequest):
    try:
        state = await LangGraph_run(
            body.question,
            body.expected_tools,
            request.app.state.mcp_client,
            request.app.state.mcp_tools,
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
        "answer": state["answer"],
        "sources": sources,
        "tool_calls": state["tool_call_records"],
        "mismatch" : state["selection_mismatch"],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
