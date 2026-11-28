"""BSV-67 TEL-01, PAR-01, PAR-02, FIX-01: TelaWhatsApp com Chromium real sobre as fixtures redigidas da pagina
real (tools/tests/fixtures/whatsapp/) e o simulador de teste (simulador_vinculo.js), como na AD-120.

web.whatsapp.com e interceptado (page.route): nada sai da maquina. Pula sem Playwright (CI); roda no PC e no WSL.
"""
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

from wa import pareamento as p

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "whatsapp"
NUMERO = "5511987650000"


def _ler(nome):
    return (FIXTURES / nome).read_text(encoding="utf-8")


def _pagina_html(idioma):
    numero = _ler(f"numero_{idioma}.html")
    codigo = _ler("codigo_pt.html")          # a tela do codigo so existe em pt (tabela do dono)
    return (f'<!doctype html><html><head><meta charset="utf-8"></head><body><div id="raiz"></div>'
            f'<template id="t-qr">{_ler(f"qr_{idioma}.html")}</template>'
            f'<template id="t-numero">{numero}</template><template id="t-codigo">{codigo}</template>'
            '<template id="t-logado"><div id="pane-side"></div></template></body></html>')


@pytest.fixture(scope="module")
def navegador():
    try:
        with sync_api.sync_playwright() as pw:
            b = pw.chromium.launch()
            yield b
            b.close()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Chromium indisponivel ({type(e).__name__})")


@pytest.fixture
def abrir(navegador):
    contextos = []

    def _abrir(idioma="pt", **sim):
        ctx = navegador.new_context()
        contextos.append(ctx)
        # recarregar a pagina volta ao QR, como no WhatsApp real (o codigo nao sobrevive ao reload)
        ctx.add_init_script(f"window.__sim = {json.dumps(sim)};"
                            "if (sessionStorage.getItem('carregou')) window.__sim.inicio = 't-qr';"
                            "sessionStorage.setItem('carregou', '1');")
        ctx.add_init_script(path=str(FIXTURES / "simulador_vinculo.js"))
        corpo = _pagina_html(idioma)
        ctx.route("https://web.whatsapp.com/**",
                  lambda r: r.fulfill(status=200, content_type="text/html; charset=utf-8", body=corpo))
        page = ctx.new_page()
        page.goto(p.WHATSAPP_URL, wait_until="domcontentloaded")
        return page, p.TelaWhatsApp(page, dormir=lambda s: time.sleep(0.05))

    yield _abrir
    for c in contextos:
        c.close()


@pytest.mark.parametrize("idioma, inicio, esperado", [
    ("pt", "t-qr", p.QR), ("en", "t-qr", p.QR), ("pt", "t-numero", p.NUMERO), ("en", "t-numero", p.NUMERO),
    ("pt", "t-codigo", p.CODIGO), ("pt", "t-logado", p.LOGADO),
])
def test_estado_reconhece_cada_tela_real(abrir, idioma, inicio, esperado):  # TEL-01, FIX-01
    _, tela = abrir(idioma, inicio=inicio)
    assert tela.esperar(10) == esperado


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_do_qr_ao_codigo_pelos_seletores_reais(abrir, idioma):  # PAR-01
    page, tela = abrir(idioma)
    tela.abrir_numero()
    assert tela.estado() == p.NUMERO
    valor = tela.informar_numero(NUMERO)
    assert valor == "+55 11 98765-0000" and p.so_digitos(valor) == NUMERO
    tela.avancar()
    assert p.codigo_valido(tela.ler_codigo(10)) == "TESTE123"
    assert page.evaluate("window.__avancos") == 1
    assert page.evaluate("window.__valorAvancado") == "+55 11 98765-0000"


def test_link_por_texto_quando_o_testid_some(abrir):  # TEL-01: texto visivel como reserva
    page, tela = abrir("en")
    page.evaluate("""document.querySelector('[data-testid="link_device_qr_phone_number_link"]')
                     .removeAttribute('data-testid')""")
    page.evaluate("""document.addEventListener('click', ev => {
        if (ev.target.closest('[role="button"]') && ev.target.innerText.trim() === 'Log in with phone number')
            document.getElementById('raiz').innerHTML = document.getElementById('t-numero').innerHTML;
    }, true)""")
    tela.abrir_numero()
    assert tela.estado() == p.NUMERO


def test_tela_do_codigo_velha_recarrega_e_volta_ao_numero(abrir):  # PAR-04: pedir outro a partir do codigo
    _, tela = abrir("pt", inicio="t-codigo")
    tela.abrir_numero()
    assert tela.estado() == p.NUMERO


def test_vinculo_completo_e_ddi_duplicado_com_a_pagina(abrir, tmp_path):  # PAR-01, PAR-02
    page, tela = abrir("pt")
    t = [datetime(2026, 11, 27, 15, 0, tzinfo=UTC)]
    enviados = []

    def dormir(s):
        t[0] += timedelta(seconds=s)
        if t[0] >= datetime(2026, 11, 27, 15, 1, tzinfo=UTC):
            page.evaluate("document.getElementById('raiz').innerHTML = '<div id=\"pane-side\"></div>'")

    p.Vinculo(tela, NUMERO, 10, p.Teto(tmp_path / "a.json"), enviados.append, lambda: None,
              relogio=lambda: t[0], dormir=dormir).aguardar()
    assert enviados == [p.msg_codigo("TESTE123", datetime(2026, 11, 27, 15, 0, tzinfo=UTC)), p.MSG_VINCULADO]

    page2, tela2 = abrir("pt", mascara="duplica")
    t2 = [datetime(2026, 11, 27, 15, 0, tzinfo=UTC)]
    enviados2 = []

    def dormir2(s):
        t2[0] += timedelta(seconds=s)
        if t2[0] >= datetime(2026, 11, 27, 15, 1, tzinfo=UTC):
            page2.evaluate("document.getElementById('raiz').innerHTML = '<div id=\"pane-side\"></div>'")

    p.Vinculo(tela2, NUMERO, 10, p.Teto(tmp_path / "b.json"), enviados2.append, lambda: None,
              relogio=lambda: t2[0], dormir=dormir2).aguardar()
    assert enviados2 == [p.MSG_SEM_NUMERO]
    assert page2.evaluate("window.__avancos") == 0
