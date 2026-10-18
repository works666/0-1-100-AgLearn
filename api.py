from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel,field_validator
from main import generate_response
# from pathlib import Path
from vector_search import load_vector_index, retrieve
from dotenv import load_dotenv
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_vector_index()
    yield

app = FastAPI(lifespan=lifespan)  

class AskRequest(BaseModel):
    question: str

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
    load_dotenv()#将.env文件中的环境变量加载到系统环境变量中，不会覆盖已经存在的环境变量
    api_key = os.environ.get("DEEPSEEK_KEY")
    if not api_key or not api_key.strip():
        return {
            "message": "DEEPSEEK_KEY is missing. Add it to the project .env file.",
            "answer": None,
            "sources": [],
        }
   
    try:
        results = retrieve(request.question, top_k=3)
    except Exception as e:
        return {
            "message": f"检索过程中发生错误: {e}",
            "answer": None,
            "sources": [],
        }
    information = "\n\n".join(
      (
        f"[来源：{item['source']}"
        f"{f'，第 {item['page']} 页' if item['page'] is not None else ''}]\n"
        f"{item['text']}"
     )
    for item in results
)
    sources = [
        {
            "chunk_id": item["chunk_id"],
            "filename": item["source"],
            "page": item["page"],
        }
        for item in results
    ]
    try:
        answer = generate_response(request.question, information, api_key)
    except Exception as e:
        return {
            "message": f"模型请求回答发生错误: {e}",
            "answer": None,
            "sources": [],
        }
    return {
        "message": "成功获取回答。",
        "answer": answer,
        "sources": sources,
    }

