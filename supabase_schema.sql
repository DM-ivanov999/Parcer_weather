-- Run this in Supabase SQL Editor
create table if not exists public.uv_index (
  id bigserial primary key,
  timestamp timestamptz not null,
  city text not null,
  uv_index double precision,
  uv_desc text,
  temperature double precision,
  feels_like double precision,
  humidity integer,
  wind_speed double precision,
  weather_desc text
);

create index if not exists uv_index_city_timestamp_idx
  on public.uv_index (city, timestamp desc);

-- Enable Row Level Security
alter table public.uv_index enable row level security;

-- RLS Policies
-- Allow public read access (for API endpoints)
create policy "Allow public read access"
on public.uv_index
for select
using (true);

-- Allow insert only for service_role (for GitHub Actions)
create policy "Allow service role insert"
on public.uv_index
for insert
with check (
  auth.role() = 'service_role' or auth.role() = 'authenticated'
);

-- Allow update only for service_role
create policy "Allow service role update"
on public.uv_index
for update
using (auth.role() = 'service_role')
with check (auth.role() = 'service_role');

-- Allow delete only for service_role
create policy "Allow service role delete"
on public.uv_index
for delete
using (auth.role() = 'service_role');

-- For server-side ingestion scripts, use SERVICE_ROLE key.
-- For public API read access, anon key is sufficient.
