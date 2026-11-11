-- 002: the machines on each site (solar, wind, battery, heat pump, ...).
-- Paste into Supabase: SQL Editor -> New query -> Run. Safe to run twice.
-- Until a site has rows here, the app shows the demo components from offpeak/components.py.

create table if not exists site_components (
  id          text        primary key,
  site_id     integer     not null,
  kind        text        not null,                  -- a key of CATALOGUE in offpeak/components.py
  name        text        not null,
  params      jsonb       not null default '{}',     -- e.g. {"kwp": 40}
  created_at  timestamptz not null default now()
);
create index if not exists site_components_site on site_components (site_id, created_at);

alter table site_components enable row level security;
