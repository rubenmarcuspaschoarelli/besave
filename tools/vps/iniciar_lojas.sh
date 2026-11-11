#!/usr/bin/env bash
# Lancador da captura das lojas (capture-store-pages --monitorar) no Linux (BSV-57).
#
# Uso:  iniciar_lojas.sh [--aguardar]
#   sem flag    : sobe numa sessao tmux e volta
#   --aguardar  : idem, e fica ate o robo sair (devolve o codigo dele; e o que a unidade systemd usa)
#
# O robo roda no scope `besave-lojas-robo` (systemd-run --user --scope) DENTRO do painel do tmux, igual ao
# WhatsApp: o tmux poe o painel fora da unidade, entao o KillSignal=SIGINT da unidade nao chegava ao python e um
# python congelado (kill -STOP) sobrevivia ao `restart`, segurando o perfil do Chromium. Parar o scope manda
# SIGINT e, vencido o prazo, SIGKILL (que tambem mata processo parado). Scope ativo na partida -> recusa subir.
# Sem teto de memoria por ora (o Chromium das lojas nao cresce; reavaliar com medicao).
#
# Env (testes e instalacoes fora do padrao): BESAVE_LOJAS_DIR, BESAVE_PY, BESAVE_TMUX, BESAVE_DISPLAY,
# BESAVE_SESSAO, BESAVE_SYSTEMD_RUN, BESAVE_SYSTEMCTL.

set -u

AQUI=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
RAIZ=$(cd "${BESAVE_LOJAS_DIR:-$AQUI/../capture-store-pages}" && pwd -P)
PY=${BESAVE_PY:-$RAIZ/.venv/bin/python}
SESSAO=${BESAVE_SESSAO:-besave-lojas}
# SYSTEMD_RUN e SYSTEMCTL sao lidas pelo scope.sh (carregado com `.` mais abaixo)
# shellcheck disable=SC2034
SYSTEMD_RUN=${BESAVE_SYSTEMD_RUN:-systemd-run}
# shellcheck disable=SC2034
SYSTEMCTL=${BESAVE_SYSTEMCTL:-systemctl}
SCOPE=besave-lojas-robo
LOG="$RAIZ/destino/log/main_monitorar.log"

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

scope_preparar "$SCOPE"
scope_montar "$SCOPE" -- "$PY" -u main.py --monitorar --sem-perguntas

mkdir -p "$(dirname "$LOG")"
BESAVE_DISPLAY=${BESAVE_DISPLAY:-:1} "$AQUI/rodar_em_tmux.sh" iniciar "$SESSAO" "$RAIZ" "$LOG" "${CMD[@]}" ||
    falhar "nao consegui criar a sessao tmux $SESSAO."

echo "OK - captura das lojas lancada no scope $SCOPE (tela: tmux -L $SESSAO attach; log: $LOG)."

if [ "$aguardar" -eq 1 ]; then
    exec "$AQUI/rodar_em_tmux.sh" esperar "$SESSAO"
fi
