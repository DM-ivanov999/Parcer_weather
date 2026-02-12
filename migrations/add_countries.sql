-- ============================================================
-- Migration: Add Countries Support
-- Run this in Supabase SQL Editor
-- ============================================================

-- 1. Create countries table
CREATE TABLE IF NOT EXISTS public.countries (
  id bigserial PRIMARY KEY,
  name text UNIQUE NOT NULL,
  code text UNIQUE NOT NULL,  -- ISO 3166-1 alpha-2 (IN, US, GB, etc.)
  active boolean DEFAULT true,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS countries_active_idx ON public.countries (active);
CREATE INDEX IF NOT EXISTS countries_code_idx ON public.countries (code);

-- 2. Add country_id to cities table
ALTER TABLE public.cities ADD COLUMN IF NOT EXISTS country_id bigint REFERENCES public.countries(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS cities_country_id_idx ON public.cities (country_id);

-- 3. Seed countries
INSERT INTO public.countries (name, code, active) VALUES
  ('India', 'IN', true),
  ('United States', 'US', false),
  ('United Kingdom', 'GB', false),
  ('Australia', 'AU', false),
  ('Canada', 'CA', false),
  ('Germany', 'DE', false),
  ('France', 'FR', false),
  ('Spain', 'ES', false),
  ('Italy', 'IT', false),
  ('Japan', 'JP', false)
ON CONFLICT (code) DO NOTHING;

-- 4. Update existing cities to belong to India
UPDATE public.cities
SET country_id = (SELECT id FROM public.countries WHERE code = 'IN')
WHERE country_id IS NULL;

-- 5. Make country_id required (after data migration)
ALTER TABLE public.cities ALTER COLUMN country_id SET NOT NULL;

-- 6. RLS for countries table
ALTER TABLE public.countries ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Public read countries" ON public.countries;
CREATE POLICY "Public read countries" ON public.countries
  FOR SELECT USING (true);

DROP POLICY IF EXISTS "Service role manage countries" ON public.countries;
CREATE POLICY "Service role manage countries" ON public.countries
  FOR ALL USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

-- 7. Update RPC function to support country filtering (optional)
-- This allows banners to query by country code if needed
CREATE OR REPLACE FUNCTION public.get_uv_for_banner(
  p_city text,
  p_fields text[] DEFAULT NULL
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_city_id bigint;
  v_city_name text;
  v_country_name text;
  v_result jsonb;
BEGIN
  -- 1. Direct lookup by city name (case-insensitive)
  SELECT c.id, c.name, co.name INTO v_city_id, v_city_name, v_country_name
  FROM public.cities c
  JOIN public.countries co ON co.id = c.country_id
  WHERE lower(c.name) = lower(trim(p_city))
    AND c.active = true
    AND co.active = true;

  -- 2. If not found — try DSP mapping
  IF v_city_id IS NULL THEN
    SELECT cm.city_id, c.name, co.name INTO v_city_id, v_city_name, v_country_name
    FROM public.city_mapping cm
    JOIN public.cities c ON c.id = cm.city_id AND c.active = true
    JOIN public.countries co ON co.id = c.country_id AND co.active = true
    WHERE lower(cm.dsp_name) = lower(trim(p_city));
  END IF;

  -- 3. City not found
  IF v_city_id IS NULL THEN
    RETURN jsonb_build_object(
      'ok', false,
      'error', format('City "%s" not found or inactive', p_city)
    );
  END IF;

  -- 4. Get UV data
  SELECT jsonb_build_object(
    'ok', true,
    'city', v_city_name,
    'country', v_country_name,
    'uv_index', ud.uv_index,
    'uv_desc', ud.uv_desc,
    'temperature', ud.temperature,
    'feels_like', ud.feels_like,
    'humidity', ud.humidity,
    'wind_speed', ud.wind_speed,
    'weather_desc', ud.weather_desc,
    'updated_at', ud.updated_at
  ) INTO v_result
  FROM public.uv_data ud
  WHERE ud.city_id = v_city_id;

  -- 5. No data for city
  IF v_result IS NULL THEN
    RETURN jsonb_build_object(
      'ok', false,
      'error', format('No data yet for city "%s"', v_city_name)
    );
  END IF;

  -- 6. Filter fields if requested
  IF p_fields IS NOT NULL AND array_length(p_fields, 1) > 0 THEN
    v_result := (
      SELECT jsonb_object_agg(key, value)
      FROM jsonb_each(v_result)
      WHERE key = 'ok' OR key = 'city' OR key = 'country' OR key = ANY(p_fields)
    );
  END IF;

  RETURN v_result;
END;
$$;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION public.get_uv_for_banner(text, text[]) TO anon;
GRANT EXECUTE ON FUNCTION public.get_uv_for_banner(text, text[]) TO authenticated;

-- ============================================================
-- Verification queries
-- ============================================================

-- Check countries
-- SELECT * FROM public.countries ORDER BY active DESC, name;

-- Check cities with countries
-- SELECT c.name as city, co.name as country, c.active as city_active, co.active as country_active
-- FROM public.cities c
-- JOIN public.countries co ON co.id = c.country_id
-- ORDER BY co.name, c.name;

-- Check active cities from active countries
-- SELECT c.name as city, co.name as country
-- FROM public.cities c
-- JOIN public.countries co ON co.id = c.country_id
-- WHERE c.active = true AND co.active = true
-- ORDER BY co.name, c.name;
