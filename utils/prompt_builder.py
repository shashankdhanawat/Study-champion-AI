def build_prompt (query, relevant_chunks):
    context = "\n\n".join(relevant_chunks)
    prompt = f"""
you are a helpful assistant.
answer the user question based on provided content and if the answer is not available in the content, say "I don't know"."""
    study_material = f"""
Content:
{context}
Question: {query}
Answer:"""
    return prompt + study_material  