from utils.llm import ask_llm

prompt = "Explain machine learning in simple words."

answer = ask_llm(prompt)

print("Mistral Answer:")
print(answer)