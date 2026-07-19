-- ╔══════════════════════════════════════════════╗
-- ║       NOX AI — Schema do Banco de Dados      ║
-- ║  WR Programação & Neurocode Web Systems      ║
-- ╚══════════════════════════════════════════════╝
-- Execute este script no SQL Editor do Supabase

-- ── Extensões ──────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Tabela: users ──────────────────────────────────
CREATE TABLE IF NOT EXISTS public.users (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL,
  username TEXT UNIQUE NOT NULL,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  avatar_url TEXT,
  bio TEXT,
  plan TEXT DEFAULT 'free',
  is_verified BOOLEAN DEFAULT FALSE,
  verification_code TEXT,
  verification_code_expires_at TIMESTAMPTZ,
  reset_code TEXT,
  reset_code_expires_at TIMESTAMPTZ,
  theme TEXT DEFAULT 'dark',
  language TEXT DEFAULT 'pt-BR',
  ai_provider TEXT DEFAULT 'groq',
  notifications_enabled BOOLEAN DEFAULT TRUE,
  auto_save BOOLEAN DEFAULT TRUE,
  last_login TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Tabela: conversations ──────────────────────────
CREATE TABLE IF NOT EXISTS public.conversations (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  title TEXT NOT NULL DEFAULT 'Nova Conversa',
  is_favorite BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Tabela: messages ──────────────────────────────
CREATE TABLE IF NOT EXISTS public.messages (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  conversation_id UUID NOT NULL REFERENCES public.conversations(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
  content TEXT NOT NULL,
  model TEXT,
  provider TEXT,
  tokens INTEGER,
  file_urls TEXT[] DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Índices ───────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON public.conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_updated ON public.conversations(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON public.messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created ON public.messages(created_at ASC);
CREATE INDEX IF NOT EXISTS idx_users_email ON public.users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON public.users(username);

-- ── Row Level Security (RLS) ───────────────────────
-- ATENÇÃO: O backend usa service_role key que bypass RLS
-- Mas habilitar RLS protege contra acesso direto
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;

-- Políticas: usuário autenticado acessa apenas seus dados
-- (O backend usa service_role e não é afetado pelas policies)
CREATE POLICY "users_own_data" ON public.users
  FOR ALL USING (auth.uid()::text = id::text);

CREATE POLICY "conversations_own_data" ON public.conversations
  FOR ALL USING (auth.uid()::text = user_id::text);

CREATE POLICY "messages_via_conversations" ON public.messages
  FOR ALL USING (
    conversation_id IN (
      SELECT id FROM public.conversations WHERE user_id::text = auth.uid()::text
    )
  );
