r"""
Publica no site (bucket local) as fotos JA capturadas (backfill).

A partir de 23/09/2026 a captura publica sozinha (wa/storage.py, `publicar_s3`),
mas as ~57 mil fotos anteriores ficaram de fora. Este script percorre
captura/img/ e cria, para cada oferta com numero DEFINITIVO (ignora os ~124
'tmp<N>' orfaos de runs que crasharam antes de renomear), a pasta
<destino>/<id_oferta>/ com <id_oferta>.webp (imagem principal, mesma
resolucao) e <id_oferta>-small.webp (a miniatura _small), usando a MESMA
funcao da captura ao vivo (`storage.publicar_s3`) - destino/qualidade saem do
bloco "publicacao_s3" do conf/config.json.

Uso (do diretorio do projeto):
    .venv\Scripts\python.exe diag\publicar_s3.py             # publica o que falta
    .venv\Scripts\python.exe diag\publicar_s3.py --dry-run   # so mede, nao grava
    .venv\Scripts\python.exe diag\publicar_s3.py --limite 500
    .venv\Scripts\python.exe diag\publicar_s3.py --refazer   # republica as existentes

Pode rodar com a captura no ar: so LE as fotos de captura/img/ (nunca altera)
e escreve na pasta do site. E interrompivel (Ctrl+C) e retomavel - a oferta
cuja pasta ja tem o <id_oferta>.webp e pulada.
"""

import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wa import storage  # noqa: E402

_NOME_OK = re.compile(r"^(\d+)_")   # so o numero DEFINITIVO; ignora 'tmp<N>_...'


def imagens_definitivas(pasta: Path):
    """(numero, caminho) das fotos principais de captura/img/, na ordem do id."""
    achadas = []
    for p in pasta.iterdir():
        if not p.is_file() or p.stem.endswith("_small"):
            continue
        m = _NOME_OK.match(p.name)
        if not m:
            continue  # 'tmp<N>_...' orfao de run que crashou antes de renomear
        achadas.append((int(m.group(1)), p))
    achadas.sort(key=lambda t: t[0])
    return achadas


def main() -> int:
    ap = argparse.ArgumentParser(description="Publica no site as fotos que faltam.")
    ap.add_argument("--dry-run", action="store_true", help="so conta, nao grava")
    ap.add_argument("--refazer", action="store_true", help="republica mesmo se ja existir")
    ap.add_argument("--limite", type=int, default=0,
                     help="publica no maximo N ofertas NOVAS (o que ja existe e pulado "
                          "de graca e NAO conta no limite - seguro rodar em lotes)")
    args = ap.parse_args()

    pasta = storage.IMG_DIR
    if not pasta.exists():
        print(f"Pasta nao encontrada: {pasta}")
        return 1

    cfg = storage._cfg_s3()
    if not bool(cfg.get("ativo", True)):
        print("publicacao_s3.ativo=false no config.json - nada a fazer.")
        return 0
    destino_raiz = Path(cfg.get("destino") or storage.S3_IMG_DIR_PADRAO)
    print(f"Origem  : {pasta}")
    print(f"Destino : {destino_raiz}\\<id_oferta>\\")
    print(f"Modo    : {'DRY-RUN' if args.dry_run else 'gravando'}"
          f"{' (republicando existentes)' if args.refazer else ''}\n")

    feitas = puladas = falhas = ignoradas_tmp = 0
    t0 = time.perf_counter()
    total = 0
    try:
        lista = imagens_definitivas(pasta)
        total = len(lista)
        for i, (numero, foto) in enumerate(lista, 1):
            if args.limite and feitas >= args.limite:
                break
            ja_existe = (destino_raiz / str(numero) / f"{numero}.webp").exists()
            if ja_existe and not args.refazer:
                puladas += 1
            elif args.dry_run:
                feitas += 1
            else:
                saida = storage.publicar_s3(str(foto), numero)
                if saida:
                    feitas += 1
                else:
                    falhas += 1
            if i % 1000 == 0:
                print(f"  {i:6d}/{total} ofertas | {feitas} publicadas, {puladas} puladas, "
                      f"{falhas} falhas | {time.perf_counter() - t0:.0f}s")
    except KeyboardInterrupt:
        print("\nInterrompido - o que ficou pronto esta no disco; rodar de novo retoma.")

    seg = time.perf_counter() - t0
    print(f"\nPublicadas {feitas} | puladas {puladas} | falhas {falhas} | {seg:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
