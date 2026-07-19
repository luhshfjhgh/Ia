// ╔══════════════════════════════════════════════╗
// ║        NOX AI — API Server v1.0              ║
// ║  WR Programação & Neurocode Web Systems      ║
// ╚══════════════════════════════════════════════╝

import 'dotenv/config';
import Fastify from 'fastify';
import fastifyCors from '@fastify/cors';
import fastifyHelmet from '@fastify/helmet';
import fastifyJwt from '@fastify/jwt';
import fastifyMultipart from '@fastify/multipart';
import fastifyRateLimit from '@fastify/rate-limit';
import fastifyWebSocket from '@fastify/websocket';

import { authRoutes } from './routes/auth';
import { chatRoutes } from './routes/chat';
import { profileRoutes } from './routes/profile';
import { historyRoutes } from './routes/history';
import { uploadRoutes } from './routes/upload';
import { voiceRoutes } from './routes/voice';
import { settingsRoutes } from './routes/settings';
import { updateRoutes } from './routes/update';
import { authMiddleware } from './middleware/auth';

const PORT = parseInt(process.env.PORT || '8080', 10);
const HOST = process.env.HOST || '0.0.0.0';

const fastify = Fastify({
  logger: {
    level: process.env.NODE_ENV === 'production' ? 'warn' : 'info',
    transport:
      process.env.NODE_ENV !== 'production'
        ? { target: 'pino-pretty', options: { colorize: true } }
        : undefined,
  },
});

async function bootstrap() {
  // ── Segurança ──────────────────────────────────────────
  await fastify.register(fastifyHelmet, {
    contentSecurityPolicy: false,
  });

  await fastify.register(fastifyCors, {
    origin: process.env.CORS_ORIGINS?.split(',') || ['http://localhost:3000'],
    credentials: true,
    methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
  });

  await fastify.register(fastifyRateLimit, {
    max: parseInt(process.env.RATE_LIMIT_MAX || '100', 10),
    timeWindow: parseInt(process.env.RATE_LIMIT_WINDOW_MS || '60000', 10),
    errorResponseBuilder: () => ({
      statusCode: 429,
      error: 'Too Many Requests',
      message: 'Muitas requisições. Tente novamente em instantes.',
    }),
  });

  // ── JWT ────────────────────────────────────────────────
  await fastify.register(fastifyJwt, {
    secret: process.env.JWT_SECRET!,
  });

  // ── Multipart (uploads) ───────────────────────────────
  await fastify.register(fastifyMultipart, {
    limits: {
      fileSize: parseInt(process.env.MAX_FILE_SIZE_MB || '50', 10) * 1024 * 1024,
    },
  });

  // ── WebSocket ─────────────────────────────────────────
  await fastify.register(fastifyWebSocket);

  // ── Decorators globais ────────────────────────────────
  fastify.decorate('authenticate', authMiddleware(fastify));

  // ── Health check ──────────────────────────────────────
  fastify.get('/health', async () => ({
    status: 'ok',
    service: 'NOX AI API Server',
    version: '1.0.0',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
  }));

  // ── Rotas ─────────────────────────────────────────────
  await fastify.register(authRoutes, { prefix: '/api/auth' });
  await fastify.register(chatRoutes, { prefix: '/api/chat' });
  await fastify.register(profileRoutes, { prefix: '/api/profile' });
  await fastify.register(historyRoutes, { prefix: '/api/history' });
  await fastify.register(uploadRoutes, { prefix: '/api/upload' });
  await fastify.register(voiceRoutes, { prefix: '/api/voice' });
  await fastify.register(settingsRoutes, { prefix: '/api/settings' });
  await fastify.register(updateRoutes, { prefix: '/api/update' });

  // ── 404 handler ───────────────────────────────────────
  fastify.setNotFoundHandler((request, reply) => {
    reply.status(404).send({
      statusCode: 404,
      error: 'Not Found',
      message: `Rota não encontrada: ${request.method} ${request.url}`,
    });
  });

  // ── Error handler ─────────────────────────────────────
  fastify.setErrorHandler((error, request, reply) => {
    fastify.log.error(error);
    const statusCode = error.statusCode || 500;
    reply.status(statusCode).send({
      statusCode,
      error: error.name || 'Internal Server Error',
      message: error.message || 'Erro interno do servidor',
    });
  });

  // ── Start ─────────────────────────────────────────────
  await fastify.listen({ port: PORT, host: HOST });

  console.log(`
╔══════════════════════════════════════════════╗
║          NOX AI — API Server v1.0            ║
║   WR Programação & Neurocode Web Systems     ║
╠══════════════════════════════════════════════╣
║  ✅  Servidor rodando na porta ${PORT}          ║
║  🌐  http://${HOST}:${PORT}                 ║
║  📡  Use: ngrok http ${PORT}                  ║
╚══════════════════════════════════════════════╝
  `);
}

bootstrap().catch((err) => {
  console.error('Erro ao iniciar servidor:', err);
  process.exit(1);
});
