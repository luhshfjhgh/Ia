-- ╔══════════════════════════════════════════════════════╗
-- ║  NOX AI — Migração v3: segurança, auditoria e cotas   ║
-- ╚══════════════════════════════════════════════════════╝
-- Execute UMA VEZ no SQL Editor do Supabase, depois das migrações
-- anteriores (schema.sql e schema_update_v2_roles.sql).

ALTER TABLE public.users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS ban_reason TEXT;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS ban_until TIMESTAMPTZ;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS failed_login_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS daily_message_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS daily_message_reset_at DATE;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS daily_message_limit INTEGER NOT NULL DEFAULT 200;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS last_login_ip TEXT;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS last_login_location TEXT;

CREATE TABLE IF NOT EXISTS public.audit_log (
  id         BIGSERIAL PRIMARY KEY,
  user_id    UUID REFERENCES public.users(id) ON DELETE SET NULL,
  username   TEXT,
  event      TEXT NOT NULL,
  details    TEXT,
  ip         TEXT,
  location   TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_log_user    ON public.audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_event   ON public.audit_log(event);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON public.audit_log(created_at DESC);
