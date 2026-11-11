-- 004: the weather that moves electricity prices, as forecast `lead` days before each hour
-- (offpeak/weather/price_drivers.py). Used by the ML price model.
-- Paste into Supabase: SQL Editor -> New query -> Run. Safe to run twice.

create table if not exists weather_drivers (
  ts          timestamptz not null,   -- UTC hour start
  lead        smallint    not null,   -- forecast made this many days before (1..7)
  wind_share  real,                   -- typical turbine output in northern Germany, 0..1
  sun_wm2     real,                   -- solar radiation in southern Germany, W/m²
  temp_c      real,                   -- temperature in central Germany, °C
  primary key (ts, lead)
);

alter table weather_drivers enable row level security;
