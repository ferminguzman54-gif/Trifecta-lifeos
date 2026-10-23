-- ============================================================================
-- TRIFECTA LifeOS — Catálogo Semilla (40 Ejercicios Ponderados + Categorías Base)
-- Archivo: sql/02_seed_catalog.sql
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. ÍNDICE ÚNICO PARA EVITAR DUPLICADOS EN EJERCICIOS GLOBALES
-- ----------------------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS idx_exercises_global_unique_name
    ON public.exercises (name)
    WHERE user_id IS NULL;

-- ----------------------------------------------------------------------------
-- 2. CATÁLOGO GLOBAL DE 40 EJERCICIOS PONDERADOS (1.0 Primario / 0.5 Secundarios)
-- ----------------------------------------------------------------------------
INSERT INTO public.exercises (user_id, name, equipment, primary_muscle, secondary_muscles, movement_pattern)
VALUES
    -- PECHO (chest) - 5 ejercicios
    (NULL, 'Press de Banca Plano con Barra', 'barbell', 'chest', ARRAY['triceps', 'front_delts'], 'compound'),
    (NULL, 'Press Inclinado con Mancuernas', 'dumbbell', 'chest', ARRAY['front_delts', 'triceps'], 'compound'),
    (NULL, 'Press de Pecho en Máquina Convergente', 'machine', 'chest', ARRAY['triceps', 'front_delts'], 'compound'),
    (NULL, 'Fondos en Paralelas (Énfasis Pecho)', 'bodyweight', 'chest', ARRAY['triceps', 'front_delts'], 'compound'),
    (NULL, 'Cruces en Polea Alta / Peck Deck', 'cable', 'chest', ARRAY['front_delts'], 'isolation'),

    -- ESPALDA AMPLITUD / DORSALES (back_lats) - 4 ejercicios
    (NULL, 'Dominadas Pronas / Lastradas', 'bodyweight', 'back_lats', ARRAY['biceps', 'back_upper', 'forearms'], 'compound'),
    (NULL, 'Jalón al Pecho en Polea Alta', 'cable', 'back_lats', ARRAY['biceps', 'back_upper'], 'compound'),
    (NULL, 'Remo con Mancuerna a Una Mano', 'dumbbell', 'back_lats', ARRAY['back_upper', 'biceps', 'rear_delts'], 'compound'),
    (NULL, 'Pull-Over en Polea Alta con Cuerda', 'cable', 'back_lats', ARRAY['chest', 'triceps'], 'isolation'),

    -- ESPALDA DENSIDAD / TRAPECIO-ROMBOIDES (back_upper) - 4 ejercicios
    (NULL, 'Remo con Barra Inclinado (Pendlay / Prono)', 'barbell', 'back_upper', ARRAY['back_lats', 'rear_delts', 'biceps', 'forearms'], 'compound'),
    (NULL, 'Remo en Máquina con Apoyo al Pecho (T-Bar)', 'machine', 'back_upper', ARRAY['back_lats', 'rear_delts', 'biceps'], 'compound'),
    (NULL, 'Remo Sentado en Polea Baja (Agarre Neutro)', 'cable', 'back_upper', ARRAY['back_lats', 'biceps', 'rear_delts'], 'compound'),
    (NULL, 'Encogimientos de Hombros con Mancuernas', 'dumbbell', 'back_upper', ARRAY['forearms'], 'isolation'),

    -- CUÁDRICEPS (quads) - 5 ejercicios
    (NULL, 'Sentadilla Libre con Barra (Back Squat)', 'barbell', 'quads', ARRAY['glutes', 'hamstrings', 'abs'], 'compound'),
    (NULL, 'Sentadilla Hack en Máquina (Hack Squat)', 'machine', 'quads', ARRAY['glutes'], 'compound'),
    (NULL, 'Prensa de Piernas Inclinada 45°', 'machine', 'quads', ARRAY['glutes', 'hamstrings'], 'compound'),
    (NULL, 'Sentadilla Búlgara con Mancuernas', 'dumbbell', 'quads', ARRAY['glutes', 'hamstrings'], 'compound'),
    (NULL, 'Extensión de Cuádriceps en Máquina', 'machine', 'quads', ARRAY[]::TEXT[], 'isolation'),

    -- ISQUIOTIBIALES (hamstrings) - 4 ejercicios
    (NULL, 'Peso Muerto Rumano con Barra (RDL)', 'barbell', 'hamstrings', ARRAY['glutes', 'back_upper', 'forearms'], 'compound'),
    (NULL, 'Peso Muerto Convencional con Barra', 'barbell', 'hamstrings', ARRAY['glutes', 'back_upper', 'quads', 'forearms'], 'compound'),
    (NULL, 'Curl Femoral Sentado en Máquina', 'machine', 'hamstrings', ARRAY['calves'], 'isolation'),
    (NULL, 'Curl Femoral Tumbado en Máquina', 'machine', 'hamstrings', ARRAY['glutes'], 'isolation'),

    -- GLÚTEOS (glutes) - 3 ejercicios
    (NULL, 'Hip Thrust con Barra Olímpica', 'barbell', 'glutes', ARRAY['hamstrings', 'quads'], 'compound'),
    (NULL, 'Patada de Glúteo en Polea Baja', 'cable', 'glutes', ARRAY['hamstrings'], 'isolation'),
    (NULL, 'Abducción de Cadera en Máquina', 'machine', 'glutes', ARRAY[]::TEXT[], 'isolation'),

    -- HOMBRO ANTERIOR (front_delts) - 2 ejercicios
    (NULL, 'Press Militar de Pie con Barra (OHP)', 'barbell', 'front_delts', ARRAY['triceps', 'side_delts', 'abs'], 'compound'),
    (NULL, 'Press de Hombros Sentado con Mancuernas', 'dumbbell', 'front_delts', ARRAY['triceps', 'side_delts'], 'compound'),

    -- HOMBRO LATERAL (side_delts) - 2 ejercicios
    (NULL, 'Elevaciones Laterales con Mancuernas', 'dumbbell', 'side_delts', ARRAY['front_delts'], 'isolation'),
    (NULL, 'Elevaciones Laterales en Polea Baja', 'cable', 'side_delts', ARRAY['front_delts'], 'isolation'),

    -- HOMBRO POSTERIOR (rear_delts) - 2 ejercicios
    (NULL, 'Face Pull en Polea Alta con Cuerda', 'cable', 'rear_delts', ARRAY['back_upper', 'side_delts'], 'isolation'),
    (NULL, 'Pájaros / Vuelos Posteriores en Peck Deck', 'machine', 'rear_delts', ARRAY['back_upper'], 'isolation'),

    -- BÍCEPS (biceps) - 3 ejercicios
    (NULL, 'Curl de Bíceps con Barra EZ', 'barbell', 'biceps', ARRAY['forearms'], 'isolation'),
    (NULL, 'Curl de Bíceps Inclinado con Mancuernas', 'dumbbell', 'biceps', ARRAY['forearms'], 'isolation'),
    (NULL, 'Curl Martillo con Mancuernas', 'dumbbell', 'biceps', ARRAY['forearms'], 'isolation'),

    -- TRÍCEPS (triceps) - 3 ejercicios
    (NULL, 'Extensión de Tríceps en Polea Alta con Cuerda', 'cable', 'triceps', ARRAY[]::TEXT[], 'isolation'),
    (NULL, 'Press Francés / Rompecráneos con Barra EZ', 'barbell', 'triceps', ARRAY['front_delts'], 'isolation'),
    (NULL, 'Extensión de Tríceps Tras Nuca en Polea (Katana)', 'cable', 'triceps', ARRAY[]::TEXT[], 'isolation'),

    -- PANTORRILLAS (calves), ABDOMINALES (abs), ANTEBRAZOS (forearms) - 3 ejercicios
    (NULL, 'Elevación de Talones de Pie en Máquina', 'machine', 'calves', ARRAY[]::TEXT[], 'isolation'),
    (NULL, 'Crunch Abdominal en Polea Alta / Elevación de Piernas', 'cable', 'abs', ARRAY[]::TEXT[], 'isolation'),
    (NULL, 'Paseo del Granjero / Curl de Muñeca con Mancuernas', 'dumbbell', 'forearms', ARRAY['back_upper', 'abs'], 'isolation')
ON CONFLICT (name) WHERE user_id IS NULL DO NOTHING;

-- ----------------------------------------------------------------------------
-- 3. FUNCIÓN SEMILLA DE CATEGORÍAS FINANCIERAS Y METAS NUTRICIONALES POR USUARIO
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.seed_default_user_data(target_user_id UUID)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    -- Categorías base de Gasto (expense)
    INSERT INTO public.finance_categories (user_id, name, kind, monthly_budget_limit, icon, color_hex, is_essential)
    VALUES
        (target_user_id, 'Supermercado y Despensa', 'expense', 5000.00, '🛒', '#10B981', TRUE),
        (target_user_id, 'Vivienda y Servicios', 'expense', 8000.00, '🏠', '#3B82F6', TRUE),
        (target_user_id, 'Transporte y Gasolina', 'expense', 3000.00, '🚗', '#F59E0B', TRUE),
        (target_user_id, 'Restaurantes y Café', 'expense', 2500.00, '🍽️', '#EC4899', FALSE),
        (target_user_id, 'Salud, Gym y Suplementos', 'expense', 2000.00, '💪', '#FF5500', TRUE),
        (target_user_id, 'Suscripciones y Digital', 'expense', 1000.00, '📱', '#8B5CF6', FALSE),
        (target_user_id, 'Compras y Tecnología', 'expense', 3000.00, '🛍️', '#06B6D4', FALSE),
        (target_user_id, 'Educación y Desarrollo', 'expense', 1500.00, '📚', '#6366F1', TRUE)
    ON CONFLICT (user_id, name, kind) DO NOTHING;

    -- Categorías base de Ingreso (income)
    INSERT INTO public.finance_categories (user_id, name, kind, monthly_budget_limit, icon, color_hex, is_essential)
    VALUES
        (target_user_id, 'Nómina / Sueldo Principal', 'income', 0.00, '💰', '#22C55E', TRUE),
        (target_user_id, 'Proyectos / Honorarios', 'income', 0.00, '🚀', '#10B981', FALSE),
        (target_user_id, 'Rendimientos y Cashback', 'income', 0.00, '📈', '#06B6D4', FALSE)
    ON CONFLICT (user_id, name, kind) DO NOTHING;

    -- Categoría base de Transferencia / Pago TDC (transfer)
    INSERT INTO public.finance_categories (user_id, name, kind, monthly_budget_limit, icon, color_hex, is_essential)
    VALUES
        (target_user_id, 'Pago de Tarjeta / Transferencia', 'transfer', 0.00, '🔄', '#94A3B8', TRUE)
    ON CONFLICT (user_id, name, kind) DO NOTHING;

    -- Meta nutricional base reservada (conector futuro)
    INSERT INTO public.nutrition_targets (user_id, goal_phase, daily_calories_target, protein_g_target, carbs_g_target, fat_g_target)
    VALUES (target_user_id, 'maintenance', 2400, 160, 250, 75)
    ON CONFLICT (user_id) DO NOTHING;
END;
$$;

-- Actualizar el trigger handle_new_user() para que al registrarse un usuario cree perfil + categorías base
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, full_name)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1))
    )
    ON CONFLICT (id) DO NOTHING;

    PERFORM public.seed_default_user_data(NEW.id);
    RETURN NEW;
END;
$$;

-- Backfill automático para usuarios ya registrados en public.profiles
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN SELECT id FROM public.profiles LOOP
        PERFORM public.seed_default_user_data(r.id);
    END LOOP;
END;
$$;
