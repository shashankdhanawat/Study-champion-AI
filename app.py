import streamlit as st
from utils.pdf_reader import read_pdf
from utils.pdf_cleaning import clean_text
from utils.text_chuncker import chunk_text

st.title("STUDY CHAMPION🏆")
st.divider()
st.subheader("Your Personal Study Companion")   
st.write("Welcome to Study Champion! This app is designed to help you stay organized, track your study progress, and provide useful resources for effective learning. Whether you're preparing for exams or just looking to improve your study habits, Study Champion is here to support you every step of the way.")
if st.button("Start learning"):
    st.write("Let's get started! Please select a topic or subject you want to focus on.")
uploaded_file = st.file_uploader("Upload your study materials (PDF, DOCX, etc.)", type=["pdf", "docx"])
if uploaded_file is not None:
        st.write("File uploaded successfully!", f"File name: {uploaded_file.name}")
        
        temp_file_path = f"temp_{uploaded_file.name}"
        with open(temp_file_path, "wb") as f:
          f.write(uploaded_file.getbuffer())

          text = read_pdf(temp_file_path)
          cleaned_text = clean_text(text)
          chunks = chunk_text(cleaned_text)
          for i, chunk in enumerate(chunks):
              st.write(f"Chunk {i+1}:")
              st.text_area(f"Chunk {i+1}", chunk, height=100)