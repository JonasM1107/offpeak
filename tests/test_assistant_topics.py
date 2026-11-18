"""Ollie's jump buttons: which pages an answer talks about (offpeak/assistant/topics.py)."""

import sys
from pathlib import Path

from offpeak.assistant.topics import MAX_TOPICS, TOPICS, topics_in

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))


def ids(answer):
    return [t["id"] for t in topics_in(answer)]


def test_an_answer_about_savings_offers_the_savings_page():
    assert ids("Your plan for this week saves **4.20 €**.")[0] == "savings"


def test_topics_come_in_the_order_the_answer_mentions_them():
    answer = "Sunday has the cheapest price. Your solar panels cover the morning."
    assert ids(answer) == ["analytics", "weather"]


def test_german_answers_are_understood_too():
    assert "savings" in ids("Damit sparst du 3 € pro Woche.")


def test_no_topic_no_buttons():
    assert topics_in("Hello! How can I help?") == []
    assert topics_in("") == []
    assert topics_in(None) == []


def test_at_most_a_few_buttons():
    answer = "price saved solar battery forecast machine"
    assert len(topics_in(answer)) == MAX_TOPICS


def test_words_match_at_word_starts_only():
    """'spun' must not count as 'pv', 'unsaved' not as 'save'."""
    assert topics_in("The wheel spun; the file is unsaved.") == []


def test_every_topic_has_a_page_in_the_app():
    from ui.assistant import PAGES

    assert {t[0] for t in TOPICS} == set(PAGES)
    for page in PAGES.values():
        assert (Path(__file__).parent.parent / "app" / page).exists()
