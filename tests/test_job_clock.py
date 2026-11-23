"""The clock in Supabase (db/supabase/job_clock.sql) starts our GitHub workflows on time.

The SQL only runs on Supabase (it needs pg_cron, pg_net and Vault), so these tests read the
files as text: no database, no network. They catch the mistakes that would otherwise show up
only as a job that silently never starts, or starts at the wrong time.
"""

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
SQL = (ROOT / "db" / "supabase" / "job_clock.sql").read_text(encoding="utf-8")

# select cron.schedule('name', 'times', $$select public.start_workflow('file.yml')$$);
CLOCK_ENTRY = re.compile(
    r"cron\.schedule\('([^']+)',\s*'([^']+)',\s*\$\$select public\.start_workflow\('([^']+)'\)\$\$"
)
CRON_LINE = re.compile(r"""^\s*- cron: ["']([^"']+)["']""", re.MULTILINE)
# What GitHub's tokens look like: ghp_..., gho_..., github_pat_...
TOKEN = re.compile(r"gh[a-z]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}")


def clock_times() -> dict[str, set[str]]:
    """Workflow file -> the times at which the clock starts it."""
    times: dict[str, set[str]] = {}
    for _name, schedule, file in CLOCK_ENTRY.findall(SQL):
        times.setdefault(file, set()).add(schedule)
    return times


def workflow_times() -> dict[str, set[str]]:
    """Workflow file -> its own "cron:" lines, for every workflow that has a schedule."""
    times = {
        p.name: set(CRON_LINE.findall(p.read_text(encoding="utf-8")))
        for p in WORKFLOWS.glob("*.yml")
    }
    return {file: crons for file, crons in times.items() if crons}


def test_clock_and_workflows_agree_on_the_times():
    # Accepted: every scheduled workflow is started by the clock at exactly its own times.
    # Rejected: a clock entry for a file that does not exist, a workflow that lost its own
    # schedule (the fallback when the clock or GitHub's API fails), or a time changed in one place.
    assert clock_times() == workflow_times()
    # and the comparison is not two empty lists: the entry we know best was really read
    assert clock_times()["prices.yml"] == {"45 11 * * *", "*/15 12-13 * * *", "0 14 * * *"}


def test_every_entry_is_read_and_has_its_own_name():
    entries = CLOCK_ENTRY.findall(SQL)
    # an entry written in a way the pattern above cannot read would be skipped by these tests
    assert len(entries) == SQL.count("cron.schedule(")
    names = [name for name, _, _ in entries]
    # pg_cron replaces an entry of the same name without a word: one start time would be lost
    assert len(names) == len(set(names))
    # switching off and running the file twice both find our entries by this prefix
    assert all(name.startswith("offpeak-") for name in names)
    assert SQL.index("cron.unschedule(") < SQL.index("cron.schedule(")


def test_every_started_workflow_has_a_run_button():
    # The clock uses GitHub's "Run workflow" request, which needs the workflow_dispatch trigger.
    for file in clock_times():
        text = (WORKFLOWS / file).read_text(encoding="utf-8")
        assert re.search(r"^  workflow_dispatch:", text, re.MULTILINE), file


def test_no_token_in_the_sql_file():
    assert not TOKEN.search(SQL)
    assert "vault.decrypted_secrets" in SQL  # the token comes from Supabase Vault
    # the pattern does catch a token, so the first line is a real check
    assert TOKEN.search("github_pat_" + "A1b2C3d4" * 5)
    assert TOKEN.search("ghp_" + "A1b2C3d4" * 5)


def test_only_the_database_owner_may_start_workflows():
    revoke = re.search(
        r"revoke execute on function public\.start_workflow\(text\) from ([^;]+);", SQL
    )
    assert revoke
    assert {"public", "anon", "authenticated"} <= {role.strip() for role in revoke[1].split(",")}
    # runs with the caller's rights: a role that cannot read Vault cannot use the token either
    assert "security definer" not in SQL.lower()
