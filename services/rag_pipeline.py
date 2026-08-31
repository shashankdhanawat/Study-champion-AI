from utils.embeddings import (
    create_embeddings,
    search_similar_chunks,
)
from utils.vector_store import (
    add_embeddings,
    get_relevant_chunks,
    index,
)
from utils.prompt_builder import build_prompt
from utils.llm import ask_llm


def answer_question(chunks, query, language="English", difficulty="Intermediate", length="Detailed"):
    """Answer a question using the current document's FAISS + MiniLM RAG flow."""

    if not chunks:
        return "I don't know. No study material is available."

    if not query or not query.strip():
        return "Please enter a question."

    # Start fresh for the currently uploaded document. This prevents vectors
    # from previous questions/documents being mapped to the wrong chunk list.
    index.reset()

    embeddings = create_embeddings(chunks)

    if not add_embeddings(embeddings):
        return "I don't know. No valid document embeddings were created."

    # Never ask FAISS for more vectors than exist in both the chunk list
    # and the index.
    top_k = min(3, len(chunks), index.ntotal)

    if top_k <= 0:
        return "I don't know. No searchable study material is available."

    distances, indices = search_similar_chunks(
        query,
        index,
        top_k=top_k,
    )

    relevant_chunks = get_relevant_chunks(chunks, indices)

    if not relevant_chunks:
        return "I don't know. I could not find relevant information in the study material."

    prompt = build_prompt(query, relevant_chunks, language, difficulty, length)
    return ask_llm(prompt)
