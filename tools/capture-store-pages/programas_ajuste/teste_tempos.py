"""
Perfil de TEMPO de uma pagina de produto, fase a fase -- o "por que essa loja
demora tanto?" respondido com numero, nao com palpite.

Nasceu da Amazon passando de 1 minuto por oferta (11/09). O log do main.py ja
mostra o tempo de cada FASE (nav/capt/img/afil/db); aqui a lupa e mais forte:
mostra o tempo de CADA SELETOR da varredura e de CADA MINIATURA do download de
imagens, que e onde um timeout silencioso se esconde.

Nao grava NADA: nem Oracle, nem CSV, e as imagens vao para uma pasta temporaria
(--pasta-img, por padrao uma tmp do sistema), nunca para destino/img.

Uso:
    python teste_tempos.py <url> [<url> ...]
    python teste_tempos.py --da-fila amazon 3     # 3 ofertas ja capturadas dessa loja
    python teste_tempos.py --da-fila amazon 3 --sem-afiliado

ATENCAO: o perfil do Chrome (.chrome_perfil) e UNICO -- nao rode isto com o
main.py capturando ao mesmo tempo.
"""

import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import argparse
import os
import sys
import tempfile
import time

from playwright.sync_api import sync_playwright

from core import registry, link_afiliado
from core.browser import launch_persistent, PERFIL_DIR
from core.oracle_db import OracleDB

from main import (_gate_fechar_navegadores, _gate_login_manual, _assentar_pos_login,
                  _gates_login_afiliados, _goto_robusto, _nova_page)


def _cron():
    """Devolve (marcar, fases): marcar('nome') fecha a fase corrente."""
    estado = {'t0': time.perf_counter()}
    fases = []

    def marcar(nome):
        agora = time.perf_counter()
        fases.append((nome, agora - estado['t0']))
        estado['t0'] = agora
        return fases[-1][1]

    return marcar, fases


def _urls_da_fila(loja, quantas):
    """URLs de produto ja capturadas da loja (DS_URL_FINAL e a pagina real)."""
    db = OracleDB()
    if not db.conectar():
        return []
    nome = registry.nome_loja(loja)
    cur = db._conn.cursor()
    try:
        cur.execute(
            "SELECT * FROM (SELECT DS_URL_FINAL FROM OFERTA_FILA_CAPTURA "
            " WHERE ST_CAPTURA = '1' AND DS_URL_FINAL IS NOT NULL "
            "   AND EXISTS (SELECT 1 FROM OFERTA o WHERE o.ID_OFERTA = "
            "               OFERTA_FILA_CAPTURA.ID_OFERTA AND o.DS_LOJA = :loja) "
            " ORDER BY ID_OFERTA DESC) WHERE ROWNUM <= :n",
            {'loja': nome, 'n': int(quantas)})
        return [u for (u,) in cur if u]
    finally:
        cur.close()
        db.desconectar()


def _detalhar_scan(page, store):
    """Tempo de CADA seletor da varredura. O que interessa aqui e o seletor
    AUSENTE: ele paga o SCAN_TIMEOUT inteiro (4s por padrao) so p/ concluir que
    nao existe -- 10 campos opcionais ausentes viram 40s de captura."""
    print('  varredura por seletor (so os >= 0,2s):')
    total_ausente = 0.0
    for it in store.arr_items_scan:
        seletor = store.to_selector(it['by'], it['value'])
        if seletor is None:
            continue
        t0 = time.perf_counter()
        try:
            page.locator(seletor).first.wait_for(state='attached',
                                                 timeout=store.SCAN_TIMEOUT)
            achou = True
        except Exception:  # noqa: BLE001
            achou = False
        gasto = time.perf_counter() - t0
        if not achou:
            total_ausente += gasto
        if gasto >= 0.2:
            print(f'    {gasto:6.2f}s  {"ok     " if achou else "AUSENTE"}  {it["key"]}')
    print(f'    -> {total_ausente:.1f}s gastos em campos AUSENTES '
          f'(SCAN_TIMEOUT = {store.SCAN_TIMEOUT / 1000:g}s)')


def _detalhar_miniaturas(page, store):
    """Tempo de CADA miniatura (modo Amazon: clicar p/ trocar a imagem grande).
    Mostra tambem quantas miniaturas nao tem o <input> que o codigo clica -- em
    cada uma delas o clique espera o timeout padrao da pagina inteiro."""
    if not store.img_thumbs_selector:
        print('  imagens: esta loja usa URLs diretas (sem clique em miniatura).')
        return
    thumbs = page.locator(store.img_thumbs_selector).locator('li')
    n = thumbs.count()
    print(f'  miniaturas: {n} <li> em {store.img_thumbs_selector}')
    for i in range(n):
        thumb = thumbs.nth(i)
        tem_input = thumb.locator('input').count()
        t0 = time.perf_counter()
        erro = ''
        try:
            thumb.locator('input').first.click()
        except Exception as e:  # noqa: BLE001
            erro = str(e).splitlines()[0][:60]
        gasto = time.perf_counter() - t0
        print(f'    li[{i}] input={tem_input} clique {gasto:6.2f}s '
              f'{("FALHOU: " + erro) if erro else "ok"}')
        if gasto > 5:
            print('      ^ esse e o custo escondido: clique que expira no '
                  'timeout padrao da pagina e morre num except silencioso.')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('urls', nargs='*')
    ap.add_argument('--da-fila', nargs=2, metavar=('LOJA', 'N'),
                    help='Usa N ofertas ja capturadas da LOJA (amazon/mercadolivre/shopee).')
    ap.add_argument('--sem-afiliado', action='store_true',
                    help='Pula a fase do link de afiliado (isola o resto).')
    ap.add_argument('--pasta-img', default=None,
                    help='Onde jogar as imagens do teste (padrao: pasta temporaria).')
    args = ap.parse_args()

    urls = list(args.urls)
    if args.da_fila:
        urls += _urls_da_fila(args.da_fila[0], args.da_fila[1])
    if not urls:
        print('Informe uma URL ou use --da-fila LOJA N.')
        sys.exit(1)

    img_root = args.pasta_img or os.path.join(tempfile.gettempdir(), 'captura_tempos')
    os.makedirs(img_root, exist_ok=True)
    print(f'Imagens do teste vao para: {img_root}')

    link_afiliado.configurar(not args.sem_afiliado)
    _gate_fechar_navegadores()

    with sync_playwright() as p:
        try:
            context = launch_persistent(p, headless=False)
        except Exception as e:  # noqa: BLE001
            print(f'Nao consegui abrir o Chrome com o perfil {PERFIL_DIR}: {e}')
            sys.exit(1)
        link_afiliado.preparar_contexto(context)
        page = _nova_page(context)

        if any(registry.resolver_loja(u) == 'shopee' for u in urls):
            _gate_login_manual(page)
            _assentar_pos_login(page)
        if not args.sem_afiliado:
            _gates_login_afiliados(page)

        for n, url in enumerate(urls, 1):
            loja = registry.resolver_loja(url)
            store = registry.get_store(loja) if loja else None
            print('')
            print('=' * 70)
            print(f'{n}/{len(urls)} {loja or "?"} | {url[:80]}')
            if store is None:
                print('  (loja sem store implementada)')
                continue

            marcar, fases = _cron()
            try:
                _goto_robusto(page, url, timeout=60000)
                try:
                    store.prepare(page)
                except Exception:  # noqa: BLE001
                    pass
                if store.ready_selector:
                    try:
                        page.wait_for_selector(store.ready_selector, timeout=25000)
                    except Exception:  # noqa: BLE001
                        pass
                page.wait_for_timeout(store.post_load_wait)
            except Exception as e:  # noqa: BLE001
                print(f'  falhou ao abrir: {e}')
                continue
            marcar('nav')

            dados = store.capture(page)
            marcar('capt')

            pasta = os.path.join(img_root, f'teste_{n}')
            baixadas = store.get_images(page, pasta) if store.baixar_imagens else 0
            marcar('img')

            if not args.sem_afiliado and loja in link_afiliado.LOJAS:
                afiliado = link_afiliado.capturar(page, loja, page.url)
            else:
                afiliado = {}
            marcar('afil')

            total = sum(t for _, t in fases)
            print('  ' + ' | '.join(f'{nome} {t:.1f}s' for nome, t in fases)
                  + f'  => TOTAL {total:.1f}s')
            unicas = len(set(os.path.getsize(os.path.join(pasta, f))
                             for f in os.listdir(pasta))) if os.path.isdir(pasta) else 0
            print(f'  titulo   = {(dados.get("produto_titulo") or "-")[:60]}')
            print(f'  imagens  = {baixadas} arquivo(s) baixado(s), '
                  f'{unicas} tamanho(s) distinto(s) (repetidas = re-download)')
            print(f'  afiliado = {afiliado.get("url_afiliado") or "-"}')

            # A lupa: onde foram os segundos de 'capt' e de 'img'.
            _detalhar_scan(page, store)
            if store.baixar_imagens:
                _detalhar_miniaturas(page, store)

        print('')
        print('Fim (nada gravado no banco nem em destino/).')
        context.close()


if __name__ == '__main__':
    main()
