r"""
06/10/2026 - duas correcoes de historico no Oracle (a pedido do usuario):

1) OFERTA.DS_CUPOM cortado em 30 pela STP_OFERTA_PUBLICAR antiga: copia o valor
   inteiro de OFERTA_FILA_CAPTURA, so onde o da OFERTA e PREFIXO EXATO dele.
2) Conversa fiada gravada como PRODUTO em OFERTA_FILA_CAPTURA (sem preco, sem
   cupom e sem link de loja -- mesma regra do monitor._tem_conteudo novo):
   apaga, exceto ST_CAPTURA = '1' e o que ja estiver publicado em OFERTA.

Backups em conf/backup_*_<data>.csv antes de qualquer gravacao.

Uso:
    .venv\Scripts\python.exe diag\limpa_conversa_e_cupom.py            # so mostra
    .venv\Scripts\python.exe diag\limpa_conversa_e_cupom.py --aplicar  # grava
"""

import argparse
import csv
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "diag"))

from normaliza_loja_cupom import conectar  # noqa: E402

from wa.parser import eh_link_whatsapp  # noqa: E402

ORIGEM = "WHATSAPP"


def _backup(nome, cabecalho, linhas):
    caminho = RAIZ / "conf" / f"backup_{nome}_{datetime.now():%d_%m_%Y_%H_%M}.csv"
    with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(cabecalho)
        w.writerows(linhas)
    return caminho


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    conn = conectar()
    cur = conn.cursor()

    # --- 1) cupom cortado na OFERTA ---
    cur.execute("""select o.ID_OFERTA, o.DS_CUPOM, f.DS_CUPOM
                     from OFERTA o join OFERTA_FILA_CAPTURA f on f.ID_OFERTA = o.ID_OFERTA
                    where length(f.DS_CUPOM) > 30 and o.DS_CUPOM = substr(f.DS_CUPOM, 1, 30)""")
    cupons = cur.fetchall()
    print(f"[cupom] OFERTA com DS_CUPOM cortado (prefixo exato): {len(cupons)}")
    for i, antes, novo in cupons[:5]:
        print(f"   {i}: {antes!r} -> {novo!r}")

    # --- 2) conversa fiada ---
    cur.execute("""select ID_OFERTA, ST_CAPTURA, DS_TIPO_ORIGEM, DS_ORIGEM, DS_OFERTA, DS_URL_ORIGEM,
                          DS_IMAGEM_OFERTA, DT_OFERTA, DT_CAPTACAO
                     from OFERTA_FILA_CAPTURA
                    where VL_PRECO_POR is null and VL_PRECO_DE is null and DS_CUPOM is null
                      and upper(DS_TIPO_ORIGEM) like :o""", o=f"%{ORIGEM}%")
    candidatas = [r for r in cur.fetchall() if not r[5] or eh_link_whatsapp(r[5])]
    cur.execute("select ID_OFERTA from OFERTA")
    publicadas = {r[0] for r in cur}
    print(f"\n[conversa] candidatas: {len(candidatas)} | ST_CAPTURA:",
          dict(Counter(r[1] for r in candidatas)),
          "| ja publicadas em OFERTA:", sum(r[0] in publicadas for r in candidatas))
    apagar = [r for r in candidatas if r[1] != "1" and r[0] not in publicadas]
    print(f"[conversa] a apagar (ST_CAPTURA <> '1' e fora da OFERTA): {len(apagar)}")
    for r in apagar[:8]:
        print(f"   {r[0]} st={r[1]} | {(r[4] or '')[:50]!r} | {(r[5] or '')[:35]}")

    if not args.aplicar:
        print("\n(simulacao - nada gravado; use --aplicar)")
        return 0

    if cupons:
        b = _backup("oferta_ds_cupom", ["ID_OFERTA", "DS_CUPOM_ANTES", "DS_CUPOM_NOVO"], cupons)
        cur.executemany("update OFERTA set DS_CUPOM = :novo where ID_OFERTA = :id and DS_CUPOM = :antes",
                        [{"id": i, "novo": novo, "antes": antes} for i, antes, novo in cupons])
        print(f"[cupom] atualizadas: {cur.rowcount} (backup {b.name})")
    if apagar:
        b = _backup("conversa_fiada_apagada",
                    ["ID_OFERTA", "ST_CAPTURA", "DS_TIPO_ORIGEM", "DS_ORIGEM", "DS_OFERTA",
                     "DS_URL_ORIGEM", "DS_IMAGEM_OFERTA", "DT_OFERTA", "DT_CAPTACAO"], apagar)
        cur.executemany("delete from OFERTA_FILA_CAPTURA where ID_OFERTA = :1 and ST_CAPTURA <> '1'",
                        [(r[0],) for r in apagar])
        print(f"[conversa] apagadas: {cur.rowcount} (backup {b.name})")
    conn.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
