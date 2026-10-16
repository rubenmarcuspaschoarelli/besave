"""
Dump da BARRA DE AFILIADO do Mercado Livre, para mapear onde ficam os botoes
de copiar (link e codigo do produto) do menu "Compartilhar".

Mesmo papel do shopee_dump.py: em vez de adivinhar seletor por seletor num
site que muda a cada deploy, olha o HTML de verdade UMA vez. Necessario porque
a barra e injetada pelo programa de afiliados DEPOIS da pagina carregar, com
classes "andes-*" que nao servem de ancora.

    $env:PYTHONIOENCODING="utf-8"; .venv\\Scripts\\python.exe -u ml_dump_barra.py <url do produto>

Precisa da sessao de AFILIADO logada no .chrome_perfil (sem ela a barra nem
aparece). Nao grava nada no banco.

Salva destino/log/ml_barra_dump.html com o HTML da barra JA COM O MENU ABERTO, e
imprime, para cada nivel de ancestral acima do botao "Compartilhar", quantos
botoes-de-icone existem e que texto o nivel tem -- que e exatamente o que
core/link_afiliado._escopo_menu_ml() precisa acertar.
"""

import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import os
import sys

from playwright.sync_api import sync_playwright

from core.browser import launch_persistent
from core.caminhos import em_log

BOTAO = '[data-testid="generate_link_button"]'
COPIAR = 'button:has(svg):not([data-testid="generate_link_button"])'
NIVEIS = 7


def _resumo(el):
    """tag#id.classe de um elemento, curto o bastante para caber na tela."""
    try:
        return el.evaluate(
            "e => e.tagName.toLowerCase()"
            " + (e.id ? '#' + e.id : '')"
            " + (e.className && typeof e.className === 'string'"
            "    ? '.' + e.className.trim().split(/\\s+/).slice(0, 3).join('.') : '')"
        )
    except Exception:  # noqa: BLE001
        return '?'


def main():
    if len(sys.argv) < 2:
        print('Uso: python ml_dump_barra.py <url de um produto do Mercado Livre>')
        sys.exit(1)
    url = sys.argv[1]

    with sync_playwright() as p:
        ctx = launch_persistent(p)
        ctx.grant_permissions(['clipboard-read', 'clipboard-write'])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(url, timeout=60000, wait_until='domcontentloaded')
        page.wait_for_timeout(4000)
        print('url_final:', page.url)

        botao = page.locator(BOTAO).first
        try:
            botao.wait_for(state='visible', timeout=25000)
        except Exception:  # noqa: BLE001
            print('BARRA DE AFILIADO NAO APARECEU -- sessao de afiliado logada?')
            ctx.close()
            return
        print('botao "Compartilhar" encontrado. Abrindo o menu...')
        botao.click()
        page.wait_for_timeout(2500)

        print('\nNivel | elemento                                   | botoes-icone | texto')
        print('-' * 100)
        for nivel in range(1, NIVEIS + 1):
            alvo = botao.locator(f'xpath=ancestor::*[{nivel}]')
            if not alvo.count():
                break
            el = alvo.first
            try:
                copias = el.locator(COPIAR).count()
            except Exception:  # noqa: BLE001
                copias = -1
            try:
                texto = ' '.join((el.inner_text() or '').split())[:60]
            except Exception:  # noqa: BLE001
                texto = '?'
            print(f'{nivel:>5} | {_resumo(el)[:42]:<42} | {copias:>12} | {texto}')

        # Todos os botoes de icone do menu, com o que cada um "e" -- e a partir
        # daqui que se decide em qual clicar.
        print('\nBotoes-icone visiveis a partir do nivel 2:')
        escopo = botao.locator('xpath=ancestor::*[2]')
        if escopo.count():
            botoes = escopo.first.locator(COPIAR)
            for i in range(botoes.count()):
                b = botoes.nth(i)
                try:
                    print(f'  [{i}] {_resumo(b)[:60]:<60} aria-label='
                          f'{b.get_attribute("aria-label")!r} title={b.get_attribute("title")!r} '
                          f'texto={" ".join((b.inner_text() or "").split())[:30]!r}')
                except Exception as e:  # noqa: BLE001
                    print(f'  [{i}] (falhou: {e})')

        # HTML da barra inteira (nivel mais alto que ainda nao e o <nav> do site)
        for nivel in range(NIVEIS, 0, -1):
            alvo = botao.locator(f'xpath=ancestor::*[{nivel}]')
            if alvo.count() and _resumo(alvo.first).startswith('nav'):
                alvo = botao.locator(f'xpath=ancestor::*[{max(nivel - 1, 1)}]')
                break
        saida = em_log('ml_barra_dump.html')
        try:
            html = alvo.first.evaluate('e => e.outerHTML')
        except Exception:  # noqa: BLE001
            html = page.content()
        with open(saida, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f'\nHTML da barra salvo em {saida} ({os.path.getsize(saida)} bytes)')
        ctx.close()


if __name__ == '__main__':
    main()
