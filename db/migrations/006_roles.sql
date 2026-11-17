-- 006: two kinds of customer, homeowner and business (offpeak/roles.py).
-- Paste into Supabase: SQL Editor -> New query -> Run. Safe to run twice.
--
-- accounts: the role of each account, chosen at its first sign-in and never changed by a
-- later one (to change it, delete the row here; the next sign-in chooses again).
-- profile on site_components and cockpit_machines: which catalogue a row belongs to, so a
-- household's devices and a business's machines are kept apart in the database as well,
-- not only by the site they belong to.

create table if not exists accounts (
  email       text        primary key,
  role        text        not null check (role in ('home', 'business')),
  created_at  timestamptz not null default now()
);

alter table accounts enable row level security;

alter table site_components add column if not exists profile text not null default 'business';
alter table cockpit_machines add column if not exists profile text not null default 'business';

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'site_components_profile_check') then
    alter table site_components
      add constraint site_components_profile_check check (profile in ('home', 'business'));
  end if;
  if not exists (select 1 from pg_constraint where conname = 'cockpit_machines_profile_check') then
    alter table cockpit_machines
      add constraint cockpit_machines_profile_check check (profile in ('home', 'business'));
  end if;
end $$;
