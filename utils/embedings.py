from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
def create_embeddings(chunks):
     embeddings = model.encode(chunks)
     return embeddings
def search_similar_chunks(query, index, top_k=3):
    query_embedding = model.encode([query])
    distances, indices = index.search(query_embedding, top_k)
    return distances, indices 