-- ╔══════════════════════════════════════════════╗
-- ║   NOX AI — Migração v2: papéis (admin/user)  ║
-- ╚══════════════════════════════════════════════╝
-- Execute UMA VEZ no SQL Editor do seu projeto Supabase
-- (https://supabase.com/dashboard/project/_/sql/new)
--
-- Isso adiciona a coluna "role" na tabela de usuários, usada pela
-- NOX AI (terminal) para diferenciar administradores de usuários
-- comuns. O primeiro usuário a se cadastrar vira admin automaticamente.

ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'user';

-- (Opcional) Torne um usuário existente admin manualmente:
-- UPDATE public.users SET role = 'admin' WHERE username = 'seu_usuario';
