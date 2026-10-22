#!/usr/bin/env bash
# Backup diário do schema BESAVE (BSV-49): Data Pump → bucket da OCI → cópia no S3 → retenção na OCI.
# Idempotente: o log do dia no bucket é o marcador de "export feito"; no S3, de "cópia feita".
# Uso: backup-diario.sh   (variáveis em backup.env, ver backup.env.example)
set -uo pipefail

AQUI=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
. "$AQUI/lib.sh"
MODO=diario
carregar_env
exigir BACKUP_DB_USER BACKUP_DB_PASS BACKUP_DB_DSN BACKUP_OCI_URI BACKUP_OCI_BUCKET \
  BACKUP_OCI_CREDENCIAL BACKUP_S3_BUCKET TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID

DIA=${BACKUP_DIA:-$(date +%Y%m%d)}
[[ $DIA =~ ^[0-9]{8}$ ]] || { echo "BACKUP_DIA inválido: $DIA" >&2; exit 2; }
RETENCAO_DIAS=${BACKUP_RETENCAO_OCI_DIAS:-7}
PREFIXO="besave-$DIA"
MARCADOR="$PREFIXO.log"
OCI=(oci --auth instance_principal)
INICIO=$SECONDS

mkdir -p "$ESTADO"
rm -f "$ESTADO/alertado-$MODO"
exec 9> "$ESTADO/backup.lock"
flock -n 9 || { log "outra execução em andamento; nada a fazer"; exit 0; }

TMP=$(mktemp -d "${BACKUP_TMP:-$BACKUP_DIR/tmp}.XXXXXX") || falhar "$MODO" "pasta temporária"
trap 'rm -rf "$TMP"' EXIT

# Quantos objetos do bucket começam com o prefixo (falha se a OCI falhar).
oci_contar() {
  local n
  n=$("${OCI[@]}" os object list --bucket-name "$BACKUP_OCI_BUCKET" --prefix "$1" --all \
    --query 'length(data)' --raw-output) || return 1
  if [[ $n =~ ^[0-9]+$ ]]; then echo "$n"; else echo 0; fi
}

oci_nomes() {
  local json
  json=$("${OCI[@]}" os object list --bucket-name "$BACKUP_OCI_BUCKET" --prefix "$1" --all     --query 'data[].name' --output json) || return 1
  # Sem objetos não é erro: grep sai com 1 e o resultado é vazio.
  grep -o '"besave-[^"]*"' <<< "$json" | tr -d '"' || true
}

oci_apagar_prefixo() {
  local nome nomes
  nomes=$(oci_nomes "$1") || return 1
  while IFS= read -r nome; do
    [ -n "$nome" ] || continue
    "${OCI[@]}" os object delete --bucket-name "$BACKUP_OCI_BUCKET" --object-name "$nome" --force || return 1
  done <<< "$nomes"
}

etapa_export() {
  local n
  n=$(oci_contar "$MARCADOR") || return 1
  if [ "$n" -gt 0 ]; then
    log "export de $DIA já existe no bucket da OCI; pulando"
    return 0
  fi
  # Sobra de tentativa anterior sem marcador: sem apagar, o Data Pump recusa o nome existente.
  oci_apagar_prefixo "$PREFIXO-" || return 1
  parfile "$TMP/exp.par" \
    "userid=$BACKUP_DB_USER/$BACKUP_DB_PASS@$BACKUP_DB_DSN" \
    "schemas=BESAVE" \
    "credential=$BACKUP_OCI_CREDENCIAL" \
    "dumpfile=$BACKUP_OCI_URI/$PREFIXO-%L.dmp" \
    "filesize=5GB" \
    "parallel=1" \
    "exclude=statistics" \
    "directory=data_pump_dir" \
    "logfile=$MARCADOR" || return 1
  expdp parfile="$TMP/exp.par" > "$TMP/$MARCADOR" 2>&1
  local rc=$?
  cat "$TMP/$MARCADOR"
  [ "$rc" -eq 0 ] || return 1
  n=$(oci_contar "$PREFIXO-") || return 1
  [ "$n" -gt 0 ] || { echo "expdp terminou sem erro mas nenhum dump apareceu no bucket" >&2; return 1; }
  # O marcador só sobe depois do dump: sua presença significa export completo.
  "${OCI[@]}" os object put --bucket-name "$BACKUP_OCI_BUCKET" --file "$TMP/$MARCADOR" \
    --name "$MARCADOR" --force
}

etapa_copiar() {
  local ja
  ja=$(aws s3api list-objects-v2 --bucket "$BACKUP_S3_BUCKET" --prefix "db/$DIA/$MARCADOR" \
    --query 'KeyCount' --output text) || return 1
  if [ "$ja" != 0 ]; then
    log "cópia de $DIA já existe no S3; pulando"
    return 0
  fi
  mkdir -p "$TMP/dl"
  "${OCI[@]}" os object bulk-download --bucket-name "$BACKUP_OCI_BUCKET" --prefix "$PREFIXO" \
    --download-dir "$TMP/dl" --overwrite || return 1
  local esperados baixados
  esperados=$(oci_contar "$PREFIXO") || return 1
  baixados=$(find "$TMP/dl" -type f | wc -l)
  if [ "$esperados" -le 1 ] || [ "$baixados" -ne "$esperados" ]; then
    echo "baixados $baixados de $esperados objetos (esperado: dump + log)" >&2
    return 1
  fi
  (cd "$TMP/dl" && sha256sum -- besave-* > "$TMP/SHA256SUMS") || return 1
  mv "$TMP/SHA256SUMS" "$TMP/dl/SHA256SUMS"
  BYTES=$(find "$TMP/dl" -type f -exec stat -c %s {} + | awk '{s+=$1} END {print s+0}')
  # Dump e somas primeiro; o log (marcador) por último.
  aws s3 cp "$TMP/dl" "s3://$BACKUP_S3_BUCKET/db/$DIA/" --recursive --exclude "$MARCADOR" --only-show-errors || return 1
  aws s3 cp "$TMP/dl/$MARCADOR" "s3://$BACKUP_S3_BUCKET/db/$DIA/$MARCADOR" --only-show-errors
}

etapa_retencao() {
  local corte nome d nomes
  corte=$(date -d "$DIA -$((RETENCAO_DIAS - 1)) days" +%Y%m%d) || return 1
  nomes=$(oci_nomes "besave-") || return 1
  while IFS= read -r nome; do
    [[ $nome =~ ^besave-([0-9]{8})[-.] ]] || continue
    d=${BASH_REMATCH[1]}
    if [ "$d" -lt "$corte" ]; then
      log "retenção OCI: apagando $nome"
      "${OCI[@]}" os object delete --bucket-name "$BACKUP_OCI_BUCKET" --object-name "$nome" --force || return 1
    fi
  done <<< "$nomes"
}

BYTES=0
etapa_export || falhar "$MODO" "export (Data Pump)"
etapa_copiar || falhar "$MODO" "cópia para o S3"
etapa_retencao || falhar "$MODO" "retenção na OCI"

# Reexecução que só pulou etapas (BYTES=0) não apaga o tamanho já registrado do dia.
if [ "$BYTES" -gt 0 ] || ! grep -q "^$DIA ok " "$ESTADO/historico.log" 2> /dev/null; then
  printf '%s ok %s %s\n' "$DIA" "$BYTES" "$((SECONDS - INICIO))" >> "$ESTADO/historico.log"
fi
log "backup $DIA ok: $BYTES bytes, $((SECONDS - INICIO)) s"
