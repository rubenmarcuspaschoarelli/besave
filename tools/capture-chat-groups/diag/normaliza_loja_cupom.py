r"""
Normaliza DS_CUPOM_LOJA no Oracle: dominio cru -> nome canonico de loja.

Ate 22/09/2026 o parser so conhecia 6 lojas; o resto caia no fallback
"dominio provisorio, mapear depois" (blz.to, epocacosmeticos.com.br...) e nunca
foi mapeado. O parser passou a conhece-las (wa/parser.py, _LOJAS); este script
corrige o que ja esta gravado, usando a MESMA funcao do parser - o que ele nao
souber traduzir fica como esta.

Uso:
    .venv\Scripts\python.exe diag\normaliza_loja_cupom.py            # so mostra
    .venv\Scripts\python.exe diag\normaliza_loja_cupom.py --aplicar  # grava
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import oracledb  # noqa: E402

from wa.parser import _detectar_loja  # noqa: E402


def conectar():
    cfg = json.loads((RAIZ / "conf" / "config.json").read_text(encoding="utf-8"))["db"]
    if (cfg.get("modo") or "thick").lower() == "thick":
        oracledb.init_oracle_client(lib_dir=(cfg.get("instant_client_dir") or "").strip() or None)
    return oracledb.connect(
        user=cfg["usuario"], password=cfg["senha"],
        dsn=oracledb.makedsn(cfg["host"], int(cfg.get("porta", 1521)),
                             service_name=cfg.get("servico") or "XE"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true", help="grava (sem isso, so mostra)")
    args = ap.parse_args()

    con = conectar()
    cur = con.cursor()
    cur.execute("""select DS_CUPOM_LOJA, count(*) from OFERTA_FILA_CAPTURA
                   where DS_CUPOM_LOJA is not null group by DS_CUPOM_LOJA order by 2 desc""")
    atuais = cur.fetchall()

    plano = []
    for valor, qtd in atuais:
        canonico = _detectar_loja(valor)
        if canonico and canonico != valor:
            plano.append((valor, canonico, qtd))

    print(f"{len(atuais)} valores distintos hoje; {len(plano)} a normalizar:\n")
    for valor, canonico, qtd in plano:
        print(f"  {qtd:5d}  {valor:32s} -> {canonico}")
    total = sum(q for _, _, q in plano)
    print(f"\n  TOTAL: {total} linhas")
    if not plano:
        return 0
    if not args.aplicar:
        print("\n(dry-run: rode com --aplicar para gravar)")
        return 0

    # Backup das linhas afetadas ANTES de mexer.
    carimbo = datetime.now().strftime("%d_%m_%Y_%H_%M")
    backup = RAIZ / "conf" / f"backup_ds_cupom_loja_{carimbo}.csv"
    valores = [v for v, _, _ in plano]
    binds = {f"v{i}": v for i, v in enumerate(valores)}
    lista = ", ".join(f":{k}" for k in binds)
    cur.execute(f"select ID_OFERTA, DS_CUPOM_LOJA, DS_URL_ORIGEM from OFERTA_FILA_CAPTURA "
                f"where DS_CUPOM_LOJA in ({lista}) order by ID_OFERTA", binds)
    with open(backup, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["ID_OFERTA", "DS_CUPOM_LOJA", "DS_URL_ORIGEM"])
        w.writerows(cur)
    print(f"\nBackup das linhas afetadas: {backup.name}")

    mudadas = 0
    for valor, canonico, _qtd in plano:
        cur.execute("update OFERTA_FILA_CAPTURA set DS_CUPOM_LOJA = :novo "
                    "where DS_CUPOM_LOJA = :velho", novo=canonico, velho=valor)
        print(f"  {cur.rowcount:5d} linhas: {valor} -> {canonico}")
        mudadas += cur.rowcount
    con.commit()
    print(f"\nCommit: {mudadas} linhas atualizadas.")

    cur.execute("""select DS_CUPOM_LOJA, count(*) from OFERTA_FILA_CAPTURA
                   where DS_CUPOM_LOJA is not null group by DS_CUPOM_LOJA order by 2 desc""")
    print("\nComo ficou:")
    for v, q in cur:
        print(f"  {q:6d}  {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
