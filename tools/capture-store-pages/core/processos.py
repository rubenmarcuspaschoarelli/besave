"""Processos do navegador no Windows (so la existe Chrome de usuario aberto).

No Linux (VPS) o robo usa o Chromium do Playwright num perfil dedicado, entao
nao ha janela do usuario para conferir nem para fechar: tudo aqui vira no-op.
"""
import subprocess
import sys


def _windows(plataforma=None):
    return (plataforma or sys.platform) == 'win32'


def chrome_aberto(plataforma=None):
    # True se houver algum processo chrome.exe (janela do usuario) em execucao.
    if not _windows(plataforma):
        return False
    try:
        out = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq chrome.exe', '/NH'],
            capture_output=True, text=True, check=False,
        ).stdout.lower()
        return 'chrome.exe' in out
    except OSError:
        return False


def fechar_chrome_forcado(plataforma=None):
    if not _windows(plataforma):
        return
    subprocess.run(['taskkill', '/IM', 'chrome.exe', '/F'], capture_output=True, check=False)
