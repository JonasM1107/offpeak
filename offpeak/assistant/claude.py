"""Ollie through Claude (Anthropic API), with the team's own key from the Claude Console.

Why a second provider: the course's standard router is Requesty (llm.py), but the team has
a budget in the Claude Console, so Ollie uses Claude directly when ANTHROPIC_API_KEY is set.
Without it, Ollie keeps using the free models through Requesty.

The conversation in agent.py is written in one format (role, content, tool_calls). This
file translates it to Claude's Messages API and the answer back:
- the system message becomes `system`, the tool list becomes Claude's tool definitions;
- an assistant turn that called tools goes back exactly as Claude sent it (its thinking
  blocks included, which Claude needs to continue), kept in the message's "raw" field;
- tool results become `tool_result` blocks, all results of one turn in one user message.

If Claude declines a request for safety reasons, the API's built-in fallback lets another
Claude model answer instead ("fallbacks": "default").
"""

import json

from offpeak.assistant.llm import AssistantUnavailable

MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _tools(schemas: list[dict]) -> list[dict]:
    return [
        {
            "name": s["function"]["name"],
            "description": s["function"]["description"],
            "input_schema": s["function"]["parameters"],
        }
        for s in schemas
    ]


def to_claude(messages: list[dict]) -> tuple[str, list[dict]]:
    """agent.py's messages as Claude's (system, messages)."""
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    out: list[dict] = []
    for m in messages:
        if m["role"] == "system":
            continue
        if m["role"] == "tool":
            block = {
                "type": "tool_result",
                "tool_use_id": m["tool_call_id"],
                "content": m["content"],
            }
            last = out[-1] if out else None
            if last and last["role"] == "user" and isinstance(last["content"], list):
                last["content"].append(block)  # every result of one turn in one message
            else:
                out.append({"role": "user", "content": [block]})
        elif m["role"] == "assistant" and m.get("raw"):
            out.append({"role": "assistant", "content": m["raw"]})  # unchanged, as sent
        else:
            out.append({"role": m["role"], "content": m["content"] or ""})
    return system, out


def from_claude(response) -> dict:
    """Claude's answer in agent.py's format: content, tool_calls, and the raw blocks."""
    if response.stop_reason == "refusal":
        return {"content": "Sorry, I can't help with that one. Ask me about energy use."}
    text, calls = [], []
    for block in response.content:
        if block.type == "text":
            text.append(block.text)
        elif block.type == "tool_use":
            calls.append(
                {
                    "id": block.id,
                    "type": "function",
                    "function": {"name": block.name, "arguments": json.dumps(block.input)},
                }
            )
    reply = {"content": "".join(text)}
    if calls:
        reply["tool_calls"] = calls
        reply["raw"] = [block.to_dict() for block in response.content]
    return reply


def complete(
    messages: list[dict],
    schemas: list[dict],
    api_key: str | None,
    model: str | None = None,
    client=None,
) -> dict:
    """Claude's next message for agent.answer (same contract as llm.complete)."""
    if not api_key and client is None:
        raise AssistantUnavailable("no Anthropic API key")
    # Imported here, not at the top: the SDK takes about a second to load, and every page
    # loads this file through Ollie, even when Ollie runs on Requesty and never needs it.
    import anthropic

    client = client or anthropic.Anthropic(api_key=api_key, timeout=60.0, max_retries=1)
    system, chat = to_claude(messages)
    try:
        response = client.beta.messages.create(
            model=model or MODEL,
            max_tokens=4000,
            system=system,
            messages=chat,
            tools=_tools(schemas),
            output_config={"effort": "low"},  # a chat answer: quick and short
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
    except anthropic.RateLimitError as err:
        raise AssistantUnavailable("request limit reached") from err
    except anthropic.AuthenticationError as err:
        raise AssistantUnavailable("the Anthropic API key was not accepted") from err
    except anthropic.APIStatusError as err:
        raise AssistantUnavailable(f"Anthropic API error {err.status_code}") from err
    except anthropic.APIConnectionError as err:
        raise AssistantUnavailable("Anthropic API not reachable") from err
    return from_claude(response)
