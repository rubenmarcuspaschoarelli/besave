"""
DIAGNOSTICO (30/07/2026) — a ORDEM do que _coletar_subindo devolve.

Pergunta a responder, medindo em vez de teorizar:
  1) 'cronologico' sai ASCENDENTE (antiga->nova), como o codigo anuncia e como o
     recorte por POSICAO exige, ou nao?
  2) o marker_id aparece? em que INDICE? o que cada um dos dois recortes
     (posicao e data) devolveria a partir dessa lista?

POR QUE ELE EXISTE (30/07/2026): o recorte por POSICAO de _capturar_desde_ultima
(`cronologico[indice_do_marcador + 1:]`) depende INTEIRAMENTE de a lista sair em
ordem cronologica. O assentamento (28/07) e a hidratacao (29/07) quebraram essa
premissa em silencio: as passadas seguintes anexam AO MESMO CHUNK mensagens que
hidrataram depois e sao mais ANTIGAS. O sintoma e sorteado pela posicao em que o
marcador cai — marcador no inicio da lista devolve o historico velho inteiro (o
carol regravou 27 linhas anteriores ao proprio marcador e o marcador andou para
tras, 21:42 -> 15:29); marcador perto do fim devolve ZERO e o dia se perde (Ly e
#03 deram "0 novas" tendo mensagens que o rodizio pegou segundos depois).
Um bug, dois sintomas OPOSTOS — por isso vale medir em vez de teorizar.

RODE ESTE SCRIPT sempre que mexer na caminhada da subida (_coletar_subindo,
assentamento, hidratacao, ancora). O sinal que decide e OS DOIS RECORTES
CONCORDAREM: antes do fix 46 vs 27 com 19 pre-marcador; depois 43 vs 43 com 0.

E READ-ONLY quanto a estado: nao grava CSV, nao toca Oracle, nao chama
_gravar_cronologico (que e quem avanca marcador e contador). As imagens tmp que a
subida salva no caminho sao apagadas no fim. Pode rodar com a captura PARADA — o
perfil do Chrome (user_data/) e exclusivo, dois processos nao abrem o mesmo.

Uso:  .venv\\Scripts\\python.exe -u diag\\diag_ordem.py ["nome do grupo"]
      (sem argumento usa o 1o grupo do conf/config.json)
"""

import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

os.environ["WA_DEBUG_SUBIDA"] = "1"          # liga a instrumentacao ja existente

# O pacote 'wa' esta na raiz, um nivel acima de diag/. Caminho relativo ao proprio
# arquivo: nao quebra se o projeto mudar de pasta nem depende do cwd de quem roda.
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from playwright.sync_api import sync_playwright  # noqa: E402

from wa import browser, estado as estado_mod, monitor, storage  # noqa: E402


def fmt(dh):
    return estado_mod.fmt_dt(dh) or "-"


def escolher_grupo(est, pedido: str | None) -> str:
    """
    Devolve SEMPRE uma chave existente em conf/config.json.

    O argumento da linha de comando serve so para CASAR com a chave, nunca como
    nome literal: nome com emoji perde caractere no caminho shell -> argv (o
    '@achadinhoscomcarol 🛍️' tem um variation selector U+FE0F que sumiu no
    copy/paste em 25/07), e o estado e indexado pelo nome EXATO. Casando por
    trecho, o nome usado e identico a chave — mesma razao de existir do
    run_captura.py.
    """
    chaves = list((est.get("grupos") or {}).keys())
    if not chaves:
        raise SystemExit("[diag] conf/config.json nao tem grupo nenhum.")
    if not pedido:
        return chaves[0]
    alvo = pedido.strip().lower()
    casados = [k for k in chaves if alvo in k.lower()]
    if len(casados) == 1:
        return casados[0]
    if not casados:
        raise SystemExit(f"[diag] {pedido!r} nao casa com nenhum grupo: {chaves}")
    raise SystemExit(f"[diag] {pedido!r} e ambiguo, casa com: {casados}")


def main():
    est = estado_mod.carregar()
    GRUPO = escolher_grupo(est, sys.argv[1] if len(sys.argv) > 1 else None)
    g = estado_mod.get_grupo(est, GRUPO) or {}
    cutoff = estado_mod.parse_dt(g.get("ultima_data_hora"))
    marker = g.get("ultimo_data_id")
    print(f"[diag] grupo   : {GRUPO!r}")
    print(f"[diag] marcador: {g.get('ultima_data_hora')!r} / data_id={marker!r}")

    with sync_playwright() as pw:
        context = None
        try:
            context, page = browser.abrir_whatsapp(pw, headless=False)
            browser.abrir_grupo(page, GRUPO)
            page.wait_for_timeout(800)

            itens, achou, processados = monitor._coletar_subindo(
                page, cutoff_dt=cutoff, marker_id=marker,
            )

            print(f"\n[diag] === devolvido: {len(itens)} item(ns), "
                  f"achou_marcador={achou}, baloes vistos={len(processados)} ===")

            # 1) ORDEM
            datas = [it["data_hora"] for it in itens]
            print("[diag] sequencia na ordem devolvida:")
            print("      " + " ".join(fmt(d)[-5:] for d in datas))
            pares = [(a, b) for a, b in zip(datas, datas[1:]) if a and b]
            desc = sum(1 for a, b in pares if a > b)
            asc = sum(1 for a, b in pares if a < b)
            print(f"[diag] pares: {asc} ascendentes, {desc} DESCENDENTES, de {len(pares)}")
            if desc == 0:
                veredito = "ASCENDENTE (ok para recorte por posicao)"
            elif asc == 0:
                veredito = "DESCENDENTE por inteiro (recorte por posicao INVERTIDO)"
            else:
                veredito = "MISTA (blocos) — recorte por posicao NAO e confiavel"
            print(f"[diag] VEREDITO DA ORDEM: {veredito}")

            # Estrutura de blocos: onde a sequencia quebra para tras.
            blocos, ini = [], 0
            for i in range(1, len(datas)):
                if datas[i] and datas[i - 1] and datas[i] < datas[i - 1]:
                    blocos.append((ini, i - 1))
                    ini = i
            blocos.append((ini, len(datas) - 1))
            print(f"[diag] {len(blocos)} bloco(s) internamente ascendente(s):")
            for a, b in blocos:
                print(f"      [{a:>3}..{b:>3}] {fmt(datas[a])} -> {fmt(datas[b])}")

            # 2) O QUE CADA RECORTE DEVOLVERIA
            ids = [it["data_id"] for it in itens]
            if marker and marker in ids:
                idx = ids.index(marker)
                pos = itens[idx + 1:]
                antes = sum(1 for it in pos if it["data_hora"] and cutoff and it["data_hora"] < cutoff)
                print(f"\n[diag] marcador no INDICE {idx} de {len(ids)-1} "
                      f"(data {fmt(itens[idx]['data_hora'])})")
                print(f"[diag] recorte por POSICAO devolveria {len(pos)} item(ns), "
                      f"dos quais {antes} com data ANTERIOR ao marcador "
                      f"{'<-- E O DEFEITO' if antes else ''}")
                if pos:
                    print(f"[diag]   primeira={fmt(pos[0]['data_hora'])} "
                          f"ultima={fmt(pos[-1]['data_hora'])} "
                          f"(a ULTIMA e quem vira o novo marcador)")
                    mais_nova = max((it['data_hora'] for it in pos if it['data_hora']), default=None)
                    print(f"[diag]   mais nova do lote={fmt(mais_nova)} -> marcador "
                          f"{'RETROCEDE' if mais_nova and pos[-1]['data_hora'] != mais_nova else 'ok'}")
            else:
                print(f"\n[diag] marcador NAO esta na lista (achou={achou}).")
            if cutoff:
                por_data = [it for it in itens if it["data_hora"] and it["data_hora"] > cutoff]
                print(f"[diag] recorte por DATA (>{fmt(cutoff)}) devolveria {len(por_data)} item(ns)")

            print("\n[diag] NADA foi gravado: sem CSV, sem Oracle, marcador intacto.")
        finally:
            if context is not None:
                try:
                    context.close()
                except Exception:  # noqa: BLE001
                    pass

    # As imagens tmp da subida sao lixo do diagnostico.
    apagadas = 0
    for f in os.listdir(storage.IMG_DIR):
        if f.startswith("tmp"):
            try:
                os.remove(os.path.join(storage.IMG_DIR, f))
                apagadas += 1
            except OSError:
                pass
    print(f"[diag] imagens tmp apagadas: {apagadas}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
