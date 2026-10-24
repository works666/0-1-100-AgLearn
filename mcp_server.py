'''MCP服务端，为客户端提供MCP服务，其中放了tools列表'''
from contextlib import asynccontextmanager
from mcp.server.mcpserver import MCPServer
from vector_search import load_vector_index
from pathlib import Path
from vector_search import retrieve

def search_knowledge_base_impl(query: str, top_k: int = 3) -> list[dict]:
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

def search_list_base_impl() -> list[dict]:
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

@asynccontextmanager
async def server_lifespan(server: MCPServer):
    load_vector_index()
    yield

mcp = MCPServer("AgLearn Local Tools", lifespan=server_lifespan)
'''创建服务实例，并将服务命名为 AgLearn Local Tools。
MCPServer 支持 lifespan 参数。在服务启动生命周期中调用 load_vector_index()，之后才开始处理工具请求。
加载失败时让异常向外传递，避免服务启动成功却在搜索时才发现索引不可用。'''

@mcp.tool()
def search_knowledge_base(query: str, top_k: int = 3) -> list[dict]:
    """根据查询搜索本地知识库，返回文本块和来源信息。

    Args:
        query: 搜索内容或短语。
        top_k: 返回结果数量，范围为 1 到 5，默认为 3。

    Returns:
        包含 chunk_id、text、source 和 page 的结果列表。
    """
    return search_knowledge_base_impl(query, top_k)

@mcp.tool()
def search_list_base() -> list[dict]:
    """列出 data 目录中的 TXT 和 PDF 来源文件。

    Returns:
        包含 source 文件名的列表。
    """
    return search_list_base_impl()


if __name__ == "__main__":
    # stdio 模式下由 MCP 客户端启动此进程，并通过标准输入/输出交换协议消息。
    mcp.run(transport="stdio")