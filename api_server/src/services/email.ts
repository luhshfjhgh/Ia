async function sendEmail(templateId: string, payload: any): Promise<void> {
  const serviceId = process.env.EMAILJS_SERVICE_ID!;
  const publicKey = process.env.EMAILJS_PUBLIC_KEY!;
  const privateKey = process.env.EMAILJS_PRIVATE_KEY!;

  const body = {
    service_id: serviceId,
    template_id: templateId,
    user_id: publicKey,
    accessToken: privateKey,
    template_params: {
      to_name: payload.to_name,
      to_email: payload.to_email,
      email: payload.to_email,
      name: payload.to_name,
      verification_code: payload.code || '',
      reset_code: payload.code || '',
      code: payload.code || '',
    },
  };

  console.log('[EmailJS] Enviando para:', payload.to_email, '| template:', templateId);

  const response = await fetch('https://api.emailjs.com/api/v1.0/email/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  const responseText = await response.text();

  if (!response.ok) {
    console.error('[EmailJS] ERRO:', response.status, responseText);
    throw new Error(`EmailJS erro ${response.status}: ${responseText}`);
  }

  console.log('[EmailJS] Enviado com sucesso!');
}

export async function sendVerificationEmail(to_email: string, to_name: string, code: string): Promise<void> {
  const templateId = process.env.EMAILJS_TEMPLATE_VERIFY!;
  await sendEmail(templateId, { to_email, to_name, code });
}

export async function sendPasswordResetEmail(to_email: string, to_name: string, code: string): Promise<void> {
  const templateId = process.env.EMAILJS_TEMPLATE_RESET!;
  await sendEmail(templateId, { to_email, to_name, code });
}

export function generateCode(length = 6): string {
  const chars = '0123456789';
  let code = '';
  for (let i = 0; i < length; i++) {
    code += chars[Math.floor(Math.random() * chars.length)];
  }
  return code;
}