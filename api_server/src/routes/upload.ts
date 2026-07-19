import { FastifyInstance } from 'fastify';
import path from 'path';
import fs from 'fs/promises';
import { v4 as uuidv4 } from 'uuid';

const ALLOWED_TYPES = [
  'application/pdf',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain',
  'text/csv',
  'application/json',
  'image/png',
  'image/jpeg',
  'image/webp',
  'audio/mpeg',
  'audio/wav',
  'video/mp4',
  'application/zip',
  'application/x-rar-compressed',
];

export async function uploadRoutes(fastify: FastifyInstance) {
  const uploadDir = process.env.UPLOAD_DIR || './uploads';
  await fs.mkdir(uploadDir, { recursive: true });

  fastify.post('/file', { preHandler: [fastify.authenticate] }, async (request, reply) => {
    const data = await request.file();

    if (!data) {
      return reply.status(400).send({ error: 'Nenhum arquivo enviado' });
    }

    if (!ALLOWED_TYPES.includes(data.mimetype)) {
      return reply.status(400).send({ error: 'Tipo de arquivo não permitido' });
    }

    const ext = path.extname(data.filename);
    const filename = `${uuidv4()}${ext}`;
    const filepath = path.join(uploadDir, filename);

    const buffer = await data.toBuffer();
    await fs.writeFile(filepath, buffer);

    const fileUrl = `${process.env.API_BASE_URL}/uploads/${filename}`;

    return reply.send({
      url: fileUrl,
      filename: data.filename,
      mimetype: data.mimetype,
      size: buffer.length,
    });
  });
}
