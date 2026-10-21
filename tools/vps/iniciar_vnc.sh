#!/usr/bin/env bash
# Sobe a tela remota :N (TigerVNC) em primeiro plano. Uso: iniciar_vnc.sh N
#   tela 1  : Xfce completo (xstartup-xfce.sh)
#   outras  : so o gerenciador de janelas (xstartup-leve.sh), sem 2a sessao Xfce
# Cada tela tem o proprio barramento dbus (dbus-run-session nos xstartup).
#
# Recusa subir sem senha do VNC: o TigerVNC 1.13 (Ubuntu 24.04) le
# ~/.config/tigervnc/passwd e as versoes antigas ~/.vnc/passwd; vale qualquer um dos dois.
# Sem nenhum, sai com 78, que a unidade (RestartPreventExitStatus=78) trata como "nao reiniciar".
#
# Env (testes): BESAVE_VNCSERVER.

set -u

AQUI=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

tela=${1:-}
case "$tela" in
    [1-9] | [1-9][0-9]) ;;
    *) echo "uso: $0 N   (numero da tela, ex.: 1)" >&2; exit 2 ;;
esac

if [ ! -s "$HOME/.config/tigervnc/passwd" ] && [ ! -s "$HOME/.vnc/passwd" ]; then
    echo "ABORTADO: sem senha do VNC (procurei ~/.config/tigervnc/passwd e ~/.vnc/passwd)." >&2
    echo "Rode 'vncpasswd' (interativo) como o usuario besave e suba a unidade de novo." >&2
    exit 78
fi

if [ "$tela" = 1 ]; then
    xstartup=$AQUI/xstartup-xfce.sh
else
    xstartup=$AQUI/xstartup-leve.sh
fi

exec "${BESAVE_VNCSERVER:-/usr/bin/vncserver}" ":$tela" -fg -localhost yes \
    -geometry 1600x900 -xstartup "$xstartup"
