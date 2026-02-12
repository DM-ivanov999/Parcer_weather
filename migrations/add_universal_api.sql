-- ============================================================
-- Migration: Universal Weather API
-- Run this in Supabase SQL Editor
-- ============================================================

-- 1. New universal function for single city
CREATE OR REPLACE FUNCTION public.get_weather_data(
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

  -- 4. Get weather data
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

-- 2. New function for multiple cities
CREATE OR REPLACE FUNCTION public.get_weather_data_batch(
  p_cities text[],
  p_fields text[] DEFAULT NULL
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_result jsonb := '[]'::jsonb;
  v_city text;
  v_city_data jsonb;
BEGIN
  -- Loop through cities
  FOREACH v_city IN ARRAY p_cities
  LOOP
    v_city_data := public.get_weather_data(v_city, p_fields);
    v_result := v_result || jsonb_build_array(v_city_data);
  END LOOP;

  RETURN jsonb_build_object(
    'ok', true,
    'count', array_length(p_cities, 1),
    'data', v_result
  );
END;
$$;

-- 3. Function to get data by country
CREATE OR REPLACE FUNCTION public.get_weather_data_by_country(
  p_country_code text,
  p_fields text[] DEFAULT NULL
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_country_id bigint;
  v_country_name text;
  v_result jsonb;
BEGIN
  -- Find country
  SELECT id, name INTO v_country_id, v_country_name
  FROM public.countries
  WHERE lower(code) = lower(trim(p_country_code))
    AND active = true;

  IF v_country_id IS NULL THEN
    RETURN jsonb_build_object(
      'ok', false,
      'error', format('Country "%s" not found or inactive', p_country_code)
    );
  END IF;

  -- Get all cities data
  SELECT jsonb_build_object(
    'ok', true,
    'country', v_country_name,
    'code', upper(trim(p_country_code)),
    'count', count(*),
    'data', jsonb_agg(
      CASE
        WHEN p_fields IS NOT NULL AND array_length(p_fields, 1) > 0 THEN
          (SELECT jsonb_object_agg(key, value)
           FROM jsonb_each(row_to_json(sub)::jsonb)
           WHERE key = 'city' OR key = ANY(p_fields))
        ELSE
          row_to_json(sub)::jsonb
      END
    )
  ) INTO v_result
  FROM (
    SELECT
      c.name as city,
      ud.uv_index,
      ud.uv_desc,
      ud.temperature,
      ud.feels_like,
      ud.humidity,
      ud.wind_speed,
      ud.weather_desc,
      ud.updated_at
    FROM public.cities c
    JOIN public.uv_data ud ON ud.city_id = c.id
    WHERE c.country_id = v_country_id
      AND c.active = true
    ORDER BY c.name
  ) sub;

  RETURN v_result;
END;
$$;

-- 4. Grant permissions
GRANT EXECUTE ON FUNCTION public.get_weather_data(text, text[]) TO anon;
GRANT EXECUTE ON FUNCTION public.get_weather_data(text, text[]) TO authenticated;

GRANT EXECUTE ON FUNCTION public.get_weather_data_batch(text[], text[]) TO anon;
GRANT EXECUTE ON FUNCTION public.get_weather_data_batch(text[], text[]) TO authenticated;

GRANT EXECUTE ON FUNCTION public.get_weather_data_by_country(text, text[]) TO anon;
GRANT EXECUTE ON FUNCTION public.get_weather_data_by_country(text, text[]) TO authenticated;

-- 5. Keep old function as alias for backward compatibility
-- (Already exists from add_countries.sql migration)

-- ============================================================
-- Usage Examples
-- ============================================================

-- Single city, all fields:
-- SELECT get_weather_data('Mumbai');

-- Single city, specific fields:
-- SELECT get_weather_data('Mumbai', ARRAY['uv_index', 'temperature', 'humidity']);

-- Multiple cities:
-- SELECT get_weather_data_batch(ARRAY['Mumbai', 'Delhi', 'Bangalore'], ARRAY['uv_index', 'temperature']);

-- All cities from country:
-- SELECT get_weather_data_by_country('IN', ARRAY['uv_index', 'temperature']);
