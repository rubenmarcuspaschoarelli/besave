import sys
from pathlib import Path

import falsos
import pytest

TOOLS = Path(__file__).resolve().parent.parent
LOJAS = TOOLS / "capture-store-pages"
CHAT = TOOLS / "capture-chat-groups"

for p in (LOJAS, CHAT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


class Loja:
    ready_selector = None
    post_load_wait = 0
    baixar_imagens = False

    def prepare(self, page):
        pass

    def pagina_sem_produto(self, page):
        return False

    def status_descarte(self, page):
        return None

    def capture(self, page):
        return {}


@pytest.fixture
def lojas(monkeypatch):
    antes = set(sys.modules)
    falsos.instalar(monkeypatch)
    from core import estado
    monkeypatch.setattr(estado, "ler_raiz_s3", lambda *a, **k: "/s3-falso")
    mod = falsos.importar(monkeypatch, "main_lojas", LOJAS / "main.py")
    for nome, valor in [("resolver_loja", lambda url: "AMAZON"), ("get_store", lambda loja: Loja()),
                        ("loja_ativa", lambda *a: True)]:
        monkeypatch.setattr(mod.registry, nome, valor)
    monkeypatch.setattr(mod, "_goto_robusto", lambda *a, **k: None)
    monkeypatch.setattr(mod.afiliados, "gerar_url", lambda *a: "")
    monkeypatch.setattr(mod.afiliados, "loja_ativa", lambda *a: False)
    monkeypatch.setattr(mod.link_afiliado, "capturar", lambda *a: {})
    monkeypatch.setattr(mod.link_afiliado, "habilitado", lambda: False)
    monkeypatch.setattr(mod.imagens_oferta, "tem_imagem_publicada", lambda i: True)
    monkeypatch.setattr(mod.estado, "usa_imagem_loja", lambda g: False)
    mod.ponteiro = []
    monkeypatch.setattr(mod.estado, "gravar_ultimo_id", mod.ponteiro.append)
    yield mod
    for nome in set(sys.modules) - antes:
        if nome != "core.janela":
            sys.modules.pop(nome, None)
