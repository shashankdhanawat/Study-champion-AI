import faiss
index = faiss.IndexFlatL2(384)  # 384 is the dimension of the embeddings
def add_embeddings(embeddings):
    index.add(embeddings)
def get_relevant_chunks(chunks, indices):
    results = [chunks[i] for i in indices[0]]
    return results