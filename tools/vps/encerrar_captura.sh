#!/usr/bin/env bash
# Encerra a captura do WhatsApp e libera o perfil do navegador (equivalente do
# encerrar_captura.ps1).
#
# Cuidados:
#   - filtra por 'run_captura.py' e pelo --user-data-dir do projeto.
#     NUNCA matar todo python: o capture-store-pages roda na mesma maquina.
#   - SIGTERM primeiro (o `finally` da captura salva o contador); SIGKILL so no
#     que sobrar depois de BESAVE_GRACA segundos.
#   - se a unidade systemd estiver ativa, ela e parada antes; senao o
#     Restart=on-failure subiria o robo de novo.
#
# Env: BESAVE_CHAT_DIR, BESAVE_PGREP, BESAVE_KILL, BESAVE_TMUX, BESAVE_SESSAO,
#      BESAVE_UNIDADE, BESAVE_GRACA.

set -u

AQUI=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
RAIZ=$(cd "${BESAVE_CHAT_DIR:-$AQUI/../capture-chat-groups}" && pwd -P)
PGREP=${BESAVE_PGREP:-pgrep}
KILL=${BESAVE_KILL:-kill}
TMUX_BIN=${BESAVE_TMUX:-tmux}
SESSAO=${BESAVE_SESSAO:-besave-whatsapp}
UNIDADE=${BESAVE_UNIDADE:-besave-captura-whatsapp.service}
GRACA=${BESAVE_GRACA:-10}

PADRAO_RUN='^[^ ]*python[0-9.]* -u run_captura\.py$'
PADRAO_PERFIL="--user-data-dir=$RAIZ/user_data"

pids() { "$PGREP" -f -- "$1" 2>/dev/null || true; }
contar() {
    if [ -z "$1" ]; then echo 0; else echo "$1" | wc -l | tr -d ' '; fi
}

if command -v systemctl >/dev/null 2>&1; then
    systemctl --user stop "$UNIDADE" 2>/dev/null || true
fi

pythons=$(pids "$PADRAO_RUN")
chromes=$(pids "$PADRAO_PERFIL")

if [ -z "$pythons" ] && [ -z "$chromes" ]; then
    "$TMUX_BIN" kill-session -t "$SESSAO" 2>/dev/null || true
    echo "Nada rodando - nenhum run_captura.py, nenhum navegador do perfil."
    exit 0
fi

echo "Encerrando $(contar "$pythons") python (captura) e $(contar "$chromes") processo(s) do perfil..."
for p in $pythons; do
    echo "  python PID $p"
    "$KILL" -TERM "$p" 2>/dev/null || true
done

# espera o python sair (o finally salva o estado)
for _ in $(seq 1 "$GRACA"); do
    [ -z "$(pids "$PADRAO_RUN")" ] && break
    sleep 1
done
for p in $(pids "$PADRAO_RUN"); do "$KILL" -KILL "$p" 2>/dev/null || true; done

# o navegador pode ter ficado: ele trava o perfil
for p in $(pids "$PADRAO_PERFIL"); do "$KILL" -TERM "$p" 2>/dev/null || true; done
sleep 1
for p in $(pids "$PADRAO_PERFIL"); do "$KILL" -KILL "$p" 2>/dev/null || true; done

"$TMUX_BIN" kill-session -t "$SESSAO" 2>/dev/null || true
sleep 1

resta_py=$(contar "$(pids "$PADRAO_RUN")")
resta_ch=$(contar "$(pids "$PADRAO_PERFIL")")
echo
echo "Restantes: python=$resta_py  navegador=$resta_ch"
if [ "$resta_py" -eq 0 ] && [ "$resta_ch" -eq 0 ]; then
    echo "OK - perfil liberado."
    echo "Antes de relancar, o iniciar_captura.sh confere o contador sozinho."
else
    echo "ATENCAO: sobrou processo - confira antes de relancar." >&2
    exit 1
fi
