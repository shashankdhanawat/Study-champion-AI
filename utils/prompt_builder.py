def build_prompt(query, relevant_chunks, language="English", difficulty="Intermediate", length="Detailed"):
    context = "\n\n---\n\n".join(relevant_chunks)
    return f"""You are Study Champion AI. Answer ONLY from the supplied study material.
If the answer is missing, say exactly: I don't know based on the uploaded study material.
Explain at {difficulty} level, in {language}, with a {length.lower()} answer.

STUDY MATERIAL:
{context}

QUESTION: {query}
ANSWER:"""
