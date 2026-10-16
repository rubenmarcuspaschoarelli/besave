#!/usr/bin/env bash
# Instala na VPS os binários Linux ARM64 do worker gerados pelo workflow worker-arm64.yml (BSV-43).
# Nada é compilado aqui. Uso (como o usuário besave, com `gh auth login` feito):
#   instalar.sh            última execução ok de push em main (produção, AD-060)
#   instalar.sh <ID>       uma execução específica: reverter, ou testar a PR antes do merge
# Variáveis: BESAVE_BIN (padrão /srv/besave/bin), BESAVE_REPO (padrão rubenmarcuspaschoarelli/besave).
set -euo pipefail

BIN=${BESAVE_BIN:-/srv/besave/bin}
REPO=${BESAVE_REPO:-rubenmarcuspaschoarelli/besave}
WORKFLOW=worker-arm64.yml
BINARIOS=(besave-ciclo besave-envio besave-worker)

erro() { echo "instalar.sh: $*" >&2; exit 1; }

if [ $# -gt 1 ] || { [ $# -eq 1 ] && ! [[ $1 =~ ^[0-9]+$ ]]; }; then
  echo "uso: instalar.sh [ID da execução do $WORKFLOW]" >&2
  exit 2
fi
[ -d "$BIN" ] || erro "pasta $BIN não existe (docs/infra/VPS-INSTANCIA-1.md, Fase 2)"

if [ $# -eq 1 ]; then
  id=$1
else
  id=$(gh run list -R "$REPO" --workflow "$WORKFLOW" --branch main --event push --status success \
    --limit 1 --json databaseId --jq '.[0].databaseId')
  [ -n "$id" ] && [ "$id" != null ] || erro "nenhuma execução ok do $WORKFLOW em main"
fi

IFS=$'\t' read -r sha ramo evento < <(gh run view "$id" -R "$REPO" \
  --json headSha,headBranch,event --jq '[.headSha, .headBranch, .event] | @tsv')
[[ ${sha:-} =~ ^[0-9a-f]{40}$ ]] || erro "execução $id sem commit válido"
if [ "$ramo" != main ] || [ "$evento" != push ]; then
  echo "AVISO: execução $id é $evento em $ramo, não push em main: só para o teste real antes do merge (AD-060)" >&2
fi

# Pasta temporária dentro de BIN: o `mv` final é um rename no mesmo sistema de arquivos.
tmp=$(mktemp -d "$BIN/.instalar.XXXXXX")
trap 'rm -rf "$tmp"' EXIT

gh run download "$id" -R "$REPO" -n "worker-linux-arm64-${sha:0:7}" -D "$tmp"

[ -f "$tmp/SHA256SUMS" ] || erro "artefato sem SHA256SUMS"
for b in "${BINARIOS[@]}"; do
  grep -Eq "^[0-9a-f]{64} [ *]$b\$" "$tmp/SHA256SUMS" || erro "SHA256SUMS não lista $b"
  [ -f "$tmp/$b" ] || erro "artefato sem $b"
done
(cd "$tmp" && sha256sum --strict --quiet -c SHA256SUMS) || erro "SHA256SUMS não confere"

# O zip do artefato não guarda a permissão de execução.
for b in "${BINARIOS[@]}"; do chmod 755 "$tmp/$b"; done
printf 'execucao=%s\ncommit=%s\nramo=%s\nevento=%s\ninstalado_em=%s\n' \
  "$id" "$sha" "$ramo" "$evento" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$tmp/VERSAO"

# Cada rename é atômico: um timer nunca executa binário pela metade; quem já roda segue com o antigo.
for f in "${BINARIOS[@]}" VERSAO; do mv -f "$tmp/$f" "$BIN/$f"; done

echo "instalado: execução $id, commit ${sha:0:7} ($evento em $ramo), em $BIN"
