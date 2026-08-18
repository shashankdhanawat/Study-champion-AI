import streamlit as st

st.title("STUDY CHAMPION🏆")
st.divider()
st.subheader("Your Personal Study Companion")   
st.write("Welcome to Study Champion! This app is designed to help you stay organized, track your study progress, and provide useful resources for effective learning. Whether you're preparing for exams or just looking to improve your study habits, Study Champion is here to support you every step of the way.")
if st.button("Start learning"):
    st.write("Let's get started! Please select a topic or subject you want to focus on.")
    uploaded_file = st.file_uploader("Upload your study materials (PDF, DOCX, etc.)", type=["pdf", "docx"])
    if uploaded_file is not None:
        st.write("File uploaded successfully!", f"File name: {uploaded_file.name}")
        


