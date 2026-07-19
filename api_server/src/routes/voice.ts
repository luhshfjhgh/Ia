import { FastifyInstance } from 'fastify';
import { z } from 'zod';
import { supabase } from '../config/supabase';

// ── Voz ─────────────────────────────────────────────
export async function voiceRoutes(fastify: FastifyInstance) {
  fastify.post('/transcribe', { preHandler: [fastify.authenticate] }, async (request, reply) => {
    // Transcrição de áudio via Whisper (Groq)
    const data = await request.file();
    if (!data) {
      return reply.status(400).send({ error: 'Nenhum arquivo de áudio enviado' });
    }

    const buffer = await data.toBuffer();
    const base64Audio = buffer.toString('base64');

    // Usar Groq Whisper para transcrição
    const groqKey = process.env.GROQ_API_KEY;
    if (!groqKey) {
      return reply.status(500).send({ error: 'Groq API Key não configurada' });
    }

    const formData = new FormData();
    const blob = new Blob([buffer], { type: data.mimetype });
    formData.append('file', blob, data.filename);
    formData.append('model', 'whisper-large-v3');
    formData.append('language', 'pt');

    const response = await fetch('https://api.groq.com/openai/v1/audio/transcriptions', {
      method: 'POST',
      headers: { Authorization: `Bearer ${groqKey}` },
      body: formData,
    });

    if (!response.ok) {
      const err = await response.text();
      return reply.status(502).send({ error: 'Erro na transcrição: ' + err });
    }

    const result = await response.json() as { text: string };
    return reply.send({ text: result.text });
  });
}

// ── Configurações ──────────────────────────────────
const settingsSchema = z.object({
  theme: z.enum(['dark', 'light', 'system']).optional(),
  language: z.string().optional(),
  ai_provider: z.string().optional(),
  notifications_enabled: z.boolean().optional(),
  auto_save: z.boolean().optional(),
});

export async function settingsRoutes(fastify: FastifyInstance) {
  fastify.get('/', { preHandler: [fastify.authenticate] }, async (request, reply) => {
    const { data, error } = await supabase
      .from('users')
      .select('theme, language, ai_provider, notifications_enabled, auto_save')
      .eq('id', request.user.id)
      .single();

    if (error) return reply.status(500).send({ error: 'Erro ao buscar configurações' });

    return reply.send({ settings: data });
  });

  fastify.put('/', { preHandler: [fastify.authenticate] }, async (request, reply) => {
    const parse = settingsSchema.safeParse(request.body);
    if (!parse.success) {
      return reply.status(400).send({ error: 'Dados inválidos' });
    }

    const { error } = await supabase
      .from('users')
      .update(parse.data)
      .eq('id', request.user.id);

    if (error) return reply.status(500).send({ error: 'Erro ao salvar configurações' });

    return reply.send({ message: 'Configurações salvas', settings: parse.data });
  });
}

// ── Atualização OTA via GitHub ─────────────────────
const GITHUB_REPO = 'luhshfjhgh/No-Ai';
const GITHUB_API = `https://api.github.com/repos/${GITHUB_REPO}/releases/latest`;

export async function updateRoutes(fastify: FastifyInstance) {
  fastify.get('/check', async (_request, reply) => {
    try {
      const response = await fetch(GITHUB_API, {
        headers: { 'User-Agent': 'NOX-AI-App/1.0' },
      });

      if (!response.ok) {
        return reply.status(502).send({ error: 'Erro ao verificar atualizações' });
      }

      const release = await response.json() as any;

      return reply.send({
        version: release.tag_name,
        name: release.name,
        body: release.body,
        published_at: release.published_at,
        assets: (release.assets || []).map((a: any) => ({
          name: a.name,
          download_url: a.browser_download_url,
          size: a.size,
          content_type: a.content_type,
        })),
      });
    } catch (err: any) {
      return reply.status(502).send({ error: 'Erro ao verificar atualizações: ' + err.message });
    }
  });
}
