"""Confere o contador do config contra MAX(ID_OFERTA) do Oracle e o maior ID dos CSVs.

So REPORTA - nao altera nada. Codigo de saida:
    0 = contador OK (e o maior), pode relancar
    1 = contador ATRASADO, corrigir antes de relancar (senao REEMITE ID)

Nasceu da armadilha de 03/08/2026: parada que nao foi Ctrl+C nao roda o `finally`,
entao o `ultimo_id_processado` do config fica atras do que ja foi gravado em CSV/Oracle.
Rodar SEMPRE antes de relancar depois de uma parada anormal.
"""

import csv
import glob
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)


def maior_id_nos_csvs():
    maior, arquivo = 0, None
    for caminho in glob.glob(os.path.join(RAIZ, "captura", "*.csv")):
        nome = os.path.basename(caminho)
        if "bak" in nome or "backup" in nome:
            continue
        with open(caminho, encoding="utf-8") as fh:
            for linha in csv.DictReader(fh):
                try:
                    oid = int(linha.get("ID_OFERTA") or 0)
                except (TypeError, ValueError):
                    continue
                if oid > maior:
                    maior, arquivo = oid, nome
    return maior, arquivo


def maior_id_no_oracle(cfg_db):
    """Devolve (valor, erro). Valor None se nao deu para consultar."""
    try:
        from wa import oracle_db

        db = oracle_db.OracleDB(cfg_db)
        db.conectar()
        if db._conn is None:
            return None, "conexao nao estabelecida (db desabilitado?)"
        with db._conn.cursor() as cur:
            cur.execute("SELECT MAX(ID_OFERTA) FROM OFERTA_FILA_CAPTURA")
            valor = cur.fetchone()[0]
        db.desconectar()
        return (int(valor) if valor is not None else 0), None
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


def main():
    caminho_cfg = os.path.join(RAIZ, "conf", "config.json")
    with open(caminho_cfg, encoding="utf-8") as fh:
        conf = json.load(fh)
    contador = int(conf["controle"]["ultimo_id_processado"])

    max_csv, arq_csv = maior_id_nos_csvs()
    max_db, erro_db = maior_id_no_oracle(conf.get("db", {}))

    print(f"config ultimo_id_processado : {contador}")
    print(f"maior ID nos CSVs           : {max_csv}  ({arq_csv})")
    if erro_db is None:
        print(f"MAX(ID_OFERTA) no Oracle    : {max_db}")
    else:
        print(f"MAX(ID_OFERTA) no Oracle    : NAO CONSULTADO -> {erro_db}")

    candidatos = [contador, max_csv] + ([max_db] if max_db is not None else [])
    alvo = max(candidatos)

    print()
    if alvo > contador:
        print(f"ATRASADO: contador {contador} < trabalho real {alvo}.")
        print(f"Corrigir 'ultimo_id_processado' para {alvo} em conf/config.json")
        print("antes de relancar (com backup), senao o proximo run REEMITE IDs.")
        return 1

    if erro_db is not None:
        print(f"OK pelos CSVs: contador ({contador}) e o maior.")
        print("ATENCAO: o Oracle nao foi consultado - conferencia PARCIAL.")
        return 0

    print(f"OK: contador ({contador}) e o maior. Pode relancar sem reemitir ID.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
