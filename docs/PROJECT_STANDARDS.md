# Project standards: what offpeak must fulfil

This file sums up the course rules for the team project, the grading criteria, and what each criterion means for offpeak in concrete, checkable terms. Our goal is the top level ("High", 100 %) in every criterion. Every change to the repo is measured against this file.

Sources: the [team project page](https://2477-introduction-programming.gitlab.io/wiki/team-project/) and the course guides it links to (preparing the demo, secrets, working as a team, external APIs, storing data, hosting, user accounts), read on 11 November 2026. If the course pages change, they win; update this file.

The last section, [Status and open points](#status-and-open-points), says where we stand today.

---

## 1. The rules

| What | Rule |
|---|---|
| Weight | The team project is **40 %** of the final grade (the written exam is 60 %). Everyone in the team gets the **same grade**. |
| Team | 3 to 4 students. **Every member contributes code to the repository.** Every member must understand the whole project, not only their own parts. |
| Scope | Judged against what a team of 3 to 4 can build in three weeks. |
| Deployment | The app runs at a **public URL** (ours: https://offpeak.streamlit.app). The deployed app runs the code on `main`. |
| Submission | **One** member submits the link to the GitHub repository on the team project assignment on [Moodle](https://moodle.novasbe.pt/course/view.php?id=932). |
| Deadline | **23 November 2026, 23:59.** Commits after the deadline are not considered for grading. |
| Repository | **Public**, so staff can open it without an invitation. No keys or passwords in it. The code of the deployed app is on `main`. |
| README.md | Must contain: the **deployed URL**; the **names and student numbers** of all members; the **commands to run the app and its tests** locally. |
| Presentation | Weeks 11 and 12, in class, half the teams each week. Two parts, below. |

### The presentation

1. **Live demo.** The app runs at its deployed URL in front of the class. Slides or recorded videos do not replace it.
2. **Repository walkthrough.** Staff open the repository and ask high-level questions about how the project is built. **Any member can be asked about any part.** Example questions from the course page:
   - Where is the data stored?
   - What do the tests cover, and what do they not cover?
   - What happens if the external API the app depends on is unavailable?

Staff also review the repository on their own: they read the README as a newcomer and follow its commands on a fresh copy.

---

## 2. Grading criteria and what 100 % means for us

Each criterion is graded Low (30 %), Mid (70 %) or High (100 %).

### 2.1 It works (20 %)

**High:** "All workflows run without errors, including invalid input."

For offpeak this means:

- Every page opens on the deployed app without an exception, with and without a database, and before and after tomorrow's prices are published (around 13:00 CET).
- Every input rejects invalid values with a clear message, never a traceback. This covers component forms, cockpit sliders and names, tariff settings and settings. Values sent from the browser are checked in Python before they are saved (`offpeak.cockpit.clean_machines`, `offpeak.components.validate`).
- Every external source can fail without breaking a page. See [section 4](#4-when-an-external-source-fails).
- Before the demo: try invalid input and a failing source on purpose, on the deployed app.

### 2.2 User interface and experience (20 %)

**High:** "Interface fits the problem; workflows are direct; results and errors are clearly shown."

For offpeak this means:

- **Answer first.** The top of every page is something a business owner can act on (for example the week plan on the dashboard: which machine, when, how much it saves).
- Their units on screen: ct/kWh, kWh, euros, local time. Never €/MWh or UTC.
- Loading, empty and error states are designed: spinners with a sentence, "waiting for tomorrow's prices", "could not be loaded, we try again". Never a blank card or a raw error.
- No unnecessary steps: changes save on their own (cockpit), resets are buttons, and every page has one clear purpose.
- One look across all pages: Safety Orange `#FF5F00` accent, the same cards, charts and spacing.
- Slow work (the price forecast) never blocks the rest of a page.

### 2.3 Scope and ambition (20 %)

**High:** "Substantial features well beyond a solo project, implemented consistently."

What we have that a solo project does not:

- **Live external data:** Energy-Charts prices; Open-Meteo forecast, archive, satellite and previous runs.
- **A shared database:** Supabase, kept current by scheduled GitHub Actions jobs.
- **A machine-learning price forecast:** honest walk-forward backtest, weather features, "what the model learned".
- **A site energy model and a 3D site view.**
- **A planner:** a simulation cockpit and a week plan.
- **A tariff calculator and a savings replay.**

To stay at High, every feature must be *consistent*: same look, same units, same failure handling, tested. A half-finished feature costs more than it adds, so we finish or remove.

### 2.4 Verification (10 %)

**High:** "Tests cover accepted and rejected actions and edge cases, and all pass on `main`."

For offpeak this means:

- Every rule in `offpeak/` has tests for the **accepted** case, the **rejected** case (invalid input, missing data, a failing source) and **edge cases**. Edge cases include clock-change days (23 and 25 hours), negative prices, 15-minute vs hourly prices, prices not yet published, an empty list, and a job that does not fit its hours.
- Tests never call a real API: they use saved responses in `tests/fixtures/`. Database tests run on a local or throwaway Postgres (CI starts one), never on Supabase.
- `uv run pytest` passes on `main`, and CI shows it green.
- Every member can say what the tests cover **and what they do not** (see [section 5](#5-walkthrough-answers-we-must-all-be-able-to-give)).

### 2.5 Security (10 %)

**High:** "Access control and input validation enforced; dependencies minimal, pinned, and free of known vulnerabilities."

For offpeak this means:

- **No credentials in the repository.**
  - `.env` and `.streamlit/secrets.toml` are git-ignored. `.env.example` holds placeholders only.
  - Real values live in GitHub Actions secrets and Streamlit Cloud secrets.
  - Nobody pastes keys into chat, issues or pull requests.
  - If a key leaks: revoke it at once, create a new one, and update the host settings. Deleting the commit is not enough.
- **Access control at the action, not only in the interface.** "Hiding a button is not a permission." Everything that changes shared data (site components, cockpit machines) is checked where the change is saved.
- **Input validation** on every value that comes from a user or the browser, before it is stored.
- **Supabase row level security** is on for every table. The app connects with a server-side connection string that is never sent to the browser.
- **Dependencies:**
  - Minimal: every library in `pyproject.toml` is used.
  - Pinned: exact versions in `uv.lock`, and CI installs with `--locked`.
  - Free of known vulnerabilities: checked with `pip-audit`.

### 2.6 Repository walkthrough (20 %)

**High:** "Members explain how the project is built, why, its limits, and how it could change."

For offpeak this means:

- Every member can open the repo and find, without searching: the screens (`app/views/`), the rules (`offpeak/`), the storage (`offpeak/db.py`, `db/migrations/`), the jobs (`offpeak/jobs/`, `.github/workflows/`) and the tests (`tests/`).
- Every member can explain the **why** of the main decisions and their **limits**. The answers are in [section 5](#5-walkthrough-answers-we-must-all-be-able-to-give). Examples of decisions:
  - Streamlit, with logic kept separate from pages.
  - Supabase plus scheduled jobs.
  - UTC timestamps.
  - Training the model on forecast weather.
  - A backtest instead of trusting the model.
- Every member can say **how it could change**: more price zones (Portugal is prepared), real meter data, user accounts, and precomputing the forecast in a job.

---

## 3. How we work (from the course guides)

- **Secrets** come from environment variables or the Streamlit secrets file, never from code. `DATABASE_URL` is the only secret the app needs.
- **Database code** stays in `offpeak/db.py`. Schema changes are numbered SQL files in `db/migrations/`, each run once in Supabase. The schema has one owner at a time.
- **Every external API** has a decided, tested failure behaviour (section 4), and its responses are cached (Streamlit reruns on every click).
- **Small changes, merged often.** A branch per task, a pull request, CI green, and a teammate's review before `main`. The person who merges owns the result. Reviews check that tests cover the change *including rejected actions*, and that nothing outside the change's scope (especially tests) was touched.
- **`AGENTS.md`** holds the rules for coding agents. It lives in the repo and changes through pull requests.
- **Deploy early and keep it live.** Streamlit Cloud deploys `main`. After every merge, check that the latest version is live.

---

## 4. When an external source fails

"Crashing is not an option." This is asked in the walkthrough and is part of the demo.

| Source | Used for | If it is unavailable |
|---|---|---|
| Energy-Charts (day-ahead prices) | Every price on every page | The app reads stored prices from Supabase first. If neither works, the pages show "Prices could not be loaded right now. We try again in a few minutes." Before ~13:00 CET, "tomorrow" shows "Waiting for tomorrow's prices". |
| Open-Meteo forecast | Weather, solar, cockpit, dashboard | The stored forecast from the database is used (if under 6 hours old). Otherwise: "The weather forecast is not available right now." |
| Open-Meteo previous runs (weather for Offpeak Intelligence) | Price outlook | Read from Supabase, which the daily job fills. If missing, the outlook runs without weather (prices only) and the day cards show no weather reason. |
| Offpeak Intelligence outlook (computed by our forecast job) | Price outlook, cockpit, dashboard plan, Ollie | Read from Supabase. If no stored outlook fits the latest prices (job late or failed), the app computes one itself (about half a minute, once) and stores it. |
| Requesty (language model for Ollie) | Ask Ollie chat | Ollie says "can't answer right now" and points to the dashboard plan and the cockpit, which do not need it. If the first model fails, a second one is tried. Each visitor can ask 25 questions per session (free plan: 200 requests a day). |
| Open-Meteo archive and satellite | Savings replay, solar accuracy | A clear message on that card or page. The rest of the app is unaffected. |
| Supabase | Stored data, components, cockpit machines | The pages fall back to the APIs. Components and machines are kept for the session only, and the page says so. |

Tests: `tests/test_app.py` runs every page offline with saved responses.

---

## 5. Walkthrough answers we must all be able to give

**Where is the data stored?**

- In Supabase (hosted Postgres): day-ahead prices, weather forecast runs, the weather that drives the price outlook, the latest Offpeak Intelligence outlook, site components, cockpit machines and the job log.
- GitHub Actions jobs fill it on a schedule:
  - prices every 15 minutes around 13:00;
  - weather every 3 hours;
  - price-model weather daily;
  - the Offpeak Intelligence outlook after the morning weather and after new prices (its log shows the backtest scores and what the outlook relies on).
- The app reads the database first and calls the APIs only for what is missing.
- Only `offpeak/db.py` talks to the database. The schema is in `db/migrations/`.

**What do the tests cover, and what not?**

- They cover:
  - the data adapters, on saved API responses, including errors and odd formats;
  - time handling, including clock changes;
  - tariffs and bills;
  - the site model, cockpit planning and machine checks;
  - the forecasts and their backtest, including that the model never sees the future;
  - the database round trips, on a local Postgres;
  - the jobs, including skip and failure logging;
  - every page opening without an exception.
- They do **not** cover:
  - the browser-side JavaScript (cockpit sliders, charts);
  - how the pages look;
  - the live APIs and Supabase themselves;
  - Streamlit Cloud deployment;
  - forecast accuracy on future data (the backtest estimates it).

**What happens if an external API is unavailable?** See section 4.

**How does Ollie (the chat) answer?** The language model does not know our prices and is not allowed to compute them. It gets a short set of instructions (today's date, the known days, the rules) and five tools: plain Python functions in `offpeak/assistant/tools.py` that run the same planning as the cockpit on our data. It asks for what it needs, gets the results, and puts them into words. Everything the model sends to a tool is checked like user input. The tests use a fake model.

**Why these choices, and what are their limits?**

- **UTC everywhere:**
  - *Why:* no clock-change bugs.
  - *Limit:* every screen must convert to local time.
- **Logic only in `offpeak/`:**
  - *Why:* it can be tested without Streamlit.
- **The forecast is retrained in the app:**
  - *Why:* simple, with no model files.
  - *Limit:* about half a minute once a day for the first visitor. It could move into a scheduled job.
- **Weather as forecast, not as measured:**
  - *Why:* honest training that matches real use.
  - *Limit:* only about a year of such data.
- **Demo site instead of real meter data:**
  - *Limit:* consumption is modelled, not measured.
- **Ollie through a free Requesty model:**
  - *Why:* the course's standard router, no card needed. The numbers come from our tools, so a smaller model is enough.
  - *Limit:* 200 requests a day for the whole app, and answers can be slower than the rest of the app.
- **No user accounts:**
  - *Why:* one demo site.
  - *Limit:* changes are shared by everyone with edit access.

---

## 6. Before the demo (checklist)

**The week before**

- [ ] Everything merged to `main` and live at the public URL.
- [ ] Run the whole demo on the deployed app, not on a laptop.
- [ ] Prepare starting data: demo site components and cockpit machines.
- [ ] Try failures on purpose: invalid input and a failing source.
- [ ] All tests pass on `main`. Every member can say what they cover and what not.
- [ ] Repo public. README has the URL, members with student numbers, and run/test commands. No credentials.
- [ ] Follow the README on a fresh clone.

**The day before**

- [ ] Rehearse once, start to finish, with the person who operates.
- [ ] Supabase and Streamlit dashboards: nothing paused, suspended or over a limit. A free Supabase project pauses after a week without activity; our daily jobs keep it active, but check anyway.
- [ ] Reset demo data. Stop merging.

**On the day**

- [ ] Open the public URL early. This wakes the app and lets the price forecast compute.
- [ ] One browser window, only the tabs needed. Close dashboards and secrets before sharing the screen.
- [ ] If something fails: say what happened and continue.

---

## Status and open points

Checked on 11 November 2026. ✅ meets High · ⚠️ partly · ❌ missing.

| Criterion | Status | Evidence / what is missing |
|---|---|---|
| Public repo, code on `main`, deployed | ✅ | Public on GitHub. offpeak.streamlit.app deploys `main`. |
| README requirements | ⚠️ | The deployed URL and run/test commands are in. **Student numbers are missing** (placeholders in README.md). |
| Every member contributes code | ❌ | Git history: commits by JonasM1107 and by "Claude" (work directed by Mika). **No commits under Mika's or Noa's own name.** Mika: commit under your own name from now on. Noa: own a feature and commit it. |
| It works | ⚠️ | Pages handle unavailable sources (section 4) and tests open every page. Still to do: a systematic invalid-input pass on the deployed app, and tests that open pages with each source failing. |
| UI and experience | ✅ | Consistent design, answer-first dashboard, designed error states. The outlook is computed in the background, so pages no longer wait for it. |
| Scope and ambition | ✅ | See 2.3. |
| Verification | ⚠️ | 159 tests, green on `main`. Missing: page tests with failing sources; rejected-action tests for the component form and settings. |
| Security: no credentials | ✅ | `.env` and secrets git-ignored, `.env.example` placeholders only, RLS on in every migration. |
| Security: access control | ❌ | **Anyone with the public URL can change the shared site components and cockpit machines.** Needed: an edit passcode (Streamlit secret), checked where the change is saved; visitors without it keep changes in their session only. |
| Security: input validation | ✅ / ⚠️ | Cockpit machines and new components are validated before saving. To check: every remaining input. |
| Security: dependencies | ✅ | Pinned in `uv.lock`, installed `--locked`. CI runs `pip-audit` on every push: no known vulnerabilities. |
| Ollie (chat) | ⚠️ | Built and tested with a fake model. Goes live once `REQUESTY_API_KEY` is in the Streamlit secrets; not yet tried against the real model. |
| Walkthrough readiness | ⚠️ | Section 5 has the answers. Every member should walk through the repo once, using this file. |
| Team workflow | ⚠️ | `AGENTS.md` asks for a branch and pull request per task, but recent work was pushed straight to `main`. From now on: a pull request per change, reviewed by a teammate. |
