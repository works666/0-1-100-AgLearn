from fastapi import FastAPI
from pydantic import BaseModel,field_validator
from main import generate_response
from pathlib import Path
from KeyWord_Search import search_files
from dotenv import load_dotenv
import os
app = FastAPI()
class AskRequest(BaseModel):
    question: str
    keyword: str

    @field_validator('question', 'keyword')#要检验的值，自动调用下面的函数
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
    information = search_files(Path(__file__).parent / "data", request.keyword)  # 调用 search_files 函数，传入文件夹路径和搜索关键词，返回搜索结果
    if information == "无资料":
         return {
            "message": "没有找到相关资料，请尝试其他关键词。",
            "answer": None,
            "sources": [],
        }
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
        "sources": information,
    }

