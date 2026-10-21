from contextlib import asynccontextmanager
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel,field_validator
# from main import generate_rag_response
# from pathlib import Path
from vector_search import load_vector_index # , retrieve
# from dotenv import load_dotenv
# import os
from agent_graph import LangGraph_run

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_vector_index()
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
def ask(request: AskRequest):
    try:
        state = LangGraph_run(request.question,request.expected_tools)
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

