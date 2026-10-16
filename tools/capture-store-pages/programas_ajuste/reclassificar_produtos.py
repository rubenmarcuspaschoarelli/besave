"""
Reclassifica TODO o historico de BESAVE.PRODUTO com a regra ATUAL de
core/classificador.py e grava so onde o resultado mudou. Criado em 2026-10-08
para a correcao Elas x Eles (o genero passou a decidir a comunidade -- antes
havia 0 ofertas "Eles" e ~740 "Elas" com publico "Masculino").

Por produto que mudou:
  * PRODUTO.DS_COMUNIDADE / DS_PUBLICO ('Outros' quando nenhuma regra bate,
    mesma regra de core/produtos.py);
  * PRODUTO_COMUNIDADE / PRODUTO_PUBLICO (core/produtos.gravar_classificacao);
  * OFERTA.DS_COMUNIDADE / DS_PUBLICO de TODAS as ofertas do produto (a
    OFERTA guarda uma copia da classificacao do produto).
Nao mexe em datas, precos nem DT_PUBLICACAO_SITE.

Diferente do classificar_produtos.py (so DS_COMUNIDADE IS NULL), este
recalcula todos. Idempotente: rodar de novo nao muda nada.

Uso:
    .venv/Scripts/python.exe reclassificar_produtos.py --dry-run     # resumo + log, nada gravado
    .venv/Scripts/python.exe reclassificar_produtos.py               # grava
Log de cada mudanca: destino/reclassificacao_<data>.tsv
"""

import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import argparse
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime

from core.classificador import classificar
from core.oracle_db import OracleDB
from core.caminhos import em_log
from core.produtos import clob_para_texto, gravar_classificacao


def _ler_vinculos(db):
    cur = db._conn.cursor()
    try:
        cur.execute('SELECT pc.ID_PRODUTO, c.DS_COMUNIDADE FROM BESAVE.PRODUTO_COMUNIDADE pc '
                    'JOIN BESAVE.COMUNIDADE c ON c.ID_COMUNIDADE = pc.ID_COMUNIDADE '
                    'ORDER BY pc.ID_PRODUTO, pc.NR_ORDEM')
        vinc = defaultdict(list)
        for id_produto, nome in cur:
            vinc[id_produto].append(nome)
        return vinc
    finally:
        cur.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dry-run', action='store_true', dest='dry_run')
    args = ap.parse_args()

    db = OracleDB()
    if not db.conectar():
        print('Sem conexao com o Oracle.')
        sys.exit(1)

    cur = db._conn.cursor()
    cur.execute('SELECT p.ID_PRODUTO, p.DS_PRODUTO, p.LS_CATEGORIA, p.DS_CATEGORIA_RANKING, '
                '       p.DS_COMUNIDADE, p.DS_PUBLICO, '
                '       (SELECT COUNT(*) FROM BESAVE.OFERTA o WHERE o.ID_PRODUTO = p.ID_PRODUTO) '
                '  FROM BESAVE.PRODUTO p ORDER BY p.ID_PRODUTO')
    produtos = [(a, b, clob_para_texto(c), d, e, f, g) for a, b, c, d, e, f, g in cur.fetchall()]
    vinculos = _ler_vinculos(db)

    log_path = em_log(f'reclassificacao_{datetime.now():%Y%m%d_%H%M}.tsv')
    transicoes = Counter()
    transicoes_ofertas = Counter()
    mudados = ofertas_mudadas = 0
    with open(log_path, 'w', encoding='utf-8') as log:
        log.write('ID_PRODUTO\tQT_OFERTAS\tCOMUNIDADE_ANTES\tPUBLICO_ANTES\t'
                  'COMUNIDADE_DEPOIS\tPUBLICO_DEPOIS\tVINCULOS_ANTES\tVINCULOS_DEPOIS\tTITULO\n')
        for id_produto, titulo, ls_cat, ranking, com0, pub0, qt_ofertas in produtos:
            comunidades, publico = classificar(ls_cat, titulo, ranking)
            com1 = comunidades[0][0] if comunidades else 'Outros'
            # Escopo da correcao de 08/10 = genero. O DS_COMUNIDADE escalar de
            # alguns produtos ja divergia dos vinculos N:N (recapturas antigas
            # com categoria vazia; a SP nunca rebaixa p/ 'Outros'), entao:
            #  - nunca rebaixa uma comunidade real p/ 'Outros' (ex. panela que
            #    hoje nao casa regra nenhuma continua "Meu Lar");
            #  - so troca a comunidade principal quando Elas/Eles esta em jogo
            #    (whey "Esporte & vida" x "Meu Lar" empatado fica como esta).
            # Publico e vinculos N:N seguem sempre a regra atual.
            # (2026-10-08, 2a rodada: infantil -> Família & filhos entrou no escopo.)
            escopo = ('Elas', 'Eles', 'Família & filhos')
            if com0 not in (None, 'Outros') and (
                    com1 == 'Outros' or (com0 not in escopo and com1 not in escopo)):
                com1 = com0
            vinc0 = vinculos.get(id_produto, [])
            vinc1 = [nome for nome, _ in comunidades]
            if (com0, pub0, vinc0) == (com1, publico, vinc1):
                continue
            mudados += 1
            ofertas_mudadas += qt_ofertas
            transicoes[(com0, pub0, com1, publico)] += 1
            transicoes_ofertas[(com0, pub0, com1, publico)] += qt_ofertas
            log.write(f'{id_produto}\t{qt_ofertas}\t{com0}\t{pub0}\t{com1}\t{publico}\t'
                      f'{",".join(vinc0)}\t{",".join(vinc1)}\t{(titulo or "")[:120]}\n')
            if args.dry_run:
                continue
            cur.execute('UPDATE BESAVE.PRODUTO SET DS_COMUNIDADE = :c, DS_PUBLICO = :p '
                        'WHERE ID_PRODUTO = :id', c=com1, p=publico, id=id_produto)
            cur.execute('UPDATE BESAVE.OFERTA SET DS_COMUNIDADE = :c, DS_PUBLICO = :p '
                        'WHERE ID_PRODUTO = :id', c=com1, p=publico, id=id_produto)
            db._conn.commit()
            gravar_classificacao(db, id_produto, comunidades, publico)
            if mudados % 500 == 0:
                print(f'... {mudados} produto(s) gravado(s)', flush=True)
    cur.close()

    print(f'\n{len(produtos)} produto(s) avaliado(s); {mudados} mudam '
          f'({ofertas_mudadas} oferta(s) afetada(s)).')
    print('Transicoes (comunidade/publico antes -> depois): produtos | ofertas')
    for k, v in transicoes.most_common(25):
        print(f'  {v:5} | {transicoes_ofertas[k]:5}  {k[0]}/{k[1]} -> {k[2]}/{k[3]}')
    print(f'Log: {log_path}')
    print('[--dry-run] nada gravado.' if args.dry_run else 'Gravado.')
    db.desconectar()


if __name__ == '__main__':
    main()
