# BSV-44 · Investigação: Shopee pela API de afiliados em vez do navegador

**Papel:** Python (pesquisa + protótipo) · **Pasta:** `tools/capture-store-pages/programas_ajuste/` (protótipo)
e `docs/specs/BSV-44-relatorio.md` · **Depende de:** nada. AD-101, AD-104

## Contexto
A captura da Shopee pelo navegador está quebrada: nos 7 dias até 16/10, 102 ok e 293 erros no PC (274
"bloqueado_ou_login"), e 0/10 na VPS (o captcha abre e responde "A verificação falhou"). A Shopee tem um
programa de afiliados com API própria (GraphQL assinado com HMAC-SHA256; endpoint do Brasil citado por
SDKs de terceiros como `open-api.affiliate.shopee.com.br/graphql`; consultas `productOfferV2` e
`generateShortLink`). Nada disso foi conferido na documentação oficial ainda.

## Objetivo
Responder, com evidência, se a API de afiliados da Shopee substitui o navegador para os dados que o
Besave grava (título, preço de/por, imagem, loja, nota, avaliações, link de afiliado) e em que condições.

## Saídas
1. **Relatório** (`BSV-44-relatorio.md`, ≤ 2 páginas): documentação oficial encontrada (links); como obter
   acesso (app ID e secret no portal de afiliados; quem pode pedir; prazo); limites de uso; campos
   disponíveis × colunas de `OFERTA`/`PRODUTO`/`OFERTA_FILA_CAPTURA` (tabela com o que falta); como o link
   de afiliado sai (curto, de quem é a comissão); termos de uso relevantes; recomendação (adotar, adotar
   em parte, descartar) com o motivo.
2. **Protótipo** (só se o dono já tiver credencial): `programas_ajuste/shopee_api_teste.py` que, para os
   IDs de oferta Shopee de um CSV, resolve o link curto do grupo, consulta a API e grava um CSV de
   comparação (campo a campo) com o que o robô capturou quando funcionou. Credencial lida do
   `config.json` (fora do git); nada grava no banco.
3. Se a recomendação for adotar: rascunho do ticket de implementação (pastas, mudança no fluxo do
   `main.py`, o que acontece com as ofertas pendentes de hoje).

## Regras
1. Regra 8: só fonte oficial da Shopee vale como fato; SDK de terceiro é pista, e o relatório diz qual é
   qual.
2. Nenhuma credencial, app ID ou ID de afiliado no repositório nem no relatório (regra 11).
3. Sem dependência nova; HTTP com `requests` (já está no `requirements.txt`).
4. Não mexer no fluxo de produção do robô.

## Fora de escopo
Implementar a troca, outras lojas, automação de login, contornar captcha.

## Critério de aceite
- Relatório com cada afirmação ligada a uma fonte (oficial ou marcada como terceiro) e a tabela de
  campos completa.
- Com credencial: protótipo rodado sobre ≥ 10 ofertas Shopee recentes, CSV de comparação anexado ao PR
  (URLs de afiliado de terceiros trocadas por `REDACTED`).
- **Real (dono):** decisão registrada (AD) a partir do relatório.

## Definition of done
PR com relatório (e protótipo, se houver credencial), sem segredos, revisado pelo dono.
