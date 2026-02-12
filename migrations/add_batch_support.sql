-- ============================================================
-- Migration: Add Batch Support for Large City Lists
-- Run this in Supabase SQL Editor
-- ============================================================

-- 1. Add batch column to cities
ALTER TABLE public.cities ADD COLUMN IF NOT EXISTS batch integer DEFAULT 1;
CREATE INDEX IF NOT EXISTS cities_batch_idx ON public.cities (batch);

-- 2. Example: Distribute existing cities across batches
-- Distribute evenly (for ~500 cities = 4 batches of ~125 each)
UPDATE public.cities
SET batch = CASE
  WHEN id % 4 = 0 THEN 1
  WHEN id % 4 = 1 THEN 2
  WHEN id % 4 = 2 THEN 3
  ELSE 4
END;

-- 3. Verification query
-- SELECT batch, COUNT(*) as city_count
-- FROM public.cities
-- GROUP BY batch
-- ORDER BY batch;
