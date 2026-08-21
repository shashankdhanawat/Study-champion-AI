from utils.embedings import create_embeddings, search_similar_chunks
from utils.vector_store import add_embeddings, index, get_relevant_chunks
from utils.prompt_builder import build_prompt
from utils.llm import ask_llm


def answer_question(chunks, query):

    embeddings = create_embeddings(chunks)

    add_embeddings(embeddings)

    distances, indices = search_similar_chunks(query, index)

    relevant_chunks = get_relevant_chunks(chunks, indices)

    prompt = build_prompt(query, relevant_chunks)

    answer = ask_llm(prompt)

    return answer