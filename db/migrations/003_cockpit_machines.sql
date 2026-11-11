-- 003: the machines set up in the Simulation cockpit, one list per site.
-- Paste into Supabase: SQL Editor -> New query -> Run. Safe to run twice.
-- Until a site has a row here, the cockpit starts from the site's flexible components.

create table if not exists cockpit_machines (
  site_id     integer     primary key,
  machines    jsonb       not null default '[]',    -- [{"name", "kw", "hours", "earliest", ...}]
  updated_at  timestamptz not null default now()
);

alter table cockpit_machines enable row level security;
