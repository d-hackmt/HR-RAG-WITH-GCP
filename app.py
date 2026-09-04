"""23 · app.py — entry point: Streamlit chat UI, the full secure pipeline.
(No login on this branch — the Google OAuth gate is added in `deployment`.)

Run with:  streamlit run app.py
"""

import uuid

import streamlit as st

from hr_assistant.logging_config import configure_logging
from hr_assistant.pipeline import (
    INPUT_BLOCKED_MESSAGE,
    OUTPUT_BLOCKED_MESSAGE,
    ask,
    build_hr_assistant,
)
from hr_assistant.tracing import check_langsmith_tracing, enable_tracing

# Guardrail / cache telemetry (INPUT GUARDRAIL:, CACHE HIT, ...) goes
# through logging -> the server console, not the chat UI.
configure_logging()

# Make sure LangChain sees the LANGSMITH_* env vars before any agent runs.
enable_tracing()

st.set_page_config(page_title="HR Policy Assistant", page_icon="🤖")
st.title("🤖 HR Policy Assistant")
st.caption("Ask me anything about company HR policy — leave, WFH, notice period, and more.")

from hr_assistant import config


@st.cache_resource(show_spinner=False)
def _tracing_status():
    """Run the LangSmith connectivity check once per session."""
    try:
        return check_langsmith_tracing()
    except Exception as exc:  # never let a health check break the app
        return False, f"LangSmith check errored: {exc}"


_ok, _msg = _tracing_status()
st.sidebar.caption(("🟢 " if _ok else "⚪ ") + _msg)
st.sidebar.caption(f"🛡️ Safety guardrail: {config.GUARDRAIL_PROVIDER}")


@st.cache_resource(show_spinner="Setting up the assistant (only happens once)...")
def get_agent():
    return build_hr_assistant()  # (agent, cache) — the guarded, cached, clean-collection stack


agent, cache = get_agent()

if "thread_id" not in st.session_state:
    # One thread_id per browser session — keeps this conversation's memory
    # separate from any other visitor's, and separate from a page refresh
    # if you want a clean slate (see the "New conversation" button below).
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
            answer = ask(agent, cache, question, thread_id=st.session_state.thread_id)
        if answer in (INPUT_BLOCKED_MESSAGE, OUTPUT_BLOCKED_MESSAGE):
            st.warning(answer)
        else:
            st.markdown(answer)

    # Keep the visible transcript in step with the agent's own memory:
    #  - input block  -> ask() kept the prompt out of memory entirely; keep
    #    it out of the transcript too (just the ephemeral warning above).
    #  - output block -> ask() recorded [question, blocked notice] in memory;
    #    mirror that here.
    #  - normal answer / cache hit -> recorded in memory; mirror it here.
    if answer != INPUT_BLOCKED_MESSAGE:
        st.session_state.messages.append({"role": "user", "content": question})
        st.session_state.messages.append({"role": "assistant", "content": answer})
