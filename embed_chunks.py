import json
from pathlib import Path

from sentence_transformers import SentenceTransformer


PROJECT_DIR = Path(__file__).resolve().parent
INPUT_FILE = PROJECT_DIR / "chunks.jsonl"
OUTPUT_FILE = PROJECT_DIR / "chunks_with_embeddings.jsonl"
MODEL_NAME = "BAAI/bge-small-zh-v1.5"


def main() -> None:
    with INPUT_FILE.open("r", encoding="utf-8") as file:
        records = [json.loads(line) for line in file if line.strip()]#json.loads()将JSON字符串解析为Python对象，这里是将每一行的JSON字符串解析为字典，并存储在records列表中。if line.strip()确保只处理非空行，避免解析空行导致错误。

    if not records:
        raise ValueError(f"{INPUT_FILE.name} 中没有文本块。")

    texts = [record["text"] for record in records]

    model = SentenceTransformer(MODEL_NAME, device="cpu")
    vectors = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    with OUTPUT_FILE.open("w", encoding="utf-8", newline="\n") as file:
        for record, vector in zip(records, vectors):
            output_record = {
                **record,
                "embedding": vector.tolist(),
            }
            file.write(json.dumps(output_record, ensure_ascii=False) + "\n")

    print(f"已为 {len(records)} 个文本块生成向量：{OUTPUT_FILE.name}")


if __name__ == "__main__":
    main()