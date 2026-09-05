"""23 · app.py — entry point: Streamlit chat UI, the full secure pipeline,
behind a Google OAuth gate when [auth] secrets are configured.

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
from hr_assistant.tracing import check_langsmith_tracing

# Guardrail / cache telemetry (INPUT GUARDRAIL:, CACHE HIT, ...) goes
# through logging -> the server console / Cloud Run logs, not the chat UI.
configure_logging()
check_langsmith_tracing()  # logs once whether this run is traced

st.set_page_config(page_title="HR Policy Assistant", page_icon="🤖")
st.title("🤖 HR Policy Assistant")
st.caption("Ask me anything about company HR policy — leave, WFH, notice period, and more.")

from hr_assistant import config


def _auth_configured() -> bool:
    """True only when Streamlit's [auth] block is present (i.e. the
    streamlit-auth secret is mounted, as it is on Cloud Run). Locally,
    without it, we run in open mode instead of crashing on st.user."""
    try:
        return bool(st.secrets.get("auth"))
    except Exception:
        return False


if _auth_configured():
    if not st.user.is_logged_in:
        st.info("Please log in with your company Google account.")
        st.button("Log in with Google", on_click=st.login, args=("google",))
        st.stop()

    if st.user.email not in config.ALLOWED_EMPLOYEE_EMAILS:
        st.error(f"'{st.user.email}' isn't on the approved employee list.")
        st.button("Log out", on_click=st.logout)
        st.stop()

    st.sidebar.caption(f"Logged in as {st.user.email}")
    st.sidebar.button("Log out", on_click=st.logout)
else:
    st.sidebar.warning("Open local mode — Google login is not configured.")


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
