#!/usr/bin/env bash
# Backup diário do schema BESAVE (BSV-49): Data Pump → bucket da OCI → cópia no S3 → retenção na OCI.
# Idempotente: o log do dia no bucket é o marcador de "export feito"; no S3, de "cópia feita".
# Uso: backup-diario.sh   (variáveis em backup.env, ver backup.env.example)
set -uo pipefail

AQUI=$(cd "$(dirname "$0")" && pwd)
# O sudo herda o diretório de onde foi chamado (ex.: /home/ubuntu), que o usuário besave pode não ler; `find -delete`
# e outros comandos falham ao voltar a ele ("Failed to restore initial working directory"). Os caminhos são absolutos.
cd / || exit 2
# shellcheck source=lib.sh
. "$AQUI/lib.sh"
MODO=diario
carregar_env
exigir BACKUP_DB_USER BACKUP_DB_PASS BACKUP_DB_DSN BACKUP_OCI_URI BACKUP_OCI_BUCKET \
  BACKUP_OCI_CREDENCIAL BACKUP_S3_BUCKET TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID
exigir_senha_do_parfile

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
  # Bucket sem objetos: a OCI CLI não devolve `data`; o `|| []` evita o erro do JMESPath (crases = literal JMESPath).
  # shellcheck disable=SC2016
  n=$("${OCI[@]}" os object list --bucket-name "$BACKUP_OCI_BUCKET" --prefix "$1" --all \
    --query 'length(data || `[]`)' --raw-output) || return 1
  if [[ $n =~ ^[0-9]+$ ]]; then echo "$n"; else echo 0; fi
}

oci_nomes() {
  local json
  json=$("${OCI[@]}" os object list --bucket-name "$BACKUP_OCI_BUCKET" --prefix "$1" --all --query 'data[].name' --output json) || return 1
  # Sem objetos não é erro: grep sai com 1 e o resultado é vazio.
  grep -o '"besave-[^"]*"' <<< "$json" | tr -d '"' || true
}

oci_apagar_prefixo() {
  local nome nomes
  nomes=$(oci_nomes "$1") || return 1
  # Ordem reversa: segmentos (`<dmp>_...`) antes do `.dmp` de 0 byte que os referencia.
  nomes=$(LC_ALL=C sort -r <<< "$nomes")
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

# Quantos objetos do S3 começam com o prefixo. A CLI v2 devolve "None" (não 0) em `KeyCount` quando não há
# objeto; `length(Contents || [])` dá 0. Resposta que não é número é erro, nunca "já existe".
s3_contar() {
  local n
  # shellcheck disable=SC2016
  n=$(aws s3api list-objects-v2 --bucket "$BACKUP_S3_BUCKET" --prefix "$1" \
    --query 'length(Contents || `[]`)' --output text) || return 1
  [[ $n =~ ^[0-9]+$ ]] || { echo "resposta inesperada do S3 ao contar '$1': '$n'" >&2; return 1; }
  echo "$n"
}

# O Data Pump grava no Object Storage o `.dmp` com 0 byte e o conteúdo em segmentos (`<dmp>_aaaaaa`,
# `<dmp>_segments/aaaaaa…`); baixar o `.dmp` pela CLI não traz o dump (docs da Oracle). Remonta cada `.dmp`
# concatenando seus segmentos em ordem alfabética (a Oracle não documenta a ordem; ver README), confere
# tamanho = soma dos segmentos e apaga os segmentos, para subir ao S3 só o `.dmp` inteiro.
remontar_dumps() { # pasta
  local pasta=$1 dmp seg soma tam todos
  todos=$(cd "$pasta" && find . -type f | sed 's#^\./##' | LC_ALL=C sort) || return 1
  while IFS= read -r dmp; do
    [[ $dmp =~ ^$PREFIXO-[0-9]+\.dmp$ ]] || continue
    local segs=()
    while IFS= read -r seg; do
      case $seg in "$dmp"_*) segs+=("$seg") ;; esac
    done <<< "$todos"
    tam=$(stat -c %s "$pasta/$dmp")
    if [ "${#segs[@]}" -eq 0 ]; then
      [ "$tam" -gt 0 ] || { echo "$dmp tem 0 byte e nenhum segmento no bucket" >&2; return 1; }
      continue
    fi
    [ "$tam" -eq 0 ] || { echo "$dmp tem $tam bytes e também segmentos; layout inesperado" >&2; return 1; }
    soma=0
    for seg in "${segs[@]}"; do soma=$((soma + $(stat -c %s "$pasta/$seg"))); done
    [ "$soma" -gt 0 ] || { echo "os segmentos de $dmp somam 0 byte" >&2; return 1; }
    : > "$pasta/$dmp.novo"
    for seg in "${segs[@]}"; do
      cat "$pasta/$seg" >> "$pasta/$dmp.novo" || return 1
      rm -f "$pasta/$seg"
    done
    tam=$(stat -c %s "$pasta/$dmp.novo")
    [ "$tam" -eq "$soma" ] || { echo "$dmp remontado tem $tam bytes; os segmentos somavam $soma" >&2; return 1; }
    mv "$pasta/$dmp.novo" "$pasta/$dmp" || return 1
    log "$dmp remontado: ${#segs[@]} segmento(s), $soma bytes"
  done <<< "$todos"
  find "$pasta" -mindepth 1 -type d -empty -delete
}

etapa_copiar() {
  local ja
  ja=$(s3_contar "db/$DIA/$MARCADOR") || return 1
  if [ "$ja" -gt 0 ]; then
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
  remontar_dumps "$TMP/dl" || return 1
  # Só vale export com dump de verdade (> 0 byte) e log do Data Pump terminando com sucesso.
  if [ -z "$(find "$TMP/dl" -maxdepth 1 -type f -name "$PREFIXO-[0-9]*.dmp" -size +0c -print -quit)" ]; then
    echo "nenhum besave-$DIA-NNN.dmp com tamanho maior que zero no export" >&2
    return 1
  fi
  if ! grep -q 'successfully completed' "$TMP/dl/$MARCADOR" || grep -q 'completed with' "$TMP/dl/$MARCADOR"; then
    echo "o log do Data Pump não termina com sucesso" >&2
    return 1
  fi
  # Soma do .dmp inteiro (já remontado); a restauração a partir do S3 confere com ela.
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
  nomes=$(LC_ALL=C sort -r <<< "$nomes")
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
