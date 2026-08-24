from services.rag_pipeline import answer_question

chunks = [
    "Machine learning is a branch of artificial intelligence.",
    "Deep learning uses neural networks to learn patterns."
]

question = "What is machine learning?"

answer = answer_question(
    chunks,
    question
)

print(answer)