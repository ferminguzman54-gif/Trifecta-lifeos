-- ============================================================================
-- TRIFECTA LifeOS — Migración Sprint 6 (Perfil, Preferencias y Ponderación Fija)
-- Archivo: sql/06_sprint6_settings_and_export.sql
-- Propósito:
--   1. Extender `public.profiles` con preferencias de visualización:
--      - alias (nombre corto para la cabecera móvil)
--      - weight_unit ('kg' | 'lb')
--      - preferred_currency ('MXN', 'USD', 'EUR', etc.)
--      - date_format ('DD/MM/YYYY' | 'YYYY-MM-DD' | 'MM/DD/YYYY')
--   2. Añadir ponderación fija personalizada del Trifecta Score:
--      - weight_habits (por defecto 40.00)
--      - weight_workouts (por defecto 35.00)
--      - weight_finances (por defecto 25.00)
--   3. Exponer vista compatible `public.user_settings` y políticas RLS con auth.uid().
-- ============================================================================

ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS alias TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS preferred_currency TEXT NOT NULL DEFAULT 'MXN',
    ADD COLUMN IF NOT EXISTS weight_unit TEXT NOT NULL DEFAULT 'kg'
        CHECK (weight_unit IN ('kg', 'lb')),
    ADD COLUMN IF NOT EXISTS date_format TEXT NOT NULL DEFAULT 'DD/MM/YYYY'
        CHECK (date_format IN ('DD/MM/YYYY', 'YYYY-MM-DD', 'MM/DD/YYYY')),
    ADD COLUMN IF NOT EXISTS weight_habits NUMERIC(5,2) NOT NULL DEFAULT 40.00
        CHECK (weight_habits BETWEEN 0 AND 100),
    ADD COLUMN IF NOT EXISTS weight_workouts NUMERIC(5,2) NOT NULL DEFAULT 35.00
        CHECK (weight_workouts BETWEEN 0 AND 100),
    ADD COLUMN IF NOT EXISTS weight_finances NUMERIC(5,2) NOT NULL DEFAULT 25.00
        CHECK (weight_finances BETWEEN 0 AND 100);

-- Asegurar RLS activo y política vinculada a auth.uid() en profiles
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "profiles_self_policy" ON public.profiles;
CREATE POLICY "profiles_self_policy" ON public.profiles
    FOR ALL
    USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id);

-- Vista espejo `user_settings` para consultas semánticas de configuración
CREATE OR REPLACE VIEW public.user_settings
WITH (security_invoker = true) AS
SELECT
    id AS user_id,
    email,
    full_name,
    alias,
    preferred_currency,
    weight_unit,
    date_format,
    weight_habits,
    weight_workouts,
    weight_finances,
    created_at,
    updated_at
FROM public.profiles;
