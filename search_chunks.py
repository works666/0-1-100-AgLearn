import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer


PROJECT_DIR = Path(__file__).resolve().parent
CHUNKS_FILE = PROJECT_DIR / "chunks_with_embeddings.jsonl"
QUESTIONS_FILE = PROJECT_DIR / "questions"
MODEL_NAME = "BAAI/bge-small-zh-v1.5"

# BGE 模型建议给检索问题加上这个指令前缀
QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："


def main() -> None:
    with CHUNKS_FILE.open("r", encoding="utf-8") as file:
        records = [json.loads(line) for line in file if line.strip()]

    # questions = [
    #     line.strip()
    #     for line in QUESTIONS_FILE.read_text(encoding="utf-8").splitlines()
    #     if line.strip()
    # ]
    question = input("请输入问题：").strip()
    questions = [question] if question else []

    if not records:
        raise ValueError(f"{CHUNKS_FILE.name} 中没有资料块。")
    if not questions:
        raise ValueError(f"{QUESTIONS_FILE.name} 中没有问题。")

    # 资料块的向量已经事先生成并保存在 JSONL 中
    chunk_vectors = np.asarray(
        [record["embedding"] for record in records],
        dtype=np.float32,
    )

    model = SentenceTransformer(MODEL_NAME, device="cpu")
    query_vectors = model.encode(
        [QUERY_INSTRUCTION + question for question in questions],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    # 两边向量都已归一化，矩阵乘法的结果就是余弦相似度
    similarities = query_vectors @ chunk_vectors.T

    for question, scores in zip(questions, similarities):
        top_indices = np.argsort(scores)[-3:][::-1]

        print(f"\n问题：{question}")
        for rank, index in enumerate(top_indices, start=1):
            record = records[int(index)]
            page = f"，第 {record['page']} 页" if record["page"] is not None else ""
            print(
                f"{rank}. 相似度 {scores[index]:.4f} | "
                f"{record['source']}{page}\n"
                f"   {record['text'][:200]}"
            )


if __name__ == "__main__":
    main()