"""Publicador do canal do WhatsApp (BSV-63).

    python main.py                laco: uma volta a cada intervalo_minutos (+-30%)
    python main.py --uma-volta    uma volta e sai (teste real)
    python main.py --gravar-dom   abre o WhatsApp Web, espera 60 s e grava dom/whatsapp_<hora>.html redigido
                                  (conferir os seletores; revisar o arquivo antes de versionar)

Codigos de saida: 0 normal, 1 navegador morto/erro inesperado (o systemd reinicia), 2 config ausente ou
ilegivel na partida, 130 parado por SIGINT (SuccessExitStatus da unidade).
"""

import argparse
import random
import sys
import time
from datetime import datetime
from pathlib import Path

from pub import avisos, canal_web, config, fila, foto
from pub.batimento import Batimento
from pub.publicador import MARCA_AUTENTICADO, MARCA_ESPERANDO, OK, Publicador, agora_utc

RAIZ = Path(__file__).resolve().parent
PERFIL = RAIZ / ".chrome_perfil"


def log(texto: str) -> None:
    print(f"[{datetime.now():%d/%m %H:%M:%S}] {texto}", flush=True)


def abrir_navegador(p):
    """Contexto persistente (QR lido uma vez, pelo VNC). Perfil proprio: nunca o da captura."""
    ctx = p.chromium.launch_persistent_context(str(PERFIL), headless=False, viewport={"width": 1280, "height": 900})
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(canal_web.WHATSAPP_URL, wait_until="domcontentloaded")
    return ctx, page


def gravar_dom(page) -> Path:
    page.wait_for_timeout(60_000)
    destino = RAIZ / "dom" / f"whatsapp_{datetime.now():%Y%m%d_%H%M%S}.html"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(canal_web.redigir_dom(page.content()), encoding="utf-8")
    return destino


def main(argv=None) -> int:
    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument("--uma-volta", action="store_true")
    args.add_argument("--gravar-dom", action="store_true")
    a = args.parse_args(argv)

    try:
        cfg = config.carregar()
    except config.ErroConfig as e:
        log(f"ABORTADO: {e} (copie conf/config.example.json para conf/config.json, modo 600)")
        return 2
    aviso = config.aviso_permissao()
    if aviso:
        log(f"WARN {aviso}")

    token, chat = avisos.credenciais()
    avisar = avisos.Avisador(token, chat, log=log)
    banco = fila.Fila(lambda: fila.conectar_real(cfg.oracle), log=log)

    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            log(f"{MARCA_ESPERANDO}... (se aparecer o QR, ler pelo VNC com o numero de publicacao)")
            ctx, page = abrir_navegador(p)
            try:
                return _rodar(a, page, banco, avisar)
            finally:
                try:
                    ctx.close()
                except Exception as e:  # noqa: BLE001 - navegador ja morto
                    log(f"fechar o navegador falhou ({type(e).__name__})")
    except KeyboardInterrupt:
        log("parado (SIGINT)")
        return 130
    finally:
        banco.fechar()


def _rodar(a, page, banco, avisar) -> int:
    if a.gravar_dom:
        log(f"DOM gravado em {gravar_dom(page)}; revisar antes de versionar")
        return 0
    pagina = canal_web.CanalWeb(page, log=log, pasta_log=RAIZ / "log")
    if pagina.sessao() == OK:
        log(MARCA_AUTENTICADO)
    pub = Publicador(
        fila=banco, pagina=pagina, avisar=avisar, relogio=agora_utc,
        carregar_config=config.carregar,
        preparar_foto=lambda i, slug, destino: foto.preparar(i, slug, destino, log=log),
        batimento=Batimento(log=log), aleatorio=random.random, pasta_tmp=RAIZ / "tmp", log=log)
    if a.uma_volta:
        pub.volta()
        return 0
    return pub.rodar(time.sleep)


if __name__ == "__main__":
    sys.exit(main())
