from utils.embedings import create_embeddings , search_similar_chunks
from utils.vector_store import add_embeddings,index , get_relevant_chunks
from utils.prompt_builder import build_prompt
from utils.llm import ask_llm

chunks = [ "Chunk 1: This is the first chunk of text.",
           "Chunk 2: This is the second chunk of text.",
           "Chunk 3: This is the third chunk of text."]
embeddings = create_embeddings(chunks)
print(embeddings.shape)
add_embeddings(embeddings)
print("total number of vectors in the index:", index.ntotal)
query = "This is a query to find similar chunks."
distances, indices = search_similar_chunks(query, index)
results = get_relevant_chunks(chunks, indices)
print ("rlevant chunks:")
for result in results:
    print(result)


print("Distances:", distances)
print("Indices:", indices)
prompt = build_prompt(query, results)
print ("generated prompt")
print(prompt) 
answer = ask_llm(prompt)
print("Mistral Answer:")
print(answer)