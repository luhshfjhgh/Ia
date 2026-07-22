-- ╔══════════════════════════════════════════════════════╗
-- ║  NOX AI — Migração v4: Planos Premium (Pix)           ║
-- ╚══════════════════════════════════════════════════════╝
-- Execute UMA VEZ no SQL Editor do Supabase, depois das migrações
-- anteriores (schema.sql, v2_roles.sql, v3_security.sql).

ALTER TABLE public.users ADD COLUMN IF NOT EXISTS plan TEXT NOT NULL DEFAULT 'free';
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS plan_status TEXT NOT NULL DEFAULT 'ativo';
-- plan: 'free' | 'basic' | 'pro'
-- plan_status: 'ativo' | 'aguardando_confirmacao' | 'rejeitado'

CREATE TABLE IF NOT EXISTS public.payment_receipts (
  id               BIGSERIAL PRIMARY KEY,
  user_id          UUID REFERENCES public.users(id) ON DELETE SET NULL,
  username         TEXT,
  plan             TEXT NOT NULL,           -- 'basic' ou 'pro'
  file_name        TEXT,
  valor            TEXT,
  data_pagamento   TEXT,
  hora_pagamento   TEXT,
  nome_destino     TEXT,
  banco            TEXT,
  chave_pix        TEXT,
  e2e_txid         TEXT,
  texto_bruto      TEXT,                    -- texto cru extraído, para revisão manual
  status           TEXT NOT NULL DEFAULT 'aguardando_confirmacao',
  -- status: 'aguardando_confirmacao' | 'confirmado' | 'rejeitado'
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  reviewed_at      TIMESTAMPTZ,
  reviewed_by      TEXT
);
CREATE INDEX IF NOT EXISTS idx_receipts_user   ON public.payment_receipts(user_id);
CREATE INDEX IF NOT EXISTS idx_receipts_status ON public.payment_receipts(status);
