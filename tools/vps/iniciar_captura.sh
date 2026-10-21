#!/usr/bin/env bash
# Lancador da captura do WhatsApp no Linux (equivalente do iniciar_captura.ps1).
#
# Uso:  iniciar_captura.sh [--aguardar]
#   sem flag    : confere, sobe numa sessao tmux e volta
#   --aguardar  : idem, e fica ate o robo sair (devolve o codigo dele; e o que a
#                 unidade systemd usa)
#
# Existe porque o lancamento a mao ja falhou 3x (14/07, 30/07, 04/08). Garante
# ANTES de subir:
#   1. nenhum run_captura.py vivo   (lancar o 2o MATA o 1o - armadilha de 03/08)
#   2. nenhum navegador segurando o perfil user_data
#   3. contador do config nao esta atrasado (senao REEMITE ID_OFERTA)
# E DEPOIS de subir:
#   4. o processo continua vivo e recebeu mesmo o run_captura.py na linha de comando
#
# Env (testes e instalacoes fora do padrao): BESAVE_CHAT_DIR, BESAVE_PY,
# BESAVE_PGREP, BESAVE_TMUX, BESAVE_DISPLAY, BESAVE_SESSAO, BESAVE_ESPERA.

set -u

AQUI=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
RAIZ=$(cd "${BESAVE_CHAT_DIR:-$AQUI/../capture-chat-groups}" && pwd -P)
PY=${BESAVE_PY:-$RAIZ/.venv/bin/python}
PGREP=${BESAVE_PGREP:-pgrep}
SESSAO=${BESAVE_SESSAO:-besave-whatsapp}
ESPERA=${BESAVE_ESPERA:-8}

# python (qualquer caminho) -u run_captura.py, e so isso: nao casa o wrapper
# bash nem a linha do tmux, que trazem o comando no meio.
PADRAO_RUN='^[^ ]*python[0-9.]* (-u )?run_captura\.py( |$)'
PADRAO_PERFIL="--user-data-dir=$RAIZ/user_data"

falhar() {
    echo
    echo "ABORTADO: $1" >&2
    exit 1
}

pids() { "$PGREP" -f -- "$1" 2>/dev/null || true; }

aguardar=0
[ "${1:-}" = "--aguardar" ] && aguardar=1

echo "=== Lancador da captura - $(date '+%d/%m/%Y %H:%M:%S') ==="

[ -x "$PY" ] || falhar "python do venv nao encontrado em $PY"

# --- 1. outro run vivo? ------------------------------------------------------
vivos=$(pids "$PADRAO_RUN")
if [ -n "$vivos" ]; then
    echo "Ja existe captura rodando:" >&2
    echo "  PID $(echo "$vivos" | tr '\n' ' ')" >&2
    falhar "lancar um 2o run MATA o browser do 1o e ele fica girando em falso. Encerre o atual primeiro."
fi

# --- 2. navegador segurando o perfil? ----------------------------------------
presos=$(pids "$PADRAO_PERFIL")
if [ -n "$presos" ]; then
    echo "Sobraram processos do perfil do projeto:" >&2
    echo "  PID $(echo "$presos" | tr '\n' ' ')" >&2
    falhar "o perfil user_data esta travado. Rode encerrar_captura.sh e tente de novo."
fi

# --- 3. contador atrasado? ---------------------------------------------------
echo
echo "--- conferindo o contador (config x CSV x Oracle) ---"
"$PY" "$RAIZ/diag/checa_contador.py" || falhar "contador atrasado - corrija o config (com backup) antes de relancar."

# --- 4. nome do log (nao reaproveita arquivo de run anterior) ----------------
mkdir -p "$RAIZ/log"
base="$RAIZ/log/run_captura_$(date '+%d_%m')"
log="$base.log"
for sufixo in b c d e f g h; do
    [ -e "$log" ] || break
    log="${base}_$sufixo.log"
done
[ -e "$log" ] && falhar "muitos logs para hoje - limpe os antigos."

# --- 5. lancar ---------------------------------------------------------------
echo
echo "Lancando... log: $(basename "$log")"
# o WhatsApp tem a tela :2 (a :1 e do robo das lojas)
BESAVE_DISPLAY=${BESAVE_DISPLAY:-:2} "$AQUI/rodar_em_tmux.sh" iniciar "$SESSAO" "$RAIZ" "$log" "$PY" -u run_captura.py ||
    falhar "nao consegui criar a sessao tmux $SESSAO."

# --- 6. conferir que subiu DE VERDADE ----------------------------------------
sleep "$ESPERA"
vivos=$(pids "$PADRAO_RUN")
if [ -z "$vivos" ]; then
    echo "O processo MORREU nos primeiros ${ESPERA}s. Ultimas linhas do log:" >&2
    tail -n 20 "$log" 2>/dev/null >&2
    falhar "captura nao subiu."
fi

echo
echo "OK - captura rodando."
echo "  PID    : $(echo "$vivos" | tr '\n' ' ')"
echo "  log    : $log"
echo "  tela   : tmux -L $SESSAO attach   (sair sem parar: Ctrl+b d)"
echo "  acompanhar: tail -f '$log'"
echo "  encerrar  : $AQUI/encerrar_captura.sh"

if [ "$aguardar" -eq 1 ]; then
    exec "$AQUI/rodar_em_tmux.sh" esperar "$SESSAO"
fi
