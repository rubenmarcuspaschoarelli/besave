"""BSV-55 SEM-01..03: partida pelo systemd sem ninguem no terminal (incidente de 02-05/11)."""
import contextlib
import sys

import pytest


class Pagina:
    url = "about:blank"

    def goto(self, url, **k):
        self.url = url

    def wait_for_timeout(self, ms):
        pass

    def set_default_timeout(self, ms):
        pass

    def is_closed(self):
        return False


class Contexto:
    def new_page(self):
        return Pagina()

    def grant_permissions(self, *a, **k):
        pass

    def close(self):
        pass


class Db:
    habilitado = True

    def conectar(self):
        return True

    def desconectar(self):
        pass


class StdinQueFalha:
    """Terminal 'presente' (isatty) mas qualquer leitura derruba o teste."""

    def isatty(self):
        return True

    def read(self, *a):
        raise AssertionError("stdin lido")

    readline = read


class Varredura(Exception):
    pass


def _arranque(lojas, monkeypatch, argv, respostas=None):
    """Roda main() ate a 1a leitura da fila do monitor. Devolve (perguntas, chegou_na_varredura)."""
    perguntas = []

    def input_falso(msg=""):
        perguntas.append(msg)
        if respostas is None:
            raise AssertionError(f"input() chamado: {msg}")
        return respostas.pop(0) if respostas else "n"

    monkeypatch.setattr("builtins.input", input_falso)
    monkeypatch.setattr(sys, "stdin", StdinQueFalha())
    monkeypatch.setattr(sys, "argv", ["main.py", *argv])
    monkeypatch.setattr(lojas, "OracleDB", Db)
    monkeypatch.setattr(lojas.afiliados, "carregar", lambda db: None)
    monkeypatch.setattr(lojas, "_recuperar_publicacoes", lambda *a: None)
    monkeypatch.setattr(lojas, "_varrer_validade", lambda db: None)
    monkeypatch.setattr(lojas.estado, "ler_link_afiliado", lambda *a, **k: True)
    monkeypatch.setattr(lojas.estado, "ler_confirmar_no_arranque", lambda *a, **k: True)
    monkeypatch.setattr(lojas.processos, "chrome_aberto", lambda *a: False)
    monkeypatch.setattr(lojas, "launch_persistent", lambda p, headless=False: Contexto())
    monkeypatch.setattr(lojas, "sync_playwright", lambda: contextlib.nullcontext(object()))
    monkeypatch.setattr(lojas, "os", _OsSemMkdir(lojas.os))

    def primeira_varredura(*a, **k):
        raise Varredura

    monkeypatch.setattr(lojas, "_ler_pendentes_resiliente", primeira_varredura)
    try:
        lojas.main()
    except Varredura:
        return perguntas, True
    return perguntas, False


class _OsSemMkdir:
    def __init__(self, os_real):
        self._os = os_real

    def makedirs(self, *a, **k):
        pass

    def __getattr__(self, nome):
        return getattr(self._os, nome)


def test_sem01_sem_perguntas_chega_na_varredura_sem_ler_o_teclado(lojas, monkeypatch):
    perguntas, chegou = _arranque(lojas, monkeypatch, ["--monitorar", "--sem-perguntas"])
    assert chegou
    assert perguntas == []


def test_sem02_sem_a_opcao_a_pergunta_da_shopee_continua(lojas, monkeypatch):
    perguntas, chegou = _arranque(lojas, monkeypatch, ["--monitorar"], respostas=["n"])
    assert chegou
    assert perguntas and "Shopee" in perguntas[0]


def test_sem01_lote_com_shopee_tambem_nao_pergunta(lojas, monkeypatch):
    lojas.SEM_PERGUNTAS = True
    monkeypatch.setattr("builtins.input", lambda *a: pytest.fail("input() chamado"))
    lojas._gate_login_manual(Pagina())
    lojas._gate_login_shopee_arranque(Pagina())
    assert lojas._pode_perguntar() is False


def test_sem03_navegador_aberto_sai_com_erro_sem_matar_processo(lojas, monkeypatch, capsys):
    mortos = []
    monkeypatch.setattr(lojas.processos, "chrome_aberto", lambda *a: True)
    monkeypatch.setattr(lojas.processos, "fechar_chrome_forcado", lambda *a: mortos.append(1))
    monkeypatch.setattr("builtins.input", lambda *a: pytest.fail("input() chamado"))
    monkeypatch.setattr(sys, "stdin", StdinQueFalha())
    lojas.SEM_PERGUNTAS = True
    with pytest.raises(SystemExit) as saida:
        lojas._gate_fechar_navegadores()
    assert saida.value.code not in (0, None)
    assert mortos == []
    assert "navegador aberto" in capsys.readouterr().out


def test_sem03_sem_a_opcao_navegador_aberto_continua_perguntando(lojas, monkeypatch):
    abertos = iter([True, False])
    monkeypatch.setattr(lojas.processos, "chrome_aberto", lambda *a: next(abertos))
    perguntas = []
    monkeypatch.setattr("builtins.input", lambda msg="": perguntas.append(msg) or "s")
    lojas._gate_fechar_navegadores()
    assert len(perguntas) == 1
