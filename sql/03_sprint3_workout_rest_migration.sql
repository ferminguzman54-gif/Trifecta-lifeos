-- ============================================================================
-- TRIFECTA LifeOS — Migración Sprint 3: Descanso Inter-Serie, RIR y Densidad
-- Archivo: sql/03_sprint3_workout_rest_migration.sql
-- Ejecutable de forma idempotente sobre bases de datos con Sprints 1 y 2 activos.
-- ============================================================================

-- 1. Agregar configuración de descanso objetivo por ejercicio en plantillas de rutina
ALTER TABLE public.workout_routine_items
    ADD COLUMN IF NOT EXISTS default_rest_seconds INT NOT NULL DEFAULT 90
        CHECK (default_rest_seconds BETWEEN 10 AND 900);

-- 2. Agregar campos de RIR, descanso objetivo, descanso real transcurrido y notas en series
ALTER TABLE public.workout_sets
    ADD COLUMN IF NOT EXISTS rir NUMERIC(3,1) DEFAULT 2.0
        CHECK (rir BETWEEN 0.0 AND 5.0),
    ADD COLUMN IF NOT EXISTS rest_target_seconds INT NOT NULL DEFAULT 90
        CHECK (rest_target_seconds >= 0),
    ADD COLUMN IF NOT EXISTS rest_actual_seconds INT NOT NULL DEFAULT 0
        CHECK (rest_actual_seconds >= 0),
    ADD COLUMN IF NOT EXISTS notes TEXT DEFAULT '';

-- 3. Índices adicionales para analítica multitemporal (1D a 1Y) y correlación de descanso
CREATE INDEX IF NOT EXISTS idx_workout_sets_user_session
    ON public.workout_sets (user_id, session_id, set_number ASC);

CREATE INDEX IF NOT EXISTS idx_workout_routine_items_routine_order
    ON public.workout_routine_items (routine_id, order_index ASC);

-- 4. Re-asegurar políticas RLS estrictas por usuario en todas las tablas del Pilar 1
ALTER TABLE public.exercises ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workout_routines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workout_routine_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workout_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workout_sets ENABLE ROW LEVEL SECURITY;
