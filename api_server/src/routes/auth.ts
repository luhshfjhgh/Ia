import { FastifyInstance } from 'fastify';
import bcrypt from 'bcryptjs';
import { z } from 'zod';
import { supabase } from '../config/supabase';
import {
  sendVerificationEmail,
  sendPasswordResetEmail,
  generateCode,
} from '../services/email';

const registerSchema = z.object({
  name: z.string().min(2, 'Nome deve ter ao menos 2 caracteres'),
  username: z.string().min(3, 'Usuário deve ter ao menos 3 caracteres').regex(/^[a-zA-Z0-9_]+$/, 'Usuário só pode conter letras, números e _'),
  email: z.string().email('Email inválido'),
  password: z.string().min(6, 'Senha deve ter ao menos 6 caracteres'),
});

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

const verifySchema = z.object({
  email: z.string().email(),
  code: z.string().length(6),
});

const forgotSchema = z.object({
  email: z.string().email(),
});

const resetSchema = z.object({
  email: z.string().email(),
  code: z.string().length(6),
  newPassword: z.string().min(6),
});

const refreshSchema = z.object({
  refreshToken: z.string(),
});

export async function authRoutes(fastify: FastifyInstance) {
  // ── Cadastro ───────────────────────────────────────
  fastify.post('/register', async (request, reply) => {
    const parse = registerSchema.safeParse(request.body);
    if (!parse.success) {
      return reply.status(400).send({ error: 'Dados inválidos', details: parse.error.flatten() });
    }

    const { name, username, email, password } = parse.data;

    // Verificar se email já existe
    const { data: existingEmail } = await supabase
      .from('users')
      .select('id')
      .eq('email', email)
      .single();

    if (existingEmail) {
      return reply.status(409).send({ error: 'Email já cadastrado' });
    }

    // Verificar se username já existe
    const { data: existingUsername } = await supabase
      .from('users')
      .select('id')
      .eq('username', username)
      .single();

    if (existingUsername) {
      return reply.status(409).send({ error: 'Nome de usuário já em uso' });
    }

    const passwordHash = await bcrypt.hash(password, 12);
    const verificationCode = generateCode(6);
    const codeExpiresAt = new Date(Date.now() + 15 * 60 * 1000).toISOString(); // 15 min

    const { data: newUser, error } = await supabase
      .from('users')
      .insert({
        name,
        username,
        email,
        password_hash: passwordHash,
        is_verified: false,
        verification_code: verificationCode,
        verification_code_expires_at: codeExpiresAt,
        plan: 'free',
        ai_provider: process.env.AI_PROVIDER || 'groq',
        theme: 'dark',
        language: 'pt-BR',
        created_at: new Date().toISOString(),
      })
      .select('id, name, email, username')
      .single();

    if (error || !newUser) {
      fastify.log.error(error);
      return reply.status(500).send({ error: 'Erro ao criar conta' });
    }

    // Enviar email de verificação
    try {
      await sendVerificationEmail(email, name, verificationCode);
    } catch (emailErr) {
      fastify.log.warn('Erro ao enviar email de verificação:', emailErr);
    }

    return reply.status(201).send({
      message: 'Conta criada com sucesso. Verifique seu email.',
      userId: newUser.id,
    });
  });

  // ── Login ──────────────────────────────────────────
  fastify.post('/login', async (request, reply) => {
    const parse = loginSchema.safeParse(request.body);
    if (!parse.success) {
      return reply.status(400).send({ error: 'Dados inválidos' });
    }

    const { email, password } = parse.data;

    const { data: user, error } = await supabase
      .from('users')
      .select('*')
      .eq('email', email)
      .single();

    if (error || !user) {
      return reply.status(401).send({ error: 'Email ou senha incorretos' });
    }

    const passwordMatch = await bcrypt.compare(password, user.password_hash);
    if (!passwordMatch) {
      return reply.status(401).send({ error: 'Email ou senha incorretos' });
    }

    if (!user.is_verified) {
      return reply.status(403).send({
        error: 'Conta não verificada',
        requiresVerification: true,
        email: user.email,
      });
    }

    const accessToken = fastify.jwt.sign(
      { id: user.id, email: user.email, username: user.username },
      { expiresIn: process.env.JWT_EXPIRES_IN || '7d' }
    );

    const refreshToken = fastify.jwt.sign(
      { id: user.id, type: 'refresh' },
      { expiresIn: process.env.JWT_REFRESH_EXPIRES_IN || '30d' }
    );

    // Atualizar último login
    await supabase.from('users').update({ last_login: new Date().toISOString() }).eq('id', user.id);

    return reply.send({
      accessToken,
      refreshToken,
      user: {
        id: user.id,
        name: user.name,
        username: user.username,
        email: user.email,
        avatar_url: user.avatar_url,
        plan: user.plan,
        is_verified: user.is_verified,
      },
    });
  });

  // ── Verificar conta ────────────────────────────────
  fastify.post('/verify', async (request, reply) => {
    const parse = verifySchema.safeParse(request.body);
    if (!parse.success) {
      return reply.status(400).send({ error: 'Dados inválidos' });
    }

    const { email, code } = parse.data;

    const { data: user } = await supabase
      .from('users')
      .select('*')
      .eq('email', email)
      .single();

    if (!user) {
      return reply.status(404).send({ error: 'Usuário não encontrado' });
    }

    if (user.is_verified) {
      return reply.send({ message: 'Conta já verificada' });
    }

    if (user.verification_code !== code) {
      return reply.status(400).send({ error: 'Código inválido' });
    }

    if (new Date(user.verification_code_expires_at) < new Date()) {
      return reply.status(400).send({ error: 'Código expirado. Solicite um novo.' });
    }

    await supabase
      .from('users')
      .update({
        is_verified: true,
        verification_code: null,
        verification_code_expires_at: null,
      })
      .eq('id', user.id);

    return reply.send({ message: 'Conta verificada com sucesso!' });
  });

  // ── Reenviar código de verificação ─────────────────
  fastify.post('/resend-verification', async (request, reply) => {
    const parse = forgotSchema.safeParse(request.body);
    if (!parse.success) {
      return reply.status(400).send({ error: 'Email inválido' });
    }

    const { email } = parse.data;
    const { data: user } = await supabase.from('users').select('*').eq('email', email).single();

    if (!user) {
      return reply.send({ message: 'Se o email existir, o código será reenviado.' });
    }

    if (user.is_verified) {
      return reply.send({ message: 'Conta já verificada' });
    }

    const code = generateCode(6);
    const expiresAt = new Date(Date.now() + 15 * 60 * 1000).toISOString();

    await supabase.from('users').update({
      verification_code: code,
      verification_code_expires_at: expiresAt,
    }).eq('id', user.id);

    try {
      await sendVerificationEmail(email, user.name, code);
    } catch (e) {
      fastify.log.warn('Erro ao reenviar email:', e);
    }

    return reply.send({ message: 'Código reenviado! Verifique seu email.' });
  });

  // ── Esqueci a senha ────────────────────────────────
  fastify.post('/forgot-password', async (request, reply) => {
    const parse = forgotSchema.safeParse(request.body);
    if (!parse.success) {
      return reply.status(400).send({ error: 'Email inválido' });
    }

    const { email } = parse.data;
    const { data: user } = await supabase.from('users').select('*').eq('email', email).single();

    // Sempre retornar sucesso para não revelar existência do email
    if (!user) {
      return reply.send({ message: 'Se o email existir, você receberá um código.' });
    }

    const code = generateCode(6);
    const expiresAt = new Date(Date.now() + 15 * 60 * 1000).toISOString();

    await supabase.from('users').update({
      reset_code: code,
      reset_code_expires_at: expiresAt,
    }).eq('id', user.id);

    try {
      await sendPasswordResetEmail(email, user.name, code);
    } catch (e) {
      fastify.log.warn('Erro ao enviar email de reset:', e);
    }

    return reply.send({ message: 'Código enviado! Verifique seu email.' });
  });

  // ── Redefinir senha ────────────────────────────────
  fastify.post('/reset-password', async (request, reply) => {
    const parse = resetSchema.safeParse(request.body);
    if (!parse.success) {
      return reply.status(400).send({ error: 'Dados inválidos', details: parse.error.flatten() });
    }

    const { email, code, newPassword } = parse.data;

    const { data: user } = await supabase.from('users').select('*').eq('email', email).single();

    if (!user || user.reset_code !== code) {
      return reply.status(400).send({ error: 'Código inválido' });
    }

    if (new Date(user.reset_code_expires_at) < new Date()) {
      return reply.status(400).send({ error: 'Código expirado. Solicite um novo.' });
    }

    const passwordHash = await bcrypt.hash(newPassword, 12);

    await supabase.from('users').update({
      password_hash: passwordHash,
      reset_code: null,
      reset_code_expires_at: null,
    }).eq('id', user.id);

    return reply.send({ message: 'Senha redefinida com sucesso!' });
  });

  // ── Refresh token ──────────────────────────────────
  fastify.post('/refresh', async (request, reply) => {
    const parse = refreshSchema.safeParse(request.body);
    if (!parse.success) {
      return reply.status(400).send({ error: 'Token inválido' });
    }

    try {
      const decoded = fastify.jwt.verify<{ id: string; type: string }>(parse.data.refreshToken);

      if (decoded.type !== 'refresh') {
        return reply.status(401).send({ error: 'Token inválido' });
      }

      const { data: user } = await supabase
        .from('users')
        .select('id, email, username')
        .eq('id', decoded.id)
        .single();

      if (!user) {
        return reply.status(401).send({ error: 'Usuário não encontrado' });
      }

      const accessToken = fastify.jwt.sign(
        { id: user.id, email: user.email, username: user.username },
        { expiresIn: process.env.JWT_EXPIRES_IN || '7d' }
      );

      return reply.send({ accessToken });
    } catch {
      return reply.status(401).send({ error: 'Token expirado ou inválido' });
    }
  });

  // ── Logout (invalidação no lado cliente) ───────────
  fastify.post('/logout', { preHandler: [fastify.authenticate] }, async (_request, reply) => {
    // JWT é stateless; o cliente deve descartar os tokens
    return reply.send({ message: 'Logout realizado com sucesso' });
  });
}
