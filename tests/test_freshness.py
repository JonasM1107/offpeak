import sys
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))
import freshness  # noqa: E402


def test_changed_files_drop_our_modules_but_nothing_else(tmp_path, monkeypatch):
    monkeypatch.setattr(freshness, "_since", None)
    monkeypatch.setattr(sys, "modules", dict(sys.modules))  # a copy: the real ones stay loaded
    monkeypatch.setattr(freshness, "_seen", {})
    monkeypatch.setattr(freshness.st.cache_data, "clear", lambda: None)
    source = tmp_path / "fake.py"
    source.write_text("x = 1")
    ours, theirs = types.ModuleType("offpeak.fake_mod"), types.ModuleType("pandas_fake_mod")
    ours.__file__ = theirs.__file__ = str(source)
    monkeypatch.setitem(sys.modules, "offpeak.fake_mod", ours)
    monkeypatch.setitem(sys.modules, "pandas_fake_mod", theirs)

    assert freshness.refresh() is False  # first look: remember the files
    assert freshness.refresh() is False  # nothing changed
    later = time.time() + 5
    import os

    os.utime(source, (later, later))  # a deploy changed the file
    assert freshness.refresh() is True
    assert "offpeak.fake_mod" not in sys.modules  # ours: dropped, imported fresh next time
    assert "pandas_fake_mod" in sys.modules  # not ours: untouched


def test_a_file_changed_after_the_process_started_counts_as_a_deploy(tmp_path, monkeypatch):
    monkeypatch.setattr(freshness, "_seen", {})
    monkeypatch.setattr(freshness.st.cache_data, "clear", lambda: None)
    source = tmp_path / "fake.py"
    source.write_text("x = 1")
    monkeypatch.setattr(freshness, "_since", source.stat().st_mtime - 60)  # started before
    monkeypatch.setattr(sys, "modules", dict(sys.modules))  # a copy: the real ones stay loaded
    mod = types.ModuleType("offpeak.deployed_mod")
    mod.__file__ = str(source)
    monkeypatch.setitem(sys.modules, "offpeak.deployed_mod", mod)
    assert freshness.refresh() is True and "offpeak.deployed_mod" not in sys.modules
    # imported again from the same (new) file: one deploy reloads once, not on every run
    sys.modules["offpeak.deployed_mod"] = mod
    assert freshness.refresh() is False
    assert freshness.refresh() is False
