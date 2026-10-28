-- ============================================================================
-- TRIFECTA LifeOS — Migración Sprint 7: Soft-Delete, Catálogo Editable,
-- Reordenamiento de Rutinas y Planificador Semanal de Entrenamientos
-- Archivo: sql/07_sprint7_ux_and_planner_migration.sql
-- Ejecutable de forma idempotente en el SQL Editor de Supabase.
-- ============================================================================

-- 1. Requerimiento 1: Soft-Delete (is_active) en Cuentas de Débito y TDC
ALTER TABLE public.finance_accounts
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

CREATE INDEX IF NOT EXISTS idx_finance_accounts_user_active
    ON public.finance_accounts (user_id, is_active, account_type);

-- Compatibilidad opcional si existen tablas alias accounts o credit_cards
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'accounts'
    ) THEN
        EXECUTE 'ALTER TABLE public.accounts ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE';
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'credit_cards'
    ) THEN
        EXECUTE 'ALTER TABLE public.credit_cards ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE';
    END IF;
END $$;

-- 2. Requerimiento 5: Notas técnicas y edición en Catálogo de Ejercicios
ALTER TABLE public.exercises
    ADD COLUMN IF NOT EXISTS notes TEXT DEFAULT '';

-- Permitir que el usuario autenticado actualice ejercicios del catálogo sin romper FK de workout_sets
DROP POLICY IF EXISTS "exercises_update_own" ON public.exercises;
CREATE POLICY "exercises_update_own" ON public.exercises
    FOR UPDATE
    USING (user_id IS NULL OR auth.uid() = user_id)
    WITH CHECK (user_id IS NULL OR auth.uid() = user_id);

-- 3. Requerimiento 8: Asegurar order_index y notas en workout_routine_items
ALTER TABLE public.workout_routine_items
    ADD COLUMN IF NOT EXISTS order_index INT NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS default_rest_seconds INT NOT NULL DEFAULT 90
        CHECK (default_rest_seconds BETWEEN 10 AND 900),
    ADD COLUMN IF NOT EXISTS notes TEXT DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_workout_routine_items_routine_order
    ON public.workout_routine_items (routine_id, order_index ASC);

-- 4. Requerimiento 7: Calendario Semanal de Planificación de Entrenamientos
CREATE TABLE IF NOT EXISTS public.workout_weekly_plan (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    plan_date DATE NOT NULL,
    day_of_week INT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    focus_title TEXT NOT NULL DEFAULT 'Entrenamiento',
    routine_id UUID REFERENCES public.workout_routines(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned', 'completed', 'rest')),
    notes TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, plan_date)
);

CREATE INDEX IF NOT EXISTS idx_workout_weekly_plan_user_date
    ON public.workout_weekly_plan (user_id, plan_date ASC);

ALTER TABLE public.workout_weekly_plan ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "workout_weekly_plan_owner" ON public.workout_weekly_plan;
CREATE POLICY "workout_weekly_plan_owner" ON public.workout_weekly_plan
    FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);
