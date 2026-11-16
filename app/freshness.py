"""Use the newest code after a deploy.

Streamlit Cloud keeps the Python process running after a push and only runs app/main.py
again. Modules imported before the push (offpeak.*, ui.*, data) would stay in their old
version, which shows up as an ImportError for anything new. So on every run we check the
files of our own modules: if one changed, all of them are dropped from memory and Python
imports the new versions. Checking takes about a millisecond.
"""

import os
import sys

import streamlit as st

_seen: dict[str, float] = {}  # file -> last modified time when we last looked


def _process_started() -> float | None:
    """When this Python process started (Linux, as on Streamlit Cloud), else None."""
    try:
        return os.stat(f"/proc/{os.getpid()}").st_ctime
    except OSError:
        return None


_STARTED = _process_started()


def _ours(name: str) -> bool:
    return name in ("offpeak", "ui", "data") or name.startswith(("offpeak.", "ui."))


def refresh() -> bool:
    """Drop our modules if any of their files changed since we last looked, or, the first
    time we look at a file, since this process started (a deploy while it ran). True if
    something was dropped."""
    changed = False
    for name, module in list(sys.modules.items()):
        path = getattr(module, "__file__", None)
        if not _ours(name) or not path:
            continue
        try:
            modified = os.path.getmtime(path)
        except OSError:
            continue
        before = _seen.get(path)
        if before is not None and before != modified:
            changed = True
        elif before is None and _STARTED is not None and modified > _STARTED + 1:
            changed = True  # changed after this process started: imported before the deploy
        _seen[path] = modified
    if changed:
        for name in [n for n in sys.modules if _ours(n)]:
            del sys.modules[name]
        _seen.clear()  # filled again from the fresh imports on the next run
        st.cache_data.clear()  # results made by the old code
    return changed
