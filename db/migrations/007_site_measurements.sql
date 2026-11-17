-- 007: measured power of a site, every 15 minutes (offpeak/load/): what its solar made, what it
-- used, what it bought, sold and stored. The training data of a site's own models, such as
-- the homeowner consumption forecast (offpeak/forecast/load_model.py).
-- Paste into Supabase: SQL Editor -> New query -> Run. Safe to run twice.
--
-- Every row carries the profile of the site it belongs to. offpeak/db.py reads and writes
-- this table only with a profile, so a household's measurements can never reach a model of
-- a business, and the other way round: the two use power on very different scales.

create table if not exists site_measurements (
  site_id        integer     not null,
  profile        text        not null check (profile in ('home', 'business')),
  ts             timestamptz not null,   -- UTC start of the 15-minute slot
  pv_kw          real,                   -- own solar production
  load_kw        real,                   -- what the site used
  grid_in_kw     real,                   -- bought from the grid
  grid_out_kw    real,                   -- sold to the grid
  battery_in_kw  real,                   -- into the battery
  battery_out_kw real,                   -- out of the battery
  soc_pct        real check (soc_pct between 0 and 100),
  source         text        not null default 'import',
  primary key (site_id, ts)
);

create index if not exists site_measurements_profile on site_measurements (profile, site_id, ts);

alter table site_measurements enable row level security;
