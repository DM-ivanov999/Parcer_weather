-- ============================================================
-- UV Weather Service v2 — Migration Script
-- Run this in Supabase SQL Editor
-- ============================================================

-- 1. CITIES TABLE — dynamic city list
create table if not exists public.cities (
  id bigserial primary key,
  name text unique not null,
  lat double precision not null,
  lon double precision not null,
  active boolean default true,
  created_at timestamptz default now()
);

create index if not exists cities_active_idx on public.cities (active);

-- 2. CITY MAPPING — DSP name → our city
create table if not exists public.city_mapping (
  id bigserial primary key,
  dsp_name text unique not null,
  city_id bigint not null references public.cities(id) on delete cascade
);

create index if not exists city_mapping_dsp_name_idx
  on public.city_mapping (lower(dsp_name));

-- 3. UV DATA — current weather (one row per city, upserted)
create table if not exists public.uv_data (
  id bigserial primary key,
  city_id bigint unique not null references public.cities(id) on delete cascade,
  uv_index double precision,
  uv_desc text,
  temperature double precision,
  feels_like double precision,
  humidity integer,
  wind_speed double precision,
  weather_desc text,
  updated_at timestamptz default now()
);

-- 4. CONFIG — system settings
create table if not exists public.config (
  key text primary key,
  value text not null
);

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================

-- cities
alter table public.cities enable row level security;

create policy "Public read cities" on public.cities
  for select using (true);

create policy "Service role manage cities" on public.cities
  for all using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

-- city_mapping
alter table public.city_mapping enable row level security;

create policy "Public read city_mapping" on public.city_mapping
  for select using (true);

create policy "Service role manage city_mapping" on public.city_mapping
  for all using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

-- uv_data
alter table public.uv_data enable row level security;

create policy "Public read uv_data" on public.uv_data
  for select using (true);

create policy "Service role manage uv_data" on public.uv_data
  for all using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

-- config
alter table public.config enable row level security;

create policy "Public read config" on public.config
  for select using (true);

create policy "Service role manage config" on public.config
  for all using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

-- ============================================================
-- RPC FUNCTION — API for banners
-- ============================================================

create or replace function public.get_uv_for_banner(
  p_city text,
  p_fields text[] default null
) returns jsonb
language plpgsql
security definer
as $$
declare
  v_city_id bigint;
  v_city_name text;
  v_result jsonb;
begin
  -- 1. Direct lookup by city name (case-insensitive)
  select id, name into v_city_id, v_city_name
  from public.cities
  where lower(name) = lower(trim(p_city))
    and active = true;

  -- 2. If not found — try DSP mapping
  if v_city_id is null then
    select cm.city_id, c.name into v_city_id, v_city_name
    from public.city_mapping cm
    join public.cities c on c.id = cm.city_id and c.active = true
    where lower(cm.dsp_name) = lower(trim(p_city));
  end if;

  -- 3. City not found
  if v_city_id is null then
    return jsonb_build_object(
      'ok', false,
      'error', format('City "%s" not found', p_city)
    );
  end if;

  -- 4. Get UV data
  select jsonb_build_object(
    'ok', true,
    'city', v_city_name,
    'uv_index', ud.uv_index,
    'uv_desc', ud.uv_desc,
    'temperature', ud.temperature,
    'feels_like', ud.feels_like,
    'humidity', ud.humidity,
    'wind_speed', ud.wind_speed,
    'weather_desc', ud.weather_desc,
    'updated_at', ud.updated_at
  ) into v_result
  from public.uv_data ud
  where ud.city_id = v_city_id;

  -- 5. No data for city
  if v_result is null then
    return jsonb_build_object(
      'ok', false,
      'error', format('No data yet for city "%s"', v_city_name)
    );
  end if;

  -- 6. Filter fields if requested
  if p_fields is not null and array_length(p_fields, 1) > 0 then
    v_result := (
      select jsonb_object_agg(key, value)
      from jsonb_each(v_result)
      where key = 'ok' or key = 'city' or key = any(p_fields)
    );
  end if;

  return v_result;
end;
$$;

-- Allow anonymous access to the RPC function
grant execute on function public.get_uv_for_banner(text, text[]) to anon;
grant execute on function public.get_uv_for_banner(text, text[]) to authenticated;

-- ============================================================
-- SEED DATA — migrate cities from hardcoded list
-- ============================================================

insert into public.cities (name, lat, lon, active) values
  ('Delhi',      28.6139, 77.2090, true),
  ('Mumbai',     19.0760, 72.8777, true),
  ('Bangalore',  12.9716, 77.5946, true),
  ('Hyderabad',  17.3850, 78.4867, true),
  ('Chennai',    13.0827, 80.2707, true),
  ('Kolkata',    22.5726, 88.3639, true),
  ('Pune',       18.5204, 73.8567, false),
  ('Ahmedabad',  23.0225, 72.5714, false),
  ('Jaipur',     26.9124, 75.7873, false),
  ('Goa',        15.2993, 74.1240, false),
  ('Lucknow',    26.8467, 80.9462, false),
  ('Chandigarh', 30.7333, 76.7794, false),
  ('Kochi',       9.9312, 76.2673, false),
  ('Varanasi',   25.3176, 82.9739, false),
  ('Agra',       27.1767, 78.0081, false),
  ('Surat',      21.1702, 72.8311, false),
  ('Indore',     22.7196, 75.8577, false)
on conflict (name) do nothing;

-- Example DSP mappings
insert into public.city_mapping (dsp_name, city_id) values
  ('New Delhi',  (select id from public.cities where name = 'Delhi')),
  ('Bombay',     (select id from public.cities where name = 'Mumbai')),
  ('Bengaluru',  (select id from public.cities where name = 'Bangalore')),
  ('Calcutta',   (select id from public.cities where name = 'Kolkata'))
on conflict (dsp_name) do nothing;

-- Default config
insert into public.config (key, value) values
  ('schedule_cron', '0 * * * *'),
  ('github_repo', 'DM-ivanov999/Parcer_weather')
on conflict (key) do nothing;
