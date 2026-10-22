r"""
06/10/2026: OFERTA.DS_CUPOM 30 -> 250 CHAR + STP_OFERTA_PUBLICAR com SUBSTR 250.

Continuacao de conf/ds_cupom_250.sql (28/09, que alargou a ORIGEM,
OFERTA_FILA_CAPTURA). A SP e mantida pelo CaptureAmazon: a fonte e
CaptureAmazon/sql/STP_OFERTA_PUBLICAR.STP (ja editada); versao anterior do banco
em conf/sp_oferta_publicar_antes_ds_cupom_250.sql.

Uso:
    .venv\Scripts\python.exe conf\ds_cupom_250_oferta.py
"""

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "diag"))

from normaliza_loja_cupom import conectar  # noqa: E402

FONTE_SP = RAIZ.parent / "CaptureAmazon" / "sql" / "STP_OFERTA_PUBLICAR.STP"


def main() -> int:
    texto = FONTE_SP.read_text(encoding="utf-8")
    m = re.search(r"CREATE OR REPLACE PROCEDURE.*?END STP_OFERTA_PUBLICAR;", texto, re.S | re.I)
    if not m or texto.count("SUBSTR(P_DS_CUPOM, 1, 250)") != 2:
        print("Fonte da SP nao esta como esperado; nada feito.")
        return 1
    ddl_sp = m.group(0)

    conn = conectar()
    cur = conn.cursor()

    cur.execute("select char_length from user_tab_columns "
                "where table_name='OFERTA' and column_name='DS_CUPOM'")
    if cur.fetchone()[0] < 250:
        cur.execute("ALTER TABLE OFERTA MODIFY (DS_CUPOM VARCHAR2(250 CHAR))")
        print("OFERTA.DS_CUPOM -> 250 CHAR")

    cur.execute(ddl_sp)
    cur.execute("select status from user_objects where object_name='STP_OFERTA_PUBLICAR' "
                "and object_type='PROCEDURE'")
    status = cur.fetchone()[0]
    cur.execute("select line, position, text from user_errors where name='STP_OFERTA_PUBLICAR'")
    erros = cur.fetchall()
    print("SP status:", status, "| erros:", erros or "nenhum")
    if status != "VALID" or erros:
        return 1

    # Teste com rollback: ID inexistente, 3 cupons (> 30 chars).
    # ID_PRODUTO e NOT NULL: usa um produto que ja existe.
    cupom = "MODA2309 | LOJASOFICIAIS | CASAPROMO10"
    cur.execute("select max(ID_PRODUTO) from OFERTA")
    produto = cur.fetchone()[0]
    ret, err = cur.var(str), cur.var(str)
    cur.callproc("STP_OFERTA_PUBLICAR", keyword_parameters={
        "P_ID_OFERTA": -999999, "P_ID_PRODUTO": produto, "P_DS_CUPOM": cupom,
        "PV_RETORNO": ret, "PV_ERRO": err})
    cur.execute("select DS_CUPOM from OFERTA where ID_OFERTA = -999999")
    lido = (cur.fetchone() or [None])[0]
    conn.rollback()
    cur.execute("select count(*) from OFERTA where ID_OFERTA = -999999")
    sobrou = cur.fetchone()[0]
    print(f"teste: retorno={ret.getvalue()} erro={err.getvalue()} lido={lido!r} "
          f"inteiro={lido == cupom} | linha de teste apos rollback={sobrou}")
    return 0 if lido == cupom and sobrou == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
