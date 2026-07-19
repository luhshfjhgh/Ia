# NOX AI — API Server

**WR Programação & Neurocode Web Systems**  
© 2026 — Todos os direitos reservados

## Visão Geral

API Server do NOX AI construído com Fastify + TypeScript.  
Porta padrão: **8080**  
Compatível com ngrok para expor publicamente.

---

## Configuração Rápida

### 1. Instalar dependências

```bash
cd nox_api_server
npm install
```

### 2. Configurar .env

Edite o arquivo `.env` com suas credenciais:

| Variável | Descrição |
|---|---|
| `PORT` | Porta (padrão: 8080) |
| `JWT_SECRET` | Chave secreta JWT (mínimo 32 chars) |
| `SUPABASE_URL` | URL do seu projeto Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | Service Role Key do Supabase |
| `EMAILJS_SERVICE_ID` | ID do serviço EmailJS |
| `EMAILJS_TEMPLATE_VERIFY` | Template de verificação de conta |
| `EMAILJS_TEMPLATE_RESET` | Template de reset de senha |
| `EMAILJS_PUBLIC_KEY` | Chave pública EmailJS |
| `EMAILJS_PRIVATE_KEY` | Chave privada EmailJS |
| `GROQ_API_KEY` | Chave API Groq (IA padrão) |
| `AI_PROVIDER` | Provedor ativo: groq, openai, gemini, openrouter |

### 3. Configurar banco de dados

Execute o SQL em `database/schema.sql` no **SQL Editor** do seu projeto Supabase.

### 4. Iniciar servidor

```bash
# Desenvolvimento
npm run dev

# Produção
npm run build
npm start
```

### 5. Expor com ngrok

```bash
ngrok http 8080
```

Copie a URL pública (ex: `https://xxxx.ngrok.io`) e configure no app como `API_URL`.

---

## Endpoints

### Auth (`/api/auth`)
- `POST /register` — Cadastro
- `POST /login` — Login
- `POST /verify` — Verificar conta com código
- `POST /resend-verification` — Reenviar código
- `POST /forgot-password` — Esqueci senha
- `POST /reset-password` — Redefinir senha
- `POST /refresh` — Renovar token
- `POST /logout` — Logout

### Chat (`/api/chat`)
- `POST /message` — Enviar mensagem para IA
- `GET /conversations` — Listar conversas
- `GET /conversations/:id/messages` — Mensagens de conversa
- `PATCH /conversations/:id` — Renomear conversa
- `PATCH /conversations/:id/favorite` — Favoritar
- `DELETE /conversations/:id` — Deletar conversa
- `GET /ws` — WebSocket para chat em tempo real

### Perfil (`/api/profile`)
- `GET /me` — Dados do usuário
- `PUT /me` — Atualizar perfil
- `POST /change-password` — Alterar senha
- `DELETE /me` — Excluir conta

### Histórico (`/api/history`)
- `GET /` — Listar histórico (com busca `?q=termo`)
- `GET /favorites` — Favoritos
- `DELETE /clear` — Limpar tudo

### Upload (`/api/upload`)
- `POST /file` — Upload de arquivo

### Voz (`/api/voice`)
- `POST /transcribe` — Transcrever áudio (Whisper/Groq)

### Configurações (`/api/settings`)
- `GET /` — Buscar configurações
- `PUT /` — Salvar configurações

### Atualização (`/api/update`)
- `GET /check` — Verificar nova versão no GitHub

### Health
- `GET /health` — Status do servidor

---

## EmailJS — Configuração

1. Crie conta em https://www.emailjs.com/
2. Crie um **Service** (Gmail, Outlook, etc.)
3. Crie dois **Templates**:
   - **Verificação de conta**: variáveis `{{to_name}}`, `{{to_email}}`, `{{verification_code}}`
   - **Reset de senha**: variáveis `{{to_name}}`, `{{to_email}}`, `{{reset_code}}`
4. Copie os IDs para o `.env`

---

## Supabase — Configuração

1. Crie projeto em https://supabase.com/
2. Vá em **SQL Editor** e execute `database/schema.sql`
3. Copie `Project URL` e `service_role key` para o `.env`

> ⚠️ Use sempre a **service_role key** no backend — ela bypassa o RLS e é necessária para operações administrativas.
