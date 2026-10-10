import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_classic.chains import RetrievalQA

load_dotenv()


def create_vector_store(chunks):
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    vector_store = FAISS.from_texts(
        chunks,
        embedding=embeddings
    )

    return vector_store


def create_ai_model(vector_store):
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError(
            "GROQ_API_KEY missing. Check your .env file."
        )

    llm = ChatGroq(
        model="openai/gpt-oss-20b",
        temperature=0.3,
        api_key=api_key
    )

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=vector_store.as_retriever(),
        return_source_documents=True
    )

    return qa_chain


def ask_ai(qa_chain, question):
    response = qa_chain.invoke({
        "query": question
    })

    return response["result"]