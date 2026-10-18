from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-small-zh-v1.5", device="cpu")

sentences = [
    "今天天气很好，适合出去散步。",
    "今天天气不错，我们可以出门走走。",
]

vectors = model.encode(sentences, normalize_embeddings=True)

print("第一句话的向量：")
print(vectors[0].tolist())

print("\n第二句话的向量：")
print(vectors[1].tolist())

# 向量已归一化，因此点积就是余弦相似度
similarity = vectors[0] @ vectors[1]
print(f"\n余弦相似度：{similarity:.4f}")