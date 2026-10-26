#!/usr/bin/env bash
# Teste mensal de restauração (BSV-49): importa o último dump do bucket da OCI no schema BESAVE_RESTORE,
# compara contagem de linhas por tabela e objetos inválidos com BESAVE e apaga o schema de teste.
# Só escreve em BESAVE_RESTORE. Variáveis em backup.env.
set -uo pipefail

AQUI=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
. "$AQUI/lib.sh"
MODO=teste
carregar_env
exigir BACKUP_DB_USER BACKUP_DB_PASS BACKUP_DB_DSN BACKUP_OCI_URI BACKUP_OCI_BUCKET \
  BACKUP_OCI_CREDENCIAL TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID
exigir_senha_do_parfile

TOLERANCIA_PCT=${BACKUP_TOLERANCIA_PCT:-5}
TOLERANCIA_MIN=${BACKUP_TOLERANCIA_MIN:-20}
OCI=(oci --auth instance_principal)
INICIO=$SECONDS

mkdir -p "$ESTADO"
rm -f "$ESTADO/alertado-$MODO"
exec 9> "$ESTADO/teste.lock"
flock -n 9 || { log "outra execução em andamento; nada a fazer"; exit 0; }

TMP=$(mktemp -d "${BACKUP_TMP:-$BACKUP_DIR/tmp}.XXXXXX") || falhar "$MODO" "pasta temporária"

# SQL*Plus lendo o comando do stdin: a senha não aparece em `ps`.
sql_admin() {
  sqlplus -S -L /nolog <<SQL
whenever sqlerror exit failure
connect $BACKUP_DB_USER/"$BACKUP_DB_PASS"@$BACKUP_DB_DSN
set serveroutput on size unlimited feedback off pagesize 0 linesize 400
$1
SQL
}

LIMPEZA=0
limpar() {
  # O schema de teste sai mesmo quando o teste falha; a pasta temporária guarda a senha do parfile.
  [ "$LIMPEZA" -eq 0 ] || sql_admin "exec ADMIN.BACKUP_LIMPA_RESTORE" > /dev/null 2>&1 || true
  rm -rf "$TMP"
}
trap limpar EXIT

read -r -d '' SQL_CONTAGEM <<'SQL'
DECLARE
  n1 NUMBER;
  n2 NUMBER;
BEGIN
  FOR t IN (SELECT table_name FROM dba_tables
             WHERE owner = 'BESAVE' AND temporary = 'N' AND nested = 'NO' AND iot_name IS NULL
             ORDER BY table_name) LOOP
    EXECUTE IMMEDIATE 'SELECT COUNT(*) FROM BESAVE."' || t.table_name || '"' INTO n1;
    BEGIN
      EXECUTE IMMEDIATE 'SELECT COUNT(*) FROM BESAVE_RESTORE."' || t.table_name || '"' INTO n2;
    EXCEPTION WHEN OTHERS THEN
      n2 := -1;
    END;
    DBMS_OUTPUT.PUT_LINE('LINHAS|' || t.table_name || '|' || n1 || '|' || n2);
  END LOOP;
  SELECT COUNT(*) INTO n1 FROM dba_objects WHERE owner = 'BESAVE' AND status = 'INVALID';
  SELECT COUNT(*) INTO n2 FROM dba_objects WHERE owner = 'BESAVE_RESTORE' AND status = 'INVALID';
  DBMS_OUTPUT.PUT_LINE('INVALIDOS|' || n1 || '|' || n2);
END;
/
SQL

etapa_escolher() {
  local nomes
  nomes=$("${OCI[@]}" os object list --bucket-name "$BACKUP_OCI_BUCKET" --prefix besave- --all \
    --query 'data[].name' --output json | grep -o '"besave-[0-9]\{8\}\.log"') || return 1
  DIA=$(printf '%s\n' "$nomes" | tr -d '"' | sed 's/^besave-//; s/\.log$//' | sort | tail -n 1)
  [[ ${DIA:-} =~ ^[0-9]{8}$ ]] || { echo "nenhum export completo no bucket da OCI" >&2; return 1; }
  log "restaurando o dump de $DIA"
}

etapa_preparar() {
  LIMPEZA=1
  sql_admin "exec ADMIN.BACKUP_PREPARA_RESTORE"
}

etapa_importar() {
  parfile "$TMP/imp.par" \
    "userid=$BACKUP_DB_USER/$BACKUP_DB_PASS@$BACKUP_DB_DSN" \
    "schemas=BESAVE" \
    "remap_schema=BESAVE:BESAVE_RESTORE" \
    "credential=$BACKUP_OCI_CREDENCIAL" \
    "dumpfile=$BACKUP_OCI_URI/besave-$DIA-%L.dmp" \
    "parallel=1" \
    "transform=segment_attributes:n" \
    "exclude=cluster,db_link"     "exclude=user" \
    "directory=data_pump_dir" \
    "logfile=restore-$DIA.log" || return 1
  impdp parfile="$TMP/imp.par" > "$TMP/imp.out" 2>&1
  local rc=$?
  cat "$TMP/imp.out"
  return "$rc"
}

# Linhas LINHAS|TABELA|origem|restore. Passa se |origem-restore| <= max(MIN, origem*PCT/100) e a tabela existe.
etapa_comparar() {
  sql_admin "$SQL_CONTAGEM" > "$TMP/contagem.txt" || return 1
  local ruins
  ruins=$(awk -F'|' -v pct="$TOLERANCIA_PCT" -v min="$TOLERANCIA_MIN" '
    $1 == "LINHAS" {
      n++; d = $3 - $4; if (d < 0) d = -d
      tol = $3 * pct / 100; if (tol < min) tol = min
      if ($4 < 0 || d > tol) printf "%s (origem %s, restore %s)\n", $2, $3, $4
    }
    $1 == "INVALIDOS" { inv = 1; if ($3 + 0 > $2 + 0) printf "objetos inválidos: origem %s, restore %s\n", $2, $3 }
    END { if (n == 0) print "nenhuma tabela comparada"; if (!inv) print "sem linha INVALIDOS" }
  ' "$TMP/contagem.txt")
  if [ -n "$ruins" ]; then
    printf 'divergências:\n%s\n' "$ruins" >&2
    return 1
  fi
  TABELAS=$(grep -c '^LINHAS|' "$TMP/contagem.txt")
}

# Só desarma a limpeza do trap depois que a rotina deu certo: se falhar, o trap tenta de novo.
etapa_apagar() {
  sql_admin "exec ADMIN.BACKUP_LIMPA_RESTORE" && LIMPEZA=0
}

TABELAS=0
etapa_escolher || falhar "$MODO" "escolher o último dump"
etapa_preparar || falhar "$MODO" "preparar BESAVE_RESTORE"
etapa_importar || falhar "$MODO" "importar (Data Pump)"
etapa_comparar || falhar "$MODO" "comparar contagens"
etapa_apagar || falhar "$MODO" "apagar BESAVE_RESTORE"

printf '%s ok %s\n' "$(date +%Y%m%d)" "$DIA" > "$ESTADO/ultimo-teste.txt"
alertar "Teste de restauração ok: dump de $DIA, $TABELAS tabelas conferidas em $((SECONDS - INICIO)) s." || true
log "teste de restauração ok ($DIA, $TABELAS tabelas)"
