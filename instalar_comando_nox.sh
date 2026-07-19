#!/usr/bin/env bash
# ============================================================
# instalar_comando_nox.sh — Instala o comando "nox" no Linux/Mac
# Depois de rodar este script uma vez, basta digitar "nox" em
# qualquer terminal para abrir o projeto e ativar a IA.
# ============================================================

set -e

NOX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
LAUNCHER="$BIN_DIR/nox"

mkdir -p "$BIN_DIR"

cat > "$LAUNCHER" << EOF
#!/usr/bin/env bash
cd "$NOX_DIR"
python3 main.py
EOF

chmod +x "$LAUNCHER"

echo "=========================================================="
echo "  Comando 'nox' instalado em: $LAUNCHER"
echo "=========================================================="
echo

# Garante que ~/.local/bin esteja no PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    SHELL_RC="$HOME/.bashrc"
    [[ "$SHELL" == *zsh* ]] && SHELL_RC="$HOME/.zshrc"
    echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$SHELL_RC"
    echo "Adicionado \$HOME/.local/bin ao PATH em $SHELL_RC"
    echo "Rode: source $SHELL_RC   (ou abra um novo terminal)"
else
    echo "\$HOME/.local/bin já está no PATH. Tudo certo."
fi

echo
echo "A partir de agora, digite 'nox' em qualquer terminal"
echo "para abrir o projeto com a IA já ativa."
