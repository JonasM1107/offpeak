"""Ollie through Claude, with a fake client: the real API is never called."""

import json
from datetime import datetime
from types import SimpleNamespace

import anthropic
import pytest

from offpeak.assistant import agent, claude
from offpeak.assistant.llm import AssistantUnavailable
from offpeak.assistant.tools import SCHEMAS
from tests.test_assistant import ctx


class Block(SimpleNamespace):
    def to_dict(self):
        return dict(vars(self))


def reply(*blocks, stop="end_turn"):
    return SimpleNamespace(content=list(blocks), stop_reason=stop)


class FakeClient:
    """Answers with the given replies in turn and records each request."""

    def __init__(self, *replies):
        self.replies, self.requests = list(replies), []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **request):
        self.requests.append(json.loads(json.dumps(request, default=str)))
        answer = self.replies.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


THINK = Block(type="thinking", thinking="", signature="sig")
CALL = Block(
    type="tool_use",
    id="tu_1",
    name="find_best_time",
    input={"machine": "Heat pump", "day": "2026-11-14", "duration_hours": 3, "finish_by": 18},
)


def test_a_full_answer_with_a_tool_through_claude():
    fake = FakeClient(
        reply(THINK, CALL, stop="tool_use"), reply(Block(type="text", text="Saturday 13:00."))
    )
    text = agent.answer(
        "Wärmepumpe in 2 Tagen?",
        [],
        ctx(),
        lambda m, t: claude.complete(m, t, "key", client=fake),
        datetime(2026, 11, 12, 9),
    )
    assert text == "Saturday 13:00."
    first, second = fake.requests
    assert first["model"] == claude.MODEL and first["fallbacks"] == "default"
    assert "Today is 2026-11-12" in first["system"]
    assert {t["name"] for t in first["tools"]} == {s["function"]["name"] for s in SCHEMAS}
    assistant_turn, results = second["messages"][-2:]
    assert assistant_turn["content"][0]["type"] == "thinking"  # passed back unchanged
    result = results["content"][0]
    assert result["type"] == "tool_result" and result["tool_use_id"] == "tu_1"
    assert json.loads(result["content"])["best"] == "Sat 14 Nov · 13:00–16:00"


def test_tool_results_of_one_turn_go_in_one_message():
    system, chat = claude.to_claude(
        [
            {"role": "system", "content": "rules"},
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": "", "raw": [{"type": "tool_use", "id": "a"}]},
            {"role": "tool", "tool_call_id": "a", "content": "{}"},
            {"role": "tool", "tool_call_id": "b", "content": "{}"},
        ]
    )
    assert system == "rules" and [m["role"] for m in chat] == ["user", "assistant", "user"]
    assert [b["tool_use_id"] for b in chat[-1]["content"]] == ["a", "b"]


def test_a_refusal_becomes_a_polite_answer():
    out = claude.from_claude(reply(stop="refusal"))
    assert "can't help" in out["content"] and "tool_calls" not in out


def test_problems_with_the_api_say_ollie_is_unavailable():
    with pytest.raises(AssistantUnavailable, match="no Anthropic API key"):
        claude.complete([{"role": "user", "content": "q"}], SCHEMAS, None)
    down = anthropic.APIConnectionError.__new__(anthropic.APIConnectionError)
    with pytest.raises(AssistantUnavailable, match="not reachable"):
        claude.complete([{"role": "user", "content": "q"}], SCHEMAS, "key", client=FakeClient(down))


def test_a_chosen_model_is_used():
    fake = FakeClient(reply(Block(type="text", text="ok")))
    claude.complete([{"role": "user", "content": "q"}], SCHEMAS, "key", "claude-haiku-5-5", fake)
    assert fake.requests[0]["model"] == "claude-haiku-5-5"
