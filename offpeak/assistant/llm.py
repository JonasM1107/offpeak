"""One call to the language model, through Requesty (the course's standard AI router).

Requesty speaks the OpenAI chat format at router.requesty.ai/v1. The key comes from the
setting REQUESTY_API_KEY (Streamlit secrets or .env), never from code. We use free models
that support tool calling; if the first one fails, the next one is tried. Free plan limits:
200 requests a day and 20 a minute for the whole account, so the app limits questions too.
"""

import requests

URL = "https://router.requesty.ai/v1/chat/completions"
MODELS = ("nvidia/nemotron-3-ultra-550b-a55b", "google/gemma-4-31b-it")
TIMEOUT_S = 45


class AssistantUnavailable(RuntimeError):
    """The model could not answer (no key, network, limit reached, or every model failed)."""


def complete(
    messages: list[dict],
    tools: list[dict],
    api_key: str | None,
    models: tuple[str, ...] = MODELS,
    post=requests.post,
) -> dict:
    """The model's next message (dict with "content" and maybe "tool_calls")."""
    if not api_key:
        raise AssistantUnavailable("no API key")
    problems = []
    for model in models:
        try:
            response = post(
                URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": messages,
                    "tools": tools,
                    "temperature": 0.2,
                    "max_tokens": 1200,
                },
                timeout=TIMEOUT_S,
            )
        except requests.RequestException as err:
            problems.append(f"{model}: {type(err).__name__}")
            continue
        if response.status_code == 429:  # the free limit applies to every model
            raise AssistantUnavailable("request limit reached")
        if response.status_code != 200:
            problems.append(f"{model}: HTTP {response.status_code}")
            continue
        try:
            return response.json()["choices"][0]["message"]
        except (ValueError, KeyError, IndexError):
            problems.append(f"{model}: unexpected answer")
    raise AssistantUnavailable("; ".join(problems))
