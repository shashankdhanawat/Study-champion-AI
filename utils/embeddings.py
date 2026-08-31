import numpy as np
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")


def create_embeddings(chunks):
    if not chunks:
        return np.empty((0, 384), dtype=np.float32)
    return np.asarray(model.encode(chunks), dtype=np.float32)


def search_similar_chunks(query, index, top_k=3):
    if not query or top_k <= 0 or index.ntotal == 0:
        return np.empty((1, 0), dtype=np.float32), np.empty((1, 0), dtype=np.int64)
    query_embedding = np.asarray(model.encode([query]), dtype=np.float32)
    return index.search(query_embedding, min(top_k, index.ntotal))
