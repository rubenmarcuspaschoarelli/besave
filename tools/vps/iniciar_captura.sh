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
#   3. (removido na BSV-56: o ID_OFERTA vem da sequence do banco; nao ha contador a conferir)
# E DEPOIS de subir:
#   4. o processo continua vivo e recebeu mesmo o run_captura.py na linha de comando
#
# O robo roda no scope `besave-whatsapp-robo` (systemd-run --user --scope) DENTRO do painel do tmux, com
# MemoryHigh/MemoryMax e KillSignal=SIGINT (BSV-54): o tmux poe o painel fora da unidade, entao o teto e o
# SIGINT so valem se forem do scope. Sobra do scope anterior -> recusa subir um 2o robo.
#
# Env (testes e instalacoes fora do padrao): BESAVE_CHAT_DIR, BESAVE_PY,
# BESAVE_PGREP, BESAVE_TMUX, BESAVE_DISPLAY, BESAVE_SESSAO, BESAVE_ESPERA,
# BESAVE_SYSTEMD_RUN, BESAVE_SYSTEMCTL, BESAVE_DATE, BESAVE_MEM_HIGH (3500M), BESAVE_MEM_MAX (4500M),
# BESAVE_MEM_SWAP_MAX (0: sem isso o MemoryMax vira thrashing no swap, nao reinicio).

set -u

AQUI=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
RAIZ=$(cd "${BESAVE_CHAT_DIR:-$AQUI/../capture-chat-groups}" && pwd -P)
PY=${BESAVE_PY:-$RAIZ/.venv/bin/python}
PGREP=${BESAVE_PGREP:-pgrep}
SESSAO=${BESAVE_SESSAO:-besave-whatsapp}
ESPERA=${BESAVE_ESPERA:-8}
SYSTEMD_RUN=${BESAVE_SYSTEMD_RUN:-systemd-run}
DATE_BIN=${BESAVE_DATE:-date}
SYSTEMCTL=${BESAVE_SYSTEMCTL:-systemctl}
SCOPE=besave-whatsapp-robo
MEM_HIGH=${BESAVE_MEM_HIGH:-3500M}
MEM_MAX=${BESAVE_MEM_MAX:-4500M}
MEM_SWAP_MAX=${BESAVE_MEM_SWAP_MAX:-0}

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

# --- 2b. sobra do scope do robo? ---------------------------------------------
if "$SYSTEMCTL" --user is-active --quiet "$SCOPE.scope" 2>/dev/null; then
    falhar "o scope $SCOPE.scope ainda existe (robo anterior vivo?): subir outro duplicaria o robo. Rode systemctl --user stop $SCOPE.scope."
fi

# Scope que terminou em `failed` (OOM-kill, kill -9) fica carregado e o proximo systemd-run com o mesmo
# --unit falha ("already loaded"). Com o scope NAO ativo (conferido acima), limpa o residuo e o que sobrou
# de `set-property --runtime`; erros ignorados (scope inexistente).
"$SYSTEMCTL" --user reset-failed "$SCOPE.scope" >/dev/null 2>&1 || true
"$SYSTEMCTL" --user revert "$SCOPE.scope" >/dev/null 2>&1 || true

# --- 4. nome do log (nao reaproveita arquivo de run anterior) ----------------
mkdir -p "$RAIZ/log"
# run_captura_DD_MM_HHMMSS.log; se existir (2 partidas no mesmo segundo), _2, _3... sem limite: o nome do log
# nunca impede a partida (um limite de 8 por dia, com Restart a cada 30 s, escondeu a causa real em 05/11).
base="$RAIZ/log/run_captura_$("$DATE_BIN" '+%d_%m_%H%M%S')"
log="$base.log"
n=2
while [ -e "$log" ]; do
    log="${base}_$n.log"
    n=$((n + 1))
done

# --- 5. lancar ---------------------------------------------------------------
echo
echo "Lancando... log: $(basename "$log")"
# o WhatsApp tem a tela :2 (a :1 e do robo das lojas)
# --collect: o scope e descarregado ao terminar, mesmo em `failed`; sem isso o 1o OOM-kill deixaria todo
# systemd-run seguinte falhando com "already loaded", em laco.
# O rc do systemd-run --scope e o do proprio robo (ele vira o processo do scope): OOM-kill = rc != 0.
if command -v "$SYSTEMD_RUN" >/dev/null 2>&1; then
    cmd=("$SYSTEMD_RUN" --user --scope --collect "--unit=$SCOPE" -p "MemoryHigh=$MEM_HIGH" -p "MemoryMax=$MEM_MAX" \
        -p "MemorySwapMax=$MEM_SWAP_MAX" -p KillSignal=SIGINT -p TimeoutStopSec=30 -- "$PY" -u run_captura.py)
else
    echo "AVISO: systemd-run nao encontrado; subindo SEM teto de memoria e sem scope." >&2
    cmd=("$PY" -u run_captura.py)
fi
BESAVE_DISPLAY=${BESAVE_DISPLAY:-:2} "$AQUI/rodar_em_tmux.sh" iniciar "$SESSAO" "$RAIZ" "$log" "${cmd[@]}" ||
    falhar "nao consegui criar a sessao tmux $SESSAO."

# --- 6. conferir que subiu DE VERDADE ----------------------------------------
sleep "$ESPERA"
vivos=$(pids "$PADRAO_RUN")
if [ -z "$vivos" ]; then
    echo "O processo MORREU nos primeiros ${ESPERA}s. Ultimas linhas do log:" >&2
    tail -n 20 "$log" 2>/dev/null >&2
    ultima=$(grep -v '^[[:space:]]*$' "$log" 2>/dev/null | tail -n 1 | cut -c1-300)
    falhar "captura nao subiu${ultima:+ (ultima linha do log: $ultima)}."
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
