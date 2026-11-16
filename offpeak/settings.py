"""Finding a setting (DATABASE_URL, ANTHROPIC_API_KEY, ...) in the app's secrets.

Streamlit secrets are a TOML file. A line written below a heading such as [database] belongs
to that section, not to the top level, which is an easy mistake when pasting several
settings. So a setting is looked up at the top level first, then in each section.
"""

from collections.abc import Mapping


def lookup(secrets: Mapping, name: str):
    """The value of `name`: at the top level, else in the first section that has it."""
    try:
        if name in secrets and not isinstance(secrets[name], Mapping):
            return secrets[name]
        for value in secrets.values():
            if isinstance(value, Mapping) and name in value:
                return value[name]
    except Exception:  # no secrets file at all, or it cannot be read
        return None
    return None
