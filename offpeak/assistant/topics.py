"""Which app pages an answer of Ollie's talks about, so the chat can offer a jump there.

Plain word matching, no model call: an answer that mentions "savings" gets a button to the
Savings page. The page files themselves are known only to the app (app/ui/assistant.py);
here a topic is just an id, a button label and the words that point to it.
"""

import re

MAX_TOPICS = 3  # more buttons than that under one answer would be noise

# (id, button label, words that point to it), matched at word starts. Order breaks ties.
# Words kept specific: "plan" is in almost every answer, "sun" is in "Sunday".
TOPICS = [
    ("savings", "Savings", ["saving", "saved", "save", "backtest", "replay", "spar", "erspar"]),
    ("cockpit", "Planner", ["machine", "run the", "start at", "schedule", "maschine"]),
    ("outlook", "Price outlook", ["forecast", "tomorrow", "next week", "outlook", "prognose"]),
    (
        "weather",
        "Weather & solar",
        ["solar", "pv", "weather", "sunny", "sunshine", "wetter", "sonne"],
    ),
    ("analytics", "Power prices", ["price", "ct/kwh", "cheap", "negative", "preis", "günstig"]),
    ("site", "Site view", ["battery", "heat pump", "furnace", "component", "batterie"]),
]


def _position(text: str, words: list[str]) -> int | None:
    """Where in the text the first of these words appears (word start), or None."""
    found = [
        m.start() for w in words if (m := re.search(r"\b" + re.escape(w), text, re.IGNORECASE))
    ]
    return min(found) if found else None


def topics_in(answer: str) -> list[dict]:
    """The pages this answer talks about, in the order it mentions them, at most MAX_TOPICS:
    [{"id": "savings", "label": "Savings"}, ...]. Empty for an empty answer."""
    hits = []
    for order, (topic_id, label, words) in enumerate(TOPICS):
        pos = _position(answer or "", words)
        if pos is not None:
            hits.append((pos, order, topic_id, label))
    hits.sort()
    return [{"id": t, "label": label} for _, _, t, label in hits[:MAX_TOPICS]]
