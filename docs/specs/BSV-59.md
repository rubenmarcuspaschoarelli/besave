# BSV-59 · Robô das lojas: Shopee pela API de afiliados (produto e link sem navegador)

**Papel:** Python (stdlib) · **Pasta:** `tools/capture-store-pages/` · **Depende de:** BSV-55 (linha retida,
pausa por loja e Telegram), **mergeada em `develop` antes de abrir o worktree**. Lições 14, 16, 29

## Contexto
A Shopee é capturada pelo navegador: a página do produto (seletores com hash que mudam a cada deploy da
Shopee) e o link de afiliado no gerador `affiliate.shopee.com.br/offer/custom_link`. Os dois quebram com
frequência: a página cai em `verify/traffic` (anti-bot) e o gerador sem sessão de afiliado. Fila
`OFERTA_FILA_CAPTURA`, URLs da Shopee, últimos 30 dias (10/11):

| `ST_CAPTURA` / `DS_CAPTURA` | linhas |
|---|---|
| `1 ok` | 714 |
| `9 bloqueado_ou_login` | 455 |
| `0` retidas (`sessao_afiliado_ausente`, desde 06/11) | 225 |
| `9 pagina_sem_produto` | 168 |
| `9 descartada_atraso_bsv` | 146 |

Ou seja, metade das ofertas da Shopee se perde ou fica parada. Nenhuma das 712 ofertas da Shopee em `OFERTA`
tem `DS_ID_PRODUTO_AFILIADO` nem `DS_TAXA_COMISSAO_PROD_AFILIADO` (o Mercado Livre preenche os dois).

A Shopee tem uma API de afiliados (GraphQL, `https://open-api.affiliate.shopee.com.br/graphql`, documentação em
`https://affiliate.shopee.com.br/open_api/home`) que devolve os dados do produto (`productOfferV2`) e gera o
link de afiliado (`generateShortLink`), sem navegador.

**Medido em 10/11:**
- As 1.728 URLs da Shopee na fila (30 dias) são **todas** `https://s.shopee.com.br/<código>`; nenhuma traz
  `shopId`/`itemId` na URL.
- `curl -sI` (sem seguir) num desses links, da inst1 e do PC do dono: **`301`** com
  `Location: https://shopee.com.br/opaanlp/<shopId>/<itemId>?…&utm_source=an_<afiliado-de-terceiro>…`.
  Sem bloqueio para o IP da OCI (diferente do `promos.link`, BSV-58): resolver o link curto **não** precisa do
  navegador nem do túnel.
- Uma chamada `productOfferV2(matchId: <itemId>)` feita pelo dono devolveu **20 produtos sem relação** com o
  item (`hasNextPage: true`): `matchId` é listagem, não busca por item. A busca por item é
  `productOfferV2(shopId: …, itemId: …)`.

## Decisão do dono (10/11)
A API substitui o navegador **na Shopee**, para o produto e para o link de afiliado. Amazon e Mercado Livre
não mudam. Perde-se o que só a página tinha (descrição, detalhes técnicos, país de origem, quantidade de
avaliações, galeria com várias fotos); o contrato já trata esses campos como opcionais.

## Pré-condição (dono, antes de abrir o worktree)
Com o app de afiliado (`app_id`/`app_secret`) no `conf/config.json` do PC, provar as duas chamadas com o link
medido em 10/11 (ou outro da fila):
1. `productOfferV2(shopId: <shopId>, itemId: <itemId>)` → **exatamente 1** nó, com o mesmo `itemId`, e
   `productName`, `price`, `imageUrl`, `ratingStar`, `sales`, `commissionRate` preenchidos.
2. `generateShortLink(input: {originUrl: "https://shopee.com.br/product/<shopId>/<itemId>"})` →
   `shortLink` `https://s.shopee.com.br/…`, e o `longLink` com `utm_source=an_<nosso afiliado>`.
3. Na documentação: o limite de chamadas (por hora/dia) e a janela de validade do `Timestamp` da assinatura;
   anotar os dois aqui.

A saída vai para esta spec **redigida** (`app_id`, afiliado, assinatura → `REDACTED`). Se o passo 1 devolver
lista ou nó de outro item, esta spec volta para o arquiteto.

## Saídas
1. **Configuração** em `conf/config.json` (fora do git) e `conf/config.example.json` (valores fictícios, com
   `_obs`):
   ```json
   "shopee_afiliado": {
     "habilitado": false,
     "app_id": "<app_id>",
     "app_secret": "<app_secret>",
     "timeout_segundos": 20
   }
   ```
   Bloco ausente ou `habilitado: false` = fluxo de hoje (navegador). É o retorno sem deploy.
2. **`core/shopee_api.py`** (só stdlib: `urllib.request`, `hashlib`, `json`, `time`):
   - **Assinatura:** `Authorization: SHA256 Credential=<app_id>, Timestamp=<ts>, Signature=<hex>`, com
     `<hex>` = SHA-256 de `app_id + ts + payload + app_secret`, onde `payload` é **a mesma string** enviada
     como corpo (serializada uma vez). `ts` = segundos Unix.
   - **`produto(shop_id, item_id)`** → `(dados, None)` ou `(None, motivo)`. Só aceita resposta com 1 nó cujo
     `itemId` é o pedido.
   - **`link_afiliado(shop_id, item_id)`** → `generateShortLink` com `originUrl`
     `https://shopee.com.br/product/<shopId>/<itemId>` (URL limpa: nunca a URL do grupo, que traz o
     `utm`/afiliado de terceiro) → `(shortLink, None)` ou `(None, motivo)`.
   - **Motivos:** `api_indisponivel` (timeout, erro de rede, HTTP 5xx), `api_credencial` (erro de
     autenticação/assinatura devolvido pela API), `api_limite` (limite de chamadas), `fora_do_programa`
     (nenhum nó: item sem oferta de afiliado), `item_divergente` (nó de outro `itemId` ou mais de um nó). O
     código do erro GraphQL vai no log; o corpo da resposta não.
3. **Resolução da URL** (`core/shopee_api.py`, `resolver(url)`): link `s.shopee.com.br` → um pedido **sem
   seguir redirect**, lê o `Location`; até 3 saltos. Extrai `shopId`/`itemId` destes formatos (fixtures nos
   testes):
   - `shopee.com.br/<qualquer>/<shopId>/<itemId>` (ex.: `/opaanlp/…`, `/product/…`), dois últimos segmentos
     numéricos do caminho;
   - `shopee.com.br/<slug>-i.<shopId>.<itemId>` (também dentro de `/universal-link/`).

   Fora disso → `url_nao_reconhecida`. Resolver o link curto conta como clique no link do terceiro; não há
   como evitar e é o que o navegador já faz hoje.
4. **`main.py`**: linha da Shopee com `shopee_afiliado.habilitado` → resolve, consulta, gera o link e
   **não abre a página da Shopee nem a aba do gerador**. Preenche as mesmas chaves que a captura da página e o
   `link_afiliado` preenchem hoje:

   | chave de hoje | campo da API | regra |
   |---|---|---|
   | `produto_titulo` | `productName` | trim |
   | `preco_1` (→ `VR_PRECO_1`) | `price` | texto → `Decimal`, 2 casas; nunca `float` intermediário |
   | `avaliacao_nota` | `ratingStar` | |
   | `quantidade_vendida` | `sales` | |
   | `url_afiliado` | `shortLink` do item 2 | |
   | `taxa_comissao_afiliado` | `commissionRate` | no **mesmo formato** que Amazon/ML gravam hoje (`"0.13"` → percentual) |
   | `id_produto_afiliado` (→ `DS_ID_PRODUTO_AFILIADO`) | `shopId`, `itemId` | `<shopId>.<itemId>` (como no `-i.` da URL; o item sozinho não identifica o anúncio na API) |
   | imagem `img_1.jpg` | `imageUrl` | mesmo `download_image` e mesmo caminho de hoje; 1 foto |

   Não mudam: `VL_PRECO_POR`/`VL_PRECO_DE` vêm da mensagem do grupo e a cascata de `core/precos.py` continua
   decidindo o preço final (`VR_PRECO_1` só entra quando a mensagem não tem preço). `priceMin`/`priceMax`
   **não** são gravados: são a faixa de variantes do anúncio, não o histórico de preço (`VR_PRECO_MINIMO`/
   `MAXIMO` seguem calculados por `core/produtos.py`). `shopName` **não** vai para marca/fabricante.
   `usa_imagem_loja` por grupo continua valendo como hoje.
5. **Falhas:**
   - `api_indisponivel`, `api_credencial`, `api_limite` → status novo `shopee_api_indisponivel` em
     `STATUS_RETER`: linha `'0'`, `oracle=retida(0)`, ponteiro travado (igual à BSV-55). Entram na
     `PausaLojas` com a chave `shopee`: 3 seguidas → pausa, Telegram com o motivo, lembrete e "voltou".
     `api_credencial` diz no aviso "conferir `app_id`/`app_secret`".
   - `fora_do_programa`, `item_divergente`, `url_nao_reconhecida` → `'9'` com esse motivo em `DS_CAPTURA` (não
     é falha passageira; retida para sempre travaria o ponteiro).
6. **README** (`tools/capture-store-pages/README.md`, seção Shopee): o que a API traz e o que se perdeu,
   como ligar/desligar (`habilitado`), onde fica a credencial (só `conf/config.json`), o que cada motivo
   significa.

## Regras
1. Sem dependência nova (nem `requests`): `urllib` + `hashlib`.
2. `app_secret`, a assinatura, o cabeçalho `Authorization`, o `app_id` e o nosso id de afiliado nunca aparecem
   em log, exceção, CSV, Telegram ou evidência (regra 11). Log: `shopee api: ok item=<itemId>` e o motivo.
3. O link de afiliado é gerado **sempre** a partir da URL limpa do item; nada da URL do grupo (`utm_source`,
   `gads_t_sig`, afiliado de terceiro) entra no `originUrl` nem em `DS_URL_AFILIADO`.
4. Dinheiro do texto da API → `Decimal`; nunca `float(price)` direto.
5. `habilitado: false` reproduz o fluxo de hoje byte a byte (mesmo caminho do navegador).
6. Amazon, Mercado Livre e o robô do WhatsApp não mudam.

## Fora de escopo
- Buscar ofertas novas pela API (vitrine por categoria/palavra-chave): a fila continua vindo dos grupos.
- Gravar `productCatIds`, `shopName`, `priceDiscountRate` ou a faixa de variantes em coluna nova.
- Remover o código do navegador da Shopee (fica atrás do `habilitado: false` até a decisão do dono depois de
  uma semana em produção).
- `subIds` no `generateShortLink` para medir clique por canal: ticket próprio depois (confirmar na
  documentação).

## Retidas antigas (SQL no PR, aplicado pelo dono antes de ligar)
As 225 linhas `'0'` da Shopee desde 06/11 têm preço velho; não devem ser publicadas quando a API ligar.
```sql
SELECT COUNT(*) FROM OFERTA_FILA_CAPTURA
 WHERE ST_CAPTURA = '0' AND DS_URL_ORIGEM LIKE '%shopee%' AND DT_CAPTACAO < SYSDATE - 1;
UPDATE OFERTA_FILA_CAPTURA SET ST_CAPTURA = '9', DS_CAPTURA = 'descartada_atraso_bsv'
 WHERE ST_CAPTURA = '0' AND DS_URL_ORIGEM LIKE '%shopee%' AND DT_CAPTACAO < SYSDATE - 1;
```

## Critério de aceite
Testes com servidor HTTP falso local (ou `urlopen` substituído), no padrão de `tools/tests/`. Nenhum espelha a
implementação.

- **Assinatura:** vetor fixo (`app_id`, `ts`, `payload`, `secret` fictícios) → hex esperado calculado à mão no
  teste; o corpo enviado é byte a byte o `payload` assinado (o mutante que reserializa o JSON falha).
  Cabeçalho comparado inteiro (lição 14).
- **Resolução:** `s.shopee` → 301 `/opaanlp/<shop>/<item>` → ids; `-i.<shop>.<item>` e
  `/universal-link/…-i.<shop>.<item>` → ids; `/product/<shop>/<item>` → ids; 4 saltos → `url_nao_reconhecida`;
  página sem ids → `url_nao_reconhecida`. O pedido do link curto **não** segue redirect.
- **Produto:** 1 nó do item → chaves da tabela do item 4; `price "89.99"` → `VR_PRECO_1` 89.99 e `"19.9"` → 19.90;
  `price` vazio ou não numérico → `'9' item_divergente` (sem preço não se publica); 0 nó → `'9' fora_do_programa`; nó de outro `itemId` →
  `'9' item_divergente`; 20 nós (o caso do `matchId`) → `'9' item_divergente`.
- **Link:** `originUrl` enviado é exatamente `https://shopee.com.br/product/<shop>/<item>` mesmo quando a URL
  do grupo traz `utm_source=an_<terceiro>`; `DS_URL_AFILIADO` = `shortLink`.
- **Sem navegador:** com `habilitado: true`, nenhuma chamada a `page.goto` para `shopee.com.br` nem a
  `_shopee`/`_aba_shopee` (navegador falso que falha se chamado).
- **Desligado:** `habilitado: false` ou bloco ausente → fluxo do navegador chamado como hoje (o mutante que
  ignora o `habilitado` falha nos dois sentidos).
- **Falhas:** timeout → `retida(0)`, nada em `OFERTA`, ponteiro travado; 3 seguidas → pausa `shopee` + 1
  aviso; volta → "voltou" e a retida processada; erro de assinatura → retida com "conferir app_id/app_secret"
  no aviso; Amazon/ML seguem `ok` durante a pausa da Shopee.
- **Segredo:** com `app_secret`/`app_id` fictícios e distintos de qualquer outro valor do teste (lição 11),
  nenhuma saída capturada (stdout, log, exceção, CSV, Telegram falso) contém nenhum dos dois, nem a assinatura.
- **Gates:** `cd tools && python -m pytest -q`, ruff do CI de `tools/`.
- **Real (dono, bloqueia o merge), na inst1 com a branch e `habilitado: true`:**
  1. SQL das retidas antigas aplicado (contagem antes/depois na PR);
  2. 3 linhas novas da Shopee → `oracle=ok`, oferta no site com título, preço, imagem e CTA `/ir/<id>` que
     abre a Shopee com `utm_source=an_<nosso afiliado>` (conferir o redirect final, redigido na evidência);
     `DS_ID_PRODUTO_AFILIADO` e `DS_TAXA_COMISSAO_PROD_AFILIADO` preenchidos;
  3. `app_secret` errado no config → linhas `retida(0)`, pausa e Telegram com "conferir credencial";
     corrigido → "voltou";
  4. `habilitado: false` → volta ao navegador sem reiniciar nada além do robô;
  5. 24 h com `habilitado: true`: contagem por `DS_CAPTURA` da Shopee contra a tabela do Contexto.

## Definition of done
PR para `develop` com config e exemplo, `core/shopee_api.py`, integração no `main.py`, README, testes,
`validation.md` do Verifier independente (com sensor de discriminação), evidência redigida (regra 11), o SQL
das retidas e as decisões propostas (Shopee pela API; `fora_do_programa` vira `'9'`; id do produto como
`<shopId>.<itemId>`; navegador da Shopee mantido atrás do `habilitado`) para o `docs/DECISOES.md`.
