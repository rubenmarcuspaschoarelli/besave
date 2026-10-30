"""BSV-51 DES-01..05: clique interceptado no WhatsApp Web (pagina simulada, sem navegador)."""
import pytest
from wa import browser, destravar

BLOQUEIO = "Locator.click: Timeout 5000ms exceeded. <span> from <div id=\"wa-popovers-bucket\"> subtree intercepts pointer events"


class Alvo:
    """Clique que falha 'interceptado' ate `libera_em` (lista de eventos que o destravam)."""

    def __init__(self, pagina, libera_em):
        self.pagina, self.libera_em, self.tempos = pagina, libera_em, []

    def click(self, timeout=None):
        self.tempos.append(timeout)
        if self.libera_em in self.pagina.eventos or self.libera_em is None:
            self.pagina.eventos.append("clique")
            return
        raise RuntimeError(BLOQUEIO)


class Teclado:
    def __init__(self, pagina):
        self.pagina = pagina

    def press(self, tecla):
        self.pagina.eventos.append(f"tecla:{tecla}")

    def type(self, texto, delay=0):
        self.pagina.eventos.append("digitou")


class Pagina:
    def __init__(self, botao=None):
        self.eventos, self.botao, self.args = [], botao, []
        self.keyboard = Teclado(self)

    def evaluate(self, js, arg=None):
        self.args.append(arg)
        if self.botao is None:
            return None
        self.eventos.append("fechou")
        return self.botao


def test_sem_interceptacao_clica_uma_vez_sem_mexer_na_pagina():  # DES-05
    p = Pagina()
    a = Alvo(p, None)
    destravar.clicar(p, a)
    assert p.eventos == ["clique"] and p.args == []
    assert a.tempos == [destravar.CLIQUE_TIMEOUT_MS] and destravar.CLIQUE_TIMEOUT_MS <= 10_000


def test_escape_resolve_e_nao_procura_botao():  # DES-01
    p = Pagina(botao={"botao": "fechar", "aviso": "x"})
    destravar.clicar(p, Alvo(p, "tecla:Escape"))
    assert p.eventos == ["tecla:Escape", "clique"] and p.args == []


def test_botao_de_fechar_resolve_e_vai_para_o_log(capsys):  # DES-01, DES-02
    p = Pagina(botao={"botao": "agora nao", "aviso": "Confira suas ligacoes recentes"})
    destravar.clicar(p, Alvo(p, "fechou"))
    assert p.eventos == ["tecla:Escape", "fechou", "clique"]
    saida = capsys.readouterr().out
    assert "agora nao" in saida and "Confira suas ligacoes recentes" in saida


def test_nada_resolve_levanta_erro_em_no_maximo_tres_cliques():  # DES-03
    p = Pagina(botao=None)
    a = Alvo(p, "nunca")
    with pytest.raises(destravar.CliqueBloqueado):
        destravar.clicar(p, a)
    assert len(a.tempos) == 2          # sem aviso conhecido nao ha 3o clique
    p2 = Pagina(botao={"botao": "ok", "aviso": ""})
    a2 = Alvo(p2, "nunca")
    with pytest.raises(destravar.CliqueBloqueado):
        destravar.clicar(p2, a2)
    assert len(a2.tempos) == 3 and all(t == destravar.CLIQUE_TIMEOUT_MS for t in a2.tempos)


def test_erro_que_nao_e_interceptacao_nao_dispara_destravar():
    p = Pagina(botao={"botao": "ok", "aviso": ""})

    class Quebrado:
        def click(self, timeout=None):
            raise RuntimeError("Element is not attached to the DOM")

    with pytest.raises(RuntimeError, match="not attached"):
        destravar.clicar(p, Quebrado())
    assert p.eventos == [] and p.args == []


def test_antes_de_repetir_pode_abortar():
    p = Pagina(botao={"botao": "ok", "aviso": ""})
    a = Alvo(p, "tecla:Escape")

    def aborta():
        raise browser.ConversaErrada("busca limpa")

    with pytest.raises(browser.ConversaErrada):
        destravar.clicar(p, a, antes_de_repetir=aborta)
    assert len(a.tempos) == 1


def test_lista_de_botoes_permitidos_inteira():  # DES-04, licao 14
    assert destravar.TEXTOS_FECHAR == ("fechar", "ok", "agora nao", "close", "not now")
    assert destravar.CONTAINERS_AVISO == ("#wa-popovers-bucket", '[role="dialog"]')
    for t in ("Fechar", "OK", " Agora não ", "CLOSE", "Not now"):
        assert destravar.texto_permitido(t), t
    for t in ("Sair do grupo", "Apagar", "Apagar para todos", "Responder", "Cancelar",
              "Denunciar", "Bloquear", "Sair", "Encaminhar", "Confirmar", "Fechar conta", ""):
        assert not destravar.texto_permitido(t), t


def test_fechar_aviso_passa_a_lista_fechada_ao_navegador():  # DES-04
    p = Pagina(botao=None)
    destravar.fechar_aviso(p)
    assert p.args == [{"containers": list(destravar.CONTAINERS_AVISO),
                       "textos": list(destravar.TEXTOS_FECHAR)}]
    # o JS so clica dentro dos containers e so em button/[role=button]
    js = destravar._JS_FECHAR
    assert "caixa.querySelectorAll('button, [role=\"button\"]')" in js and js.count(".click()") == 1


def test_recarregar_espera_a_lista_e_nao_levanta():
    class P:
        def __init__(self):
            self.chamadas = []

        def reload(self, **kw):
            self.chamadas.append(("reload", kw))

        def wait_for_selector(self, sel, timeout=None):
            self.chamadas.append(("esperou", sel))

    p = P()
    assert destravar.recarregar(p) is True
    assert [c[0] for c in p.chamadas] == ["reload", "esperou"] and p.chamadas[1][1] == "#pane-side"

    class Ruim(P):
        def reload(self, **kw):
            raise RuntimeError("x")

    assert destravar.recarregar(Ruim()) is False


class Item:
    """locator('[data-testid="list-item-1"]').first / #main header etc."""

    def __init__(self, pag, seletor):
        self.pag, self.seletor = pag, seletor
        self.first = self

    def wait_for(self, state=None, timeout=None):
        pass

    def count(self):
        return 1

    def inner_text(self, timeout=None):
        if "header" in self.seletor:
            return self.pag.cabecalho
        return self.pag.texto_item

    def click(self, timeout=None):
        if self.pag.bloqueios and "tecla:Escape" not in self.pag.eventos:
            raise RuntimeError(BLOQUEIO)
        self.pag.eventos.append("clicou-item")


class PaginaGrupo(Pagina):
    """Pagina simulada para browser.abrir_grupo."""

    def __init__(self, bloqueios=True, texto_item="Promos da Ly 13:00", cabecalho="Promos da Ly"):
        super().__init__()
        self.bloqueios, self.texto_item, self.cabecalho = bloqueios, texto_item, cabecalho

    def wait_for_selector(self, *a, **k):
        pass

    def wait_for_timeout(self, ms):
        pass

    def query_selector(self, sel):
        return Alvo(self, None)

    def locator(self, sel):
        return Item(self, sel)


def test_abrir_grupo_destrava_com_escape_e_abre(monkeypatch):  # DES-01 de ponta a ponta
    monkeypatch.setattr(browser, "_texto", lambda page, sel: page.texto_item if "list" in sel else page.cabecalho)
    p = PaginaGrupo()
    browser.abrir_grupo(p, "Promos da Ly ✨")
    assert "tecla:Escape" in p.eventos and p.eventos[-1] == "clicou-item"


def test_abrir_grupo_apos_escape_com_busca_limpa_nao_clica_conversa_errada(monkeypatch):
    p = PaginaGrupo()
    monkeypatch.setattr(browser, "_texto", lambda page, sel: page.texto_item)
    antigo = p.keyboard.press

    def esc(t):
        antigo(t)
        if t == "Escape":
            p.texto_item = "Familia 12:00"      # so o Escape limpa a busca

    p.keyboard.press = esc
    with pytest.raises(browser.ConversaErrada):
        browser.abrir_grupo(p, "Promos da Ly ✨")
    assert "clicou-item" not in p.eventos


def test_recarregar_voltas_config_invalida_cai_no_padrao():
    for cfg in (None, {}, {"destravar": 3}, {"destravar": {"recarregar_voltas": 0}},
                {"destravar": {"recarregar_voltas": -2}}, {"destravar": {"recarregar_voltas": "x"}}):
        assert destravar.recarregar_voltas(cfg) == destravar.RECARREGAR_VOLTAS_PADRAO == 8
    assert destravar.recarregar_voltas({"destravar": {"recarregar_voltas": 3}}) == 3


def test_erro_nao_interceptado_no_segundo_clique_nao_vira_bloqueio():
    p = Pagina(botao={"botao": "ok", "aviso": ""})
    n = {"c": 0}

    class Alvo2:
        def click(self, timeout=None):
            n["c"] += 1
            raise RuntimeError(BLOQUEIO if n["c"] == 1 else "Element is not attached to the DOM")

    with pytest.raises(RuntimeError, match="not attached"):
        destravar.clicar(p, Alvo2())
    assert n["c"] == 2 and p.args == []


def test_abrir_grupo_clique_da_busca_bloqueado_tambem_destrava(monkeypatch):  # DES-01 (busca)
    monkeypatch.setattr(browser, "_texto", lambda page, sel: page.texto_item if "list" in sel else page.cabecalho)
    p = PaginaGrupo(bloqueios=False)

    class Busca(Alvo):
        def click(self, timeout=None):
            self.tempos.append(timeout)
            if "tecla:Escape" not in self.pagina.eventos:
                raise RuntimeError(BLOQUEIO)

    b = Busca(p, None)
    p.query_selector = lambda sel: b
    browser.abrir_grupo(p, "Promos da Ly ✨")
    assert p.eventos.index("tecla:Escape") < p.eventos.index("digitou")
    assert b.tempos == [destravar.CLIQUE_TIMEOUT_MS] * 2


def test_recarregar_voltas_1_vale_1():
    assert destravar.recarregar_voltas({"destravar": {"recarregar_voltas": 1}}) == 1
