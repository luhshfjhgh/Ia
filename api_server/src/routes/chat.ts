import { FastifyInstance } from 'fastify';
import { z } from 'zod';
import { supabase } from '../config/supabase';
import { generateAIResponse, ChatMessage } from '../services/ai';

const sendMessageSchema = z.object({
  message: z.string().min(1).max(8000),
  conversationId: z.string().uuid().optional(),
  provider: z.string().optional(),
  fileUrls: z.array(z.string()).optional(),
});

const createConversationSchema = z.object({
  title: z.string().min(1).max(200).optional(),
});

export async function chatRoutes(fastify: FastifyInstance) {
  // ── Enviar mensagem ────────────────────────────────
  fastify.post('/message', { preHandler: [fastify.authenticate] }, async (request, reply) => {
    const parse = sendMessageSchema.safeParse(request.body);
    if (!parse.success) {
      return reply.status(400).send({ error: 'Dados inválidos', details: parse.error.flatten() });
    }

    const { message, conversationId, provider, fileUrls } = parse.data;
    const userId = request.user.id;

    let convId = conversationId;

    // Criar conversa se não existir
    if (!convId) {
      const title = message.length > 50 ? message.substring(0, 50) + '...' : message;
      const { data: newConv, error } = await supabase
        .from('conversations')
        .insert({ user_id: userId, title, created_at: new Date().toISOString() })
        .select('id')
        .single();

      if (error || !newConv) {
        return reply.status(500).send({ error: 'Erro ao criar conversa' });
      }
      convId = newConv.id;
    }

    // Buscar histórico da conversa (últimas 20 mensagens)
    const { data: history } = await supabase
      .from('messages')
      .select('role, content')
      .eq('conversation_id', convId)
      .order('created_at', { ascending: true })
      .limit(20);

    const messages: ChatMessage[] = (history || []).map((m) => ({
      role: m.role as 'user' | 'assistant',
      content: m.content,
    }));

    // Adicionar mensagem atual
    messages.push({ role: 'user', content: message });

    // Salvar mensagem do usuário
    await supabase.from('messages').insert({
      conversation_id: convId,
      role: 'user',
      content: message,
      file_urls: fileUrls || [],
      created_at: new Date().toISOString(),
    });

    // Gerar resposta da IA
    let aiResponse;
    try {
      aiResponse = await generateAIResponse(messages, provider);
    } catch (err: any) {
      fastify.log.error('Erro na IA:', err);
      return reply.status(502).send({ error: 'Erro ao gerar resposta da IA: ' + err.message });
    }

    // Salvar resposta da IA
    await supabase.from('messages').insert({
      conversation_id: convId,
      role: 'assistant',
      content: aiResponse.content,
      model: aiResponse.model,
      provider: aiResponse.provider,
      tokens: aiResponse.tokens,
      created_at: new Date().toISOString(),
    });

    // Atualizar timestamp da conversa
    await supabase
      .from('conversations')
      .update({ updated_at: new Date().toISOString() })
      .eq('id', convId);

    return reply.send({
      conversationId: convId,
      message: {
        role: 'assistant',
        content: aiResponse.content,
        model: aiResponse.model,
        provider: aiResponse.provider,
        tokens: aiResponse.tokens,
      },
    });
  });

  // ── Listar conversas ───────────────────────────────
  fastify.get('/conversations', { preHandler: [fastify.authenticate] }, async (request, reply) => {
    const userId = request.user.id;

    const { data, error } = await supabase
      .from('conversations')
      .select('id, title, is_favorite, created_at, updated_at')
      .eq('user_id', userId)
      .order('updated_at', { ascending: false })
      .limit(100);

    if (error) {
      return reply.status(500).send({ error: 'Erro ao buscar conversas' });
    }

    return reply.send({ conversations: data || [] });
  });

  // ── Buscar mensagens de uma conversa ───────────────
  fastify.get('/conversations/:id/messages', { preHandler: [fastify.authenticate] }, async (request, reply) => {
    const { id } = request.params as { id: string };
    const userId = request.user.id;

    // Verificar que a conversa pertence ao usuário
    const { data: conv } = await supabase
      .from('conversations')
      .select('id')
      .eq('id', id)
      .eq('user_id', userId)
      .single();

    if (!conv) {
      return reply.status(404).send({ error: 'Conversa não encontrada' });
    }

    const { data: messages, error } = await supabase
      .from('messages')
      .select('*')
      .eq('conversation_id', id)
      .order('created_at', { ascending: true });

    if (error) {
      return reply.status(500).send({ error: 'Erro ao buscar mensagens' });
    }

    return reply.send({ messages: messages || [] });
  });

  // ── Renomear conversa ──────────────────────────────
  fastify.patch('/conversations/:id', { preHandler: [fastify.authenticate] }, async (request, reply) => {
    const { id } = request.params as { id: string };
    const parse = createConversationSchema.safeParse(request.body);

    if (!parse.success) {
      return reply.status(400).send({ error: 'Título inválido' });
    }

    const { error } = await supabase
      .from('conversations')
      .update({ title: parse.data.title })
      .eq('id', id)
      .eq('user_id', request.user.id);

    if (error) {
      return reply.status(500).send({ error: 'Erro ao renomear conversa' });
    }

    return reply.send({ message: 'Conversa renomeada' });
  });

  // ── Favoritar conversa ─────────────────────────────
  fastify.patch('/conversations/:id/favorite', { preHandler: [fastify.authenticate] }, async (request, reply) => {
    const { id } = request.params as { id: string };

    const { data: conv } = await supabase
      .from('conversations')
      .select('is_favorite')
      .eq('id', id)
      .eq('user_id', request.user.id)
      .single();

    if (!conv) {
      return reply.status(404).send({ error: 'Conversa não encontrada' });
    }

    await supabase
      .from('conversations')
      .update({ is_favorite: !conv.is_favorite })
      .eq('id', id);

    return reply.send({ is_favorite: !conv.is_favorite });
  });

  // ── Deletar conversa ───────────────────────────────
  fastify.delete('/conversations/:id', { preHandler: [fastify.authenticate] }, async (request, reply) => {
    const { id } = request.params as { id: string };

    await supabase.from('messages').delete().eq('conversation_id', id);
    const { error } = await supabase
      .from('conversations')
      .delete()
      .eq('id', id)
      .eq('user_id', request.user.id);

    if (error) {
      return reply.status(500).send({ error: 'Erro ao deletar conversa' });
    }

    return reply.send({ message: 'Conversa deletada' });
  });

  // ── WebSocket para chat em tempo real ──────────────
  fastify.get('/ws', { websocket: true, preHandler: [fastify.authenticate] }, (socket, request) => {
    const userId = request.user.id;
    fastify.log.info(`WebSocket conectado: ${userId}`);

    socket.on('message', async (rawMessage) => {
      try {
        const data = JSON.parse(rawMessage.toString());

        if (data.type === 'ping') {
          socket.send(JSON.stringify({ type: 'pong' }));
          return;
        }

        if (data.type === 'chat') {
          const messages: ChatMessage[] = data.messages || [];
          const provider = data.provider;

          socket.send(JSON.stringify({ type: 'thinking' }));

          const aiResponse = await generateAIResponse(messages, provider);

          socket.send(JSON.stringify({
            type: 'response',
            content: aiResponse.content,
            model: aiResponse.model,
            provider: aiResponse.provider,
          }));
        }
      } catch (err) {
        socket.send(JSON.stringify({ type: 'error', message: 'Erro ao processar mensagem' }));
      }
    });

    socket.on('close', () => {
      fastify.log.info(`WebSocket desconectado: ${userId}`);
    });
  });
}
