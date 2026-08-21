from services.rag_pipeline import answer_question


chunks = [
    "Python is a programming language.",
    "Machine learning allows computers to learn from data.",
    "Deep learning uses neural networks."
]

query = "What is Deep  learning?"

answer = answer_question(chunks, query)

print("Final Answer:")
print(answer)