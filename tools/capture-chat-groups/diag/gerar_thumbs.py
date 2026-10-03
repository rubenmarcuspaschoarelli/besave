r"""
Gera as miniaturas "_small" das imagens JA capturadas (backfill).

A partir de 22/09/2026 a captura gera a miniatura sozinha (wa/storage.py,
`gerar_thumbnail`), mas as ~28 mil fotos anteriores ficaram sem. Este script
percorre captura/img/ e cria o que falta, usando a MESMA funcao da captura -
formato, tamanho e qualidade saem do bloco "imagem" do conf/config.json.

Uso (do diretorio do projeto):
    .venv\Scripts\python.exe diag\gerar_thumbs.py            # gera o que falta
    .venv\Scripts\python.exe diag\gerar_thumbs.py --dry-run  # so mede, nao grava
    .venv\Scripts\python.exe diag\gerar_thumbs.py --limite 500
    .venv\Scripts\python.exe diag\gerar_thumbs.py --refazer   # regera as existentes

Pode rodar com a captura no ar: so LE as fotos e escreve arquivos "_small" que
a captura nunca abre. E interrompivel (Ctrl+C) e retomavel - o que ja existe e
pulado.
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wa import storage  # noqa: E402

EXTENSOES = {".jpeg", ".jpg", ".png", ".webp"}


def imagens(pasta: Path):
    """Fotos da pasta, ignorando as proprias miniaturas."""
    for p in sorted(pasta.iterdir()):
        if p.is_file() and p.suffix.lower() in EXTENSOES and not p.stem.endswith("_small"):
            yield p


def main() -> int:
    ap = argparse.ArgumentParser(description="Gera as miniaturas _small que faltam.")
    ap.add_argument("--dry-run", action="store_true", help="so conta, nao grava")
    ap.add_argument("--refazer", action="store_true", help="regera mesmo se ja existir")
    ap.add_argument("--limite", type=int, default=0, help="processa no maximo N fotos")
    args = ap.parse_args()

    pasta = storage.IMG_DIR
    if not pasta.exists():
        print(f"Pasta nao encontrada: {pasta}")
        return 1

    ativo, max_px, fmt, ext, _extra, qualidade = storage._cfg_thumb()
    if not ativo:
        print("thumb_ativo=false no config.json - nada a fazer.")
        return 0
    print(f"Pasta   : {pasta}")
    print(f"Formato : {fmt} q{qualidade}, maior lado {max_px}px, extensao {ext}")
    print(f"Modo    : {'DRY-RUN' if args.dry_run else 'gravando'}"
          f"{' (refazendo existentes)' if args.refazer else ''}\n")

    feitas = puladas = falhas = 0
    bytes_orig = bytes_thumb = 0
    t0 = time.perf_counter()
    try:
        for i, foto in enumerate(imagens(pasta), 1):
            if args.limite and feitas + puladas >= args.limite:
                break
            destino = storage.caminho_thumbnail(foto)
            if destino.exists() and not args.refazer:
                puladas += 1
            elif args.dry_run:
                feitas += 1
            else:
                saida = storage.gerar_thumbnail(str(foto))
                if saida:
                    feitas += 1
                    bytes_orig += foto.stat().st_size
                    bytes_thumb += Path(saida).stat().st_size
                else:
                    falhas += 1
            if i % 500 == 0:
                print(f"  {i:6d} fotos varridas | {feitas} geradas, {puladas} puladas, "
                      f"{falhas} falhas | {time.perf_counter() - t0:.0f}s")
    except KeyboardInterrupt:
        print("\nInterrompido - o que ficou pronto esta no disco; rodar de novo retoma.")

    seg = time.perf_counter() - t0
    print(f"\nGeradas {feitas} | puladas {puladas} | falhas {falhas} | {seg:.0f}s")
    if bytes_thumb:
        print(f"Original das geradas: {bytes_orig / 1e6:.1f} MB  ->  "
              f"miniaturas: {bytes_thumb / 1e6:.1f} MB  "
              f"({100 * bytes_thumb / bytes_orig:.1f}% do tamanho)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
