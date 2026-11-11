from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).parent.parent / "app" / "main.py"


def test_app_starts_without_errors():
    at = AppTest.from_file(str(APP)).run()
    assert not at.exception
