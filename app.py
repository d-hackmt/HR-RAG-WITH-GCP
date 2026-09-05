"""18 · app.py — entry point: Streamlit chat UI.

Run with:  streamlit run app.py
"""

import uuid

import streamlit as st

from hr_assistant.logging_config import configure_logging
from hr_assistant.pipeline import ask, build_hr_assistant
from hr_assistant.tracing import check_langsmith_tracing

configure_logging()
check_langsmith_tracing()  # logs once whether this run is traced

st.set_page_config(page_title="HR Policy Assistant", page_icon="🤖")
st.title("🤖 HR Policy Assistant")
st.caption("Ask me anything about company HR policy — leave, WFH, notice period, and more.")


@st.cache_resource(show_spinner="Setting up the assistant (only happens once)...")
def get_agent():
    return build_hr_assistant()


agent = get_agent()

if "thread_id" not in st.session_state:
    # One thread_id per browser session — keeps this conversation's memory
    # separate from any other visitor's.
    st.session_state.thread_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if st.sidebar.button("New conversation"):
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.messages = []
    st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input("Ask a question about HR policy...")

if question:
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            answer = ask(agent, question, thread_id=st.session_state.thread_id)
        st.markdown(answer)

    st.session_state.messages.append({"role": "user", "content": question})
    st.session_state.messages.append({"role": "assistant", "content": answer})
