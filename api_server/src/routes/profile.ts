import { FastifyInstance } from 'fastify';
import { z } from 'zod';
import bcrypt from 'bcryptjs';
import { supabase } from '../config/supabase';

const updateProfileSchema = z.object({
  name: z.string().min(2).optional(),
  username: z.string().min(3).regex(/^[a-zA-Z0-9_]+$/).optional(),
  avatar_url: z.string().url().optional(),
  bio: z.string().max(200).optional(),
});

const changePasswordSchema = z.object({
  currentPassword: z.string().min(1),
  newPassword: z.string().min(6),
});

export async function profileRoutes(fastify: FastifyInstance) {
  // ── Meu perfil ─────────────────────────────────────
  fastify.get('/me', { preHandler: [fastify.authenticate] }, async (request, reply) => {
    const { data: user, error } = await supabase
      .from('users')
      .select('id, name, username, email, avatar_url, bio, plan, is_verified, theme, language, ai_provider, created_at, last_login')
      .eq('id', request.user.id)
      .single();

    if (error || !user) {
      return reply.status(404).send({ error: 'Usuário não encontrado' });
    }

    return reply.send({ user });
  });

  // ── Atualizar perfil ───────────────────────────────
  fastify.put('/me', { preHandler: [fastify.authenticate] }, async (request, reply) => {
    const parse = updateProfileSchema.safeParse(request.body);
    if (!parse.success) {
      return reply.status(400).send({ error: 'Dados inválidos', details: parse.error.flatten() });
    }

    const updates = parse.data;

    if (updates.username) {
      const { data: existing } = await supabase
        .from('users')
        .select('id')
        .eq('username', updates.username)
        .neq('id', request.user.id)
        .single();

      if (existing) {
        return reply.status(409).send({ error: 'Nome de usuário já em uso' });
      }
    }

    const { data: updated, error } = await supabase
      .from('users')
      .update({ ...updates, updated_at: new Date().toISOString() })
      .eq('id', request.user.id)
      .select('id, name, username, email, avatar_url, bio, plan')
      .single();

    if (error) {
      return reply.status(500).send({ error: 'Erro ao atualizar perfil' });
    }

    return reply.send({ user: updated });
  });

  // ── Alterar senha ──────────────────────────────────
  fastify.post('/change-password', { preHandler: [fastify.authenticate] }, async (request, reply) => {
    const parse = changePasswordSchema.safeParse(request.body);
    if (!parse.success) {
      return reply.status(400).send({ error: 'Dados inválidos' });
    }

    const { currentPassword, newPassword } = parse.data;

    const { data: user } = await supabase
      .from('users')
      .select('password_hash')
      .eq('id', request.user.id)
      .single();

    if (!user) {
      return reply.status(404).send({ error: 'Usuário não encontrado' });
    }

    const match = await bcrypt.compare(currentPassword, user.password_hash);
    if (!match) {
      return reply.status(400).send({ error: 'Senha atual incorreta' });
    }

    const newHash = await bcrypt.hash(newPassword, 12);
    await supabase.from('users').update({ password_hash: newHash }).eq('id', request.user.id);

    return reply.send({ message: 'Senha alterada com sucesso' });
  });

  // ── Excluir conta ──────────────────────────────────
  fastify.delete('/me', { preHandler: [fastify.authenticate] }, async (request, reply) => {
    const userId = request.user.id;

    // Deletar dados do usuário em cascata
    await supabase.from('messages').delete().in(
      'conversation_id',
      (await supabase.from('conversations').select('id').eq('user_id', userId)).data?.map((c) => c.id) || []
    );
    await supabase.from('conversations').delete().eq('user_id', userId);
    await supabase.from('users').delete().eq('id', userId);

    return reply.send({ message: 'Conta excluída com sucesso' });
  });
}
