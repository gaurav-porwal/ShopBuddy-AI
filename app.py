"""
Streamlit chat UI for Shop Buddy that switches between
CrewAI, AutoGen, and LangGraph APIs
and displays conversation history.
"""

import streamlit as st
import requests

# ------------------ CONFIG ------------------

CREW_API = "http://localhost:8000/crew_chat/"
AUTOGEN_API = "http://localhost:8000/autogen_chat/"
LANGGRAPH_API = "http://localhost:8000/langgraph_chat/"

st.set_page_config(page_title="Shop Buddy", page_icon="", layout="wide")

# ------------------ STYLING ------------------

st.markdown("""
<style>
.chat-container{
    max-width:800px;
    margin:auto;
}
.user-msg{
    background-color:#dfe6e9;
    padding:10px;
    border-radius:10px;
    margin:5px 0;
    text-align:right;
}
.bot-msg{
    background-color:#f1f2f6;
    padding:10px;
    border-radius:10px;
    margin:5px 0;
    text-align:left;
}
.title{
    text-align:center;
    font-size:32px;
    font-weight:bold;
}
</style>
""", unsafe_allow_html=True)

# ------------------ SIDEBAR ------------------

with st.sidebar:
    st.title("Settings")

    mode = st.radio(
        "Choose Engine",
        ["CrewAI", "AutoGen", "LangGraph"]
    )

    st.markdown("---")

    if st.button("Clear Chat"):
        st.session_state.messages = []

    st.markdown("### Info")

    st.write(
        "Switch between CrewAI, AutoGen, and LangGraph to compare behavior."
    )

# ------------------ TITLE ------------------

st.markdown(
    '<div class="title">Shop Buddy</div>',
    unsafe_allow_html=True
)

st.write("Your AI Shopping Assistant")

# ------------------ SESSION STATE ------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

# ------------------ DISPLAY CHAT ------------------

st.markdown(
    '<div class="chat-container">',
    unsafe_allow_html=True
)

for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(
            f'<div class="user-msg">{msg["content"]}</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f'<div class="bot-msg">{msg["content"]}</div>',
            unsafe_allow_html=True
        )

st.markdown('</div>', unsafe_allow_html=True)

# ------------------ INPUT ------------------

user_input = st.chat_input("Type your message...")

if user_input:

    # Save user message
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })

    # Choose API
    if mode == "CrewAI":
        url = CREW_API
    elif mode == "AutoGen":
        url = AUTOGEN_API
    else:
        url = LANGGRAPH_API

    # API CALL
    with st.spinner("Thinking..."):
        try:
            response = requests.post(
                url,
                params={"query": user_input}
            )

            if response.status_code == 200:
                data = response.json()

                # Extract response
                reply = data.get(
                    "response",
                    str(data)
                )
            else:
                reply = "API Error"

        except Exception as e:
            reply = f"Error: {e}"

    # Save bot response
    st.session_state.messages.append({
        "role": "bot",
        "content": reply
    })

    st.rerun()