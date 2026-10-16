#!/usr/bin/env bash
# Teste do instalar.sh (BSV-43, INS-01..05) com um `gh` falso: sem rede, sem GitHub.
# Uso: bash infra/vps/teste_instalar.sh
set -uo pipefail

AQUI=$(cd "$(dirname "$0")" && pwd)
SCRIPT="$AQUI/instalar.sh"
BINARIOS=(besave-ciclo besave-envio besave-worker)
SHA=abcdef1234567890abcdef1234567890abcdef12
REPO=dono/besave
falhas=0

falhou() { echo "FALHOU: $caso: $*"; falhas=$((falhas + 1)); }

# Pasta nova com: bin/ (binários antigos), art/ (artefato com SHA256SUMS), fake/gh.
preparar() {
  T=$(mktemp -d)
  mkdir -p "$T/bin" "$T/art" "$T/fake"
  for b in "${BINARIOS[@]}"; do
    printf '#!/bin/sh\necho velho %s\n' "$b" > "$T/bin/$b"
    printf '#!/bin/sh\necho novo %s\n' "$b" > "$T/art/$b"
  done
  (cd "$T/art" && sha256sum "${BINARIOS[@]}" > SHA256SUMS)
  cat > "$T/fake/gh" <<'EOF'
#!/usr/bin/env bash
# gh falso: registra a linha de comando e responde como o gh real responderia ao --jq do script.
echo "$*" >> "$FAKE_LOG"
case "$1 $2" in
  "run list") printf '%s\n' "$FAKE_RUN_LIST" ;;
  "run view") printf '%s\t%s\t%s\n' "$FAKE_SHA" "$FAKE_RAMO" "$FAKE_EVENTO" ;;
  "run download")
    nome="" dir=""
    while [ $# -gt 0 ]; do
      case "$1" in -n) nome=$2; shift ;; -D) dir=$2; shift ;; esac
      shift
    done
    [ "$nome" = "worker-linux-arm64-${FAKE_SHA:0:7}" ] || { echo "artefato $nome não encontrado" >&2; exit 1; }
    cp "$FAKE_ART"/* "$dir"/ ;;
  *) echo "gh falso: comando inesperado: $*" >&2; exit 99 ;;
esac
EOF
  chmod +x "$T/fake/gh"
  : > "$T/gh.log"
  export FAKE_LOG="$T/gh.log" FAKE_ART="$T/art" FAKE_SHA="$SHA" FAKE_RAMO=main FAKE_EVENTO=push FAKE_RUN_LIST=4242
  ANTES=$(foto)
}

# Nome, tamanho e hash de tudo em bin/ (inclui ocultos: pega sobra de pasta temporária).
foto() { (cd "$T/bin" && find . -mindepth 1 | sort && find . -type f -exec sha256sum {} + | sort); }

rodar() {
  PATH="$T/fake:$PATH" BESAVE_BIN="$T/bin" BESAVE_REPO="$REPO" \
    bash "$SCRIPT" "$@" > "$T/out" 2> "$T/err"
  codigo=$?
}

intacto() {
  [ "$(foto)" = "$ANTES" ] || falhou "bin/ mudou: $(ls -la "$T/bin")"
}

instalado() {
  local id=$1
  for b in "${BINARIOS[@]}"; do
    cmp -s "$T/bin/$b" "$T/art/$b" || falhou "$b não é o do artefato"
    [ -x "$T/bin/$b" ] || falhou "$b não é executável"
  done
  grep -qx "execucao=$id" "$T/bin/VERSAO" || falhou "VERSAO sem execucao=$id"
  grep -qx "commit=$SHA" "$T/bin/VERSAO" || falhou "VERSAO sem commit=$SHA"
  local sobra
  sobra=$(find "$T/bin" -mindepth 1 -name '.*')
  [ -z "$sobra" ] || falhou "sobra temporária: $sobra"
}

# INS-01: sem argumento → última execução success, push, main, do worker-arm64.yml.
caso="INS-01 sem argumento"; preparar
rodar
[ "$codigo" = 0 ] || falhou "código $codigo: $(cat "$T/err")"
esperado="run list -R $REPO --workflow worker-arm64.yml --branch main --event push --status success --limit 1 --json databaseId --jq .[0].databaseId"
[ "$(sed -n 1p "$T/gh.log")" = "$esperado" ] || falhou "run list: $(sed -n 1p "$T/gh.log")"
grep -qx "run download 4242 -R $REPO -n worker-linux-arm64-abcdef1 -D .*" "$T/gh.log" || falhou "download: $(cat "$T/gh.log")"
instalado 4242
[ ! -s "$T/err" ] || falhou "aviso indevido em push/main: $(cat "$T/err")"

# INS-01 (borda): nenhuma execução success em main → falha clara, nada baixado, bin/ intacto.
caso="INS-01 sem execução"; preparar
FAKE_RUN_LIST="" rodar
[ "$codigo" != 0 ] || falhou "código 0"
grep -q "run download" "$T/gh.log" && falhou "baixou sem execução"
grep -qi "nenhuma execução" "$T/err" || falhou "mensagem: $(cat "$T/err")"
intacto

# INS-02 + INS-03: ID explícito de push em main → instala, sem aviso.
caso="INS-02 ID de main"; preparar
rodar 123
[ "$codigo" = 0 ] || falhou "código $codigo: $(cat "$T/err")"
grep -q "run list" "$T/gh.log" && falhou "listou com ID dado"
grep -qx "run download 123 -R $REPO -n worker-linux-arm64-abcdef1 -D .*" "$T/gh.log" || falhou "download: $(cat "$T/gh.log")"
instalado 123
[ ! -s "$T/err" ] || falhou "aviso indevido: $(cat "$T/err")"

# INS-02: execução de pull_request → instala e avisa que é só para teste.
caso="INS-02 ID de PR"; preparar
FAKE_EVENTO=pull_request FAKE_RAMO=rubenmarcus/bsv-43 rodar 555
[ "$codigo" = 0 ] || falhou "código $codigo: $(cat "$T/err")"
instalado 555
grep -q "teste" "$T/err" || falhou "sem aviso de teste: $(cat "$T/err")"

# INS-02: push em outro ramo também avisa.
caso="INS-02 push fora de main"; preparar
FAKE_RAMO=develop rodar 556
[ "$codigo" = 0 ] || falhou "código $codigo"
grep -q "teste" "$T/err" || falhou "sem aviso de teste: $(cat "$T/err")"

# INS-04: hash que não confere.
caso="INS-04 hash errado"; preparar
printf 'adulterado\n' >> "$T/art/besave-envio"
rodar 123
[ "$codigo" != 0 ] || falhou "código 0"
intacto

# INS-04: binário listado no SHA256SUMS mas ausente do artefato.
caso="INS-04 binário ausente"; preparar
rm "$T/art/besave-worker"
rodar 123
[ "$codigo" != 0 ] || falhou "código 0"
intacto

# INS-04: SHA256SUMS que não lista um dos 3 (o resto confere).
caso="INS-04 SHA256SUMS incompleto"; preparar
grep -v 'besave-ciclo$' "$T/art/SHA256SUMS" > "$T/s" && mv "$T/s" "$T/art/SHA256SUMS"
rodar 123
[ "$codigo" != 0 ] || falhou "código 0"
intacto

# INS-04 (borda): artefato expirado/inexistente → `gh run download` falha.
caso="INS-04 artefato inexistente"; preparar
FAKE_ART="$T/nada" rodar 123
[ "$codigo" != 0 ] || falhou "código 0"
intacto

# INS-05: argumento que não é número, ou mais de um → 2 sem chamar o gh.
for args in "abc" "12a" "-1" "1 2"; do
  caso="INS-05 argumento '$args'"; preparar
  # shellcheck disable=SC2086 # separar "1 2" é o caso
  rodar $args
  [ "$codigo" = 2 ] || falhou "código $codigo"
  [ ! -s "$T/gh.log" ] || falhou "chamou o gh: $(cat "$T/gh.log")"
  intacto
done

if [ "$falhas" -gt 0 ]; then
  echo "$falhas falha(s)"
  exit 1
fi
echo "ok: teste_instalar"
