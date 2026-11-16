from offpeak.settings import lookup


def test_settings_are_found_at_the_top_or_in_a_section():
    secrets = {"A": "top", "database": {"DATABASE_URL": "postgresql://x"}, "B": {"A": "inner"}}
    assert lookup(secrets, "A") == "top"  # the top level wins
    assert lookup(secrets, "DATABASE_URL") == "postgresql://x"  # pasted under [database]
    assert lookup(secrets, "MISSING") is None
    assert lookup({}, "A") is None


def test_unreadable_secrets_give_nothing():
    class Broken(dict):
        def __contains__(self, key):
            raise FileNotFoundError("no secrets.toml")

    assert lookup(Broken(), "A") is None
