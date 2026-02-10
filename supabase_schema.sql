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

-- For server-side ingestion scripts, prefer SERVICE_ROLE key.
-- If you use anon key, configure RLS policies accordingly.
