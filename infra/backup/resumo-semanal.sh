#!/usr/bin/env bash
# Resumo semanal curto no Telegram (BSV-49): quantos dos últimos 7 dias tiveram backup ok e o tamanho do último.
set -uo pipefail

AQUI=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
. "$AQUI/lib.sh"
MODO=resumo
carregar_env
exigir TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID

HOJE=${BACKUP_DIA:-$(date +%Y%m%d)}
INICIO=$(date -d "$HOJE -6 days" +%Y%m%d) || exit 2
HIST="$ESTADO/historico.log"
mkdir -p "$ESTADO"
rm -f "$ESTADO/alertado-$MODO"

# Última linha de cada dia da janela; "ok" conta, "falha" não.
RESUMO=$(awk -v ini="$INICIO" -v fim="$HOJE" '
  $1 >= ini && $1 <= fim { est[$1] = $2; tam[$1] = $3 }
  END {
    for (d in est) if (est[d] == "ok") { ok++; if (d > ult) { ult = d; mb = tam[d] / 1048576 } }
    printf "%d %s %.0f\n", ok, (ult == "" ? "-" : ult), mb
  }' "$HIST" 2> /dev/null)
[ -n "$RESUMO" ] || RESUMO="0 - 0"
read -r OK ULT MB <<< "$RESUMO"

TESTE="nunca rodou"
if [ -r "$ESTADO/ultimo-teste.txt" ]; then
  read -r d s _ < "$ESTADO/ultimo-teste.txt"
  TESTE="$d $s"
fi

alertar "Backup do banco: $OK/7 ok na semana, último $ULT com $MB MB. Teste de restauração: $TESTE." || falhar "$MODO" "enviar o resumo"
