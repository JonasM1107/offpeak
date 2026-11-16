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
from pathlib import Path
from zoneinfo import ZoneInfo

import data
import streamlit as st
import streamlit.components.v1 as components

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


def api_key() -> str | None:
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
    key = api_key()
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


_window = components.declare_component(
    "offpeak_ollie", path=str(Path(__file__).with_name("web") / "ollie")
)


def widget() -> None:
    """Ollie at the bottom right of every page (web/ollie/index.html draws the robot and the
    chat window). A question typed there comes back as the component's value; it is answered
    here, before the window is drawn again with the answer."""
    history: list[dict] = st.session_state.setdefault("ollie", [])
    sent = st.session_state.get("ollie_chat")
    if isinstance(sent, dict) and sent.get("id") != st.session_state.get("ollie_seen"):
        st.session_state["ollie_seen"] = sent.get("id")
        question = str(sent.get("question") or "")[: agent.MAX_QUESTION_CHARS]
        answer = _reply(question, history)
        history += [{"role": "user", "content": question}, {"role": "assistant", "content": answer}]
    with st.container(key="ollie"):
        _window(history=history[-20:], examples=EXAMPLES, key="ollie_chat", default=None)
