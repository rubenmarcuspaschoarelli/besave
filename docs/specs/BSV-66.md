# BSV-66 · Captura web de apoio: Pelando, Promobit e Pechinchou para a fila

**Papel:** Python (só stdlib + `oracledb`) · **Pasta:** `tools/capture-web-apoio/` (+ `tools/tests/` e
`tools/tests/fixtures/web/`, já com as fixtures) · **Roda em:** PC do dono (Windows), não na VPS ·
**Depende de:** nada. AD-113, AD-117; CONTRATO §4.3; lições 14, 29, 33

## Contexto
Programa auxiliar, rodado no PC do dono (IP residencial), que lê três sites de ofertas e põe na
`BESAVE.OFERTA_FILA_CAPTURA` algumas ofertas de Amazon, Mercado Livre e Shopee, como uma linha do WhatsApp.
O robô das lojas (inst1) faz o resto: abre a página da loja, cadastra produto e imagem, gera o **nosso**
link de afiliado e aplica as regras de hoje (duplicidade, pausa, preço). Serve de complemento e de reserva
quando o WhatsApp cai. Não captura imagem nem abre página de produto.

**Sem navegador.** Os três sites entregam as ofertas num JSON dentro do HTML da lista (medido em 25/11 com
`urllib`, HTTP 200 nos 12 menus). Uma requisição por menu; no Promobit, mais uma por oferta escolhida (o link
da loja não vem na lista). O `robots.txt` dos três permite essas páginas; `/api/*` é proibido no Promobit e
no Pechinchou e **não** é usado.

O link que vai para o site é sempre o oficial, gerado pelo robô das lojas no painel de afiliado
(`DS_URL_AFILIADO`); oferta sem ele não é publicada (CONTRATO §10.1). A marca de afiliado dos sites de
origem é tirada da URL antes de gravar mesmo assim (Saída 4).

## Saídas

### 1. Leitura dos sites (só `urllib.request`)
Menus (em `config.json`, com estes padrões):

| site | `DS_ORIGEM` | menus (URL) |
|---|---|---|
| Pelando | `PELANDO` | `https://www.pelando.com.br/recentes`, `/mais-baratos`, `/mais-quentes` |
| Promobit | `PROMOBIT` | `https://www.promobit.com.br/`, `/promocoes/recentes/`, `/promocoes/em-alta/`, `/promocoes/menor-preco/` |
| Pechinchou | `PECHINCHOU` | `https://pechinchou.com.br/recentes`, `/destaques`, `/menor-preco`, `/mais-pontuados`, `/pechinchas` |

Requisição: `User-Agent` de Chrome de computador (no `config.json`), `Accept-Language: pt-BR`, **sem**
`Accept-Encoding` (resposta sem compressão), sem cookies guardados, timeout 20 s. Pausa aleatória de
`pausa_s` (padrão `[3, 6]`) entre **todas** as requisições. Uma repetição em timeout/5xx. **403 ou 429** =
o site para naquela rodada (sem mais requisições nele) e aviso (Saída 7). Só a primeira página de cada menu
(sem paginação).

### 2. Extração por site (fixtures reais em `tools/tests/fixtures/web/`, recortadas em 25/11)

**Pelando** (`pelando_lista.html`): o `<astro-island ...>` cujo atributo `props` (HTML-escapado) contém
`initialDeals`. `props` é JSON na serialização do Astro: todo valor é `[tipo, valor]`; tipo `0` = valor
(objeto: cada campo de novo `[tipo, valor]`), tipo `1` = lista (cada item `[tipo, valor]`); outro tipo = usar
o valor cru. Lista = `initialDeals`.

| dado | campo | regra |
|---|---|---|
| id na origem | `id` | |
| título | `title` | |
| preço por | `price` | número em reais (`105.41`) |
| preço de | — | não existe → `NULL` |
| loja (exibição) | `store.name` | só log |
| URL da loja | `sourceUrl` | **não** usar `redirectUrl` |
| publicada em | `createdAt` | ISO UTC (`Z`) |
| válida | `status == "active"`, `kind == "promotion"`, `hideInFeed` ausente ou falso | senão descarta |
| cupom | — | não existe na lista |

**Promobit** (`promobit_lista.html`): `<script id="__NEXT_DATA__">`, lista em
`props.pageProps.serverOffers.offers` (anúncios ficam em `cardsAds`/`smallAds` e são ignorados).

| dado | campo | regra |
|---|---|---|
| id na origem | `offerId` | |
| título | `offerTitle` | |
| preço por | `offerPrice` | só se `offerPriceType == "NORMAL"` (em `COUPON` e `STARTING_AT` o preço é `0.01`, falso) |
| preço de | `offerOldPrice` | `NULL` se ausente, `≤ 0.01` ou `≤ preço por` |
| loja | `storeDomain` | filtro antes do redirect (Saída 3) |
| URL da loja | GET `https://www.promobit.com.br/Redirect/to/{offerId}/` | HTTP 200 com a URL em `l = '<url>'` no script e no `<a href>` do `<p>` (`promobit_redirect.html`); primeira das duas que achar |
| publicada em | `offerPublished` | ISO com offset (`-0300`) |
| válida | `offerStatusName` em `RECENTS`, `APPROVED`, `TOP_OFFER` | outro valor descarta, com o valor no log |
| cupom | `offerCoupon` | string ou `null` |

**Pechinchou** (`pechinchou_lista.html`): `__NEXT_DATA__`, lista em `props.pageProps.promos.results`.

| dado | campo | regra |
|---|---|---|
| id na origem | `id` + `slug` | o `id` sozinho se repete |
| título | `title` | |
| preço por | `price` | string decimal (`"23.97"`); descarta se `is_any_text_price` |
| preço de | `old_price` | `NULL` se ausente ou `≤ preço por` |
| loja | `store.slug_url` | |
| URL da loja | `long_url` | |
| publicada em | `created_at` | ISO com offset |
| válida | `status == "ACTIVE"` | `CLOSED` e outros descartam |
| cupom | `coupons` | lista de strings |

Estrutura ausente (sem a ilha / sem `__NEXT_DATA__` / chave da lista faltando / item sem campo obrigatório
em **todos** os itens) = **erro de estrutura** do menu (Saída 7), nunca exceção que pare a rodada.

### 3. Filtros, na ordem (cada descarte conta no resumo com o motivo)
1. inválida pela tabela do site;
2. publicada na origem há mais de `idade_max_horas` (padrão **24**) ou no futuro além de 10 min;
3. loja fora de Amazon, Mercado Livre e Shopee, pelo domínio da URL limpa (Saída 4) — no Promobit, primeiro
   por `storeDomain` (`amazon.com.br`, `mercadolivre.com.br`, `shopee.com.br`) para não gastar redirect;
4. já vista (Saída 5);
5. preço por ausente ou ≤ 0.

### 4. URL limpa e loja
Antes de qualquer gravação ou comparação:

| loja (`DS_LOJA`) | aceita | grava |
|---|---|---|
| `AMAZON` | `amazon.com.br` com `/dp/{ASIN}`, `/gp/product/{ASIN}` ou `/gp/aw/d/{ASIN}` | `https://www.amazon.com.br/dp/{ASIN}` |
| `MERCADO LIVRE` | `mercadolivre.com.br` (e subdomínios) | esquema + host + caminho, sem query nem `#` |
| `SHOPEE` | `shopee.com.br` com `/product/{shop}/{item}`, `/{qualquer}/{shop}/{item}` ou `-i.{shop}.{item}` | `https://shopee.com.br/product/{shop}/{item}` |

Encurtadores (`meli.la`, `amzn.to`, `s.shopee.com.br`, `mercadolivre.com/sec/`): **uma** requisição sem
seguir redirect (`HTTPRedirectHandler` desligado), lê o `Location` (até 3 saltos) e limpa. Não resolveu =
descarta (`encurtador_nao_resolvido`), nunca grava o link curto de terceiro. URL limpa > 350 caracteres =
descarta. A URL de origem com marca de terceiro (`tag=`, `matt_`, `utm_`…) **nunca** vai para log nem banco.

### 5. Já vista (não gastar o robô das lojas com repetida)
Uma oferta é **pulada** quando qualquer uma vale:
1. **estado local** (`estado/vistas.json`, gravado ao fim de cada rodada): `site:id_origem` visto nos últimos
   7 dias (entradas mais velhas saem);
2. **mesma rodada:** a mesma chave de produto já entrou (menus se repetem);
3. **chave de produto** (ASIN, `MLB` + dígitos, `{shop}.{item}` da Shopee — mesma regra de
   `capture-store-pages/core/duplicidade.chave_loja`, reimplementada aqui, sem importar o outro robô) presente
   nas últimas 24 h em `OFERTA_FILA_CAPTURA.DS_URL_ORIGEM` (por `DT_OFERTA`) **ou** numa `OFERTA` ativa com
   `DS_URL_FINAL` contendo a chave e `VL_PRECO_POR ≤` o preço novo;
4. **mesmo título**: título normalizado (minúsculas, sem acento, só letras e dígitos, espaços únicos) igual ao
   de uma linha da fila das últimas 24 h com o mesmo `DS_LOJA` e `VL_PRECO_POR` a até 1% do novo.

Oferta mais barata que a já publicada **entra**: a regra de duplicidade do robô das lojas desativa a mais cara.
Consulta ao banco com bind, `LIKE '%' || :chave || '%'`, uma por candidata.

### 6. Gravação na fila
`INSERT` com lista de colunas (sem `ID_OFERTA`: a trigger da sequence preenche), `RETURNING ID_OFERTA`:

| coluna | valor |
|---|---|
| `DS_TIPO_ORIGEM` | `'CAPTURA WEB'` |
| `DS_ORIGEM` | `'PELANDO'`, `'PROMOBIT'` ou `'PECHINCHOU'` |
| `DS_TIPO_OFERTA` | `'PRODUTO'` |
| `DT_OFERTA`, `DT_CAPTACAO` | `CAST(SYSTIMESTAMP AT TIME ZONE '-03:00' AS DATE)` (hora de Brasília, como as outras linhas) |
| `DS_OFERTA` | título, trim, ≤ 350 |
| `VL_PRECO_DE` / `VL_PRECO_POR` | reais com centavos (`NUMBER`), como na fila hoje |
| `DS_URL_ORIGEM` | URL limpa (Saída 4) |
| `DS_LOJA` | `'AMAZON'`, `'MERCADO LIVRE'` ou `'SHOPEE'` |
| `DS_CUPOM` | códigos válidos pela regra do CONTRATO §4.3 (trim, maiúsculas, `^[A-Z0-9_-]{1,30}$`, sem repetidos, até 5) unidos por `\|`; nenhum → `NULL` |
| `DS_CUPOM_LOJA` | `DS_LOJA` quando há cupom, senão `NULL` |
| `ST_CAPTURA` | `'0'` |

`COMMIT` por linha. Falha de conexão: uma reconexão e repetição; falhou de novo, a rodada para (as já
gravadas ficam) e avisa.

### 7. Cotas, rodada e avisos
- **Cota:** `por_menu` (padrão **5**) ofertas gravadas por menu e `teto_rodada` (padrão **30**) na rodada.
  Ordem: rodízio entre sites (Pelando, Promobit, Pechinchou) e, dentro do site, entre menus, na ordem da
  página; atingido o teto, a rodada termina sem novas requisições. Com 30, cada site fica com cerca de 10.
- **Rodada:** `python main.py` = uma rodada agora (manual); `--simular` = lê, filtra e mostra o que gravaria,
  **sem** conectar ao banco para gravar (as consultas da Saída 5 rodam, só leitura) e sem atualizar o estado
  local. Uma rodada por vez (arquivo de trava; segunda instância sai com código 2).
- **Resumo** no log, por site e menu: lidas, válidas, gravadas, descartes por motivo, ids da fila gravados.
- **Telegram** (bloco `alerta` do `config.json`, mesmo formato do robô das lojas; vazio = só log), **uma
  mensagem por rodada**, só quando houver problema:
  `Captura web: <site> <problema>[; <site> <problema>]. Gravadas N oferta(s).` com `<problema>` em
  `estrutura mudou em <menu>`, `bloqueado (HTTP <código>)`, `sem resposta`; e
  `Captura web: banco fora do ar; gravadas N oferta(s) antes da falha.`
  Site que leu tudo e não achou oferta válida **não** é problema (só log).
- Log em `log/` com rotação (14 dias); nada de URL com marca de terceiro, senha ou token.

### 8. Agendamento (PC)
`agendar.ps1` (rodado pelo dono uma vez) registra a tarefa `besave-captura-web` no Agendador do Windows: às
**08:00, 12:00 e 17:00**, usuário atual, só quando logado, **sem** "executar assim que possível depois de
perder" (PC desligado = perde a rodada), sem repetir, limite de 30 min. Horários vêm de parâmetros do script
com esses padrões. `--remover` apaga a tarefa.

### 9. Usuário do banco só para este programa
`sql/bsv-66-usuario.sql` (o dono roda como ADMIN; a senha entra por variável de substituição, nunca no
arquivo):
```sql
CREATE USER BESAVE_WEB IDENTIFIED BY "&senha";
GRANT CREATE SESSION TO BESAVE_WEB;
GRANT SELECT, INSERT ON BESAVE.OFERTA_FILA_CAPTURA TO BESAVE_WEB;
GRANT SELECT ON BESAVE.OFERTA TO BESAVE_WEB;
```
Com reversão comentada (`DROP USER BESAVE_WEB CASCADE`). O programa usa `BESAVE.` antes de cada tabela.
Conexão como no robô das lojas (`modo` thick/thin, `dsn` do wallet, `config_dir`, `instant_client_dir`).

### 10. `config.json` / `README.md`
`conf/config.json` fora do git; `conf/config.example.json` versionado com: `db` (sem senha; senha também por
`BESAVE_WEB_SENHA`, que vence), `alerta`, `user_agent`, `pausa_s`, `por_menu`, `teto_rodada`,
`idade_max_horas`, `sites` (por site: `habilitado` e lista de menus). Chave inválida = padrão com WARN.
README: o que faz, instalação no Windows (venv, `pip install -r requirements.txt`), usuário do banco,
agendamento, `--simular`, como ler o resumo e o que fazer com cada aviso (mudança de HTML = atualizar a
fixture e o extrator).

## Regras
1. Sem navegador e sem dependência nova (`oracledb` já é dependência dos robôs; mesma versão).
2. Nenhuma requisição a `/api/*` dos sites, nem a páginas fora das tabelas acima.
3. Não importa código de `capture-store-pages` nem de `capture-chat-groups` (roda em outra máquina).
4. Nenhuma URL com marca de afiliado de terceiro no banco ou no log.
5. Testes não fazem rede nem banco reais: extratores sobre as fixtures; `urllib` e cursor simulados.
6. Teste de mensagem e de SQL compara o texto inteiro (lição 14).

## Fora de escopo
- Prioridade entre WhatsApp e captura web na fila (quem entra primeiro sai primeiro — decisão do dono).
- Rodar sozinho quando o WhatsApp cair; paginação; imagens; outros sites; Linux/VPS.
- Qualquer mudança no robô das lojas, no worker ou no banco além do usuário da Saída 9.

## Critério de aceite
- Testes (`tools/tests/test_web_*.py`, unittest ou pytest como os outros), derivados das Saídas:
  - extração das três fixtures: quantidade e campos de cada oferta válida comparados por igualdade; Astro
    decodificado (Pelando); `COUPON`/`STARTING_AT` descartados (Promobit); `CLOSED` descartada (Pechinchou);
    `kind: coupon` e `status: expired` descartados (Pelando); fixture sem a ilha / sem `__NEXT_DATA__` →
    erro de estrutura, sem exceção;
  - redirect do Promobit: URL lida de `promobit_redirect.html`; sem URL → descarte;
  - URL limpa: tabela de casos (Amazon com `tag=`, `/gp/product/`, ML com `#`/query, Shopee nos três
    formatos, domínio fora, > 350) com a saída inteira; encurtador com `Location` simulado (1 e 3 saltos,
    sem `Location` → descarte);
  - idade: relógio fixo; 23 h 59 entra, 24 h 01 sai, futuro > 10 min sai;
  - já vista: cada um dos 4 casos pula; preço menor que a ativa entra; estado local de 8 dias é esquecido;
  - cota: `por_menu` e `teto_rodada` com rodízio (ordem das gravações comparada inteira); teto atingido = sem
    requisição a mais;
  - `INSERT` comparado inteiro (SQL e binds), cupons pela regra §4.3 (`'25 Full'` cai, repetido sai, 6 → 5);
  - 403 → site para na rodada, outros seguem, uma mensagem; estrutura mudou → mensagem; tudo ok → nenhuma
    mensagem; mensagens comparadas inteiras;
  - `--simular` não grava nem chama `INSERT`; segunda instância → código 2.
- `pytest` e `ruff check` do job `tools` verdes, com `capture-web-apoio/` no `ruff` e no `conftest.py`.
- **Real (dono, PC, branch da PR; bloqueia o merge):**
  1. `sql/bsv-66-usuario.sql` aplicado; `python main.py --simular` → resumo dos três sites com ofertas
     válidas e nenhuma gravação;
  2. `python main.py` → até 30 linhas na fila com `DS_TIPO_ORIGEM='CAPTURA WEB'`; nenhuma
     `DS_URL_ORIGEM` com `tag=`, `utm_`, `matt_` ou encurtador (consulta de leitura);
  3. o robô das lojas processa essas linhas como as outras (`ok` com `afiliado=ok`, ou `'9'` pelos motivos de
     sempre);
  4. segunda rodada logo depois → as mesmas ofertas puladas como já vistas;
  5. `agendar.ps1` cria a tarefa; o Agendador mostra os três horários; uma execução pela tarefa grava o log;
  6. evidência redigida (regra 11): sem caminho com usuário, senha, token ou `chat_id`.

## Definition of done
PR para `develop` com código, testes, README, `config.example.json`, `sql/bsv-66-usuario.sql`,
`agendar.ps1`, `validation.md` do Verifier independente (sensor de discriminação) e evidência redigida.
