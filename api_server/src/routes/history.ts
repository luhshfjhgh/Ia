import { FastifyInstance } from 'fastify';
import { supabase } from '../config/supabase';

export async function historyRoutes(fastify: FastifyInstance) {
  fastify.get('/', { preHandler: [fastify.authenticate] }, async (request, reply) => {
    const query = (request.query as any).q || '';
    const userId = request.user.id;

    let q = supabase
      .from('conversations')
      .select('id, title, is_favorite, created_at, updated_at')
      .eq('user_id', userId)
      .order('updated_at', { ascending: false })
      .limit(100);

    if (query) {
      q = q.ilike('title', `%${query}%`);
    }

    const { data, error } = await q;

    if (error) return reply.status(500).send({ error: 'Erro ao buscar histórico' });

    return reply.send({ history: data || [] });
  });

  fastify.get('/favorites', { preHandler: [fastify.authenticate] }, async (request, reply) => {
    const { data, error } = await supabase
      .from('conversations')
      .select('id, title, is_favorite, created_at, updated_at')
      .eq('user_id', request.user.id)
      .eq('is_favorite', true)
      .order('updated_at', { ascending: false });

    if (error) return reply.status(500).send({ error: 'Erro ao buscar favoritos' });

    return reply.send({ favorites: data || [] });
  });

  fastify.delete('/clear', { preHandler: [fastify.authenticate] }, async (request, reply) => {
    const userId = request.user.id;
    const convIds = (
      await supabase.from('conversations').select('id').eq('user_id', userId)
    ).data?.map((c) => c.id) || [];

    if (convIds.length > 0) {
      await supabase.from('messages').delete().in('conversation_id', convIds);
      await supabase.from('conversations').delete().eq('user_id', userId);
    }

    return reply.send({ message: 'Histórico limpo com sucesso' });
  });
}
