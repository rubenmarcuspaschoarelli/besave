#!/usr/bin/env bash
# Reinicio diario do robo do WhatsApp (BSV-54). Chamado por
# besave-reinicio-whatsapp.service (timer 05:30).
#
# O Chromium do WhatsApp Web cresce ~2,2 GB/dia; reiniciar a unidade devolve a memoria.
#   1. unidade parada de proposito (inactive, sem falha) -> so registra e sai
#   2. registra o RSS do maior processo do perfil user_data
#   3. systemctl --user restart (o ExecStop da unidade para o scope do robo com SIGINT; o `finally`
#      grava o contador)
#   4. espera ate BESAVE_ESPERA_MAX s: unidade `active` E log novo com
#      "Retomando contador" ou "Grupo aberto"
#   5. nao confirmou -> aviso no Telegram com o motivo; confirmou -> so log
# Nunca mata processo por nome: so `systemctl restart`.
#
# Env (testes e instalacoes fora do padrao): BESAVE_CHAT_DIR, BESAVE_SYSTEMCTL,
# BESAVE_JOURNALCTL, BESAVE_PS, BESAVE_PY, BESAVE_UNIDADE, BESAVE_ESPERA_MAX,
# BESAVE_INTERVALO.

set -u

AQUI=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
RAIZ=$(cd "${BESAVE_CHAT_DIR:-$AQUI/../capture-chat-groups}" && pwd -P)
SYSTEMCTL=${BESAVE_SYSTEMCTL:-systemctl}
JOURNALCTL=${BESAVE_JOURNALCTL:-journalctl}
PS_BIN=${BESAVE_PS:-ps}
PY=${BESAVE_PY:-$RAIZ/.venv/bin/python}
UNIDADE=${BESAVE_UNIDADE:-besave-captura-whatsapp.service}
ESPERA_MAX=${BESAVE_ESPERA_MAX:-180}
INTERVALO=${BESAVE_INTERVALO:-5}
PADRAO_OK='Retomando contador|Grupo aberto'
PERFIL="--user-data-dir=$RAIZ/user_data"

registrar() { echo "[reinicio] $(date '+%d/%m/%Y %H:%M:%S') $*"; }

avisar() {
    registrar "AVISO: $1"
    (cd "$RAIZ" && "$PY" -m wa.avisar "Reinicio diario do robo do WhatsApp: $1") || true
}

estado() { "$SYSTEMCTL" --user is-active "$UNIDADE" 2>/dev/null || true; }

# --- 1. parada de proposito? -------------------------------------------------
antes=$(estado)
if [ "$antes" = "inactive" ]; then
    registrar "$UNIDADE parada (inactive); nada a reiniciar."
    exit 0
fi

# --- 2. memoria do maior processo do perfil ----------------------------------
maior_kb=$("$PS_BIN" -eo rss=,args= 2>/dev/null | awk -v p="$PERFIL" 'index($0, p) && $1 + 0 > m { m = $1 + 0 } END { print m + 0 }')
registrar "RSS do maior processo do perfil antes de parar: $((maior_kb / 1024)) MB"

# --- 3. reiniciar ------------------------------------------------------------
# glob expandido pelo proprio shell (nao por `ls`): um log por partida pode somar milhares sem estourar ARG_MAX
logs_antes=$(for f in "$RAIZ"/log/run_captura_*.log; do [ -e "$f" ] && printf '%s\n' "$f"; done)
inicio=$(date '+%Y-%m-%d %H:%M:%S')
registrar "reiniciando $UNIDADE (estado antes: ${antes:-desconhecido})"
if ! "$SYSTEMCTL" --user restart "$UNIDADE"; then
    avisar "o restart de $UNIDADE falhou (estado: $(estado))."
    exit 1
fi

# --- 4. confirmar ------------------------------------------------------------
novos_logs() {
    local f
    for f in "$RAIZ"/log/run_captura_*.log; do
        [ -e "$f" ] || continue
        # linha inteira: run_captura_X.log nao pode "casar" dentro de run_captura_X_2.log
        printf '%s\n' "$logs_antes" | grep -qxF -- "$f" && continue
        echo "$f"
    done
}
texto_novo() { # log novo do robo + journal da unidade desde o restart (o ABORTADO sai no stderr do lancador)
    local f
    for f in $(novos_logs); do cat "$f" 2>/dev/null; done
    "$JOURNALCTL" --user -u "$UNIDADE" --since "$inicio" --no-pager 2>/dev/null || true
}

decorrido=0
while :; do
    est=$(estado)
    texto=$(texto_novo)
    if [ "$est" = "active" ] && printf '%s\n' "$texto" | grep -Eq "$PADRAO_OK"; then
        registrar "OK: $UNIDADE active e captura retomada."
        exit 0
    fi
    [ "$decorrido" -ge "$ESPERA_MAX" ] && break
    sleep "$INTERVALO"
    decorrido=$((decorrido + INTERVALO))
done

# --- 5. nao confirmou --------------------------------------------------------
aborto=$(printf '%s\n' "$texto" | grep -E 'ABORTADO' | tail -n 1 | cut -c1-200)
if [ -n "$aborto" ]; then
    motivo="$aborto"
elif [ "$est" != "active" ]; then
    motivo="a unidade nao subiu em ${ESPERA_MAX}s (estado: ${est:-desconhecido})."
else
    motivo="unidade active, mas sem 'Retomando contador' nem 'Grupo aberto' no log em ${ESPERA_MAX}s (pode estar pedindo QR/login: veja a tela VNC :2)."
fi
avisar "nao confirmei a retomada. $motivo"
exit 1
