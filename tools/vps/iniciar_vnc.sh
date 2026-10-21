#!/usr/bin/env bash
# Sobe a tela remota :N (Xfce sobre TigerVNC) em primeiro plano. Uso: iniciar_vnc.sh N
#
# Recusa subir sem senha do VNC (~/.vnc/passwd): sai com 78, que a unidade
# (RestartPreventExitStatus=78) trata como "nao reiniciar". Sem isso o systemd
# reiniciava a cada 10 s sem dizer por que.
#
# Env (testes): BESAVE_VNC_PASSWD (arquivo da senha), BESAVE_VNCSERVER.

set -u

tela=${1:-}
case "$tela" in
    [1-9] | [1-9][0-9]) ;;
    *) echo "uso: $0 N   (numero da tela, ex.: 1)" >&2; exit 2 ;;
esac

senha=${BESAVE_VNC_PASSWD:-$HOME/.vnc/passwd}
if [ ! -s "$senha" ]; then
    echo "ABORTADO: sem senha do VNC em $senha." >&2
    echo "Rode 'vncpasswd' (interativo) como o usuario besave e suba a unidade de novo." >&2
    exit 78
fi

exec "${BESAVE_VNCSERVER:-/usr/bin/vncserver}" ":$tela" -fg -localhost yes \
    -geometry 1600x900 -xstartup /usr/bin/startxfce4
