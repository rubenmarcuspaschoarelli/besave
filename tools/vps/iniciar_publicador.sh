#!/usr/bin/env bash
# Lancador do publicador do canal do WhatsApp (publish-whatsapp-channel, BSV-63) na inst2.
#
# Uso:  iniciar_publicador.sh [--aguardar]
#   sem flag    : sobe numa sessao tmux e volta
#   --aguardar  : idem, e fica ate o publicador sair (devolve o codigo dele; e o que a unidade systemd usa)
#
# Mesmo padrao dos robos (BSV-54, BSV-57): o python roda no scope `besave-publicador-robo` (systemd-run --user
# --scope) DENTRO do painel do tmux, com teto de memoria e KillSignal=SIGINT. Scope ativo na partida -> recusa
# subir (dois publicadores = post repetido). Um log por partida: log/run_publicador_DD_MM_HHMMSS.log (o vigia le
# o mais recente).
#
# Env (testes e instalacoes fora do padrao): BESAVE_PUB_DIR, BESAVE_PY, BESAVE_TMUX, BESAVE_DISPLAY,
# BESAVE_SESSAO, BESAVE_SYSTEMD_RUN, BESAVE_SYSTEMCTL, BESAVE_DATE, BESAVE_MEM_HIGH (1500M), BESAVE_MEM_MAX
# (2000M), BESAVE_MEM_SWAP_MAX (0).

set -u

AQUI=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
RAIZ=$(cd "${BESAVE_PUB_DIR:-$AQUI/../publish-whatsapp-channel}" && pwd -P)
PY=${BESAVE_PY:-$RAIZ/.venv/bin/python}
SESSAO=${BESAVE_SESSAO:-besave-publicador}
# SYSTEMD_RUN e SYSTEMCTL sao lidas pelo scope.sh (carregado com `.` mais abaixo)
# shellcheck disable=SC2034
SYSTEMD_RUN=${BESAVE_SYSTEMD_RUN:-systemd-run}
# shellcheck disable=SC2034
SYSTEMCTL=${BESAVE_SYSTEMCTL:-systemctl}
DATE_BIN=${BESAVE_DATE:-date}
SCOPE=besave-publicador-robo
MEM_HIGH=${BESAVE_MEM_HIGH:-1500M}
MEM_MAX=${BESAVE_MEM_MAX:-2000M}
MEM_SWAP_MAX=${BESAVE_MEM_SWAP_MAX:-0}

falhar() {
    echo
    echo "ABORTADO: $1" >&2
    exit 1
}

# shellcheck source=/dev/null
. "$AQUI/scope.sh"

aguardar=0
[ "${1:-}" = "--aguardar" ] && aguardar=1

[ -x "$PY" ] || falhar "python do venv nao encontrado em $PY"
[ -f "$RAIZ/conf/config.json" ] || falhar "sem $RAIZ/conf/config.json (copie conf/config.example.json, modo 600)"

scope_preparar "$SCOPE"

mkdir -p "$RAIZ/log"
base="$RAIZ/log/run_publicador_$("$DATE_BIN" '+%d_%m_%H%M%S')"
log="$base.log"
n=2
while [ -e "$log" ]; do
    log="${base}_$n.log"
    n=$((n + 1))
done

scope_montar "$SCOPE" -p "MemoryHigh=$MEM_HIGH" -p "MemoryMax=$MEM_MAX" -p "MemorySwapMax=$MEM_SWAP_MAX" -- \
    "$PY" -u main.py
BESAVE_DISPLAY=${BESAVE_DISPLAY:-:1} "$AQUI/rodar_em_tmux.sh" iniciar "$SESSAO" "$RAIZ" "$log" "${CMD[@]}" ||
    falhar "nao consegui criar a sessao tmux $SESSAO."

echo "OK - publicador lancado no scope $SCOPE (tela: tmux -L $SESSAO attach; log: $log)."

if [ "$aguardar" -eq 1 ]; then
    exec "$AQUI/rodar_em_tmux.sh" esperar "$SESSAO"
fi
