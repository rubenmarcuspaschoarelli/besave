#!/usr/bin/env bash
# shellcheck disable=SC2034  # CMD e lido por quem carrega este arquivo
# Trecho comum dos lancadores dos robos (BSV-54, BSV-57): o robo roda num scope systemd-run dentro do painel do
# tmux. Uso: `source scope.sh` depois de definir SYSTEMCTL, SYSTEMD_RUN e a funcao `falhar` (sai com ABORTADO).
#
#   scope_preparar NOME   recusa subir se o scope NOME.scope esta ativo; senao limpa o residuo
#                         (reset-failed e revert; erros ignorados)
#   scope_montar NOME [-p PROP]... -- CMD...   preenche o array CMD com o systemd-run do scope
#                         (--collect, KillSignal=SIGINT, TimeoutStopSec=30); sem systemd-run, so o CMD

scope_preparar() {
    local nome=$1
    if "$SYSTEMCTL" --user is-active --quiet "$nome.scope" 2>/dev/null; then
        falhar "o scope $nome.scope ainda existe (robo anterior vivo?): subir outro duplicaria o robo. Rode systemctl --user stop $nome.scope."
    fi
    # Scope que terminou em `failed` (OOM-kill, kill -9) fica carregado e o proximo systemd-run com o mesmo
    # --unit falha ("already loaded"). Com o scope NAO ativo (conferido acima), limpa o residuo e o que sobrou
    # de `set-property --runtime`; erros ignorados (scope inexistente).
    "$SYSTEMCTL" --user reset-failed "$nome.scope" >/dev/null 2>&1 || true
    "$SYSTEMCTL" --user revert "$nome.scope" >/dev/null 2>&1 || true
}

scope_montar() {
    local nome=$1
    shift
    local props=()
    while [ $# -gt 0 ] && [ "$1" != "--" ]; do
        props+=("$1")
        shift
    done
    shift
    # --collect: o scope e descarregado ao terminar, mesmo em `failed`; sem isso o 1o OOM-kill deixaria todo
    # systemd-run seguinte falhando com "already loaded", em laco.
    # O rc do systemd-run --scope e o do proprio robo (ele vira o processo do scope): OOM-kill = rc != 0.
    if command -v "$SYSTEMD_RUN" >/dev/null 2>&1; then
        CMD=("$SYSTEMD_RUN" --user --scope --collect "--unit=$nome" ${props[@]+"${props[@]}"} \
            -p KillSignal=SIGINT -p TimeoutStopSec=30 -- "$@")
    else
        echo "AVISO: systemd-run nao encontrado; subindo SEM teto de memoria e sem scope." >&2
        CMD=("$@")
    fi
}
