"""
Aplica no HISTORICO de BESAVE.OFERTA as mesmas regras que valem ao vivo
(revistas 2026-10-13, decisao do usuario):

  1. VALIDADE (core/validade.py): oferta ativa com DT_OFERTA mais antiga que
     conf/config.json -> ofertas.validade_dias (padrao 45) -> desativada.
  2. DUPLICIDADE (core/duplicidade.py): por produto (mesmo ID_PRODUTO ou
     mesmo codigo da loja -- ASIN / MLB / item Shopee), so UMA oferta ativa a
     cada janela de 24 h: a de menor preco; empate -> a mais recente.

Duplicidade no historico: dentro de cada produto, pega a melhor oferta
restante (menor preco, mais recente) e desativa as que estao a ate 24 h dela;
repete com o que sobrar. Resultado: nenhum par de ofertas ativas do mesmo
produto a menos de 24 h uma da outra -- o mesmo estado que a regra ao vivo
produz.

Desativada: OFERTA ST_ATIVO = 0 + DT_DESATIVACAO = agora. Duplicada tambem:
OFERTA_FILA_CAPTURA ST_CAPTURA = '9', DS_CAPTURA = 'duplicada de <ID mantido>'.
Nada e apagado. Backup dos valores antigos em destino/bkp/ + log TSV em destino/log/.

Uso:
    .venv/Scripts/python.exe deduplicar_ofertas.py --dry-run
    .venv/Scripts/python.exe deduplicar_ofertas.py
"""

import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import argparse
import json
import os
from collections import defaultdict, Counter
from datetime import datetime, timedelta

from core import estado
from core.duplicidade import JANELA, PREFIXO, chave_loja, vence
from core.oracle_db import OracleDB
from core.caminhos import em_bkp, em_log


def _grupos(linhas):
    """Une as ofertas do mesmo produto (ID_PRODUTO OU codigo da loja)."""
    pai = {}

    def achar(x):
        while pai.setdefault(x, x) != x:
            pai[x] = pai[pai[x]]
            x = pai[x]
        return x

    for r in linhas:
        chaves = [('O', r['id'])]
        if r['prod'] is not None:
            chaves.append(('P', r['prod']))
        if r['chave']:
            chaves.append(('C', r['chave']))
        for c in chaves[1:]:
            pai[achar(c)] = achar(chaves[0])
    g = defaultdict(list)
    for r in linhas:
        g[achar(('O', r['id']))].append(r)
    return g.values()


def _duplicadas(linhas):
    """[(oferta, mantida)] pela regra de 24 h / menor preco / mais recente."""
    out = []
    for grupo in _grupos(linhas):
        if len(grupo) < 2:
            continue
        restantes = sorted(grupo, key=lambda r: (round(float(r['preco']), 2),
                                                 -r['dt'].timestamp(), -r['id']))
        while restantes:
            melhor = restantes.pop(0)
            fica = []
            for r in restantes:
                if abs(r['dt'] - melhor['dt']) <= JANELA:
                    assert vence(melhor['preco'], melhor['dt'], melhor['id'],
                                 r['preco'], r['dt'], r['id'])
                    out.append((r, melhor))
                else:
                    fica.append(r)
            restantes = fica
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dry-run', action='store_true', dest='dry_run')
    args = ap.parse_args()
    dias = estado.ler_validade_ofertas()

    db = OracleDB()
    db.conectar()
    cur = db._conn.cursor()
    cur.execute("SELECT o.ID_OFERTA, o.DS_URL_FINAL, o.VL_PRECO_POR, o.DT_OFERTA, f.DS_ORIGEM, "
                "       o.DT_PUBLICACAO_SITE, o.ID_PRODUTO "
                "  FROM OFERTA o JOIN OFERTA_FILA_CAPTURA f ON f.ID_OFERTA = o.ID_OFERTA "
                " WHERE o.ST_ATIVO = 1 AND o.DT_OFERTA IS NOT NULL")
    linhas = [{'id': int(i), 'chave': chave_loja(u)[0], 'preco': p, 'dt': dt, 'origem': og,
               'no_site': ds is not None, 'prod': (int(pr) if pr is not None else None)}
              for i, u, p, dt, og, ds, pr in cur.fetchall()]

    limite = datetime.now() - timedelta(days=dias) if dias else None
    vencidas = [r for r in linhas if limite and r['dt'] < limite]
    ids_venc = {r['id'] for r in vencidas}
    vivas = [r for r in linhas if r['id'] not in ids_venc and r['preco'] is not None]
    duplicadas = _duplicadas(vivas)

    print(f'{len(linhas)} oferta(s) ativa(s).')
    print(f'  vencidas (DT_OFERTA > {dias} dias): {len(vencidas)} '
          f'(no site: {sum(r["no_site"] for r in vencidas)})')
    print(f'  duplicadas (24 h, menor preco, empate -> mais recente): {len(duplicadas)} '
          f'(no site: {sum(d["no_site"] for d, _ in duplicadas)}; '
          f'mesmo grupo WhatsApp: {sum(d["origem"] == m["origem"] for d, m in duplicadas)})')
    print('  duplicadas: preco x mantida:', dict(Counter(
        'igual' if round(float(d['preco']), 2) == round(float(m['preco']), 2) else 'maior'
        for d, m in duplicadas)))
    print(f'  ficam ativas: {len(linhas) - len(vencidas) - len(duplicadas)}')

    tag = datetime.now().strftime('%Y%m%d_%H%M')
    log_path = em_log(f'deduplicacao_{tag}.tsv')
    with open(log_path, 'w', encoding='utf-8') as log:
        log.write('ID_OFERTA\tMOTIVO\tID_MANTIDA\tPRECO\tPRECO_MANTIDA\tDT_OFERTA\tDT_MANTIDA\tGRUPO\tNO_SITE\n')
        for r in vencidas:
            log.write(f"{r['id']}\tvencida\t\t{r['preco']}\t\t{r['dt']}\t\t{r['origem']}\t{r['no_site']}\n")
        for d, m in duplicadas:
            log.write(f"{d['id']}\tduplicada\t{m['id']}\t{d['preco']}\t{m['preco']}\t{d['dt']}\t"
                      f"{m['dt']}\t{d['origem']}\t{d['no_site']}\n")
    print(f'Log: {log_path}')
    if args.dry_run or not (vencidas or duplicadas):
        print('[--dry-run] nada gravado.' if args.dry_run else 'Nada a fazer.')
        db.desconectar()
        return

    ids = [r['id'] for r in vencidas] + [d['id'] for d, _ in duplicadas]
    backup = {'OFERTA_FILA_CAPTURA': [], 'OFERTA': []}
    for i in range(0, len(ids), 500):
        lote = ids[i:i + 500]
        binds = ','.join(f':{k}' for k in range(len(lote)))
        cur.execute(f"SELECT ID_OFERTA, ST_CAPTURA, DS_CAPTURA FROM OFERTA_FILA_CAPTURA "
                    f"WHERE ID_OFERTA IN ({binds})", lote)
        backup['OFERTA_FILA_CAPTURA'] += [list(r) for r in cur.fetchall()]
        cur.execute(f"SELECT ID_OFERTA, ST_ATIVO, DT_DESATIVACAO FROM OFERTA "
                    f"WHERE ID_OFERTA IN ({binds})", lote)
        backup['OFERTA'] += [[a, b, str(c) if c else None] for a, b, c in cur.fetchall()]
    bk_path = em_bkp(f'backup_deduplicacao_{tag}.json')
    with open(bk_path, 'w', encoding='utf-8') as f:
        json.dump(backup, f)

    try:
        cur.executemany("UPDATE OFERTA SET ST_ATIVO = 0, DT_DESATIVACAO = SYSDATE "
                        "WHERE ID_OFERTA = :1 AND ST_ATIVO = 1", [[i] for i in ids])
        cur.executemany("UPDATE OFERTA_FILA_CAPTURA SET ST_CAPTURA = '9', DS_CAPTURA = :1 "
                        "WHERE ID_OFERTA = :2",
                        [[f'{PREFIXO}{m["id"]}', d['id']] for d, m in duplicadas])
        db._conn.commit()
    except Exception:
        db._conn.rollback()
        raise
    finally:
        cur.close()
    print(f'{len(vencidas)} vencida(s) + {len(duplicadas)} duplicada(s) desativada(s). '
          f'Backup: {bk_path}')
    db.desconectar()


if __name__ == '__main__':
    main()
