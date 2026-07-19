import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';

export function authMiddleware(fastify: FastifyInstance) {
  return async function authenticate(request: FastifyRequest, reply: FastifyReply) {
    try {
      await request.jwtVerify();
    } catch (err) {
      reply.status(401).send({
        statusCode: 401,
        error: 'Unauthorized',
        message: 'Token inválido ou expirado. Faça login novamente.',
      });
    }
  };
}

// Extend FastifyInstance typings
declare module 'fastify' {
  interface FastifyInstance {
    authenticate: (request: FastifyRequest, reply: FastifyReply) => Promise<void>;
  }
  interface FastifyRequest {
    user: {
      id: string;
      email: string;
      username: string;
    };
  }
}
