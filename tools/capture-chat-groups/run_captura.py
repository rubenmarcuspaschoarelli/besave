"""
Lancador da captura usando os grupos JA cadastrados em conf/config.json.

Existe para evitar uma armadilha real: passar o nome do grupo na linha de comando
pode PERDER caracteres do emoji (o '@achadinhoscomcarol' tem variation selector
U+FE0F, que sumiu no copy/paste -> PowerShell em 25/07). Como o estado do grupo e
indexado pelo nome EXATO, um caractere a menos faz o programa nao achar o marcador
e cair em baseline (nao captura o passado). Lendo o nome do proprio config, o nome
usado e sempre identico a chave do estado.

Uso:
    .venv\\Scripts\\python.exe -u run_captura.py                 # catch-up dos 3 grupos
    .venv\\Scripts\\python.exe -u run_captura.py --seg-grupo 8
    .venv\\Scripts\\python.exe -u run_captura.py --max 40        # sweep (ignora datas)
"""

import argparse
import json
import sys
from datetime import datetime

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


class _PrefixoHora:
    """
    Carimba data/hora no inicio de CADA linha do stream.

    Existe por causa de 02/08/2026: a maquina dormiu 45h no meio de um run e o
    log — so com '[browser] Abrindo grupo...' repetido — nao dava como perceber
    o buraco. Com o carimbo, um salto no tempo salta aos olhos.

    Prefixa na transicao de linha (nao por chamada de write) para que texto
    multilinha, como o 'Call log' do Playwright, saia carimbado linha a linha.
    """

    def __init__(self, stream):
        self._stream = stream
        self._nova_linha = True

    def write(self, texto: str) -> int:
        if not texto:
            return 0
        saida = []
        for parte in texto.splitlines(keepends=True):
            if self._nova_linha:
                saida.append(datetime.now().strftime("[%d/%m %H:%M:%S] "))
            saida.append(parte)
            self._nova_linha = parte.endswith(("\n", "\r"))
        return self._stream.write("".join(saida))

    def flush(self) -> None:
        self._stream.flush()

    def __getattr__(self, nome):
        return getattr(self._stream, nome)


sys.stdout = _PrefixoHora(sys.stdout)
sys.stderr = _PrefixoHora(sys.stderr)

from wa.monitor import captura_msg_whatsapp
from wa.storage import CONFIG_PATH


def grupos_do_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        dados = json.load(f)
    return list((dados.get("grupos") or {}).keys())


def main():
    ap = argparse.ArgumentParser(description="Captura os grupos cadastrados em conf/config.json.")
    ap.add_argument("--max", type=int, default=0, dest="max_historico",
                    help="Sweep das ultimas ~N msgs de CADA grupo (IGNORA o controle de data).")
    ap.add_argument("--force-capture-today", action="store_true", dest="force_capture_today",
                    help="Ignora o estado salvo e captura tudo desde 00:00 de hoje.")
    ap.add_argument("--seg-grupo", type=int, default=5, dest="seg_grupo",
                    help="Segundos parado em cada grupo antes de pular (padrao: 5).")
    args = ap.parse_args()

    grupos = grupos_do_config()
    if not grupos:
        print(f"[run] Nenhum grupo em {CONFIG_PATH}. Rode o main.py uma vez com os nomes.")
        return 1

    print(f"[run] Grupos lidos de {CONFIG_PATH}:")
    for g in grupos:
        print(f"[run]   - {g!r}")

    # O codigo de saida importa: 0 = encerramento normal, 3 = perdemos o browser
    # embaixo do run (ver SAIDA_BROWSER_MORTO em wa/monitor.py). Sem isso, quem
    # lanca nao consegue distinguir "acabou" de "morreu" — foi assim que um run
    # ficou ~2h girando em falso em 03/08/2026.
    return captura_msg_whatsapp(
        nomes_grupos=grupos,
        intervalo=3,
        headless=False,
        max_historico=args.max_historico,
        seg_grupo=args.seg_grupo,
        force_capture_today=args.force_capture_today,
    ) or 0


if __name__ == "__main__":
    sys.exit(main())
