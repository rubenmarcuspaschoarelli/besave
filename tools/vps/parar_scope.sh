#!/usr/bin/env bash
# Parada do robo das lojas pelo operador/systemd (BSV-57): SIGINT SO no python do scope, espera ele sair e so
# depois para o scope.
#
# Por que: `systemctl stop scope` manda SIGINT a TODOS os processos do scope, inclusive ao node do Playwright.
# O driver morre antes do python, `BrowserContext.close` estoura ("Connection closed while reading from the
# driver") e o python sai com 1: a unidade ficava em `failed` e o vigia a tratava como queda. Com SIGINT so no
# python, ele fecha o contexto pelo driver vivo e sai limpo (unidade `inactive`). Python congelado
# (kill -STOP) nao trata o SIGINT: vencido o prazo, o `stop` do scope manda SIGINT a todos e, em 30 s, SIGKILL.
#
# Uso: parar_scope.sh NOME_DO_SCOPE_SEM_.scope [PRAZO_S]     (sempre sai 0: e ExecStop)
# Env (testes): BESAVE_SYSTEMCTL, BESAVE_KILL, BESAVE_SLEEP, BESAVE_CGROUP_RAIZ, BESAVE_PROC_RAIZ,
# BESAVE_PARAR_PRAZO_S (padrao 20).

set -u

NOME=${1:?uso: parar_scope.sh NOME_DO_SCOPE [PRAZO_S]}
PRAZO=${2:-${BESAVE_PARAR_PRAZO_S:-20}}
SYSTEMCTL=${BESAVE_SYSTEMCTL:-systemctl}
KILL=${BESAVE_KILL:-kill}
DORMIR=${BESAVE_SLEEP:-sleep}
CGROUP_RAIZ=${BESAVE_CGROUP_RAIZ:-/sys/fs/cgroup}
PROC_RAIZ=${BESAVE_PROC_RAIZ:-/proc}

cg=$("$SYSTEMCTL" --user show -p ControlGroup --value "$NOME.scope" 2>/dev/null)
procs="$CGROUP_RAIZ$cg/cgroup.procs"
if [ -n "$cg" ] && [ "$cg" != "/" ] && [ -r "$procs" ]; then
    while read -r pid; do
        comm=$(cat "$PROC_RAIZ/$pid/comm" 2>/dev/null) || continue
        case "$comm" in
        python*) "$KILL" -INT "$pid" 2>/dev/null || true ;;
        esac
    done <"$procs"
    i=0
    while [ "$i" -lt "$PRAZO" ] && "$SYSTEMCTL" --user is-active --quiet "$NOME.scope" 2>/dev/null; do
        "$DORMIR" 1
        i=$((i + 1))
    done
fi
"$SYSTEMCTL" --user stop "$NOME.scope" >/dev/null 2>&1 || true
exit 0
