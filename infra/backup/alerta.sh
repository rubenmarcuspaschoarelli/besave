#!/usr/bin/env bash
# Rede de segurança do OnFailure= (BSV-49): avisa quando a unidade morreu sem o script ter alertado
# (timeout, kill, erro antes do primeiro alerta). Se o script já avisou há pouco, não repete.
# Uso: alerta.sh diario|teste|resumo
set -uo pipefail

AQUI=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
. "$AQUI/lib.sh"
MODO=${1:-}
case $MODO in
  diario | teste | resumo) ;;
  *) echo "uso: alerta.sh diario|teste|resumo" >&2; exit 2 ;;
esac
carregar_env

if [ -n "$(find "$ESTADO/alertado-$MODO" -mmin -10 2> /dev/null)" ]; then
  log "script já alertou; nada a fazer"
  exit 0
fi
alertar "Backup ($MODO): a unidade besave-backup-$MODO falhou sem aviso do script (timeout ou processo morto). Ver: journalctl -u besave-backup-$MODO"
