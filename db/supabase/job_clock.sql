-- The job clock: Supabase starts our GitHub workflows on time.
--
-- Why: GitHub starts this repository's scheduled workflows 6 to 8 hours late and drops most of
-- them (measured 19 to 22 Nov 2026). That is GitHub's scheduler, so no "cron:" line fixes it.
-- The database is always on, so it keeps the time instead: pg_cron calls a small function at
-- the planned times, and the function asks GitHub to start the workflow. That request is the
-- same as pressing "Run workflow" on GitHub (the workflow_dispatch trigger).
--
-- Not a migration: it needs pg_cron, pg_net and Vault, which only Supabase has (the test
-- database is a plain Postgres). Paste it into Supabase's SQL Editor once, after the GitHub
-- token is stored in Vault. Running it again is safe. All steps: docs/LIVE_DATA.md.

create extension if not exists pg_cron with schema pg_catalog;  -- runs SQL at set times
grant usage on schema cron to postgres;
grant all privileges on all tables in schema cron to postgres;
create extension if not exists pg_net;                          -- HTTP requests from SQL (schema "net")


-- Ask GitHub to start one workflow on main. Returns pg_net's request number; GitHub's answer
-- arrives a moment later in the table net._http_response (204 = accepted).
create or replace function public.start_workflow(file text)
returns bigint
language plpgsql
set search_path = ''  -- every table and function below is named with its schema
as $$
declare
  token text;
begin
  -- Only a plain workflow file name, so the address below cannot be bent to another place.
  if file !~ '^[a-z_]+\.yml$' then
    raise exception 'start_workflow: "%" is not a workflow file name', file;
  end if;

  -- The token is never written here. It lives encrypted in Supabase Vault under this name.
  select decrypted_secret into token
  from vault.decrypted_secrets
  where name = 'github_actions_token';
  if token is null then
    raise exception 'start_workflow: Vault has no secret "github_actions_token", see docs/LIVE_DATA.md';
  end if;

  return net.http_post(
    url := 'https://api.github.com/repos/JonasM1107/offpeak/actions/workflows/' || file || '/dispatches',
    body := '{"ref": "main"}'::jsonb,
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || token,
      'Accept', 'application/vnd.github+json',
      'X-GitHub-Api-Version', '2022-11-28',
      'User-Agent', 'offpeak-job-clock'  -- GitHub refuses requests without one
    ),
    timeout_milliseconds := 10000
  );
end;
$$;

-- Only the database owner (the role pg_cron runs our entries as) may start workflows. Without
-- this, Supabase's public API would offer the function to everyone who has the public key.
revoke execute on function public.start_workflow(text) from public, anon, authenticated, service_role;


-- Remove our old entries first, so running this file twice never leaves two clocks for one job.
select cron.unschedule(jobname) from cron.job where jobname like 'offpeak-%';

-- One entry per "cron:" line of the workflow files, with the same times (UTC, like GitHub).
-- tests/test_job_clock.py compares the two, so change a time in both places.
select cron.schedule('offpeak-prices-first',  '45 11 * * *',         $$select public.start_workflow('prices.yml')$$);
select cron.schedule('offpeak-prices-window', '*/15 12-13 * * *',    $$select public.start_workflow('prices.yml')$$);
select cron.schedule('offpeak-prices-last',   '0 14 * * *',          $$select public.start_workflow('prices.yml')$$);
select cron.schedule('offpeak-weather',       '15 */3 * * *',        $$select public.start_workflow('weather.yml')$$);
select cron.schedule('offpeak-drivers',       '40 7 * * *',          $$select public.start_workflow('drivers.yml')$$);
select cron.schedule('offpeak-forecast',      '10 8,12,13,15 * * *', $$select public.start_workflow('forecast.yml')$$);
