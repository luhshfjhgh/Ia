// Serviço de IA — suporta múltiplos provedores
// Provedor ativo configurado via AI_PROVIDER no .env

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface AIResponse {
  content: string;
  model: string;
  provider: string;
  tokens?: number;
}

async function callGroq(messages: ChatMessage[]): Promise<AIResponse> {
  const apiKey = process.env.GROQ_API_KEY!;
  const model = process.env.GROQ_MODEL || 'openai/gpt-oss-120b';
  const url = `${process.env.GROQ_API_URL || 'https://api.groq.com/openai/v1'}/chat/completions`;

  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model,
      messages,
      max_tokens: parseInt(process.env.AI_MAX_TOKENS || '2048', 10),
      temperature: parseFloat(process.env.AI_TEMPERATURE || '0.85'),
    }),
  });

  if (!res.ok) throw new Error(`Groq error: ${res.status} ${await res.text()}`);
  const data = await res.json() as any;
  return {
    content: data.choices[0].message.content,
    model,
    provider: 'groq',
    tokens: data.usage?.total_tokens,
  };
}

async function callOpenAI(messages: ChatMessage[]): Promise<AIResponse> {
  const apiKey = process.env.OPENAI_API_KEY!;
  const model = process.env.OPENAI_MODEL || 'gpt-4o-mini';

  const res = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model,
      messages,
      max_tokens: parseInt(process.env.AI_MAX_TOKENS || '2048', 10),
      temperature: parseFloat(process.env.AI_TEMPERATURE || '0.85'),
    }),
  });

  if (!res.ok) throw new Error(`OpenAI error: ${res.status} ${await res.text()}`);
  const data = await res.json() as any;
  return {
    content: data.choices[0].message.content,
    model,
    provider: 'openai',
    tokens: data.usage?.total_tokens,
  };
}

async function callGemini(messages: ChatMessage[]): Promise<AIResponse> {
  const apiKey = process.env.GEMINI_API_KEY!;
  const model = 'gemini-1.5-flash';

  const contents = messages
    .filter((m) => m.role !== 'system')
    .map((m) => ({
      role: m.role === 'user' ? 'user' : 'model',
      parts: [{ text: m.content }],
    }));

  const systemInstruction = messages.find((m) => m.role === 'system');

  const res = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contents,
        ...(systemInstruction && {
          systemInstruction: { parts: [{ text: systemInstruction.content }] },
        }),
        generationConfig: {
          maxOutputTokens: parseInt(process.env.AI_MAX_TOKENS || '2048', 10),
          temperature: parseFloat(process.env.AI_TEMPERATURE || '0.85'),
        },
      }),
    }
  );

  if (!res.ok) throw new Error(`Gemini error: ${res.status} ${await res.text()}`);
  const data = await res.json() as any;
  return {
    content: data.candidates[0].content.parts[0].text,
    model,
    provider: 'gemini',
  };
}

async function callOpenRouter(messages: ChatMessage[]): Promise<AIResponse> {
  const apiKey = process.env.OPENROUTER_API_KEY!;
  const model = 'meta-llama/llama-3.1-8b-instruct:free';

  const res = await fetch('https://openrouter.ai/api/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
      'HTTP-Referer': process.env.API_BASE_URL || 'http://localhost:8080',
      'X-Title': 'NOX AI',
    },
    body: JSON.stringify({
      model,
      messages,
      max_tokens: parseInt(process.env.AI_MAX_TOKENS || '2048', 10),
    }),
  });

  if (!res.ok) throw new Error(`OpenRouter error: ${res.status} ${await res.text()}`);
  const data = await res.json() as any;
  return {
    content: data.choices[0].message.content,
    model,
    provider: 'openrouter',
    tokens: data.usage?.total_tokens,
  };
}

export async function generateAIResponse(
  messages: ChatMessage[],
  providerOverride?: string
): Promise<AIResponse> {
  const provider = providerOverride || process.env.AI_PROVIDER || 'groq';

  const systemPrompt: ChatMessage = {
    role: 'system',
    content:
      'Você é NOX AI, um assistente de inteligência artificial avançado criado pela WR Programação e Neurocode Web Systems. Você é inteligente, prestativo, preciso e fala português brasileiro por padrão. Responda sempre de forma clara e útil.',
  };

  const fullMessages = [systemPrompt, ...messages];

  switch (provider) {
    case 'openai':
      return callOpenAI(fullMessages);
    case 'gemini':
      return callGemini(fullMessages);
    case 'openrouter':
      return callOpenRouter(fullMessages);
    case 'groq':
    default:
      return callGroq(fullMessages);
  }
}
