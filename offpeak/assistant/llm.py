"""What can go wrong when Ollie asks its language model.

Ollie talks to Claude through the Anthropic API (claude.py), with the team's key from the
setting ANTHROPIC_API_KEY (Streamlit secrets or .env), never from code. Whatever goes wrong
there (no key, network, limit, a refused request) is raised as AssistantUnavailable, so the
chat can say "Ollie can't answer right now" while every other page keeps working.
"""


class AssistantUnavailable(RuntimeError):
    """The model could not answer (no key, network, limit reached, or an error)."""
