from datetime import UTC, datetime, timedelta

from offpeak import auth

NOW = datetime(2026, 11, 16, 12, tzinfo=UTC)
ALLOWED = auth.editors(" Ann@Example.com, bob@example.com ,, ")
STORED = auth.hash_password("right horse battery", salt="fixedsalt")
SECRET = "test-secret"


def test_editor_emails_are_trimmed_and_lower_case():
    assert ALLOWED == {"ann@example.com", "bob@example.com"}
    assert auth.editors(None) == set()


def test_the_password_is_stored_only_as_a_fingerprint():
    assert "right horse battery" not in STORED and STORED.startswith("pbkdf2_sha256$200000$")
    assert auth.hash_password("x") != auth.hash_password("x")  # a new salt each time
    assert auth.password_matches("right horse battery", STORED)


def test_login_accepted():
    assert auth.check_login("  ANN@example.com ", "right horse battery", ALLOWED, STORED) == (
        "ann@example.com"
    )


def test_login_rejected():
    assert auth.check_login("ann@example.com", "wrong", ALLOWED, STORED) is None
    assert auth.check_login("eve@example.com", "right horse battery", ALLOWED, STORED) is None
    assert auth.check_login("", "", ALLOWED, STORED) is None
    assert auth.check_login("ann@example.com", "right horse battery", ALLOWED, None) is None
    assert auth.check_login("ann@example.com", "x", ALLOWED, "not$a$valid$hash$") is None


def test_token_works_for_24_hours_only():
    token = auth.make_token("ann@example.com", NOW, SECRET)
    assert auth.read_token(token, NOW + timedelta(hours=23), SECRET, ALLOWED) == "ann@example.com"
    assert auth.read_token(token, NOW + timedelta(hours=24), SECRET, ALLOWED) is None


def test_token_cannot_be_changed_made_up_or_outlive_the_editor_list():
    token = auth.make_token("ann@example.com", NOW, SECRET)
    assert auth.read_token(token, NOW, "another-secret", ALLOWED) is None
    assert auth.read_token(token, NOW, SECRET, {"bob@example.com"}) is None  # removed editor
    forged = auth.make_token("bob@example.com", NOW, "guessed-secret")
    assert auth.read_token(forged, NOW, SECRET, ALLOWED) is None
    for junk in (None, "", "abc", "!!!", "YWJj"):
        assert auth.read_token(junk, NOW, SECRET, ALLOWED) is None
    assert auth.read_token(token, NOW, None, ALLOWED) is None  # not configured: nobody


def test_too_many_wrong_logins_pause_the_form():
    failures = [NOW - timedelta(minutes=1)] * auth.MAX_ATTEMPTS
    assert not auth.may_try(failures, NOW)
    assert auth.may_try(failures, NOW + auth.PAUSE)  # after the pause
    assert auth.may_try(failures[:-1], NOW)


def test_editor_names_come_from_the_setting_or_the_email():
    setting = "Mika Weymann <Mika.Weymann@web.de>, jonas.matner@gmail.com, Noa <noa@x.de>"
    assert auth.editors(setting) == {"mika.weymann@web.de", "jonas.matner@gmail.com", "noa@x.de"}
    assert auth.editor_names(setting) == {
        "mika.weymann@web.de": "Mika Weymann",
        "jonas.matner@gmail.com": "Jonas Matner",  # made from the email
        "noa@x.de": "Noa",
    }


# ── Wrong logins counted for the whole server (a new browser tab starts at zero) ──


def test_wrong_logins_for_one_email_pause_it_in_every_browser():
    for _ in range(auth.MAX_ATTEMPTS - 1):
        auth.note_failure("Ann@Example.com", NOW)
    assert auth.email_may_try("ann@example.com", NOW)  # one try left
    auth.note_failure(" ann@example.com ", NOW)  # written differently, the same email
    assert not auth.email_may_try("ann@example.com", NOW)
    assert not auth.email_may_try("ANN@example.com", NOW + timedelta(minutes=4))
    assert auth.email_may_try("ann@example.com", NOW + auth.PAUSE)  # after the pause


def test_one_emails_wrong_logins_do_not_pause_another():
    for _ in range(auth.MAX_ATTEMPTS):
        auth.note_failure("ann@example.com", NOW)
    assert auth.email_may_try("bob@example.com", NOW)
    assert auth.email_may_try("", NOW) and auth.email_may_try(None, NOW)  # nothing typed yet


def test_old_wrong_logins_are_forgotten_so_the_memory_stays_small():
    for i in range(500):  # a script trying many made-up emails
        auth.note_failure(f"guess{i}@example.com", NOW)
    assert len(auth._FAILED) == 500
    auth.note_failure("ann@example.com", NOW + auth.PAUSE)  # the next try, after the pause
    assert set(auth._FAILED) == {"ann@example.com"}
