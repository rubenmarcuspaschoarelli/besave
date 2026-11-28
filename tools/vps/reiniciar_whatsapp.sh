#!/usr/bin/env bash
# Reinicio diario do robo do WhatsApp (BSV-54). Chamado por
# besave-reinicio-whatsapp.service (timer a cada 6 h: 05:30, 11:30, 17:30, 23:30).
#
# O Chromium do WhatsApp Web cresce ~2,2 GB/dia; reiniciar a unidade devolve a memoria.
#   1. unidade parada de proposito (inactive, sem falha) -> so registra e sai
#   2. registra o RSS do maior processo do perfil user_data
#   3. systemctl --user stop (o ExecStop da unidade para o scope do robo com SIGINT; o `finally`
#      grava os marcadores; o ID_OFERTA vem da sequence do banco desde a BSV-56), copia da sessao boa
#      (BSV-67) e systemctl --user start
#   4. espera ate BESAVE_ESPERA_MAX s, contados do start: unidade `active` E log novo com "Grupo aberto"
#      (a unica marca de partida: so sai depois do login/QR, com o rodizio de pe)
#   5. nao confirmou -> aviso no Telegram com o motivo; confirmou -> so log
# Nunca mata processo por nome: so `systemctl stop`/`start`.
#
# Copia da sessao (BSV-67): so com a unidade parada e so se o log da partida parada tem "Grupo aberto"
# (sessao sabidamente boa). user_data/ sem os caches vai para user_data.copia.nova/ e troca por `mv`
# (copia pela metade nunca vira a valida). Falha da copia avisa e a unidade parte mesmo assim. O robo
# restaura essa copia sozinho quando cai na tela de login (wa/sessao.py).
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
PADRAO_OK='Grupo aberto'
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

# --- 3. parar, copiar a sessao boa, partir -----------------------------------
# glob expandido pelo proprio shell (nao por `ls`): um log por partida pode somar milhares sem estourar ARG_MAX
logs_antes=$(for f in "$RAIZ"/log/run_captura_*.log; do [ -e "$f" ] && printf '%s\n' "$f"; done)
log_parado=""          # log da partida que vai ser parada: o de maior mtime
for f in "$RAIZ"/log/run_captura_*.log; do
    [ -e "$f" ] || continue
    if [ -z "$log_parado" ] || [ "$f" -nt "$log_parado" ]; then log_parado=$f; fi
done

# caches que o Chromium refaz sozinho e as travas de execucao; o resto (~260 MB) e a sessao
EXCLUIR=(--exclude=./Default/Cache "--exclude=./Default/Code Cache" --exclude=./Default/GPUCache
         --exclude=./GPUPersistentCache "--exclude=./Default/Service Worker/CacheStorage"
         --exclude=./SingletonLock --exclude=./SingletonCookie --exclude=./SingletonSocket
         --exclude=./copiada_em --exclude=./restaurada_em)

falha_copia() {
    rm -rf "$RAIZ/user_data.copia.nova"
    avisar "a copia da sessao falhou ($1; a anterior continua valendo); a captura parte mesmo assim."
}

copiar_sessao() {
    local perfil="$RAIZ/user_data" nova="$RAIZ/user_data.copia.nova" copia="$RAIZ/user_data.copia"
    local velha="$RAIZ/user_data.copia.velha" t0=$SECONDS mb
    if [ -z "$log_parado" ] || ! grep -qF -- "$PADRAO_OK" "$log_parado" 2>/dev/null; then
        registrar "copia da sessao: pulada (a partida parada nao chegou a '$PADRAO_OK')."
        return 0
    fi
    rm -rf "$nova" "$velha"
    if ! { [ -d "$perfil" ] && mkdir -p "$nova" &&
           (set -o pipefail; tar -C "$perfil" --anchored "${EXCLUIR[@]}" -cf - . | tar -C "$nova" -xf -) &&
           date -u '+%Y-%m-%dT%H:%M:%SZ' > "$nova/copiada_em"; }; then
        falha_copia "leitura do perfil"
        return 1
    fi
    if [ -e "$copia" ] && ! mv "$copia" "$velha"; then
        falha_copia "troca"
        return 1
    fi
    if ! mv "$nova" "$copia"; then
        [ -e "$velha" ] && mv "$velha" "$copia"
        falha_copia "troca"
        return 1
    fi
    rm -rf "$velha"
    mb=$(du -sm "$copia" 2>/dev/null | cut -f1)
    registrar "copia da sessao: ${mb:-?} MB em $((SECONDS - t0)) s"
}

inicio=$(date '+%Y-%m-%d %H:%M:%S')
registrar "parando $UNIDADE (estado antes: ${antes:-desconhecido})"
if "$SYSTEMCTL" --user stop "$UNIDADE"; then
    copiar_sessao
else
    # sem a certeza de que o Chromium parou, a copia nao le o perfil (pode estar em uso)
    avisar "o stop de $UNIDADE falhou (estado: $(estado)); sem copia da sessao."
fi
registrar "partindo $UNIDADE"
if ! "$SYSTEMCTL" --user start "$UNIDADE"; then
    avisar "o start de $UNIDADE falhou (estado: $(estado))."
    exit 1
fi

# --- 4. confirmar ------------------------------------------------------------
novos_logs() {
    local f
    for f in "$RAIZ"/log/run_captura_*.log; do
        [ -e "$f" ] || continue
        # linha inteira: run_captura_X.log nao pode "casar" dentro de run_captura_X_2.log
        grep -qxF -- "$f" <<<"$logs_antes" && continue
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
    if [ "$est" = "active" ] && grep -Eq "$PADRAO_OK" <<<"$texto"; then
        registrar "OK: $UNIDADE active e captura retomada."
        exit 0
    fi
    [ "$decorrido" -ge "$ESPERA_MAX" ] && break
    sleep "$INTERVALO"
    decorrido=$((decorrido + INTERVALO))
done

# --- 5. nao confirmou --------------------------------------------------------
aborto=$(grep -E 'ABORTADO' <<<"$texto" | tail -n 1 | cut -c1-200)
if [ -n "$aborto" ]; then
    motivo="$aborto"
elif [ "$est" != "active" ]; then
    motivo="a unidade nao subiu em ${ESPERA_MAX}s (estado: ${est:-desconhecido})."
else
    motivo="unidade active, mas sem 'Grupo aberto' no log em ${ESPERA_MAX}s (pode estar pedindo QR/login: veja a tela VNC :2)."
fi
avisar "nao confirmei a retomada. $motivo"
exit 1
