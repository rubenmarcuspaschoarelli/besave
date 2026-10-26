#!/usr/bin/env bash
# Testes dos scripts de backup (BSV-49) com oci, aws, expdp, impdp, sqlplus, curl e flock falsos:
# sem rede, sem banco, sem AWS. Os comandos montados são comparados inteiros (lição 14).
# Uso: bash infra/backup/teste_backup.sh
set -uo pipefail

AQUI=$(cd "$(dirname "$0")" && pwd)
falhas=0
total=0
caso=""

falhou() { echo "FALHOU: $caso: $*"; falhas=$((falhas + 1)); }
igual() { # descrição esperado obtido
  total=$((total + 1))
  [ "$2" = "$3" ] || falhou "$1"$'\n'"--- esperado"$'\n'"$2"$'\n'"--- obtido"$'\n'"$3"
}
contem() { # descrição texto trecho
  total=$((total + 1))
  case $2 in *"$3"*) ;; *) falhou "$1: faltou '$3' em: $2" ;; esac
}
nao_contem() {
  total=$((total + 1))
  case $2 in *"$3"*) falhou "$1: não devia ter '$3' em: $2" ;; esac
}

DIA=20261021

# Cria o ambiente: comandos falsos em $T/fake, bucket da OCI em $T/oci, S3 em $T/s3, registros em $T/reg.
preparar() {
  T=$(mktemp -d)
  mkdir -p "$T/fake" "$T/oci" "$T/s3" "$T/reg" "$T/srv/estado"
  : > "$T/reg/ordem.log"

  cat > "$T/fake/_falha.sh" <<'FALHA'
# falha TAG: FAKE_FALHA=tag falha toda chamada; tag:N só a N-ésima; lista separada por vírgula.
falha() {
  local n
  n=$(( $(cat "$FAKE_REG/n.$1" 2> /dev/null || echo 0) + 1 ))
  echo "$n" > "$FAKE_REG/n.$1"
  local spec
  for spec in ${FAKE_FALHA//,/ }; do
    case $spec in
      "$1" | "$1:$n") echo "falha simulada: $1 (chamada $n)" >&2; exit 1 ;;
    esac
  done
}
FALHA

  cat > "$T/fake/oci" <<'OCI'
#!/usr/bin/env bash
. "$(dirname "$0")/_falha.sh"
echo "$*" >> "$FAKE_REG/oci.log"
[ "$1 $2 $3 $4" = "--auth instance_principal os object" ] || exit 99
op=$5
shift 5
prefixo="" nome="" arq="" dest="" query=""
while [ $# -gt 0 ]; do
  case $1 in
    --prefix) prefixo=$2; shift ;;
    --object-name | --name) nome=$2; shift ;;
    --file) arq=$2; shift ;;
    --download-dir) dest=$2; shift ;;
    --query) query=$2; shift ;;
  esac
  shift
done
casa() { (cd "$FAKE_OCI" && find . -type f | sed 's#^\./##' | LC_ALL=C sort | awk -v p="$prefixo" 'index($0, p) == 1'); }
case $op in
  list)
    falha oci_list
    # Como a OCI CLI real: sem objetos não há `data`; length(data) puro dá erro, com `|| []` dá 0 e a lista sai vazia.
    vazio=; [ -n "$(casa)" ] || vazio=1
    if [ "$query" = "length(data)" ]; then
      [ -z "$vazio" ] || { echo "JMESPathTypeError: In function length(), invalid type for value: None" >&2; exit 1; }
      casa | grep -c . || true
    elif [[ $query == 'length(data || '* ]]; then casa | grep -c . || true
    elif [ -n "$vazio" ]; then :
    else
      echo '['
      casa | sed 's/.*/  "&",/'
      echo ']'
    fi ;;
  delete) falha oci_delete; echo "delete $nome" >> "$FAKE_REG/apagados.log"; rm -f "$FAKE_OCI/$nome" ;;
  put) falha oci_put; cp "$arq" "$FAKE_OCI/$nome" ;;
  bulk-download)
    falha oci_download
    for f in $(casa); do mkdir -p "$dest/$(dirname "$f")"; cp "$FAKE_OCI/$f" "$dest/$f"; done ;;
  *) exit 99 ;;
esac
OCI

  cat > "$T/fake/expdp" <<'EXPDP'
#!/usr/bin/env bash
. "$(dirname "$0")/_falha.sh"
echo "expdp $*" >> "$FAKE_REG/expdp.log"
echo expdp >> "$FAKE_REG/ordem.log"
par=${1#parfile=}
cp "$par" "$FAKE_REG/expdp.par"
stat -c %a "$par" > "$FAKE_REG/expdp.par.modo"
echo "Export: Release 19.0.0.0.0 simulado"
falha expdp
[ -z "${FAKE_SEM_DUMP:-}" ] || exit 0
uri=$(sed -n 's/^dumpfile=//p' "$par")
base=$(basename "$uri" | sed 's/%L/100/')
if [ -e "$FAKE_OCI/$base" ]; then echo "ORA-27038: arquivo $base já existe" >&2; exit 5; fi
# FAKE_PECAS: 1 = .dmp inteiro; 2 (padrão) = .dmp de 0 byte + <dmp>_segments/aaaaaa…; 3 = .dmp de 0 byte + <dmp>_aaaaaa…
# Os segmentos são criados fora de ordem: quem concatena na ordem da listagem do disco erra o conteúdo.
case "${FAKE_PECAS:-2}" in
  1) printf 'AAAA\nBBBB\nCCCC\n' > "$FAKE_OCI/$base" ;;
  2)
    : > "$FAKE_OCI/$base"
    mkdir -p "$FAKE_OCI/${base}_segments"
    printf 'CCCC\n' > "$FAKE_OCI/${base}_segments/aaaaac"
    printf 'AAAA\n' > "$FAKE_OCI/${base}_segments/aaaaaa"
    printf 'BBBB\n' > "$FAKE_OCI/${base}_segments/aaaaab" ;;
  3)
    : > "$FAKE_OCI/$base"
    printf 'CCCC\n' > "$FAKE_OCI/${base}_aaaaac"
    printf 'AAAA\n' > "$FAKE_OCI/${base}_aaaaaa"
    printf 'BBBB\n' > "$FAKE_OCI/${base}_aaaaab" ;;
esac
echo "Job successfully completed"
EXPDP

  cat > "$T/fake/impdp" <<'IMPDP'
#!/usr/bin/env bash
. "$(dirname "$0")/_falha.sh"
echo "impdp $*" >> "$FAKE_REG/impdp.log"
echo impdp >> "$FAKE_REG/ordem.log"
cp "${1#parfile=}" "$FAKE_REG/impdp.par"
falha impdp
echo "Import simulado"
IMPDP

  cat > "$T/fake/sqlplus" <<'SQLPLUS'
#!/usr/bin/env bash
. "$(dirname "$0")/_falha.sh"
echo "sqlplus $*" >> "$FAKE_REG/sqlplus.log"
entrada=$(cat)
printf '%s\n=====\n' "$entrada" >> "$FAKE_REG/sql.log"
case $entrada in
  *BACKUP_PREPARA_RESTORE*) echo prepara >> "$FAKE_REG/ordem.log"; falha prepara ;;
  *BACKUP_LIMPA_RESTORE*) echo limpa >> "$FAKE_REG/ordem.log"; falha limpa ;;
  *"PUT_LINE('INVALIDOS"*) echo contagem >> "$FAKE_REG/ordem.log"; falha contagem; cat "$FAKE_CONTAGEM" ;;
esac
SQLPLUS

  cat > "$T/fake/aws" <<'AWS'
#!/usr/bin/env bash
. "$(dirname "$0")/_falha.sh"
echo "$*" >> "$FAKE_REG/aws.log"
case "$1 $2" in
  "s3api list-objects-v2")
    falha aws_list
    chave=$6 consulta=$8
    n=$(cd "$FAKE_S3" && find . -type f | sed 's#^\./##' | grep -c "^$chave" || true)
    case $consulta in
      KeyCount) if [ "$n" -gt 0 ]; then echo "$n"; else echo None; fi ;;
      'length(Contents || `[]`)') echo "${FAKE_AWS_CONTAGEM:-$n}" ;;
      *) exit 99 ;;
    esac ;;
  "s3 cp")
    falha aws_cp
    origem=$3 destino=${4#s3://*/}
    if [ -d "$origem" ]; then
      mkdir -p "$FAKE_S3/$destino"
      for f in "$origem"/*; do
        [ "$(basename "$f")" = "$7" ] || cp "$f" "$FAKE_S3/$destino$(basename "$f")"
      done
    else
      mkdir -p "$FAKE_S3/$(dirname "$destino")"
      cp "$origem" "$FAKE_S3/$destino"
    fi ;;
  *) exit 99 ;;
esac
AWS

  cat > "$T/fake/curl" <<'CURL'
#!/usr/bin/env bash
. "$(dirname "$0")/_falha.sh"
echo "curl $*" >> "$FAKE_REG/curl.log"
cat >> "$FAKE_REG/curl.stdin"
falha curl
echo "enviado" >> "$FAKE_REG/alertas.log"
CURL

  cat > "$T/fake/cat" <<'CAT'
#!/usr/bin/env bash
# FAKE_CAT_CORTA: o cat de um segmento devolve só 3 bytes (concatenação que perde dados sem dar erro).
if [ -n "${FAKE_CAT_CORTA:-}" ]; then
  case "$*" in *_segments*) /usr/bin/cat "$@" | head -c 3; exit 0 ;; esac
fi
exec /usr/bin/cat "$@"
CAT

  cat > "$T/fake/flock" <<'FLOCK'
#!/usr/bin/env bash
[ "${FAKE_FLOCK:-}" != ocupado ] || exit 1
FLOCK
  chmod +x "$T"/fake/*

  : > "$T/contagem.txt"
  export FAKE_REG="$T/reg" FAKE_OCI="$T/oci" FAKE_S3="$T/s3" FAKE_CONTAGEM="$T/contagem.txt"
  unset FAKE_FALHA FAKE_SEM_DUMP FAKE_FLOCK FAKE_CAT_CORTA FAKE_AWS_CONTAGEM
}

# Ambiente do backup: tudo explícito, nada herdado do backup.env real.
ambiente() {
  ENV=(
    "PATH=$T/fake:$PATH" "HOME=$T"
    "FAKE_REG=$FAKE_REG" "FAKE_OCI=$FAKE_OCI" "FAKE_S3=$FAKE_S3" "FAKE_CONTAGEM=$FAKE_CONTAGEM"
    "FAKE_FALHA=${FAKE_FALHA:-}" "FAKE_SEM_DUMP=${FAKE_SEM_DUMP:-}" "FAKE_PECAS=${FAKE_PECAS:-2}" "FAKE_FLOCK=${FAKE_FLOCK:-}" "FAKE_CAT_CORTA=${FAKE_CAT_CORTA:-}" "FAKE_AWS_CONTAGEM=${FAKE_AWS_CONTAGEM:-}"
    "BESAVE_BACKUP_DIR=$T/srv" "BESAVE_BACKUP_ENV=$T/nao-existe.env" "BACKUP_TMP=$T/tmp"
    "BACKUP_DB_USER=BESAVE_BACKUP" "BACKUP_DB_PASS=s3nh4-secreta" "BACKUP_DB_DSN=bsvdb_high"
    "BACKUP_OCI_URI=https://ns.example/o" "BACKUP_OCI_BUCKET=bkp-oci" "BACKUP_OCI_CREDENCIAL=BACKUP_OCI_CRED"
    "BACKUP_S3_BUCKET=bkp-s3" "TELEGRAM_BOT_TOKEN=123:TOKEN-secreto" "TELEGRAM_CHAT_ID=-100"
    "HOSTNAME=inst2-teste" "BACKUP_DIA=$DIA"
  )
}

rodar() { # script args...
  ambiente
  local s=$1
  shift
  env -i "${ENV[@]}" "${EXTRA[@]}" bash "$AQUI/$s" "$@" < /dev/null > "$T/out" 2> "$T/err"
  codigo=$?
}
EXTRA=()

reg() { cat "$FAKE_REG/$1" 2> /dev/null || true; }
# Troca a pasta temporária (nome aleatório) por <TMP> para comparar o comando inteiro.
norm() { sed "s#$T/tmp\.[A-Za-z0-9]*#<TMP>#g"; }
alertas() { reg curl.log | grep -c '^curl' || true; }
texto_alerta() { grep -o 'text=.*' "$FAKE_REG/curl.log" | tail -n 1; }
# O texto vai por --data-urlencode; o curl falso grava os argumentos.

# ---------- BKP-01: dia completo ----------
caso="BKP-01 dia completo"
preparar
rodar backup-diario.sh
igual "código 0" 0 "$codigo"
igual "objetos na OCI (layout real: .dmp de 0 byte + segmentos)" "besave-$DIA-100.dmp
besave-$DIA-100.dmp_segments/aaaaaa
besave-$DIA-100.dmp_segments/aaaaab
besave-$DIA-100.dmp_segments/aaaaac
besave-$DIA.log" "$(cd "$FAKE_OCI" && find . -type f | sed 's#^\./##' | LC_ALL=C sort)"
igual "objetos no S3 (o .dmp inteiro, sem segmentos)" "db/$DIA/SHA256SUMS
db/$DIA/besave-$DIA-100.dmp
db/$DIA/besave-$DIA.log" "$(cd "$FAKE_S3" && find . -type f | sed 's#^\./##' | LC_ALL=C sort)"
(cd "$FAKE_S3/db/$DIA" && sha256sum --quiet -c SHA256SUMS) || falhou "SHA256SUMS não confere com os arquivos do S3"
igual "somas cobrem dump e log" 2 "$(wc -l < "$FAKE_S3/db/$DIA/SHA256SUMS" | tr -d ' ')"
igual "S3: .dmp = segmentos concatenados em ordem" $'AAAA\nBBBB\nCCCC' "$(cat "$FAKE_S3/db/$DIA/besave-$DIA-100.dmp")"
contem "log diz que remontou" "$(cat "$T/out")" "besave-$DIA-100.dmp remontado: 3 segmento(s), 15 bytes"
igual "expdp (comando inteiro)" "expdp parfile=<TMP>/exp.par" "$(reg expdp.log | norm)"
igual "parfile do export (inteiro)" "userid=BESAVE_BACKUP/s3nh4-secreta@bsvdb_high
schemas=BESAVE
credential=BACKUP_OCI_CRED
dumpfile=https://ns.example/o/besave-$DIA-%L.dmp
filesize=5GB
parallel=1
exclude=statistics
directory=data_pump_dir
logfile=besave-$DIA.log" "$(reg expdp.par)"
# NTFS (Git Bash no Windows) não guarda modo unix; no Linux, que é onde roda, vale.
case $(uname -s) in MINGW* | MSYS*) ;; *) igual "parfile só do dono" 600 "$(reg expdp.par.modo)" ;; esac
igual "chamadas à OCI (inteiras)" "--auth instance_principal os object list --bucket-name bkp-oci --prefix besave-$DIA.log --all --query length(data || \`[]\`) --raw-output
--auth instance_principal os object list --bucket-name bkp-oci --prefix besave-$DIA- --all --query data[].name --output json
--auth instance_principal os object list --bucket-name bkp-oci --prefix besave-$DIA- --all --query length(data || \`[]\`) --raw-output
--auth instance_principal os object put --bucket-name bkp-oci --file <TMP>/besave-$DIA.log --name besave-$DIA.log --force
--auth instance_principal os object bulk-download --bucket-name bkp-oci --prefix besave-$DIA --download-dir <TMP>/dl --overwrite
--auth instance_principal os object list --bucket-name bkp-oci --prefix besave-$DIA --all --query length(data || \`[]\`) --raw-output
--auth instance_principal os object list --bucket-name bkp-oci --prefix besave- --all --query data[].name --output json" "$(reg oci.log | norm)"
igual "chamadas à AWS (inteiras)" "s3api list-objects-v2 --bucket bkp-s3 --prefix db/$DIA/besave-$DIA.log --query length(Contents || \`[]\`) --output text
s3 cp <TMP>/dl s3://bkp-s3/db/$DIA/ --recursive --exclude besave-$DIA.log --only-show-errors
s3 cp <TMP>/dl/besave-$DIA.log s3://bkp-s3/db/$DIA/besave-$DIA.log --only-show-errors" "$(reg aws.log | norm)"
igual "histórico" "$DIA ok" "$(cut -d' ' -f1,2 "$T/srv/estado/historico.log")"
bytes=$(cut -d' ' -f3 "$T/srv/estado/historico.log")
[ "${bytes:-0}" -gt 0 ] || falhou "histórico sem tamanho: $bytes"
igual "BYTES = tamanho real do que foi para o S3 (.dmp inteiro, não o stub de 0 byte)" \
  "$(find "$FAKE_S3" -type f -exec stat -c %s {} + | awk '{s+=$1} END {print s+0}')" "$bytes"
igual "nenhum alerta no dia bom" 0 "$(alertas)"
igual "pasta temporária apagada" "" "$(ls -d "$T"/tmp.* 2> /dev/null)"
rm -rf "$T"

caso="BKP-01b dump de peça única e marca de alerta velha"
preparar
: > "$T/srv/estado/alertado-diario"
FAKE_PECAS=1
rodar backup-diario.sh
igual "código 0 com 1 peça + log" 0 "$codigo"
igual "dump de peça única vai inteiro" $'AAAA\nBBBB\nCCCC' "$(cat "$FAKE_S3/db/$DIA/besave-$DIA-100.dmp")"
[ ! -e "$T/srv/estado/alertado-diario" ] || falhou "execução nova não limpou a marca de alerta anterior"
unset FAKE_PECAS
rm -rf "$T"

caso="BKP-01c segmentos no formato <dmp>_aaaaaa (como nos exemplos da Oracle)"
preparar
FAKE_PECAS=3
rodar backup-diario.sh
igual "código 0" 0 "$codigo"
igual "S3 só com o .dmp inteiro" "db/$DIA/SHA256SUMS
db/$DIA/besave-$DIA-100.dmp
db/$DIA/besave-$DIA.log" "$(cd "$FAKE_S3" && find . -type f | sed 's#^\./##' | LC_ALL=C sort)"
igual "conteúdo na ordem dos segmentos" $'AAAA\nBBBB\nCCCC' "$(cat "$FAKE_S3/db/$DIA/besave-$DIA-100.dmp")"
unset FAKE_PECAS
rm -rf "$T"

# ---------- BKP-02: idempotência ----------
caso="BKP-02 duas vezes no mesmo dia"
preparar
rodar backup-diario.sh
oci_antes=$(cd "$FAKE_OCI" && find . -type f -exec sha256sum {} + | sort)
s3_antes=$(cd "$FAKE_S3" && find . -type f -exec sha256sum {} + | sort)
hist_antes=$(cat "$T/srv/estado/historico.log")
: > "$FAKE_REG/oci.log"; : > "$FAKE_REG/aws.log"; : > "$FAKE_REG/expdp.log"
rodar backup-diario.sh
igual "segunda execução ok" 0 "$codigo"
igual "OCI intacta" "$oci_antes" "$(cd "$FAKE_OCI" && find . -type f -exec sha256sum {} + | sort)"
igual "S3 intacto" "$s3_antes" "$(cd "$FAKE_S3" && find . -type f -exec sha256sum {} + | sort)"
igual "sem novo export" "" "$(reg expdp.log)"
igual "sem apagar nada" "" "$(reg apagados.log)"
igual "sem upload" "s3api list-objects-v2 --bucket bkp-s3 --prefix db/$DIA/besave-$DIA.log --query length(Contents || \`[]\`) --output text" "$(reg aws.log)"
igual "histórico não duplica nem zera" "$hist_antes" "$(cat "$T/srv/estado/historico.log")"
rm -rf "$T"

# ---------- BKP-03: sobra de tentativa que falhou no meio ----------
caso="BKP-03 dump parcial sem marcador"
preparar
echo velho > "$FAKE_OCI/besave-$DIA-100.dmp"
rodar backup-diario.sh
igual "código 0 (a sobra foi apagada antes do export)" 0 "$codigo"
igual "parcial apagado" "delete besave-$DIA-100.dmp" "$(reg apagados.log)"
contem "dump novo" "$(ls "$FAKE_OCI")" "besave-$DIA.log"
rm -rf "$T"

# ---------- BKP-04: retenção da OCI (7 dias: mantém D-6..D) ----------
caso="BKP-04 retenção OCI"
preparar
for d in 20261013 20261014 20261015 20261018; do
  echo x > "$FAKE_OCI/besave-$d-100.dmp"; echo x > "$FAKE_OCI/besave-$d.log"
done
echo x > "$FAKE_OCI/besave-semdata.txt"
rodar backup-diario.sh
igual "código 0" 0 "$codigo"
igual "apagou só o que passou de 7 dias (ordem reversa: segmentos antes do .dmp)" "delete besave-20261014.log
delete besave-20261014-100.dmp
delete besave-20261013.log
delete besave-20261013-100.dmp" "$(reg apagados.log)"
contem "manteve o limite" "$(ls "$FAKE_OCI")" "besave-20261015.log"
contem "manteve fora do padrão" "$(ls "$FAKE_OCI")" "besave-semdata.txt"
rm -rf "$T"

# ---------- BKP-04b: export no bucket sem dump válido ou sem sucesso no log não vai para o S3 ----------
while IFS='|' read -r nome tamanho log; do
  caso="BKP-04b export inválido: $nome"
  preparar
  printf '%s' "$tamanho" > "$FAKE_OCI/besave-$DIA-100.dmp"
  echo "$log" > "$FAKE_OCI/besave-$DIA.log"
  rodar backup-diario.sh
  igual "código 1" 1 "$codigo"
  igual "um alerta" 1 "$(alertas)"
  contem "etapa no alerta" "$(texto_alerta)" "falhou na etapa 'cópia para o S3'"
  igual "nada foi para o S3" "" "$(cd "$FAKE_S3" && find . -type f)"
  rm -rf "$T"
done <<'CASOS'
dump vazio|| Job "BESAVE_BACKUP"."SYS_EXPORT_SCHEMA_01" successfully completed
log sem sucesso|x|ORA-39095: Dump file space has been exhausted
concluído com erros|x|Job "BESAVE_BACKUP"."SYS_EXPORT_SCHEMA_01" completed with 2 error(s)
CASOS
caso="BKP-04b só o log, sem dump"
preparar
echo 'Job "X" successfully completed' > "$FAKE_OCI/besave-$DIA.log"
rodar backup-diario.sh
igual "código 1" 1 "$codigo"
igual "nada foi para o S3" "" "$(cd "$FAKE_S3" && find . -type f)"
rm -rf "$T"

# ---------- BKP-05: falha em cada etapa → alerta e código ≠ 0 ----------
while IFS='|' read -r falha etapa; do
  caso="BKP-05 falha $falha"
  preparar
  echo x > "$FAKE_OCI/besave-20261013-100.dmp"; echo x > "$FAKE_OCI/besave-20261013.log"
  FAKE_FALHA=$falha
  rodar backup-diario.sh
  igual "código 1" 1 "$codigo"
  igual "um alerta" 1 "$(alertas)"
  contem "etapa no alerta" "$(texto_alerta)" "text=[inst2-teste] Backup (diario): "
  contem "etapa no alerta" "$(texto_alerta)" "falhou na etapa '$etapa'"
  igual "histórico registra a falha" "$DIA falha 0 0" "$(tail -n 1 "$T/srv/estado/historico.log")"
  [ -e "$T/srv/estado/alertado-diario" ] || falhou "sem marca de alerta já enviado"
  unset FAKE_FALHA
  rm -rf "$T"
done <<'CASOS'
oci_list:1|export (Data Pump)
oci_list:2|export (Data Pump)
expdp|export (Data Pump)
oci_list:3|export (Data Pump)
oci_put|export (Data Pump)
aws_list|cópia para o S3
oci_download|cópia para o S3
oci_list:4|cópia para o S3
aws_cp:1|cópia para o S3
aws_cp:2|cópia para o S3
oci_list:5|retenção na OCI
oci_delete|retenção na OCI
CASOS

caso="BKP-06 expdp sai com 0 mas nenhum dump apareceu"
preparar
FAKE_SEM_DUMP=1
rodar backup-diario.sh
igual "código 1" 1 "$codigo"
contem "etapa" "$(texto_alerta)" "export (Data Pump)"
contem "motivo" "$(cat "$T/err")" "nenhum dump apareceu"
igual "sem marcador na OCI" "" "$(ls "$FAKE_OCI")"
unset FAKE_SEM_DUMP
rm -rf "$T"

caso="BKP-07 falha no export não chega à cópia nem à retenção"
preparar
echo x > "$FAKE_OCI/besave-20260101.log"
FAKE_FALHA=expdp
rodar backup-diario.sh
igual "S3 vazio" "" "$(cd "$FAKE_S3" && find . -type f)"
igual "nada apagado" "" "$(reg apagados.log)"
igual "sem chamada à AWS" "" "$(reg aws.log)"
unset FAKE_FALHA
rm -rf "$T"

caso="BKP-08 alerta que não sai não esconde a falha"
preparar
FAKE_FALHA=expdp,curl
rodar backup-diario.sh
igual "código 1 mesmo com o curl falhando" 1 "$codigo"
igual "tentou alertar" 1 "$(alertas)"
unset FAKE_FALHA
rm -rf "$T"

caso="BKP-09 token só por stdin"
preparar
FAKE_FALHA=expdp
rodar backup-diario.sh
igual "curl (comando inteiro, sem token)" "curl -sS --fail --max-time 20 -K - --data-urlencode chat_id=-100 --data-urlencode text=[inst2-teste] Backup (diario): falhou na etapa 'export (Data Pump)'. Ver: journalctl -u besave-backup-diario" "$(reg curl.log)"
contem "stdin do curl" "$(reg curl.stdin)" 'url = "https://api.telegram.org/bot123:TOKEN-secreto/sendMessage"'
nao_contem "senha do banco na saída" "$(cat "$T/out" "$T/err")" "s3nh4-secreta"
unset FAKE_FALHA
rm -rf "$T"

caso="BKP-10 variável ausente"
preparar
EXTRA=("BACKUP_S3_BUCKET=")
rodar backup-diario.sh
igual "código 2" 2 "$codigo"
contem "diz qual" "$(cat "$T/err")" "BACKUP_S3_BUCKET"
igual "nada chamado" "" "$(reg oci.log)"
EXTRA=()
rm -rf "$T"

caso="BKP-11 já em execução"
preparar
FAKE_FLOCK=ocupado
rodar backup-diario.sh
igual "código 0 sem fazer nada" 0 "$codigo"
igual "nada chamado" "" "$(reg oci.log)"
unset FAKE_FLOCK
rm -rf "$T"

caso="BKP-12 backup.env: lê literal e o ambiente vence"
preparar
cat > "$T/real.env" <<'ENVF'
# comentário
BACKUP_DB_PASS=a$b=c!d%e
BACKUP_S3_BUCKET=do-arquivo
ENVF
ambiente
SEM=()
for v in "${ENV[@]}"; do
  case $v in BACKUP_DB_PASS=* | BACKUP_S3_BUCKET=* | BESAVE_BACKUP_ENV=*) ;; *) SEM+=("$v") ;; esac
done
env -i "${SEM[@]}" "BESAVE_BACKUP_ENV=$T/real.env" "BACKUP_S3_BUCKET=do-ambiente"   bash "$AQUI/backup-diario.sh" < /dev/null > "$T/out" 2> "$T/err"
igual "código 0" 0 "$?"
# shellcheck disable=SC2016 # o esperado é literal, com $
igual "senha com \$, = e ! chega inteira" 'userid=BESAVE_BACKUP/a$b=c!d%e@bsvdb_high' "$(reg expdp.par | head -n 1)"
contem "ambiente vence o arquivo" "$(reg aws.log)" "--bucket do-ambiente"
nao_contem "arquivo perdeu" "$(reg aws.log)" "do-arquivo"
rm -rf "$T"

# ---------- BKP-13: contagem do S3 que não é número nunca vira "já existe" ----------
for resposta in None abc; do
  caso="BKP-13 S3 responde '$resposta'"
  preparar
  FAKE_AWS_CONTAGEM=$resposta
  rodar backup-diario.sh
  igual "código 1" 1 "$codigo"
  contem "etapa" "$(texto_alerta)" "falhou na etapa 'cópia para o S3'"
  contem "motivo" "$(cat "$T/err")" "resposta inesperada do S3"
  igual "nada foi para o S3" "" "$(cd "$FAKE_S3" && find . -type f)"
  nao_contem "não pulou a cópia" "$(cat "$T/out")" "já existe no S3"
  rm -rf "$T"
done

# ---------- BKP-14: remontagem do dump a partir dos segmentos ----------
caso="BKP-14 dois dumps, segmentos de cada um, nomes com prefixo comum (-1 e -10)"
preparar
echo 'Job "X" successfully completed' > "$FAKE_OCI/besave-$DIA.log"
for n in 1 10; do
  : > "$FAKE_OCI/besave-$DIA-$n.dmp"
  mkdir -p "$FAKE_OCI/besave-$DIA-$n.dmp_segments"
  printf 'b%s\n' "$n" > "$FAKE_OCI/besave-$DIA-$n.dmp_segments/aaaaab"
  printf 'a%s\n' "$n" > "$FAKE_OCI/besave-$DIA-$n.dmp_segments/aaaaaa"
done
rodar backup-diario.sh
igual "código 0" 0 "$codigo"
igual "dump 1" $'a1\nb1' "$(cat "$FAKE_S3/db/$DIA/besave-$DIA-1.dmp")"
igual "dump 10" $'a10\nb10' "$(cat "$FAKE_S3/db/$DIA/besave-$DIA-10.dmp")"
igual "S3 sem segmentos" "db/$DIA/SHA256SUMS
db/$DIA/besave-$DIA-1.dmp
db/$DIA/besave-$DIA-10.dmp
db/$DIA/besave-$DIA.log" "$(cd "$FAKE_S3" && find . -type f | sed 's#^\./##' | LC_ALL=C sort)"
rm -rf "$T"

# Layouts que não dão para remontar com segurança: falha, nada vai ao S3.
while IFS='|' read -r nome motivo; do
  caso="BKP-14b $nome"
  preparar
  echo 'Job "X" successfully completed' > "$FAKE_OCI/besave-$DIA.log"
  mkdir -p "$FAKE_OCI/besave-$DIA-100.dmp_segments"
  case $nome in
    "dump de 0 byte sem segmentos") : > "$FAKE_OCI/besave-$DIA-100.dmp" ;;
    "segmentos vazios") : > "$FAKE_OCI/besave-$DIA-100.dmp"; : > "$FAKE_OCI/besave-$DIA-100.dmp_segments/aaaaaa" ;;
    "dump com conteúdo e segmentos") echo x > "$FAKE_OCI/besave-$DIA-100.dmp"; echo y > "$FAKE_OCI/besave-$DIA-100.dmp_segments/aaaaaa" ;;
    "concatenação que perde bytes")
      : > "$FAKE_OCI/besave-$DIA-100.dmp"
      printf 'AAAAA' > "$FAKE_OCI/besave-$DIA-100.dmp_segments/aaaaaa"
      printf 'BBBBB' > "$FAKE_OCI/besave-$DIA-100.dmp_segments/aaaaab"
      FAKE_CAT_CORTA=1 ;;
  esac
  rodar backup-diario.sh
  igual "código 1" 1 "$codigo"
  contem "etapa" "$(texto_alerta)" "falhou na etapa 'cópia para o S3'"
  contem "motivo" "$(cat "$T/err")" "$motivo"
  igual "nada foi para o S3" "" "$(cd "$FAKE_S3" && find . -type f)"
  unset FAKE_CAT_CORTA
  rm -rf "$T"
done <<'CASOS'
dump de 0 byte sem segmentos|tem 0 byte e nenhum segmento
segmentos vazios|somam 0 byte
dump com conteúdo e segmentos|layout inesperado
concatenação que perde bytes|remontado tem 6 bytes; os segmentos somavam 10
CASOS

caso="BKP-14c retenção apaga os segmentos antes do .dmp de 0 byte"
preparar
: > "$FAKE_OCI/besave-20261013-100.dmp"
mkdir -p "$FAKE_OCI/besave-20261013-100.dmp_segments"
echo a > "$FAKE_OCI/besave-20261013-100.dmp_segments/aaaaaa"
echo b > "$FAKE_OCI/besave-20261013-100.dmp_segments/aaaaab"
echo x > "$FAKE_OCI/besave-20261013.log"
rodar backup-diario.sh
igual "código 0" 0 "$codigo"
igual "ordem do apagamento" "delete besave-20261013.log
delete besave-20261013-100.dmp_segments/aaaaab
delete besave-20261013-100.dmp_segments/aaaaaa
delete besave-20261013-100.dmp" "$(reg apagados.log)"
rm -rf "$T"

# ---------- BKP-15: senha que o parfile não aguenta é recusada antes de qualquer chamada ----------
bruta=('a#b' 'a b' 'a"b' "a'b" 'a@b' 'a/b' $'a\tb')
for senha in "${bruta[@]}"; do
  for script in backup-diario.sh teste-restauracao.sh; do
    caso="BKP-15 $script senha com caractere proibido"
    preparar
    EXTRA=("BACKUP_DB_PASS=$senha")
    rodar "$script"
    igual "código 2" 2 "$codigo"
    contem "diz qual variável" "$(cat "$T/err")" "BACKUP_DB_PASS"
    nao_contem "não imprime a senha" "$(cat "$T/out" "$T/err")" "$senha"
    igual "nada chamado (oci)" "" "$(reg oci.log)"
    igual "nada chamado (expdp/impdp)" "" "$(reg expdp.log)$(reg impdp.log)"
    igual "sem parfile" "" "$(reg expdp.par)$(reg impdp.par)"
    EXTRA=()
    rm -rf "$T"
  done
done

# ---------- BKP-16: backup.env com CR/espaço no fim ou nome de variável com espaço ----------
while IFS='|' read -r nome linha motivo; do
  caso="BKP-16 backup.env $nome"
  preparar
  printf '%b\n' "$linha" > "$T/real.env"
  ambiente
  env -i "${ENV[@]}" "BESAVE_BACKUP_ENV=$T/real.env" bash "$AQUI/backup-diario.sh" < /dev/null > "$T/out" 2> "$T/err"
  igual "código 2" 2 "$?"
  contem "motivo" "$(cat "$T/err")" "$motivo"
  igual "nada chamado" "" "$(reg oci.log)"
  rm -rf "$T"
done <<'CASOS'
CR no fim (arquivo do Windows)|BACKUP_S3_BUCKET=do-arquivo\r|BACKUP_S3_BUCKET termina com espaço ou CR
espaço no fim|BACKUP_DB_DSN=bsvdb_high |BACKUP_DB_DSN termina com espaço ou CR
espaço antes do igual|BACKUP_S3_BUCKET =do-arquivo|nome de variável inválido
CASOS

# ---------- ALR: rede de segurança do OnFailure= ----------
caso="ALR-01 sem aviso prévio"
preparar
rodar alerta.sh diario
igual "código 0" 0 "$codigo"
igual "um alerta" 1 "$(alertas)"
contem "texto" "$(texto_alerta)" "besave-backup-diario"
rm -rf "$T"

caso="ALR-02 o script já avisou"
preparar
: > "$T/srv/estado/alertado-diario"
rodar alerta.sh diario
igual "nenhum alerta" 0 "$(alertas)"
rm -rf "$T"

caso="ALR-03 marca antiga não vale"
preparar
: > "$T/srv/estado/alertado-diario"
touch -d '30 minutes ago' "$T/srv/estado/alertado-diario"
rodar alerta.sh diario
igual "alerta" 1 "$(alertas)"
rm -rf "$T"

caso="ALR-04 modo inválido"
preparar
rodar alerta.sh outro
igual "código 2" 2 "$codigo"
igual "nenhum alerta" 0 "$(alertas)"
rm -rf "$T"

# ---------- RES: resumo semanal ----------
caso="RES-01 resumo"
preparar
cat > "$T/srv/estado/historico.log" <<HIST
20261010 ok 999999999 10
20261015 ok 104857600 100
20261016 falha 0 0
20261017 ok 209715200 100
20261018 falha 0 0
20261018 ok 314572800 100
20261019 ok 314572800 100
20261021 falha 0 0
HIST
rodar resumo-semanal.sh
igual "código 0" 0 "$codigo"
igual "texto (janela 15..21, última linha do dia; 18 conta ok)" "text=[inst2-teste] Backup do banco: 4/7 ok na semana, último 20261019 com 300 MB. Teste de restauração: nunca rodou." "$(texto_alerta)"
rm -rf "$T"

caso="RES-02 sem histórico"
preparar
rodar resumo-semanal.sh
igual "código 0" 0 "$codigo"
contem "zero ok" "$(texto_alerta)" " 0/7 ok"
rm -rf "$T"

caso="RES-03 envio do resumo falha"
preparar
FAKE_FALHA=curl
rodar resumo-semanal.sh
igual "código 1" 1 "$codigo"
unset FAKE_FALHA
rm -rf "$T"

# ---------- RST: teste mensal de restauração ----------
contagem_boa() {
  cat > "$FAKE_CONTAGEM" <<CONT
LINHAS|OFERTA|1000|1000
LINHAS|PRODUTO|500|480
LINHAS|ENVIO_TELEGRAM|10|10
INVALIDOS|2|2
CONT
}
dumps() { for d in "$@"; do echo x > "$FAKE_OCI/besave-$d-100.dmp"; echo x > "$FAKE_OCI/besave-$d.log"; done; }
cabecalho='whenever sqlerror exit failure
connect BESAVE_BACKUP/"s3nh4-secreta"@bsvdb_high
set serveroutput on size unlimited feedback off pagesize 0 linesize 400'

caso="RST-01 teste mensal ok"
preparar
dumps 20261001 20261015 20261010
echo x > "$FAKE_OCI/besave-20261020-100.dmp" # dump sem log = export incompleto: não vale
contagem_boa
rodar teste-restauracao.sh
igual "código 0" 0 "$codigo"
igual "ordem" "prepara
impdp
contagem
limpa" "$(reg ordem.log)"
igual "parfile do import (inteiro)" "userid=BESAVE_BACKUP/s3nh4-secreta@bsvdb_high
schemas=BESAVE
remap_schema=BESAVE:BESAVE_RESTORE
credential=BACKUP_OCI_CRED
dumpfile=https://ns.example/o/besave-20261015-%L.dmp
parallel=1
transform=segment_attributes:n
exclude=cluster,db_link
directory=data_pump_dir
logfile=restore-20261015.log" "$(reg impdp.par)"
igual "impdp (comando inteiro)" "impdp parfile=<TMP>/imp.par" "$(reg impdp.log | norm)"
igual "sqlplus (comando inteiro)" "sqlplus -S -L /nolog
sqlplus -S -L /nolog
sqlplus -S -L /nolog" "$(reg sqlplus.log)"
sqls=$(reg sql.log)
contem "preparar" "$sqls" "$cabecalho
exec ADMIN.BACKUP_PREPARA_RESTORE
====="
contem "limpar" "$sqls" "$cabecalho
exec ADMIN.BACKUP_LIMPA_RESTORE
====="
contem "contagem só lê" "$sqls" "FROM dba_tables"
nao_contem "contagem não escreve" "$sqls" "INSERT"
nao_contem "contagem não apaga" "$sqls" "DELETE"
igual "um aviso de sucesso" 1 "$(alertas)"
contem "aviso" "$(texto_alerta)" "Teste de restauração ok: dump de 20261015, 3 tabelas"
igual "registro do último teste" "$(date +%Y%m%d) ok 20261015" "$(cat "$T/srv/estado/ultimo-teste.txt")"
igual "pasta temporária apagada" "" "$(ls -d "$T"/tmp.* 2> /dev/null)"
rm -rf "$T"

# Divergências: cada uma deve falhar o teste, alertar e ainda apagar BESAVE_RESTORE.
while IFS='|' read -r nome linhas; do
  caso="RST-02 $nome"
  preparar
  dumps 20261015
  printf '%b\n' "$linhas" > "$FAKE_CONTAGEM"
  rodar teste-restauracao.sh
  igual "código 1" 1 "$codigo"
  contem "etapa" "$(texto_alerta)" "falhou na etapa 'comparar contagens'"
  igual "ainda limpa o schema" "prepara
impdp
contagem
limpa" "$(reg ordem.log)"
  [ ! -e "$T/srv/estado/ultimo-teste.txt" ] || falhou "gravou último teste ok numa falha"
  rm -rf "$T"
done <<'DIVERGE'
restore com poucas linhas|LINHAS|OFERTA|1000|900\nINVALIDOS|0|0
restore com linhas demais|LINHAS|OFERTA|1000|1100\nINVALIDOS|0|0
tabela ausente no restore|LINHAS|OFERTA|1000|-1\nINVALIDOS|0|0
tabela pequena ausente no restore|LINHAS|FILA|5|-1
INVALIDOS|0|0
tabela pequena fora do mínimo|LINHAS|FILA|100|50\nINVALIDOS|0|0
mais inválidos que a origem|LINHAS|OFERTA|1000|1000\nINVALIDOS|1|2
sem tabelas|INVALIDOS|0|0
sem linha de inválidos|LINHAS|OFERTA|1000|1000
DIVERGE

caso="RST-03 tolerância: exatamente no limite passa"
preparar
dumps 20261015
printf 'LINHAS|OFERTA|1000|950\nLINHAS|FILA|100|80\nINVALIDOS|3|1\n' > "$FAKE_CONTAGEM"
rodar teste-restauracao.sh
igual "5% e mínimo de 20 passam" 0 "$codigo"
rm -rf "$T"

caso="RST-04 passo do limite falha"
preparar
dumps 20261015
printf 'LINHAS|OFERTA|1000|949\nINVALIDOS|0|0\n' > "$FAKE_CONTAGEM"
rodar teste-restauracao.sh
igual "949 de 1000 falha" 1 "$codigo"
rm -rf "$T"

while IFS='|' read -r falha etapa ordem; do
  caso="RST-05 falha $falha"
  preparar
  dumps 20261015
  contagem_boa
  FAKE_FALHA=$falha
  rodar teste-restauracao.sh
  igual "código 1" 1 "$codigo"
  igual "um alerta" 1 "$(alertas)"
  contem "etapa" "$(texto_alerta)" "falhou na etapa '$etapa'"
  igual "ordem (sempre limpa o schema de teste)" "$(printf '%b' "$ordem")" "$(reg ordem.log)"
  unset FAKE_FALHA
  rm -rf "$T"
done <<'CASOS'
prepara|preparar BESAVE_RESTORE|prepara\nlimpa
impdp|importar (Data Pump)|prepara\nimpdp\nlimpa
contagem|comparar contagens|prepara\nimpdp\ncontagem\nlimpa
limpa:1|apagar BESAVE_RESTORE|prepara\nimpdp\ncontagem\nlimpa\nlimpa
oci_list|escolher o último dump|
CASOS

caso="RST-06 sem dump completo"
preparar
echo x > "$FAKE_OCI/besave-20261015-100.dmp"
rodar teste-restauracao.sh
igual "código 1" 1 "$codigo"
contem "etapa" "$(texto_alerta)" "escolher o último dump"
igual "nada do banco foi tocado" "" "$(reg ordem.log)"
rm -rf "$T"

echo "$((total - falhas)) de $total verificações ok"
if [ "$falhas" -gt 0 ]; then
  echo "$falhas falha(s)"
  exit 1
fi
