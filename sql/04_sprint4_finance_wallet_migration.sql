-- ============================================================================
-- TRIFECTA LifeOS — Migración Sprint 4: Finanzas, Billetera Apple Wallet y Simulador TDC
-- Archivo: sql/04_sprint4_finance_wallet_migration.sql
-- Ejecutable de forma idempotente sobre bases de datos con Sprints 1, 2 y 3 activos.
-- ============================================================================

-- 1. Ampliar parámetros financieros de tarjetas de crédito (Pago mínimo % y Días de gracia)
ALTER TABLE public.finance_accounts
    ADD COLUMN IF NOT EXISTS minimum_payment_pct NUMERIC(4,2) NOT NULL DEFAULT 5.00
        CHECK (minimum_payment_pct BETWEEN 1.00 AND 100.00),
    ADD COLUMN IF NOT EXISTS grace_days INT NOT NULL DEFAULT 20
        CHECK (grace_days BETWEEN 10 AND 35);

-- 2. Agregar soporte de etiquetas (tags) en transacciones financieras
ALTER TABLE public.finance_transactions
    ADD COLUMN IF NOT EXISTS tags TEXT[] NOT NULL DEFAULT '{}';

-- 3. Índices compuestos para acelerar el dashboard mensual, simulador de TDC y calendario
CREATE INDEX IF NOT EXISTS idx_finance_accounts_user_active
    ON public.finance_accounts (user_id, is_active, account_type);

CREATE INDEX IF NOT EXISTS idx_finance_tx_user_account_date
    ON public.finance_transactions (user_id, account_id, tx_date DESC);

CREATE INDEX IF NOT EXISTS idx_finance_tx_user_category_date
    ON public.finance_transactions (user_id, category_id, tx_date DESC);

CREATE INDEX IF NOT EXISTS idx_finance_subscriptions_user_active
    ON public.finance_subscriptions (user_id, is_active, billing_day_of_month ASC);

-- 4. Asegurar políticas Row Level Security (RLS) vinculadas a auth.uid() en todo el Pilar 2
ALTER TABLE public.finance_accounts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "finance_accounts_owner" ON public.finance_accounts;
CREATE POLICY "finance_accounts_owner" ON public.finance_accounts
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

ALTER TABLE public.finance_categories ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "finance_categories_owner" ON public.finance_categories;
CREATE POLICY "finance_categories_owner" ON public.finance_categories
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

ALTER TABLE public.finance_transactions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "finance_transactions_owner" ON public.finance_transactions;
CREATE POLICY "finance_transactions_owner" ON public.finance_transactions
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

ALTER TABLE public.finance_subscriptions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "finance_subscriptions_owner" ON public.finance_subscriptions;
CREATE POLICY "finance_subscriptions_owner" ON public.finance_subscriptions
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

ALTER TABLE public.bank_statement_imports ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "bank_statement_imports_owner" ON public.bank_statement_imports;
CREATE POLICY "bank_statement_imports_owner" ON public.bank_statement_imports
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
