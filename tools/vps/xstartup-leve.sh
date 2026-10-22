#!/bin/sh
# xstartup das demais telas (WhatsApp): so o gerenciador de janelas do Xfce (xfwm4),
# sem painel nem segunda sessao Xfce, com barramento dbus proprio.
exec dbus-run-session -- /usr/bin/xfwm4
