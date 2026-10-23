# shellcheck shell=bash
# Funções comuns do backup do banco (BSV-49). Carregado com `.` pelos scripts; não executa nada.

BACKUP_DIR=${BESAVE_BACKUP_DIR:-/srv/besave/backup}
ESTADO=${BESAVE_BACKUP_ESTADO:-$BACKUP_DIR/estado}

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

# Lê KEY=valor do backup.env sem `source` (senha com $ ou aspas não vira código). O ambiente vence o arquivo.
carregar_env() {
  local arq=${BESAVE_BACKUP_ENV:-$BACKUP_DIR/backup.env} k v
  [ -r "$arq" ] || return 0
  while IFS='=' read -r k v || [ -n "$k" ]; do
    case $k in '' | '#'*) continue ;; esac
    [ -n "${!k+x}" ] || export "$k=$v"
  done < "$arq"
}

exigir() {
  local n faltam=()
  for n in "$@"; do [ -n "${!n:-}" ] || faltam+=("$n"); done
  if [ ${#faltam[@]} -gt 0 ]; then
    echo "variáveis ausentes no backup.env: ${faltam[*]}" >&2
    exit 2
  fi
}

# Telegram. O token vai por stdin do curl (-K -): não aparece em `ps`.
alertar() {
  local texto="[${HOSTNAME:-$(hostname)}] $1"
  if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
    log "sem TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID; alerta perdido: $texto" >&2
    return 1
  fi
  printf 'url = "https://api.telegram.org/bot%s/sendMessage"\n' "$TELEGRAM_BOT_TOKEN" |
    curl -sS --fail --max-time 20 -K - \
      --data-urlencode "chat_id=$TELEGRAM_CHAT_ID" --data-urlencode "text=$texto" > /dev/null
}

# Etapa que falhou: alerta, marca que o aviso já saiu (o OnFailure= não repete) e encerra com 1.
falhar() { # modo etapa
  log "FALHA na etapa '$2'" >&2
  alertar "Backup ($1): falhou na etapa '$2'. Ver: journalctl -u besave-backup-$1" || true
  mkdir -p "$ESTADO"
  : > "$ESTADO/alertado-$1"
  if [ "$1" = diario ]; then
    printf '%s falha 0 0\n' "${DIA:-$(date +%Y%m%d)}" >> "$ESTADO/historico.log"
  fi
  exit 1
}

# Arquivo de parâmetros do Data Pump com a senha: só o dono lê, apagado pelo trap do chamador.
parfile() { # destino  linhas...
  local destino=$1
  shift
  (umask 077 && printf '%s\n' "$@" > "$destino")
}
