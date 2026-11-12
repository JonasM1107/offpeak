-- 005: the latest Offpeak Intelligence price outlook, computed in the background by the
-- forecast job (offpeak/jobs/forecast_prices.py), so the app only reads it.
-- Paste into Supabase: SQL Editor -> New query -> Run. Safe to run twice.

create table if not exists price_outlook (
  ts          timestamptz primary key,  -- UTC hour start
  day         date        not null,     -- local market day
  lead        smallint    not null,     -- days after the last published day
  p10         real        not null,     -- spot ct/kWh: likely low
  p50         real        not null,     -- expected
  p90         real        not null,     -- likely high
  miss_ct     real,                     -- average miss at this lead in the backtest
  based_on    timestamptz not null,     -- last published price hour it starts from
  made_at     timestamptz not null default now()
);

alter table price_outlook enable row level security;
