import streamlit as st
from pathlib import Path
import base64

from utils.pdf_reader import read_pdf
from utils.pdf_cleaning import clean_text
from utils.text_chuncker import chunk_text
from services.rag_pipeline import answer_question


st.set_page_config(
    page_title="Study Champion AI",
    page_icon="🏆",
    layout="wide"
)


NAVY = "#0B1F3A"
NAVY_LIGHT = "#12345A"
WHITE = "#FFFFFF"
LIGHT = "#F5F8FC"


def set_background(image_path):

    if image_path.exists():

        image_data = base64.b64encode(
            image_path.read_bytes()
        ).decode()

        st.markdown(
            f"""
            <style>

            [data-testid="stAppViewContainer"] {{
                background:
                linear-gradient(
                    rgba(11,31,58,0.85),
                    rgba(11,31,58,0.90)
                ),
                url("data:image/jpg;base64,{image_data}");

                background-size:cover;
                background-position:center;
                background-attachment:fixed;
            }}

            [data-testid="stHeader"] {{
                background:transparent;
            }}

            </style>
            """,
            unsafe_allow_html=True
        )


def common_css():

    st.markdown(
        f"""
        <style>

        [data-testid="stMainBlockContainer"] {{
            max-width:1200px;
        }}


        div.stButton {{
            display:flex;
            justify-content:center;
        }}
        
        [data-testid="stSidebar"] div.stButton > button {{

          width:100%;

          height:50px;

          border-radius:12px;

         background:#12345A;

         color:white;

         font-size:16px;

         font-weight:600;

         border:1px solid rgba(255,255,255,0.2);

         margin-bottom:10px;

         transition:0.3s;

}}
[data-testid="stSidebar"] .stButton {{

    margin-bottom: 12px !important;

}}


         [data-testid="stSidebar"] div.stButton > button:hover {{

         background:white;

         color:#0B1F3A;

         transform:translateX(5px);

}}


        div.stButton > button {{

            background:{WHITE};
            color:{NAVY};

            border-radius:12px;
            padding:12px 30px;

            font-weight:700;
            border:none;

            transition:0.3s;

        }}


        div.stButton > button:hover {{

            background:{NAVY};
            color:white;

            transform:translateY(-3px);

            border:1px solid white;

        }}



        .landing {{
            text-align:center;
            padding:50px;
        }}



        .badge {{

            display:inline-block;

            padding:10px 20px;

            border-radius:30px;

            background:
            rgba(255,255,255,0.12);

            color:white;

            font-weight:700;

            letter-spacing:1px;

        }}



        .title {{

            color:white;

            font-size:70px;

            font-weight:900;

            margin-top:25px;

        }}



        .subtitle {{

            color:white;

            font-size:20px;

            max-width:750px;

            margin:auto;

            line-height:1.7;

        }}



        .chips {{

            margin-top:35px;

        }}



        .chip {{

            display:inline-block;

            padding:12px 20px;

            margin:8px;

            border-radius:30px;

            background:
            rgba(255,255,255,0.12);

            color:white;

        }}



        .hero {{

            background:white;

            padding:40px;

            border-radius:25px;

            text-align:center;

            box-shadow:
            0 10px 30px rgba(0,0,0,0.08);

        }}



        .hero h1 {{

            color:{NAVY};

            font-size:50px;

        }}



        .hero p {{

            color:#52647A;

            font-size:18px;

        }}



        .card {{

         background:#0B1F3A;

         padding:30px;

         border-radius:20px;

          text-align:center;

         color:white;

          height:220px;

         display:flex;

         flex-direction:column;

         justify-content:center;

         transition:0.3s;

}}



        .card:hover {{

            transform:translateY(-8px);

        }}



        .icon {{

            font-size:45px;

        }}



        .card h2 {{

            color:white;

        }}



        .card p {{

            color:#DDE6F2;

        }}



        .upload {{

            background:
            linear-gradient(
            135deg,
            {NAVY},
            {NAVY_LIGHT}
            );

            padding:40px;

            border-radius:25px;

            text-align:center;

            margin-top:40px;

            color:white;

        }}



        </style>
        """,
        unsafe_allow_html=True
    )


if "page" not in st.session_state:
    st.session_state.page = "landing"

if "chunks" not in st.session_state:
    st.session_state.chunks = []


common_css()


if st.session_state.page == "landing":

    set_background(
        Path("assets/background.jpg")
    )


    st.markdown(
        """
        <div class="landing">


        <div class="badge">
        ✦ AI POWERED LEARNING ✦
        </div>


        <div class="title">
        STUDY CHAMPION 🏆
        </div>


        <div class="subtitle">

        Your personal AI study companion designed
        to transform study material into a smarter,
        simpler and interactive learning experience.

        </div>


        <div class="chips">

        <span class="chip">
        📚 Smart Learning
        </span>

        <span class="chip">
        🧠 AI Assistance
        </span>

        <span class="chip">
        🎯 Progress Tracking
        </span>

        <span class="chip">
        ⚡ Fast & Simple
        </span>

        </div>


        </div>
        """,
        unsafe_allow_html=True
    )
    st.divider()

    if st.button(
        "START LEARNING →"
    ):

        st.session_state.page="home"

        st.rerun()


else:

    st.markdown(
        """
        <div class="hero">

        <h1>
        STUDY CHAMPION AI
        </h1>

        <p>
        Learn smarter. Stay organized.
        Turn your study material into
        intelligent learning content.
        </p>

        </div>
        """,
        unsafe_allow_html=True
    )
    st.divider()


    col1,col2,col3 = st.columns(3)

    with col1:

        st.markdown(
            """
            <div class="card">

            <div class="icon">
            📚
            </div>

            <h2>
            TOPICS
            </h2>

            <p>
            Explore and organize your study topics.
            </p>

            </div>
            """,
            unsafe_allow_html=True
        )


    with col2:

        st.markdown(
            """
            <div class="card">

            <div class="icon">
            🎯
            </div>

            <h2>
            PROGRESS
            </h2>

            <p>
            Track your learning progress.
            </p>

            </div>
            """,
            unsafe_allow_html=True
        )


    with col3:

        st.markdown(
            """
            <div class="card">

            <div class="icon">
            🧠
            </div>

            <h2>
            QUIZ
            </h2>

            <p>
            Test your knowledge with AI quizzes.
            </p>

            </div>
            """,
            unsafe_allow_html=True
        )


    st.markdown(
        """
        <div class="upload">

        <h1>
        📚 Upload Your Study Material
        </h1>

        <p>
        Upload your PDF and convert it into
        clean study-ready content.
        </p>

        </div>
        """,
        unsafe_allow_html=True
    )


    uploaded_file = st.file_uploader(
        "Upload your study material",
        type=["pdf"]
    )


    if uploaded_file is not None:


        st.success(
            f"File uploaded successfully: {uploaded_file.name}"
        )


        temp_path = f"temp_{uploaded_file.name}"


        with open(temp_path,"wb") as f:

            f.write(
                uploaded_file.getbuffer()
            )


        with st.spinner(
            "Processing your PDF..."
        ):


            text = read_pdf(temp_path)

            cleaned_text = clean_text(text)

            chunks = chunk_text(cleaned_text)

        st.session_state.chunks = chunks



        st.success(
            "PDF processed successfully!"
        )


        col1,col2 = st.columns(2)


        with col1:

            st.metric(
                "Characters",
                len(cleaned_text)
            )


        with col2:

            st.metric(
                "Chunks",
                len(chunks)
            )



        st.subheader(
            "Generated Study Content"
        )


        for i,chunk in enumerate(chunks):


            with st.expander(
                f"Chunk {i+1}"
            ):

                st.write(chunk)

st.markdown(
    '<div class="section-title">💬 AI Study Chat</div>',
    unsafe_allow_html=True
)


# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []


# Display previous messages
for message in st.session_state.messages:

    if message["role"] == "user":

        st.chat_message("user").write(
            message["content"]
        )

    else:

        st.chat_message("assistant").write(
            message["content"]
        )


# Chat input
if "chunks" in st.session_state:

    question = st.chat_input(
        "Ask something from your document..."
    )


    if question:

        # show user message
        st.chat_message("user").write(question)


        # generate answer
        with st.spinner("AI is thinking..."):

            answer = answer_question(
                st.session_state.chunks,
                question
            )


        # show AI message
        st.chat_message("assistant").write(answer)


        # save history

        st.session_state.messages.append(
            {
                "role": "user",
                "content": question
            }
        )

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": answer
            }
        )

else:

    st.info("Upload a PDF first to start asking questions.")


    with st.sidebar:


        st.markdown(
            """
            <h2 style="color:white;">
            🏆 STUDY CHAMPION
            </h2>

            <p style="color:#DDE6F2;">
            Your AI Study Companion
            </p>
            """,
            unsafe_allow_html=True
        )


        st.divider()



        if st.button(
            "🏠 Dashboard"
        ):

            st.session_state.page="home"

            st.rerun()



        if st.button(
            "📚 Topics"
        ):

            st.info(
                "Topics module coming soon."
            )



        if st.button(
            "🎯 Progress"
        ):

            st.info(
                "Progress module coming soon."
            )



        if st.button(
            "🧠 Quiz"
        ):

            st.info(
                "Quiz module coming soon."
            )



        st.divider()



        if st.button(
            "← Back to Welcome"
        ):

            st.session_state.page="landing"

            st.rerun()