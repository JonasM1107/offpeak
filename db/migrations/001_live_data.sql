-- 001: tables for the live data feeds (prices, weather) and the job log.
-- Paste into Supabase: SQL Editor -> New query -> Run. Safe to run twice.
-- Every time is UTC, one row per 15-minute slot start.

create table if not exists prices_da (
  ts             timestamptz  not null,                 -- slot start, UTC
  zone           text         not null default 'DE-LU',
  eur_mwh        numeric(8,2) not null,
  resolution_min smallint     not null default 15,      -- 60 for hourly history before Oct 2025
  source         text         not null default 'energy-charts',
  inserted_at    timestamptz  not null default now(),
  primary key (ts, zone)
);

create table if not exists weather_fc (
  site_id     integer     not null,
  run_at      timestamptz not null,                     -- when we fetched this forecast
  ts          timestamptz not null,                     -- slot start, UTC
  gti_wm2     real,                                     -- irradiance on the tilted panel
  ghi_wm2     real,                                     -- irradiance on flat ground
  precip_mm   real,
  temp_c      real,
  cloud_pct   real,
  wind_ms     real,
  weather_code smallint,
  primary key (site_id, run_at, ts)
);
create index if not exists weather_fc_latest on weather_fc (site_id, ts, run_at desc);

create table if not exists job_runs (
  id           bigint generated always as identity primary key,
  job          text        not null,
  started_at   timestamptz not null,
  finished_at  timestamptz,
  status       text        not null,                    -- ok / skipped / failed
  rows_written integer     not null default 0,
  message      text
);

-- Our jobs and the dashboard connect as the database owner, not through Supabase's public
-- API. Row level security without policies keeps that public API closed for these tables.
alter table prices_da  enable row level security;
alter table weather_fc enable row level security;
alter table job_runs   enable row level security;
