"""Ollie's conversation: the instructions, and the loop that lets the model look things up.

How one answer is made:
1. The model gets Ollie's instructions (today's date, the known days, the rules), the
   recent conversation and the new question, plus the list of tools (tools.py).
2. If it asks for tools, they run on our data and the results go back to it.
3. When it answers in words, that is the answer. At most MAX_ROUNDS lookups per question.

`llm` is passed in (llm.complete in the app, a fake in the tests), so tests never call a
real model.
"""

import json
from collections.abc import Callable
from datetime import datetime

from offpeak.assistant.tools import SCHEMAS, Context, known_days, run_tool

NAME = "Ollie"
MAX_ROUNDS = 5
MAX_QUESTION_CHARS = 500
HISTORY_TURNS = 6  # earlier messages sent along, so follow-up questions work

SORRY = "Sorry, I couldn't work that out just now. Please try asking in a different way."

INSTRUCTIONS = """You are Ollie, the energy assistant in offpeak, an app that tells a small \
business in Germany when to use electricity. The site is a demo site in Köln.

Now: {now} (German time). Today is {today}.
Days with prices: {days}.

How to answer:
- Answer in the language of the question.
- Get every number from the tools: prices, times, costs, savings. Never guess or compute \
prices yourself. Resolve dates like "in 3 days" or "on Friday" from today's date above.
- For "when should I run ..." questions, call find_best_time. If the device is one of the \
site's machines, pass machine; otherwise pass power_kw, or ask for the power if unknown.
- Lead with the answer: the day and the start and end time. Then the cost, the saving and \
one short reason (for example cheap night prices or own solar power). Keep it short: a few \
lines, simple markdown, no tables unless asked.
- Prices are all-in ct/kWh (spot price plus grid fees, levies and tax). Costs are in euros.
- Prices for today and tomorrow are published. Later days are an estimate by Offpeak \
Intelligence: say so in a few words and give the likely range when it matters.
- Never mention tools, models, machine learning or training. Call the outlook "Offpeak \
Intelligence".
- If a tool returns an error, fix the request or ask the person. If something is outside \
the known days or unrelated to energy use at this site, say so politely in one sentence."""


def instructions(ctx: Context, now: datetime) -> str:
    days = ", ".join(
        f"{d['date'].isoformat()} {d['name']} "
        f"({'published' if ctx.hours['kind'][d['start']] == 'published' else 'estimate'})"
        for d in known_days(ctx)
    )
    return INSTRUCTIONS.format(
        now=f"{now:%A %-d %B %Y, %H:%M}", today=ctx.today.isoformat(), days=days
    )


def clean_question(text) -> str:
    """The question as it may be sent: text, trimmed, not empty, not too long."""
    question = str(text or "").strip()
    if not question:
        raise ValueError("Please type a question.")
    if len(question) > MAX_QUESTION_CHARS:
        raise ValueError(f"Please keep questions under {MAX_QUESTION_CHARS} characters.")
    return question


def answer(
    question: str,
    history: list[dict],
    ctx: Context,
    llm: Callable[[list[dict], list[dict]], dict],
    now: datetime,
) -> str:
    """Ollie's answer. `history` holds earlier {"role", "content"} messages of this chat.
    llm.AssistantUnavailable from `llm` is passed on to the caller."""
    messages = [{"role": "system", "content": instructions(ctx, now)}]
    messages += [
        {"role": m["role"], "content": m["content"]}
        for m in history[-2 * HISTORY_TURNS :]
        if m.get("role") in ("user", "assistant")
    ]
    messages.append({"role": "user", "content": clean_question(question)})
    for _ in range(MAX_ROUNDS):
        reply = llm(messages, SCHEMAS)
        calls = reply.get("tool_calls") or []
        if not calls:
            text = (reply.get("content") or "").strip()
            return text or SORRY
        messages.append(
            {"role": "assistant", "content": reply.get("content") or "", "tool_calls": calls}
        )
        for call in calls:
            fn = call.get("function") or {}
            result = run_tool(ctx, fn.get("name", ""), fn.get("arguments"))
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id", ""),
                    "content": json.dumps(result, default=str),
                }
            )
    return SORRY
