╔══════════════════════════════════════════════════════════════╗
║               NOX AI v3.0 — Terminal Assistant               ║
║             by WR Programação / Neurocode                    ║
╚══════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  INSTALAÇÃO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Python 3.10+
   pip install -r requirements.txt

2. Para WhatsApp: instale Node.js 18+
   https://nodejs.org/en/download

3. Para músicas locais no Linux:
   sudo apt install mpg123
   (ou ffmpeg: sudo apt install ffmpeg)

4. Configure sua chave no .env:
   ANTHROPIC_API_KEY=sk-ant-...

5. Execute:
   python main.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  NOVIDADES v3.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🖥️  CONTROLE TOTAL DO NOTEBOOK
  /arquivo    → Criar, deletar, mover, copiar, ler arquivos
  /pasta      → Listar conteúdo de pastas
  /app        → Abrir qualquer aplicativo (chrome, vscode, spotify...)
  /volume     → Controlar volume do sistema (0-100%)
  /processo   → Listar e encerrar processos
  /sistema    → Info de CPU, RAM, disco e bateria
  /screenshot → Capturar tela e salvar
  /travar     → Bloquear a tela

🎵  MÚSICA
  /player     → Tocar arquivos de música locais (mp3, wav, flac...)
               Busca automaticamente na pasta ~/Music ou ~/Música
  /spotify    → Abrir Spotify ou pesquisar uma música
  /musica     → Playlists de foco no YouTube (anterior)

📱  WHATSAPP VIA QR CODE
  /wpp        → Conectar WhatsApp escaneando QR Code
  /wpp_enviar → Enviar mensagem para qualquer número
  /wpp_auto   → Ativar auto-resposta: a NOX responde toda mensagem
                recebida automaticamente usando IA!
  /wpp_status → Ver status da conexão

💬  LINGUAGEM NATURAL PARA O PC
  Você pode pedir à NOX diretamente:
  • "abre o chrome"
  • "abre o vscode"
  • "toca a música bohemian.mp3"
  • "volume para 70"
  • "muta o volume"
  • "deleta o arquivo teste.txt"
  • "cria uma pasta chamada projetos"
  • "screenshot"
  • "trava a tela"
  • "mostra os processos"
  • "info do sistema"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  FUNCIONALIDADES ANTERIORES (v2.9)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Voz (TTS/STT), Morse, Caesar, Base64, Senhas,
  Clima, Tradução, Calculadora, Pomodoro, Metas,
  Lembretes, Notas, Alias, Streak, Modo Noturno,
  Sistema de Ban, IMC, Conversor, Dados, Sorteio,
  Countdown, Tabelas de referência e muito mais.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ESTRUTURA DE ARQUIVOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  main.py            → Core da NOX
  system_control.py  → Controle do sistema (NOVO v3.0)
  whatsapp_bot.py    → Integração WhatsApp (NOVO v3.0)
  whatsapp_bridge.js → Bridge Node.js (gerado automaticamente)
  memory.py          → Sistema de memória
  config_manager.py  → Configurações
  ban_system.py      → Sistema de segurança
  .env               → Suas chaves API
  memory.json        → Memória persistente
  config.json        → Config salva

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SOBRE O WHATSAPP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  O WhatsApp usa a biblioteca whatsapp-web.js (Node.js).
  Na primeira vez que usar /wpp, o NOX vai instalar as
  dependências automaticamente (~60-90 segundos).

  Depois é só escanear o QR Code com o app do WhatsApp:
  WhatsApp → ⋮ Menu → Aparelhos conectados → Conectar aparelho

  A sessão fica salva em whatsapp_session/ e não precisa
  escanear de novo nas próximas vezes.

  AUTO-RESPOSTA: com /wpp_auto você pode deixar a NOX
  responder automaticamente qualquer mensagem recebida
  usando IA. Você pode personalizar a instrução da IA
  (ex: "responda sempre em inglês e de forma formal").
