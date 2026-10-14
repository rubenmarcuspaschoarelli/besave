"""
Resolve o preco "por" final de uma oferta -- cascata de regras, cada uma so
troca o preco se o valor novo for MENOR (nunca sobe, sempre mantem o mais
barato visto entre os candidatos ate agora):

1. VL_PRECO_POR (preco de origem, mensagem do WhatsApp) ausente -> usa
   VR_PRECO_1 (preco capturado na pagina). So substitui quando VL_PRECO_POR e
   nulo -- nao compara os dois quando ambos tem valor (decisao do usuario,
   2026-09-28: manter esta regra como estava, so as de baixo comparam de
   verdade).
2. VR_RECORRENCIA ("Assine e economize", Amazon) > 0 e MENOR que o preco da
   regra 1 -> vira o preco final.
3. VR_ESPERE_ECONOMIZE ("Espere e economize", Amazon -- escolher entrega mais
   lenta para ganhar desconto) > 0 e MENOR que o preco das regras 1+2 -> vira
   o preco final. So a Amazon preenche este campo por ora; nas demais lojas
   fica NULL e a regra e um no-op.

Usado por core/ofertas.py (feed BESAVE.OFERTA) e core/produtos.py
(BESAVE.PRODUTO.VR_PRECO_MINIMO/MAXIMO) -- os dois precisam do MESMO preco
final, cada um no seu ponto de gravacao.
"""

# Ordem importa: cada regra so entra depois que a anterior ja decidiu o preco
# "corrente" -- mas como cada uma so troca se for MENOR, a ordem nao muda o
# resultado (e o minimo dos candidatos presentes).
_CAMPOS_DESCONTO_CONDICIONAL = ('VR_RECORRENCIA', 'VR_ESPERE_ECONOMIZE')


def resolver_preco_por(linha):
    """`linha` e um dict com pelo menos VL_PRECO_POR/VR_PRECO_1 e, quando a
    loja capturar, VR_RECORRENCIA/VR_ESPERE_ECONOMIZE. Retorna o preco final
    (float) ou None se nenhum candidato existir."""
    preco = linha.get('VL_PRECO_POR')
    if preco is None:
        preco = linha.get('VR_PRECO_1')
    for campo in _CAMPOS_DESCONTO_CONDICIONAL:
        candidato = linha.get(campo)
        if candidato is not None and candidato > 0:
            if preco is None or candidato < preco:
                preco = candidato
    return preco
