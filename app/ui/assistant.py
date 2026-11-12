"""Ask Ollie: the chat button at the bottom right of every page.

The answers come from offpeak/assistant/ (the conversation and the tools that look up the
app's own data). This file only draws the chat and passes the question on.

Safeguards: questions are checked (not empty, at most 500 characters), and each visitor can
ask MAX_QUESTIONS per session, because the free Requesty plan allows 200 requests a day for
the whole app. Without a key, or when the model is unavailable, Ollie says so instead of
failing.
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import data
import streamlit as st

from offpeak.assistant import agent, llm
from offpeak.assistant.tools import Context
from offpeak.timeutils import market_today

MAX_QUESTIONS = 25
EXAMPLES = [
    "When should I run the heat pump in 3 days? 3 hours, done by 18:00.",
    "Which day this week has the cheapest power?",
    "What does my plan for this week save?",
]
BUSY = (
    "Ollie can't answer right now. Please try again in a moment; the plan on the dashboard "
    "and the Simulation cockpit work as usual."
)


def _api_key() -> str | None:
    try:
        key = st.secrets.get("REQUESTY_API_KEY")
    except Exception:  # no secrets file
        key = None
    return key or os.environ.get("REQUESTY_API_KEY")


def _context() -> Context | None:
    """The data Ollie answers from, or None if prices or weather are unavailable."""
    ahead = data.hours_ahead()
    if ahead is None:
        return None
    hours, now_index = ahead
    machines, _, _ = data.machines_to_plan()
    components, _ = data.site_components()
    site = [{"name": c.name, "kind": c.kind, "params": c.params} for c in components]
    return Context(hours, now_index, machines, site, market_today())


def _reply(question: str, history: list[dict]) -> str:
    asked = st.session_state.get("ollie_asked", 0)
    if asked >= MAX_QUESTIONS:
        return "That's all the questions I can take for now. Please come back later."
    try:
        question = agent.clean_question(question)
    except ValueError as err:
        return str(err)
    ctx = _context()
    if ctx is None:
        return "I can't see the prices right now, so I can't plan. Please try again soon."
    st.session_state["ollie_asked"] = asked + 1
    key = _api_key()
    try:
        return agent.answer(
            question,
            history,
            ctx,
            lambda messages, tools: llm.complete(messages, tools, key),
            datetime.now(ZoneInfo("Europe/Berlin")),
        )
    except llm.AssistantUnavailable as err:
        print(f"offpeak: Ollie unavailable: {err}")
        return BUSY


@st.dialog("Ask Ollie", width="medium")
def _chat() -> None:
    history: list[dict] = st.session_state.setdefault("ollie", [])
    if not history:
        st.markdown(
            "Hi, I'm **Ollie**. Ask me when to run a machine, which day is cheapest, or what "
            "your plan saves. I use today's prices and Offpeak Intelligence."
        )
        for i, example in enumerate(EXAMPLES):
            if st.button(example, key=f"ollie_example_{i}", width="stretch"):
                st.session_state["ollie_pending"] = example
    for m in history:
        icon = ":material/bolt:" if m["role"] == "assistant" else ":material/person:"
        with st.chat_message(m["role"], avatar=icon):
            st.markdown(m["content"])

    with st.form("ollie_form", clear_on_submit=True, border=False):
        ask, send = st.columns([5, 1], vertical_alignment="bottom")
        question = ask.text_input(
            "Your question",
            placeholder="e.g. When should I charge the EVs on Saturday?",
            max_chars=agent.MAX_QUESTION_CHARS,
            label_visibility="collapsed",
        )
        sent = send.form_submit_button("Send", type="primary", width="stretch")
    pending = st.session_state.pop("ollie_pending", None)
    if pending or (sent and question.strip()):
        question = pending or question
        with st.spinner("Ollie is checking the prices…"):
            text = _reply(question, history)
        history += [{"role": "user", "content": question}, {"role": "assistant", "content": text}]
        st.rerun(scope="fragment")


def widget() -> None:
    """The round "Ask Ollie" button, fixed at the bottom right (styled in components.py)."""
    with st.container(key="ollie_fab"):
        if st.button("Ask Ollie", icon=":material/forum:", key="ollie_open", type="primary"):
            _chat()
