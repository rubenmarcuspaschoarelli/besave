"""
Agente de captura de mensagens do WhatsApp Web (um ou varios grupos em rodizio).

Uso:
    # um grupo. Na 1a vez marca baseline (so novas); nas proximas RETOMA
    # automaticamente desde a ultima mensagem lida (estado por grupo em
    # ./config.json).
    python main.py "Nome do Grupo"

    # varios grupos em rodizio (le novas, espera, pula p/ o proximo, e repete)
    python main.py "Grupo A" "Grupo B" "Grupo C"

    # SWEEP: varre as ultimas ~40 msgs de CADA grupo (IGNORA o controle de data)
    python main.py "Grupo A" "Grupo B" "Grupo C" --max 40

    # captura tudo desde 00:00 de hoje (ignora o estado salvo; util na estreia)
    python main.py "Grupo A" --force-capture-today

    # tempo (segundos) parado em cada grupo antes de pular
    python main.py "Grupo A" "Grupo B" --seg-grupo 8

Controle de data/hora (por grupo): a cada mensagem gravada o programa anota em
./config.json a data/hora (do WhatsApp) e o data-id da ultima mensagem lida, alem
do contador global `controle.ultimo_id_processado` (ID_OFERTA continuo entre
execucoes). Assim, ao reiniciar, retoma de onde parou sem repetir nem perder
mensagens. --max e --force-capture-today ignoram esse controle de data.

Primeira execucao: o navegador abre e pede o QR Code (leia com o celular).
Nas proximas, a sessao ja fica salva em ./user_data e entra direto.
"""

import argparse
import sys

# Garante UTF-8 na saida (nomes de grupo tem emoji, ex.: "Promos da Ly ✨").
# Sem isso, no Windows com stdout redirecionado para arquivo o print quebra
# com UnicodeEncodeError (codec cp1252).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

from wa.monitor import captura_msg_whatsapp


def main():
    ap = argparse.ArgumentParser(description="Captura promocoes de um ou mais grupos do WhatsApp Web.")
    ap.add_argument("nomes_grupos", nargs="+",
                    help="Nome(s) do(s) grupo(s) a monitorar (como aparecem na busca).")
    ap.add_argument("--max", type=int, default=0, dest="max_historico",
                    help="Sweep das ultimas ~N msgs de CADA grupo (IGNORA o controle de data).")
    ap.add_argument("--force-capture-today", action="store_true", dest="force_capture_today",
                    help="Ignora o estado salvo e captura tudo desde 00:00 de hoje.")
    ap.add_argument("--seg-grupo", type=int, default=5, dest="seg_grupo",
                    help="Segundos parado em cada grupo antes de pular (padrao: 5).")
    ap.add_argument("--intervalo", type=int, default=3, help="(reservado)")
    ap.add_argument("--headless", action="store_true", help="Roda sem interface (nao use na 1a vez).")
    args = ap.parse_args()

    captura_msg_whatsapp(
        nomes_grupos=args.nomes_grupos,
        intervalo=args.intervalo,
        headless=args.headless,
        max_historico=args.max_historico,
        seg_grupo=args.seg_grupo,
        force_capture_today=args.force_capture_today,
    )


if __name__ == "__main__":
    main()
