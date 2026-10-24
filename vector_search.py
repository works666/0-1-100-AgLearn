'''
为问题生成向量，在chunks_with_embeddings与文本块向量计算相似度，
然后返回最相关的 top_k 条结果，包含文本、来源、页码和相似度分数。
'''

import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer


PROJECT_DIR = Path(__file__).resolve().parent
CHUNKS_FILE = PROJECT_DIR / "chunks_with_embeddings.jsonl"
MODEL_NAME = "BAAI/bge-small-zh-v1.5"
QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："

model = None
records = []
chunk_vectors = None


def load_vector_index() -> None:
    global model, records, chunk_vectors

    with CHUNKS_FILE.open("r", encoding="utf-8") as file:
        records = [json.loads(line) for line in file if line.strip()]

    if not records:
        raise ValueError(f"{CHUNKS_FILE.name} 中没有资料块。")

    model = SentenceTransformer(MODEL_NAME, device="cpu")
    chunk_vectors = np.asarray(
        [record["embedding"] for record in records],
        dtype=np.float32,
    )


def retrieve(question: str, top_k: int = 3) -> list[dict]:
    if model is None or chunk_vectors is None:
        raise RuntimeError("向量检索索引尚未加载。")

    query_vector = model.encode(
        QUERY_INSTRUCTION + question,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    scores = chunk_vectors @ query_vector
    top_indices = np.argsort(scores)[-top_k:][::-1]

    results = []
    for index in top_indices:
        record = records[int(index)]
        results.append({
            "chunk_id": record["chunk_id"],
            "text": record["text"],
            "source": record["source"],
            "page": record["page"],
            "score": float(scores[index]),
        })

    return results