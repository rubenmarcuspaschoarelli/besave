#!/usr/bin/env bash
# Roda um robo dentro de uma sessao tmux (as telas de login pedem input(): o
# operador responde com `tmux attach -t SESSAO`) e espelha a saida num log.
#
# Uso:
#   rodar_em_tmux.sh iniciar  SESSAO DIRETORIO LOG CMD [ARGS...]   cria a sessao e volta
#   rodar_em_tmux.sh esperar  SESSAO                               bloqueia ate o robo sair
#                                                                  e sai com o codigo dele
#
# `esperar` e o que o systemd enxerga: se o robo cai com erro, a unidade falha
# e o Restart=on-failure sobe de novo.
#
# Env: BESAVE_TMUX (binario do tmux), BESAVE_DISPLAY (padrao :1),
#      XDG_RUNTIME_DIR ou /tmp (arquivo com o codigo de saida).

set -u

TMUX_BIN=${BESAVE_TMUX:-tmux}
DISPLAY_VNC=${BESAVE_DISPLAY:-:1}
ESTADO_DIR=${XDG_RUNTIME_DIR:-/tmp}

arquivo_estado() { echo "$ESTADO_DIR/besave-$1.rc"; }
canal() { echo "besave-$1"; }

modo=${1:-}
case "$modo" in
iniciar)
    [ $# -ge 5 ] || { echo "uso: $0 iniciar SESSAO DIRETORIO LOG CMD [ARGS...]" >&2; exit 2; }
    sessao=$2 dir=$3 log=$4
    shift 4
    rm -f "$(arquivo_estado "$sessao")"
    "$TMUX_BIN" kill-session -t "$sessao" 2>/dev/null || true
    mkdir -p "$(dirname "$log")"
    self=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")
    comando=$(printf '%q ' env "DISPLAY=$DISPLAY_VNC" "$self" interno "$sessao" "$log" "$@")
    "$TMUX_BIN" new-session -d -s "$sessao" -c "$dir" "$comando"
    ;;
interno)
    # roda DENTRO da sessao tmux
    sessao=$2 log=$3
    shift 3
    set -o pipefail
    "$@" 2>&1 | tee -a "$log"
    rc=${PIPESTATUS[0]}
    echo "$rc" >"$(arquivo_estado "$sessao")"
    "$TMUX_BIN" wait-for -S "$(canal "$sessao")"
    exit "$rc"
    ;;
esperar)
    [ $# -eq 2 ] || { echo "uso: $0 esperar SESSAO" >&2; exit 2; }
    sessao=$2
    "$TMUX_BIN" wait-for "$(canal "$sessao")"
    rc=$(cat "$(arquivo_estado "$sessao")" 2>/dev/null || echo 1)
    exit "${rc:-1}"
    ;;
*)
    echo "uso: $0 {iniciar|esperar} ..." >&2
    exit 2
    ;;
esac
