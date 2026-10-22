"""Lojas: confirmacao dos logins de afiliado no arranque (input) so com terminal e config ligada."""
import json
import types


class Pagina:
    def __init__(self, url):
        self.url = url

    def goto(self, *a, **k):
        pass


def _stdin(monkeypatch, lojas, tty, confirmar):
    monkeypatch.setattr(lojas.sys, "stdin", types.SimpleNamespace(isatty=lambda: tty))
    monkeypatch.setattr(lojas.estado, "ler_confirmar_no_arranque", lambda *a, **k: confirmar)
    perguntas = []

    def input_falso(msg=""):
        perguntas.append(msg)
        return "s"
    monkeypatch.setattr("builtins.input", input_falso)
    return perguntas


GATE = ("LOJA", "https://loja.exemplo", "instrucao")


def test_sem_terminal_segue_sem_perguntar(lojas, monkeypatch, capsys):
    perguntas = _stdin(monkeypatch, lojas, tty=False, confirmar=True)
    assert lojas._gate_login_afiliado(Pagina("https://loja.exemplo/home"), *GATE) is True
    assert perguntas == []


def test_sem_terminal_e_login_inativo_so_avisa(lojas, monkeypatch, capsys):
    perguntas = _stdin(monkeypatch, lojas, tty=False, confirmar=True)
    assert lojas._gate_login_afiliado(Pagina("https://loja.exemplo/ap/signin?x"), *GATE) is False
    assert perguntas == []
    assert "AVISO" in capsys.readouterr().out


def test_config_desliga_a_pergunta_mesmo_com_terminal(lojas, monkeypatch):
    perguntas = _stdin(monkeypatch, lojas, tty=True, confirmar=False)
    assert lojas._gate_login_afiliado(Pagina("https://loja.exemplo/home"), *GATE) is True
    assert perguntas == []


def test_no_pc_continua_perguntando(lojas, monkeypatch):
    perguntas = _stdin(monkeypatch, lojas, tty=True, confirmar=True)
    assert lojas._gate_login_afiliado(Pagina("https://loja.exemplo/home"), *GATE) is True
    assert len(perguntas) == 1


def test_chave_do_config(tmp_path):
    from core import estado
    arq = tmp_path / "c.json"
    assert estado.ler_confirmar_no_arranque(str(tmp_path / "nao_existe.json")) is True
    arq.write_text(json.dumps({}))
    assert estado.ler_confirmar_no_arranque(str(arq)) is True
    arq.write_text(json.dumps({"afiliados": {"confirmar_no_arranque": False}}))
    assert estado.ler_confirmar_no_arranque(str(arq)) is False
