-- ============================================================================
-- TRIFECTA LifeOS — Migración Sprint 5 (Command Center Hub & Trifecta Score)
-- Archivo: sql/05_sprint5_hub_and_snapshots_migration.sql
-- Propósito:
--   1. Crear tabla `public.daily_life_snapshots` para persistir el Trifecta Score
--      diario y el pulso integrado de los 3 pilares (Hábitos, Entrenamiento y Finanzas).
--   2. Incluir las columnas requeridas: user_id, date, habit_score, workout_completed,
--      budget_status, trifecta_score, metadata (más workout_score y finance_score).
--   3. Configurar índices compuestos y políticas RLS vinculadas a auth.uid().
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.daily_life_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    habit_score NUMERIC(5,2) NOT NULL DEFAULT 0.00 CHECK (habit_score BETWEEN 0 AND 100),
    workout_score NUMERIC(5,2) NOT NULL DEFAULT 0.00 CHECK (workout_score BETWEEN 0 AND 100),
    finance_score NUMERIC(5,2) NOT NULL DEFAULT 0.00 CHECK (finance_score BETWEEN 0 AND 100),
    workout_completed BOOLEAN NOT NULL DEFAULT FALSE,
    budget_status TEXT NOT NULL DEFAULT 'OPTIMAL'
        CHECK (budget_status IN ('OPTIMAL', 'WARNING', 'CRITICAL')),
    trifecta_score NUMERIC(5,2) NOT NULL DEFAULT 0.00 CHECK (trifecta_score BETWEEN 0 AND 100),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, date)
);

CREATE INDEX IF NOT EXISTS idx_daily_life_snapshots_user_date
    ON public.daily_life_snapshots (user_id, date DESC);

ALTER TABLE public.daily_life_snapshots ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "daily_life_snapshots_owner" ON public.daily_life_snapshots;
CREATE POLICY "daily_life_snapshots_owner" ON public.daily_life_snapshots
    FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);
