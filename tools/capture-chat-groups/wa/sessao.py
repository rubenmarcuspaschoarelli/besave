"""
Sessao do WhatsApp Web: copia guardada e entrada sem operador (BSV-67).

O reinicio programado (tools/vps/reiniciar_whatsapp.sh) guarda `user_data.copia/` de uma sessao sabidamente
boa. Caindo na tela de login, o robo restaura essa copia UMA vez (marca `restaurada_em` no diretorio da copia)
e, se nao resolver, pede o codigo de pareamento (wa/pareamento.py). Nunca apaga `user_data/`: move para
`user_data.qr/` (fica para diagnostico). A copia so e lida com o contexto fechado pelo proprio robo.
"""

import os
import shutil
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from . import pareamento

RAIZ = Path(__file__).resolve().parent.parent
USER_DATA, COPIA, QR_DIR = "user_data", "user_data.copia", "user_data.qr"
MARCA_COPIADA, MARCA_RESTAURADA = "copiada_em", "restaurada_em"
BRASILIA = timezone(timedelta(hours=-3))
FMT = "%Y-%m-%dT%H:%M:%SZ"


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime(FMT)


def msg_restaurada(data: datetime) -> str:
    return f"WhatsApp: sessao perdida e restaurada da copia de {data.astimezone(BRASILIA):%d/%m %H:%M} (sem acao)."


def copia_disponivel(raiz=RAIZ) -> bool:
    copia = Path(raiz) / COPIA
    return copia.is_dir() and not (copia / MARCA_RESTAURADA).exists()


def data_da_copia(raiz=RAIZ) -> datetime:
    """`copiada_em` gravado pelo script do reinicio; sem ele, o mtime do diretorio."""
    copia = Path(raiz) / COPIA
    try:
        return datetime.strptime((copia / MARCA_COPIADA).read_text(encoding="utf-8").strip(), FMT).replace(tzinfo=UTC)
    except (OSError, ValueError):
        return datetime.fromtimestamp(copia.stat().st_mtime, UTC)


def restaurar(raiz, agora: datetime) -> None:
    """Marca a tentativa, move `user_data/` para `user_data.qr/` (substitui a anterior) e copia a copia de volta."""
    raiz = Path(raiz)
    copia, perfil, qr = raiz / COPIA, raiz / USER_DATA, raiz / QR_DIR
    (copia / MARCA_RESTAURADA).write_text(_iso(agora), encoding="utf-8")   # antes de tudo: nunca em laco
    if qr.exists():
        shutil.rmtree(qr)
    if perfil.exists():
        os.replace(perfil, qr)
    marcas = {MARCA_COPIADA, MARCA_RESTAURADA}
    shutil.copytree(copia, perfil,
                    ignore=lambda d, nomes: [n for n in nomes if Path(d) == copia and n in marcas])


def entrar(lancar, cfg, avisar, bater, raiz=RAIZ, agora=pareamento.agora_utc,
           tela_de=pareamento.TelaWhatsApp, teto=None, vinculo_de=pareamento.Vinculo):
    """
    `lancar()` -> (context, page) com o WhatsApp Web aberto. Devolve (context, page) ja logado:
    logado direto; senao restaura a copia (uma vez) e, se ainda pedir login, espera o vinculo pelo codigo.
    Sem tela conhecida em 5 min -> TimeoutError (o systemd religa, como antes).
    """
    context, page = lancar()
    tela = tela_de(page)
    if tela.esperar() == pareamento.LOGADO:
        return context, page
    if copia_disponivel(raiz):
        data = data_da_copia(raiz)
        print(f"[sessao] tela de login; restaurando a copia de {_iso(data)}")
        try:
            context.close()
        except Exception as e:  # noqa: BLE001
            print(f"[sessao] contexto ja fechado ({type(e).__name__})")
        try:
            restaurar(raiz, agora())
        except Exception as e:  # noqa: BLE001
            print(f"[sessao] falha ao restaurar a copia ({type(e).__name__}: {e}); segue para o codigo.")
        context, page = lancar()
        tela = tela_de(page)
        if tela.esperar() == pareamento.LOGADO:
            print("[sessao] copia restaurada; sessao ok")
            avisar(msg_restaurada(data))
            return context, page
        print("[sessao] a copia tambem caiu na tela de login.")
    numero, validade = pareamento.ler_config(cfg)
    vinculo_de(tela, numero, validade, teto or pareamento.Teto(), avisar, bater).aguardar()
    return context, page
