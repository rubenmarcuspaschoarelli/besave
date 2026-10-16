# Resumo — CaptureAmazon (multi-loja)

_Última atualização: 2026-09-28. **Imagem de OFERTA no bucket do site**
(`s3/ofertas/img`) — funcionalidade portada do `AgenteCapturaWhatsapp`
(`DOCS/ESPEC_CONVERSAO_IMAGEM_S3_OFERTAS.md`): substitui a foto original do
WhatsApp pela foto capturada na página do produto, só para os grupos de
origem marcados em `conf/config.json` → `"grupos"`. Implementado, testado e **RODADO no S3 real**: 6.280 imagens publicadas, 80
puladas (sem foto em disco), 0 falhas, de 6.360 ofertas de
`@achadinhoscomcarol 9`. Ver seção logo abaixo._

_Anterior (2026-09-28, mesma sessão): **"Espere e economize"** (Amazon, escolher
entrega mais lenta por preço menor) — `VR_ESPERE_ECONOMIZE`/`ST_ESPERE_ECONOMIZE`
entram na MESMA cascata de preço da recorrência (regra 3), agora numa função
compartilhada `core/precos.py`. SPs recompiladas e testadas — **só falta o
seletor de captura em `stores/amazon.py`** (precisa de HTML real da página,
ver "Onde paramos"). Ver seção logo abaixo._

_Anterior (2026-09-28, mesma sessão): **Cupom fora do padrão** (código duplo unido
por "|", ex. "MODA2309 | LOJASOFICIAIS") passa a virar 2 registros distintos em
`BESAVE.CUPOM`, e `ID_ULT_OFERTA` (nova coluna) rastreia a última oferta que
usou cada cupom — implementado, SP recompilada, histórico corrigido (69 linhas
erradas separadas) e backfilado (713/843 cupons com `ID_ULT_OFERTA`). Ver seção
logo abaixo._

_Anterior (2026-09-28, mesma sessão): **Recorrência ("Assine e economize",
Amazon)** combinada em `VR_RECORRENCIA`/`ST_RECORRENCIA`, nova regra de preço
(recorrência mais barata vence) e `QT_MINIMA_RECORRENCIA` levado até `OFERTA`
— implementado, 3 SPs recompiladas e histórico completo backfilado._

_Anterior (2026-09-24): **Cópia de imagens por produto (`.webp`)**
implementada, integrada ao `main.py`, validada em produção e com o BACKFILL DO
HISTÓRICO COMPLETO (11.933 produtos, 9.887 com foto publicada) — ver seção logo abaixo._

_Anterior (2026-09-10): **`DS_URL_AFILIADO`** (link OFICIAL do programa de
afiliados de cada loja, clicado no widget da própria página) implementado e integrado ao
`main.py` — ver a seção "Link OFICIAL de afiliado". Antes disso (02/09): `DS_URL_BESAVE` implementado (link com o NOSSO código de
afiliado) e backfilado no histórico. `QT_OPINIOES`/`DS_AVALIACAO_GERAL` (Mercado Livre)
implementados e EM PRODUÇÃO. Cadastro consolidado `BESAVE.PRODUTO` (8.781) e feed
`BESAVE.OFERTA` (17.137) implementados, backfilados e **integrados ao `main.py`** — toda
captura de sucesso já sai com produto cadastrado e oferta publicada na mesma passada. O
monitor rodou sozinho de 31/07 a 31/08 sem intervenção de código.

## 🎯 Onde paramos  — retomar por aqui

**⏸️ 28/09/2026: "Espere e economize" (Amazon) — backend pronto, falta SÓ o
seletor de captura.** Usuário identificou 2 ajustes na regra de preço:

1. **Confirmado, já estava certo**: a recorrência só substitui `VL_PRECO_POR`
   quando é MENOR — nunca sobe o preço. Validado com um caso real do histórico
   (oferta 21310, produto ASIN B0CYVJYTDL): `VL_PRECO_POR`=49,78 (origem),
   `VR_PRECO_1`=43,81 (página), `VR_RECORRENCIA`=44,80 — aqui a recorrência é
   MAIS CARA que o preço da página, mas como a regra 1 só compara
   `VL_PRECO_POR` (nunca `VR_PRECO_1`, decisão antiga do usuário) contra a
   recorrência, o resultado vira 44,80 (`min(49.78, 44.8)`) — correto pela
   regra definida, mas **não é o menor valor absoluto dos 3** (que seria
   43,81). Mencionado ao usuário como FYI; não mudado sem pedido explícito.
2. **Novo campo `VR_ESPERE_ECONOMIZE`/`ST_ESPERE_ECONOMIZE`** (Amazon,
   escolher entrega mais lenta por um preço menor) — mesmo comportamento da
   recorrência: só substitui o preço se for MENOR que o preço já resolvido
   pelas regras 1+2. Colunas já criadas pelo usuário em `OFERTA_FILA_CAPTURA`
   e `OFERTA` (não em `PRODUTO`, mesmo padrão da recorrência).

**Refatoração**: a cascata de preço (antes duplicada em `core/ofertas.py` e
`core/produtos.py`) virou uma função só, `core/precos.py::resolver_preco_por()`
— usada pelos dois. Regra 3 (`VR_ESPERE_ECONOMIZE`) adicionada lá.

**Backend 100% pronto e testado** (round-trip com ID fake: preço 30/recorrência
28/espere-e-economize 25 → gravou `VL_PRECO_POR=25`, o menor dos 3):
`sql/STP_OFERTA_FILA_CAPTURA_UPDATE.STP` e `sql/STP_OFERTA_PUBLICAR.STP`
recompiladas (+`P_VR_ESPERE_ECONOMIZE`/`P_ST_ESPERE_ECONOMIZE`); `core/oracle_db.py`
(`COLUNAS_PARA_OFERTA`/`COLUNAS_PARA_PRODUTO`); `core/ofertas.py`/`core/produtos.py`
usando `resolver_preco_por()`.

**Captura implementada com o HTML real** (usuário mandou 2 blocos: o preço
"Compra única" R$47,90, idx=0, e o de "Espere e economize" R$43,90, idx=1).
Achado: os dois preços usam a MESMA classe (`apex-pricetopay-value`/
`a-offscreen`, igual o preço principal já capturado como `preco_1`) — a
única diferença entre as linhas do acordeão é o TEXTO da legenda ("Compra
única" vs a legenda da 2ª linha, que deve conter "economize"). Por isso o
seletor identifica pelo TEXTO da legenda dentro do `<h5>` que envolve
legenda+preço da mesma linha, não pelo índice (`buying-option-idx` varia
conforme quantas opções o produto tem):

```
#buybox h5:has-text("economize") .apex-pricetopay-value .a-offscreen
```

`stores/amazon.py` (`espere_economize`, `price: True`, igual `preco_1`) +
`core/oracle_db.py` (`MAPA_CAMPOS`, `_NUMERICOS`, `P_ST_ESPERE_ECONOMIZE`
derivado em `atualizar_captura`) + SPs recompiladas de novo.

**✅ Testado e CONFIRMADO ao vivo (28/09/2026)**: unitário (bind/cascata) +
round-trip no banco + captura real contra a página (script isolado, só
captura, nada gravado no Oracle). Os 2 primeiros links de exemplo dados
inicialmente (B0i2g1flG, B0fnHTGlA, B0hiPNhbk) já não mostravam mais a opção
no momento do teste (oferta é dinâmica, vai e volta) — o usuário corrigiu
para `link.amazon/B0fVwHyrj`, que capturou **`preco_1=47.90` /
`espere_economize=43.90`**, batendo exatamente com o HTML original. Seletor
confirmado funcionando tanto no caso positivo (acha o valor) quanto negativo
(produto sem a opção → vazio, sem erro).

**➡️ Próximo passo**: nenhum — feature completa (regra de preço + captura),
testada ponta a ponta. Só acompanhar no dia a dia se `ST_ESPERE_ECONOMIZE`
aparece com alguma frequência razoável nas capturas reais.

### 🎫 Cupom fora do padrão ("|") + `ID_ULT_OFERTA` (2026-09-28)

Achado do usuário: em alguns casos a origem manda mais de 1 código de cupom no
MESMO campo, unidos por `" | "` (ex. oferta 30303: `DS_CUPOM = "MODA2309 |
LOJASOFICIAIS"`), e o programa vinha gravando essa string INTEIRA como se fosse
1 único `CUPOM` em `BESAVE.CUPOM` — errado, e às vezes ainda **truncado em 30
caracteres** (limite da coluna), cortando o 2º/3º código no meio (achado
paralelo: essa truncagem já acontece na ORIGEM, `OFERTA_FILA_CAPTURA.DS_CUPOM`
é `VARCHAR2(30 BYTE)` — fora do nosso controle, é outro sistema/tabela).

**Também**: nova coluna `BESAVE.CUPOM.ID_ULT_OFERTA` (criada pelo usuário) —
guarda o `ID_OFERTA` da última captura que gravou/atualizou aquele cupom.

**Pontas mexidas**:
- `sql/STR_CUPOM_UPSERT.STP`: +`P_ID_ULT_OFERTA` (atribuição direta no INSERT,
  `NVL` no UPDATE). A SP em si **não separa nada** — sempre recebe 1 código
  por chamada.
- `core/cupons.py`: `_separar_codigos()` quebra `DS_CUPOM` em `"|"`, e
  `publicar_cupom()` chama a SP **uma vez por código** — mesma `DS_LOJA`/
  `DS_CUPOM` (comentário)/`ID_ULT_OFERTA`, `CUPOM` diferente, `ID_CUPOM` novo
  para cada. Retorno mudou de `(id, erro)` para `(lista de ids, erro)`.
- `core/oracle_db.py`: `ID_OFERTA` entrou em `COLUNAS_PARA_CUPOM` (a SP precisa
  saber qual oferta está gravando).
- `main.py` / `backfill_cupons.py`: ajustados para o novo retorno em lista
  (log com os IDs separados por vírgula).
- `backfill_cupom_split.py` (novo, rodado 1x): corrigiu as **69 linhas já
  gravadas erradas** no histórico — separa em N códigos (find-or-create) e
  apaga a linha antiga. Todas as 69 corrigidas, 0 erro.
- `backfill_cupom_ult_oferta.py` (novo, rodado 1x): preenche `ID_ULT_OFERTA`
  no histórico **só nos casos fáceis** (mesmo código + mesma loja batendo
  exatamente contra `OFERTA.DS_CUPOM`, pega a oferta mais recente) — decisão
  do usuário de não tentar casar os cupons que vieram de um "|" (o
  `OFERTA.DS_CUPOM` de origem continua com a string unida, nunca bate exato
  contra 1 código só). **713 de 843 cupons preenchidos**; os outros 130 ficam
  sem `ID_ULT_OFERTA` (não é erro, só não achou com segurança).

**Estado final** (checado após os 2 backfills, idempotentes — rodar de novo
não muda nada): 843 linhas em `CUPOM`, 0 com `"|"`, 0 acima de 30 caracteres,
713 com `ID_ULT_OFERTA`.

### 🔁 `VR_RECORRENCIA`/`ST_RECORRENCIA` + regra de preço + `QT_MINIMA_RECORRENCIA` (2026-09-28)

Pedido do usuário: unir os 2 fragmentos já capturados na página da Amazon
(`VR_PRECO_RECORRENCIA_INTEIRO`="18" + `VR_PRECO_RECORRENCIA_FRACAO`="99") num
único `VR_RECORRENCIA` (18.99), marcar `ST_RECORRENCIA` (1 com recorrência, 0
sem), e — quando essa recorrência for **mais barata** que o preço corrente —
usá-la para substituir `VL_PRECO_POR`, que por sua vez alimenta o mínimo/máximo
do produto. Também levar `QT_MINIMA_RECORRENCIA` (já capturado, campo raro) até
a tabela `OFERTA` (coluna nova criada pelo usuário, junto com `VR_RECORRENCIA`/
`ST_RECORRENCIA` em `OFERTA` e `OFERTA_FILA_CAPTURA`).

**Achado antes de implementar**: a captura de `VR_PRECO_RECORRENCIA_INTEIRO/
FRACAO` (via `#sns-base-price`) e de `QT_MINIMA_RECORRENCIA` (via
`#trigger_popover` + extração de dígitos) **já funcionava** — 3.461/8.359
ofertas Amazon e 367 ofertas já tinham esse dado gravado, respectivamente. Não
houve mudança de seletor; só faltava combinar/propagar o que já existia.

**Achado paralelo (não relacionado ao pedido)**: o arquivo
`sql/STP_OFERTA_PUBLICAR.STP` estava **vazio no disco** (0 bytes, provavelmente
desde a recompilação do `ST_ATIVO` em 25/09) — o código-fonte real foi
recuperado direto do Oracle (`USER_SOURCE`) antes de editar, e o arquivo foi
reescrito por completo.

**Regras de preço, na ordem** (decidido com o usuário, ver conversa):
1. (já existia, mantida como estava) `VL_PRECO_POR` ausente na origem (mensagem
   sem preço) → usa `VR_PRECO_1` (preço capturado na página). **Só substitui
   quando `VL_PRECO_POR` é nulo** — não compara os dois quando ambos têm valor.
2. (nova) Depois da regra 1: se `VR_RECORRENCIA > 0` e for **menor** que o
   preço resultante da regra 1, o preço final passa a ser `VR_RECORRENCIA`.
3. O preço final (pós regras 1+2) alimenta `OFERTA.VL_PRECO_POR` e, através
   dele, `PRODUTO.VR_PRECO_MINIMO/MAXIMO` (`core/produtos.py`/`core/ofertas.py`
   aplicam a MESMA cascata, cada um no seu ponto de gravação).
   `OFERTA.VR_PRECO_1`/`VR_RECORRENCIA` continuam com os valores CRUS
   capturados (informativo), só `VL_PRECO_POR` reflete a cascata.

**`'Outros'` em vez de `NULL`** (`DS_COMUNIDADE`/`DS_CATEGORIA_PROD_AFILIADO`,
mesmo pedido): aplicado em `OFERTA` (por registro, sem risco) e também em
`PRODUTO.DS_COMUNIDADE` — com uma proteção extra na SP
(`sql/STP_PRODUTO_UPSERT.STP`): `'Outros'` só entra quando a coluna está `NULL`
ou já é `'Outros'`, **nunca sobrescreve uma comunidade real** já identificada
antes, e ainda deixa a porta aberta para uma classificação real corrigir um
`'Outros'` depois (o `NVL` puro travaria `'Outros'` para sempre).

**Pontas mexidas**:
- `stores/amazon.py`: removida `recorrencia_quantidade_minima` (entrada morta,
  duplicada sem `_descricao`, não mapeada a nenhuma coluna).
- `core/oracle_db.py`: `_recorrencia()` combina INTEIRO+FRACAO → injetado em
  `atualizar_captura`; `VR_RECORRENCIA` em `COLUNAS_PARA_PRODUTO`; as 3 colunas
  novas em `COLUNAS_PARA_OFERTA`.
- `sql/STP_OFERTA_FILA_CAPTURA_UPDATE.STP`: +`P_VR_RECORRENCIA`/
  `P_ST_RECORRENCIA` (atribuição direta, como os demais campos de
  recorrência — não é `NVL`-preservado).
- `sql/STP_OFERTA_PUBLICAR.STP`: reescrita completa (ver achado acima) +3
  parâmetros novos.
- `sql/STP_PRODUTO_UPSERT.STP`: proteção do `'Outros'` em `DS_COMUNIDADE`
  (`CASE`, ver acima).
- `core/ofertas.py` / `core/produtos.py`: regra 2 da cascata de preço +
  defaults `'Outros'`.
- `backfill_recorrencia.py` (novo): Fase 1 (preenche as 3 colunas, UPDATE puro,
  sem SP) + Fase 2 `--tambem-preco` (corrige `VL_PRECO_POR` e recalcula
  `VR_PRECO_MINIMO/MAXIMO` **do zero**, por agregação `MIN/MAX` sobre as
  ofertas atuais do produto — não incrementalmente, porque o `GREATEST`
  incremental da SP nunca *diminui* um máximo antigo).

**Armadilha achada na recompilação**: os `.STP` deste projeto terminam com uma
linha `/` (terminador de SQL*Plus) que o `oracledb` não entende num
`cursor.execute()` de bloco único — `PLS-00103: Encountered the symbol "/"`,
deixando a SP `INVALID` (a `CREATE OR REPLACE` já tinha substituído o objeto
antigo). Corrigido removendo a linha antes de executar; **backup do código-fonte
das 3 SPs tirado do `USER_SOURCE` antes de recompilar**, por segurança. Todas
recompiladas e validadas com um round-trip real (ID de teste inexistente,
removido depois) antes do backfill.

**Backfill rodado no histórico completo (28/09/2026)**:
- Fase 1: **26.392 ofertas** (`ST_CAPTURA='1'`) receberam `VR_RECORRENCIA`/
  `ST_RECORRENCIA` na fila; **25.883** espelhadas em `OFERTA`. 3.461 ficaram
  com `ST_RECORRENCIA=1` (981 produtos distintos), as demais com `0`.
- Fase 2: **2.386 ofertas** tiveram `VL_PRECO_POR` corrigido para baixo (a
  recorrência era mais barata) e os produtos afetados tiveram
  `VR_PRECO_MINIMO/MAXIMO` recalculados do zero. Checagem pós-backfill: 0
  produtos com mínimo > máximo, 0 ofertas com `ST_RECORRENCIA` nulo, rodada de
  novo em `--dry-run` confirma 0 pendências (idempotente).
- `OFERTA_FILA_CAPTURA.VL_PRECO_POR`/`VR_PRECO_1` (dados de origem) **não
  foram tocados** — só o preço final em `OFERTA`/`PRODUTO` foi corrigido.

**Backfill de `'Outros'` no histórico** (`backfill_outros.py`, novo,
28/09/2026 — a pedido do usuário na sequência): `OFERTA.DS_COMUNIDADE` (253),
`OFERTA.DS_CATEGORIA_PROD_AFILIADO` (23.180 — maioria esperada, o widget de
afiliado raramente traz categoria) e `PRODUTO.DS_COMUNIDADE` (188) que
estavam `NULL` viraram `'Outros'`. Não toca `PRODUTO_COMUNIDADE` (N:N — `'Outros'`
não é uma das 9 comunidades reais) nem `OFERTA_FILA_CAPTURA.DS_CATEGORIA_PROD_AFILIADO`
(captura RAW do widget, continua `NULL` quando o widget não trouxe nada,
preservado por `NVL` na SP). Rodada de novo em `--dry-run` confirma 0
pendências.

---

**✅ 23-24/09/2026: cópia de imagens por produto validada em produção E backfilada no
histórico inteiro** (11.933 produtos, 9.887 com foto — ver seção logo abaixo). Logs
temporários do backfill (`backfill_produtos_lote*.log`) já apagados. **Sessão encerrada
aqui, nada travado.** Próximo passo (fôlego, sem pressa): backfill de `QT_OPINIOES` do
histórico ML e a Magazine Luiza (ver pendências abaixo).

### 🖼️ Cópia de imagens por produto em `.webp` (2026-09-23)

Pedido do usuário: depois de capturar os dados e cadastrar o produto (`ID_PRODUTO`), copiar
as fotos da oferta (já com marca d'água, em `destino/img/<ID_OFERTA>/`) para a pasta do
PRODUTO no S3 do server, convertidas para `.webp` mantendo a resolução original. Se o
produto já tinha fotos (outra oferta da mesma família capturada antes), sobrescreve.

- **Novo módulo**: `core/imagens_produto.py` → `publicar_imagens_produto(id_produto,
  pasta_origem)`. Esvazia `E:\Work\besave\server\s3\produtos\img\<ID_PRODUTO>\` se já
  existir, depois grava cada foto de `pasta_origem` (ordem numérica `img_1, img_2, ...`)
  como `<ID_PRODUTO>_<seq>.webp` (qualidade 90, sem resize). O original em `destino/img/`
  nunca é alterado — é só leitura de lá.
- **Convenção de nome decidida com o usuário**: `<ID_PRODUTO>_<seq>.webp` (ex.:
  `234_1.webp`, `234_2.webp`) — não achamos código do lado do server lendo essa pasta
  ainda pra inferir sozinho.
- **Integrado ao `main.py`**: `out['pasta_imagens']` guarda o caminho usado por
  `store.get_images` na hora da captura; logo depois do `STP_PRODUTO_UPSERT` (mesmo bloco
  do cadastro de produto), chama `imagens_produto.publicar_imagens_produto(id_produto,
  out.get('pasta_imagens'))`. Best-effort, como cupom/produto: falha aqui NUNCA derruba a
  captura. Aparece no log como `imgs_produto=N`.
- **Testado isoladamente** (fora do fluxo ao vivo, com pastas de teste apagadas depois):
  conversão preserva resolução (679×679, 679×1879 confirmados) e a sobreposição funciona
  (produto que tinha 2 fotos e recebeu uma nova captura com só 1 ficou só com 1 — a antiga
  sobrando foi apagada). **Validado com captura real em produção no mesmo dia (23/09) —
  ok.**
- **Backfill do histórico CONCLUÍDO** (23/09, mesmo dia da validação): novo script
  `backfill_imagens_produto.py` — le `ID_OFERTA`/`ID_PRODUTO` já gravados no Oracle, sem
  reabrir página nem tocar em outro campo. Agrupa por `ID_PRODUTO` e usa a maior
  `ID_OFERTA` que tiver fotos no disco (a mais recente vence, reproduzindo o que o
  `main.py` teria feito se a cópia sempre tivesse existido) — só 1 conversão por
  produto, não 1 por oferta.
  - **Resultado final**: 11.933 produtos avaliados, **9.887 com foto publicada** no S3
    (os demais nunca tiveram nenhuma oferta com foto no disco -- não é bug, é histórico
    real sem imagem).
  - **Rodou em ~20 lotes** (`--desde`/`--limite`, retomável) em vez de um processo
    único: uma tentativa de rodar tudo de uma vez em background (~20h estimadas) foi
    abandonada a favor de lotes de 500-1000 produtos. Mesmo assim o Claude Code matou o
    processo em background 3 vezes por "pouca memória do sistema" enquanto a sessão
    ficava ociosa esperando (nada a ver com o script -- é o watchdog de memória do
    proprio Code) -- cada vez foi so retomar com `--desde <ultimo produto + 1>`, sem
    perda de trabalho (idempotente).
  - **Para produtos NOVOS** (capturados depois de 23/09): a cópia já roda sozinha
    dentro do `main.py`, esse script so serve se precisar reprocessar algo pontual.

**✅ 11/09/2026: fila ZERADA.** Depois do conserto da galeria da Amazon (ver *Tempo por
oferta* logo abaixo) o `--monitorar` rodou o dia inteiro e limpou a fila: **22.451
capturadas (`1`) / 3.002 erro (`9`) / 0 pendentes**, último ID 26017. Link oficial de
afiliado saltou de 53 para **760 ofertas** (ML 385, Amazon 300, Shopee 75). Das 303 ofertas
Amazon do dia, só 3 ficaram sem foto — e não por falha da galeria: são URLs
`/promotion/psp/...`, páginas de promoção que passam como `ok` (ver *Pendências menores*).

**➡️ Próximo passo**: nada travado. As pendências de fôlego continuam sendo o backfill de
`QT_OPINIOES` do histórico ML e a Magazine Luiza.

### ⏱️ Tempo por oferta no log + a galeria da Amazon (2026-09-11)

O usuário notou que a Amazon passava de 1 min por página e pediu (1) horário e duração no
log e (2) a investigação. As duas coisas estão feitas, e a segunda achou um problema maior
que lentidão: **a Amazon não estava salvando imagem nenhuma desde 10/09 18h28**.

**O log** (`_Cronometro` em `main.py`) — fases `ponte · nav · capt · img · afil · db`:

```
[11/09 10:32:29] linha 25292 | loja=mercadolivre | status=ok | oracle=ok | ... |  16.3s (nav 7.7 | capt 4.5 | img 2.1 | afil 2.1)

[tempos] media por loja (segundos):
  mercadolivre  n=4    total  14.3  (pior  16.3)  = nav 7.5 | capt 2.5 | img 2.4 | afil 1.8
```

⚠️ `_Cronometro.total` congela na última marcação de propósito. A 1ª versão media "agora
menos o início" e, como o resumo do lote só é lido no fim, linhas de 14s viravam média de
35s.

**O diagnóstico** (`teste_tempos.py --da-fila amazon 2`, novo — mede fase a fase, seletor a
seletor, miniatura a miniatura, sem gravar nada):

| | antes | depois |
|---|---|---|
| total | **125s** | **17,5s** |
| `img` | 105s | 1,9s |
| `capt` | 29s | 10,3s |
| `afil` | 1,8s | 1,0s (nunca foi o culpado) |
| imagens | **0** | 5, todas distintas |

**Causa raiz**: a Amazon trocou o `<input>` de cada miniatura por `<button>`. O
`get_images` clicava nesse `<input>`; sem timeout próprio o clique usava o padrão da página
(15s) e morria num `except Exception: pass` — **7 miniaturas × 15s = 105s por oferta, zero
imagem, zero log**. Quando ainda funcionava, o mesmo laço rebaixava todas as fotos já
carregadas a cada clique: **27 arquivos para 6 imagens distintas**, mais 6 GIFs de **43
bytes** (o `grey-pixel.gif` de lazy-load da Amazon) gravados como se fossem foto.

**A correção** — a Amazon saiu do modo "clicar na miniatura" e entrou no modo "ler URL",
como o Mercado Livre já fazia. `amazon_dump_galeria.py` (novo, mesmo papel do
`shopee_dump.py`/`ml_dump_barra.py`) mostrou onde estão as fotos:

| o quê | onde |
|---|---|
| galeria | `#imageBlock [data-a-dynamic-image]` — atributo com JSON `{url: [larg, alt]}` |
| escopo | **`#imageBlock` é essencial**: o mesmo atributo aparece nos carrosséis de "quem viu, viu" e traria fotos de OUTROS produtos |
| resolução | a maior anunciada no JSON é pequena (466px, 42 KB); tirando o recorte do nome (`._AC_SX466_`) vem a original: **2560px, 143 KB** |

Mudou também, para o problema não se repetir calado:

- `SCAN_TIMEOUT` virou por loja; Amazon = **1200ms** (era 4000). A Amazon é renderizada no
  servidor: campo ausente ao fim do `post_load_wait` não vai aparecer depois — eram **28s
  por oferta** só em campos opcionais ausentes (parcelamento, assinatura, "enviado por").
- `download_image` recusa HTTP≠200, `Content-Type` não-imagem e arquivo **< 1 KB** (o GIF de
  43 bytes), e devolve `True/False` — quem chama tenta a URL da página se a normalizada não
  existir.
- O modo "clicar na miniatura" continua existindo para quem precisar, mas com timeout de 3s
  e **aviso no log** quando as miniaturas não aceitam clique.

**Resolvido no mesmo dia**: as 36 ofertas Amazon (`25200…25505`) que ficaram com a pasta de
imagens vazia foram recuperadas por `backfill_imagens.py --loja amazon --desde 25190` —
**36 com imagem, 0 sem foto, 0 erro**, ~6s cada (sem varredura de campos nem link de
afiliado, é bem mais rápido que a captura completa). Preferiu-se isso a devolver à fila
(`ST_CAPTURA='0'`), que reescreveria preço, título e link de afiliado só para buscar foto.

O script serve para qualquer loja e é retomável (a fonte da verdade é o disco: quem já tem
foto sai da lista). As outras **89 pastas Amazon vazias são antigas**, de outras causas, e
não foram investigadas — `python backfill_imagens.py --loja amazon --listar` mostra todas.

---

**➡️ Próximo passo anterior: rodar `main.py --monitorar`** — das 933 ofertas `meli.la`
reenfileiradas, um lote de 40 já foi validado manualmente (35 ok, 5 `pagina_sem_produto`
legítimo, 0 erro — confirma que era rajada) e gravou `DS_URL_BESAVE`/`QT_OPINIOES`/
`DS_AVALIACAO_GERAL` corretamente. **Restam 893** esperando a próxima varredura do usuário
(decisão dele: rodar quando quiser, não precisa ser agora).

**Estado da fila em 02/09** (21.060 linhas, ID 496–21624), ANTES do reenfileiramento:
**17.439 `'1'` sucesso / 3.621 `'9'` erro / 0 `'0'` pendente**. Nada travado — o
`--monitorar` processou tudo sozinho até o último backup em 31/08 22h34. Motivos dos erros
(`DS_CAPTURA`):

| Motivo | Qtde | |
|---|---|---|
| `erro: Error` | 1625 | **933 eram `meli.la`** — ver investigação abaixo |
| `pagina_sem_produto` | 747 | cupom/lista/campanha — legítimo |
| `url_vazia` | 527 | linha sem `DS_URL_ORIGEM` |
| `bloqueado_ou_login` | 465 | sessão Shopee expirada entre varreduras — reprocessa sozinho após novo login |
| `loja_desconhecida` | 203 | domínio não mapeado |
| `erro: TargetClosedError` | 42 | aba/contexto fechado no meio da captura |
| `oferta_expirada` | 11 | ponte (achadinhos) que saiu do ar antes de processar |
| `erro: TimeoutError` | 1 | |

`pagina_sem_produto`/`url_vazia`/`loja_desconhecida` são definitivos, não reprocessar.

### 🔍 Investigação dos 933 `erro: Error` do `meli.la` (2026-09-02) — RESOLVIDO (transitório)

`DS_CAPTURA` só gravava `type(e).__name__` (ex. `"Error"`), sem a mensagem — não tinha como
saber a causa real sem reproduzir. Peguei 45 URLs reais da fila (espalhadas entre
28/07–28/08 e as 3 origens) e rodei o MESMO fluxo do `main.py` (goto → prepare → capture)
contra o Mercado Livre ao vivo: **0/45 falharam** (42 `ok`, 3 `pagina_sem_produto` — listas
legítimas). Nenhum bug estrutural nem quebra do site.

**Causa raiz**: quase todos os 933 têm `DT_CAPTACAO` entre 28–31/07 — exatamente a janela em
que **2116 ofertas ficaram represadas** porque o monitor esteve desligado de 26 a 31/07 (ver
seção de páginas-ponte). Quando voltou, processou esse backlog inteiro em sequência rápida,
centenas de hits seguidos no Mercado Livre — a mesma classe de problema já visto na Shopee
(anti-bot/rate-limit sob rajada), só que aqui vira erro genérico do Playwright (provável
`net::ERR_*` ou "execution context destroyed" por um redirect/pixel do ML no meio da
captura) em vez de um bloqueio explícito.

**Ações tomadas**:
1. **`main.py` agora grava a mensagem real** (`_status_erro()`, nova função): DS_CAPTURA
   passa a ser `"erro: {Tipo}: {1a linha da mensagem}"` (truncado a 400 chars, limite da
   coluna) em vez de só `"erro: Error"`. Da próxima vez que isso acontecer dá pra
   diagnosticar sem reproduzir na mão.
2. **933 linhas reenfileiradas**: `UPDATE OFERTA_FILA_CAPTURA SET ST_CAPTURA='0' WHERE
   DS_CAPTURA='erro: Error' AND LOWER(DS_URL_ORIGEM) LIKE '%meli.la%'` — rodar
   `--monitorar` para reprocessar (expectativa: quase todas voltam a `'1'`, com base na
   amostra de 45/45).
3. **Os outros ~692 `erro: Error`** (Amazon 163, Shopee 256, ML sem `meli.la` 13, epoca 27,
   outros) não foram reenfileirados — mesma hipótese de rajada, mas não testados
   individualmente ainda.

### 🆕 QT_OPINIOES / DS_AVALIACAO_GERAL — específicos do ML, EM PRODUÇÃO (2026-09-02)

2 campos novos, só para Mercado Livre: contagem de comentários (`.total-opinion`, ex.
"2.697 comentários" → `QT_OPINIOES NUMBER`) e o resumo de IA das opiniões
(`.ui-review-capability__summary__plain_text__summary_container` → `DS_AVALIACAO_GERAL
CLOB`). Ausente quando o produto não tem opiniões suficientes p/ o ML gerar o resumo (igual
`avaliacao_nota`) — validado ao vivo que NÃO é lazy-render (sem scroll já aparece).

**Pontas mexidas** (mesmo padrão do `DS_URL_BESAVE`):
- `stores/mercadolivre.py`: 2 novas entradas em `arr_items_scan`
  (`quantidade_opinioes`/`avaliacao_geral`).
- `core/oracle_db.py`: `MAPA_CAMPOS` (`P_QT_OPINIOES`/`P_DS_AVALIACAO_GERAL`),
  `quantidade_opinioes` em `_CONTADORES` (reusa o parser "2.697 comentários" → 2697, sem
  código novo), `avaliacao_geral` em `_CLOB_CAMPOS` (texto livre, sem corte, mesmo mecanismo
  `setinputsizes` dos `LS_*`).
- `sql/STP_OFERTA_FILA_CAPTURA_UPDATE.STP`: parâmetros `P_QT_OPINIOES NUMBER DEFAULT NULL` e
  `P_DS_AVALIACAO_GERAL CLOB DEFAULT NULL` (atribuição direta — colunas novas, sem dado
  prévio a preservar) — **recompilada e VALID no banco**.

**Nota de processo**: cheguei a ligar o `MAPA_CAMPOS` antes de confirmar que `QT_OPINIOES`
existia no banco — como a SP ainda não tinha os parâmetros, isso teria quebrado a gravação
de TODAS as lojas ("wrong number or types of arguments"). Revertido na hora e só religado
depois que a coluna foi confirmada. Lição: nunca mapear campo novo em `MAPA_CAMPOS` antes de
a SP já aceitar o parâmetro correspondente.

**Validado ao vivo, ponta a ponta**: capture → bind Oracle → gravação real (oferta 21624,
"9 comentários" → `QT_OPINIOES=9`, demais colunas intactas) + bind de CLOB longo (6400
bytes, sem `ORA-01461`) via ID de teste inexistente (não tocou em dado real).

### 📦 Cadastro consolidado `BESAVE.PRODUTO` — implementado e RODADO NO HISTÓRICO (2026-09-02)

Pedido do usuário: um cadastro de produtos ÚNICO (deduplicado por título), montado a partir
de TODAS as ofertas já capturadas (`ST_CAPTURA='1'`), consolidando preço mín/máx entre
ofertas repetidas e extraindo atributos (marca, modelo, dimensões, avaliação, ranking...) do
texto livre das 4 colunas `LS_DETALHES_PRODUTO/_TECNICOS/_INFO_ADICIONAIS/_COMPLEMENTO_PRODUTO`.
**Script novo e SEPARADO — não mexe no `main.py`/fluxo de captura**, só lê dado já gravado.

**Arquitetura (decisão registrada com o usuário)**: extração de atributos em **Python**
(mineração de texto livre com dezenas de sinônimos de rótulo — iterar regex em Python é
rápido de testar; em PL/SQL 11g seria uma cascata de `REGEXP_SUBSTR` difícil de evoluir).
Busca/insert-or-update/sequence/write-back em **Stored Procedure** (transacional, evita
race condition entre "olhei se existe" e "inseri" — pedido explícito do usuário).

**Componentes**:
- `core/produto_extrator.py` (novo): `extrair_atributos(ls_detalhes_produto,
  ls_detalhes_tecnicos, ls_info_adicionais, ls_complemento_produto)`. Junta os 4 campos numa
  lista de pares "rótulo normalizado → valor" (rótulo = texto antes do 1º `:`; sem `:` vira
  "frase solta" p/ fallback de prosa), na ordem TECNICOS → INFO_ADICIONAIS → COMPLEMENTO →
  DETALHES_PRODUTO (do mais estruturado ao mais "prosa"; 1ª ocorrência de cada rótulo
  vence — validado com teste explícito de prioridade). Cada campo-alvo tem uma lista de
  rótulos candidatos (sinônimos observados nos exemplos reais do usuário); regras especiais
  p/ avaliação ("4,8 de 5 estrelas (2.654)" → nota 4.8 + qtd 2654), ranking ("Nº 455 em
  Beleza (...)" → "455" + "Beleza"), dimensões ("42 x 70 x 191 milímetros" → assume
  Comprimento x Largura x Altura, decisão do usuário; + fallback de prosa "28.2cm de
  largura" e "comprimento de 39 cm", nas duas ordens) e peso em prosa ("Pesa 4.3kg."). Todas
  as regras testadas byte a byte contra os exemplos reais fornecidos pelo usuário ANTES de
  tocar o banco.
- `sql/STP_PRODUTO_UPSERT.STP` (nova SP): acha o produto por **título exato** (normalizado
  maiúsculo/trim — SEM `LIKE`, decisão do usuário: títulos de Amazon/ML são específicos o
  bastante, e um `LIKE` por substring arriscaria mesclar produtos diferentes, ex. mesmo
  perfume em tamanhos diferentes). Achou → `UPDATE` com **NVL em TODO campo de
  enriquecimento** (decisão do usuário: "preserva o que já existe" — só sobrescreve quando o
  valor novo vier preenchido, pra não ir perdendo dado conforme ofertas mais pobres chegam
  depois); `VR_PRECO_MINIMO`/`MAXIMO` são a exceção "ativa" (`LEAST`/`GREATEST` com NVL
  cruzado nos dois lados — cobre os 4 casos sem precisar de `IF`). Não achou → `INSERT` com
  `SEQ_PRODUTO.NEXTVAL`. Em AMBOS os casos grava `OFERTA_FILA_CAPTURA.ID_PRODUTO` de volta.
- `cadastrar_produtos.py` (script novo, mesmo padrão do `backfill_url_besave.py`):
  `WHERE ST_CAPTURA='1' AND ID_PRODUTO IS NULL` (idempotente/retomável — nunca precisa de
  ponteiro). `--dry-run` só mostra título+atributos extraídos; `--limite N` corta o lote.
- Infra nova no banco: `OFERTA_FILA_CAPTURA.ID_PRODUTO NUMBER`
  (`sql/ALTER_OFERTA_FILA_CAPTURA_ID_PRODUTO.sql`) e `SEQ_PRODUTO`
  (`sql/CREATE_SEQ_PRODUTO.sql`) — criados pelo Claude nesta sessão (autorizado pelo
  usuário). A tabela `BESAVE.PRODUTO` em si já existia (criada pelo usuário).

**2 bugs achados e corrigidos ANTES de rodar em massa** (ambos via teste ao vivo, não só
inspeção de código):
1. **Truncamento ausente**: a SP só tinha `SUBSTR` no título/descrição — todo o resto
   (marca/modelo/etc.) ia direto sem limite. Vendedores de marketplace às vezes enfiam o
   título inteiro no campo "Marca" (SEO abusivo — confirmado ao vivo: `Marca: Veronz
   Superior Qualidade Camiseta Camisa Basica Branca Preta...By`, ~210 chars num campo de 40).
   Sem `SUBSTR` isso vira `ORA-12899` e a linha fica sem produto, silenciosa. Fix: `SUBSTR`
   no tamanho exato de CADA coluna, em todo INSERT/UPDATE.
2. **`V_TITULO VARCHAR2(250)` sem `CHAR`**: mesma armadilha de byte-vs-caractere já
   documentada neste projeto para `OFERTA_FILA_CAPTURA` (ver seção "Integração Oracle"
   abaixo) — sem o qualificador `CHAR`, a variável vale 250 **BYTES** neste banco. Um título
   de 250+ caracteres com acentos (ex. "...Sensíveis...", 295 chars/299 bytes) estourava no
   `SUBSTR` com `ORA-06502` ("buffer too small"). Achado rodando o histórico inteiro (7 de
   16.959 ofertas falharam com esse erro) e diagnosticado por eliminação binária dos
   parâmetros até isolar que era o título. Fix: `VARCHAR2(250 CHAR)`.

**Rodado no histórico completo em 2026-09-02** (~2min23s, puro banco, sem navegador):
**16.959/16.959 ofertas vinculadas a um produto** (as 7 do bug acima reprocessadas depois do
fix) → **8.774 produtos** (8.329 novos + 8.623 vezes que uma oferta atualizou um produto já
existente — o dedup por título exato funcionou em produção: ~50% das ofertas são reofertas
de produtos já vistos). Cobertura dos atributos: marca 88% (7.752/8.774), modelo 39%,
avaliação 19% (só produtos com review na página), ASIN 19% (só Amazon tem ASIN). 2.216
produtos já têm faixa de preço real (mín≠máx, de ofertas em preços diferentes).

**Observações de qualidade de dado (não são bugs deste pipeline)**:
- `DS_GENERO` puxa "Literatura" em alguns produtos — a Amazon reusa o rótulo "Gênero:" tanto
  p/ gênero de pessoa (roupas) quanto p/ gênero literário (livros); o extrator não distingue
  contexto de categoria. Aceito por ora — daria pra checar `LS_CATEGORIA` por "Livros" se
  incomodar.
- Um produto (`Aparador Buffet... Lyam Decor`, id 7697) tem `VR_PRECO_MAXIMO = R$
  1.327.591,57` — erro de digitação na ORIGEM (`VL_PRECO_POR` do `AgenteCapturaWhatsapp`),
  não deste pipeline.
- Alguns campos de 20 CHAR (`DS_LINHA`, `DS_CATEGORIA_RANKING`, etc.) são apertados pra
  texto livre — truncamento vai cortar valores mais longos que isso (silencioso, por
  design, não crasheia).

**Retomada**: rodar `cadastrar_produtos.py` de novo a qualquer momento pega só o que for
novo (`ID_PRODUTO IS NULL`) — não precisa reprocessar o que já foi feito.

#### 🔁 Integrado ao `main.py` (2026-09-02) — não é mais preciso rodar o script à parte

A pedido do usuário, o cadastro agora roda **automaticamente dentro do `main.py`**, logo
após cada captura virar `ST_CAPTURA='1'`: lê a linha recém-gravada
(`OracleDB.buscar_para_produto`, só as colunas que o cadastro usa — números e `LS_*` já no
formato final gravado no banco, não os dados "crus" do Python) e chama
`core.produtos.cadastrar_produto()`, que já grava `ID_PRODUTO` na mesma linha. A linha do
console ganhou `| produto=<id>` (ou `| produto=FALHOU`, non-fatal — nunca derruba a captura
que já foi bem-sucedida).

**Refatoração**: a lógica de chamar a SP saiu do `cadastrar_produtos.py` para
`core/produtos.py` (`cadastrar_produto(db, id_oferta, linha)`), reaproveitada pelos dois
lugares — evita duas implementações divergindo com o tempo. `cadastrar_produtos.py`
continua existindo só para reprocessar o histórico anterior a 2026-09-02 (ou qualquer linha
que porventura falhe o cadastro ao vivo); com o `main.py` já cadastrando na hora, não há
mais rotina para rodar à parte no dia a dia.

**Validado ao vivo** (10 capturas reais via Mercado Livre): 8/10 `ok` → todas as 8 saíram
com `ID_PRODUTO` gravado na mesma passada (4 acharam produto já existente, 4 criaram novo);
as 2 `pagina_sem_produto` corretamente não tentaram cadastro (só roda dentro do galho
`status_captura == 'ok'`).

### 📰 Feed `BESAVE.OFERTA` — implementado, backfilado e integrado ao `main.py` (2026-09-02)

Pedido do usuário, na sequência do cadastro de produtos: uma tabela nova, **1 linha por
OFERTA** (não por produto — o mesmo produto pode ter várias ofertas, cada uma com seu
preço/data/cupom), só com as ofertas **aprovadas**: `ST_CAPTURA='1'` E loja com afiliado
**ATIVO em `BESAVE.LOJA_AFILIADA`** (confirmado com o usuário: é um conceito DIFERENTE do
`OFERTA_FILA_CAPTURA.ST_ATIVO`, que vem de `conf/config.json` → `"lojas_ativas"` — hoje as
duas fontes coincidem nas mesmas 3 lojas, mas podem divergir no futuro).

**Estrutura** (colunas propostas pelo Claude e aceitas pelo usuário, tamanhos batendo com
as colunas de origem em `OFERTA_FILA_CAPTURA` para não repetir o erro de truncamento):
- `sql/CREATE_TABLE_OFERTA.sql`: `ID_OFERTA` (PK, **reaproveita o mesmo ID de
  OFERTA_FILA_CAPTURA** — chave natural 1:1, sem sequence própria) + `ID_PRODUTO`, `DS_LOJA`,
  `DS_TITULO`, `DS_IMAGEM_OFERTA`, `DS_URL_BESAVE`, `DS_URL_FINAL`, `VL_PRECO_DE`,
  `VL_PRECO_POR`, `VR_PRECO_1`, `DS_CUPOM`, `DS_CUPOM_COMENTARIO`, `NR_NOTA_AVALIACAO`,
  `QT_AVALIACAO`, `DT_OFERTA`, `DT_CAPTACAO`, `DT_PUBLICACAO` (`SYSDATE` no insert).
  `DS_LOJA` é resolvido no Python (`registry.nome_loja`) — a coluna
  `OFERTA_FILA_CAPTURA.DS_LOJA` existe mas **nunca é gravada por nenhuma SP** (checado:
  0 linhas preenchidas), não dava pra confiar nela.
- `sql/STP_OFERTA_PUBLICAR.STP`: `MERGE` (insere ou atualiza atomicamente, idempotente) —
  bem mais simples que `STP_PRODUTO_UPSERT` porque não tem busca fuzzy nem sequence (a
  chave já vem pronta do chamador).
- `core/afiliados.py` ganhou `loja_ativa(loja)` (checa membership no cache já carregado de
  `LOJA_AFILIADA` — comentário no código já avisa da diferença pro `registry.loja_ativa()`).
- `core/ofertas.py` (novo, mesmo padrão de `core/produtos.py`): `publicar_oferta(db,
  id_oferta, id_produto, loja_nome, linha)`.
- `core/oracle_db.py`: `OracleDB.buscar_para_oferta(id_oferta)` + `COLUNAS_PARA_OFERTA` (lê
  de volta o que FOI GRAVADO, mesmo princípio do `buscar_para_produto`).
- **Integrado ao `main.py`** desde o início (não passou por uma fase "só backfill" como o
  PRODUTO): logo após o cadastro do produto, se `ID_PRODUTO` foi obtido E a loja está ativa
  em `LOJA_AFILIADA`, publica em `OFERTA` na mesma passada. Console ganhou `|
  oferta=publicada` / `| oferta=FALHOU` (best-effort, non-fatal).
- `publicar_ofertas.py` (backfill do histórico, mesmo padrão do `cadastrar_produtos.py`):
  `LEFT JOIN OFERTA ... WHERE ... IS NULL` (idempotente); resolve a loja a partir de
  `DS_URL_FINAL` (mesma técnica do `backfill_url_besave.py`, já que
  `OFERTA_FILA_CAPTURA` não guarda o nome da loja).

**Rodado no histórico completo em 2026-09-02** (13,5s, puro banco): **17.111/17.462**
ofertas com produto cadastrado foram publicadas; **351 ficaram de fora** por pertencer a
loja sem afiliado ativo (schemaorg: época/zzmall/belezanaweb/Natura) — exatamente o
comportamento esperado. **0 erros.** Distribuição: Mercado Livre 9.839, Amazon 5.682,
Shopee 1.610 — **8.517 produtos distintos** têm ao menos 1 oferta publicada (dos 8.781
cadastrados; a diferença são produtos vistos só em lojas sem afiliado).

**Validado ao vivo, ponta a ponta** (6 capturas reais novas): captura → grava Oracle →
cadastra produto → publica oferta, tudo na MESMA passada do `main.py`, sem precisar rodar
nenhum script à parte depois.

### 🔗 `DS_URL_BESAVE` — link com o NOSSO afiliado (2026-09-02)

Ver seção dedicada mais abaixo. Resumo: implementado para Amazon/Mercado Livre/Shopee,
rodando em produção a partir de agora, e **backfilado nas 17.087 ofertas já capturadas**
dessas 3 lojas (`backfill_url_besave.py`).

### 🏷️ Lojas ativas: `ST_ATIVO` + `DS_URL_BESAVE` (2026-07-31)

Nem toda loja capturada vai para produção agora. `conf/config.json` ganhou
**`lojas_ativas`** — hoje `["Amazon", "Mercado Livre", "Shopee"]`:

```json
"lojas_ativas": ["Amazon", "Mercado Livre", "Shopee"],
```

O que está fora da lista **continua sendo capturado e mapeado do mesmo jeito** (epoca,
zzmall, belezanaweb, Natura…) — o trabalho de mapear cada estrutura fica pronto e a oferta
nasce com **`ST_ATIVO = '0'`**. Para ativar uma loja depois, basta pôr o nome na lista e
reprocessar: **não há código a mexer**.

- **Coluna `ST_ATIVO`** (`VARCHAR2(1 CHAR)`, `sql/ALTER_OFERTA_FILA_CAPTURA_ST_ATIVO.sql`):
  `'1'` loja ativa | `'0'` loja mapeada mas fora do ar | `NULL` linha ainda não processada
  por esta versão. Gravada pelas **duas** SPs (sucesso e erro), com `DEFAULT NULL` +
  `NVL(P_ST_ATIVO, ST_ATIVO)` — quem não informa não mexe na coluna.
- **Quem decide**: `registry.loja_ativa(loja, url)`, comparando o **nome comercial** da loja
  com a lista (sem acento/caixa: "Época Cosméticos" == "epoca cosmeticos"). O nome vem de
  `BaseStore.nome_exibicao` (`'Mercado Livre'` para `nome='mercadolivre'`); a
  **`SchemaOrgStore` resolve por domínio** (`_NOMES_POR_DOMINIO`: Época Cosméticos, ZZ Mall,
  Beleza na Web, Natura), porque uma store só atende várias lojas de verdade.
- **Página-ponte fica ATIVA**: a decisão usa a loja **de destino**, não a origem — um
  `achadinhoscomcarol.com.br` que resolve para a Amazon grava `ST_ATIVO='1'` (validado).
- O CSV de segurança ganhou a coluna `st_ativo` (49 colunas agora).
- **Backfill do histórico**: `backfill_st_ativo.py` (simulação por padrão, `--aplicar`
  grava) classificou as **1022 linhas já processadas** — 981 ativas / 41 inativas. As
  pendentes ficam `NULL` de propósito: a loja de uma ponte só aparece depois de navegar.

### 🔗 `DS_URL_BESAVE` — link com o NOSSO afiliado, implementado (2026-09-02)

Continua a pendência acima (coluna criada vazia em 31/07). Agora `main.py` calcula
`DS_URL_BESAVE` a partir da `DS_URL_FINAL` (a URL real do produto, já sem redirect), trocando
o código de rastreio do divulgador que originou a oferta pelo NOSSO código de afiliado. Só
funciona para lojas com afiliado cadastrado; as demais mantêm a coluna `NULL` (consumir com
`NVL(DS_URL_BESAVE, DS_URL_FINAL)`).

**Fonte dos códigos: `BESAVE.LOJA_AFILIADA`** (schema `BESAVE`, tabela nova/externa a este
projeto — não faz parte de `OFERTA_FILA_CAPTURA`):

| `DS_LOJA` | `ID_AFILIADO` | `ID_REF_AFILIADO` |
|---|---|---|
| AMAZON | besave-20 | — |
| MERCADO LIVRE | REDACTED | REDACTED |
| SHOPEE | REDACTED | — |

`core/afiliados.py` → `carregar(db)` lê `SELECT DS_LOJA, ID_AFILIADO, ID_REF_AFILIADO FROM
BESAVE.LOJA_AFILIADA WHERE ST_ATIVO = 1` **uma vez por execução** (no arranque, logo após
conectar — vale tanto para lote quanto para `--monitorar`) e guarda em memória (dict `nome
interno da store → {id_afiliado, id_ref_afiliado}`), pronta para reuso em regras futuras.
`gerar_url(loja, url_final)` aplica a regra da loja e devolve `None` se ela não tiver
afiliado ativo/regra implementada.

**Regras por loja** (cada uma preserva os demais parâmetros da URL, só mexe no necessário):
- **Amazon**: troca o parâmetro `tag=` pelo `ID_AFILIADO` (`besave-20`); se não houver
  `tag=` na URL, acrescenta. `linkCode`/`linkId`/`ascsubtag`/etc. ficam intactos.
- **Mercado Livre**: descarta TUDO depois do `?` (rastreio do divulgador, inclusive a
  `#fragment` de recomendações) e substitui por `?matt_word=<ID_AFILIADO>&matt_d2id=<ID_REF_AFILIADO>`.
- **Shopee**: remove só o parâmetro `gads_t_sig` (mantém os demais, ex. `exp_group`) e
  acrescenta `mmp_pid=an_<ID_AFILIADO>&utm_content=----&utm_medium=affiliates&utm_source=an_<ID_AFILIADO>`.

As 3 regras foram validadas byte a byte contra os exemplos fornecidos pelo usuário antes de
rodar em produção. `stores/*.py` e `core/base_store.py` não mudaram — a URL usada é sempre a
`out['url_final']` que o loop já capturava.

**Pontas mexidas**: `core/afiliados.py` (novo) · `main.py` (chama `afiliados.carregar(db)`
no arranque; calcula `out['url_besave']` logo após `store.capture()`, só quando
`status_captura == 'ok'`) · `core/oracle_db.py` (`MAPA_CAMPOS['url_besave'] =
'P_DS_URL_BESAVE'`) · `sql/STP_OFERTA_FILA_CAPTURA_UPDATE.STP` (novo parâmetro `DEFAULT
NULL`, gravado com `NVL(P_DS_URL_BESAVE, DS_URL_BESAVE)` — mesmo padrão do `ST_ATIVO`, quem
não informa não apaga o que já tinha — **recompilada e VALID no banco**) · `core/csv_io.py`
(coluna `url_besave` no CSV de segurança).

**Backfill do histórico**: `backfill_url_besave.py` (`--dry-run` só conta, sem flag aplica) —
recalcula `DS_URL_BESAVE` a partir da `DS_URL_FINAL` já salva, **sem reabrir o navegador**;
`UPDATE` direto na tabela (não passa pela SP, para não arriscar tocar em outra coluna).
Rodado em 02/09: **17.087 linhas** (mercadolivre 9795, amazon 5682, shopee 1610) das 17.438
com `ST_CAPTURA='1'` e `DS_URL_FINAL` preenchida; as ~350 restantes são lojas sem afiliado
(schemaorg: época/zzmall/belezanaweb/Natura) e ficaram `NULL` de propósito. Amostras
conferidas ao vivo no banco batem exatamente com as regras acima.

**Incidente durante o teste manual (corrigido na hora)**: uma chamada de teste chamou
`atualizar_captura` com um dict **parcial** (só `url_besave`) na oferta 498 — como só
`ST_ATIVO`/`DS_URL_BESAVE` usam `NVL` na SP, as demais colunas (`DS_TITULO`, `VR_PRECO_1`,
`LS_*` etc.) foram **zeradas** para `NULL` nessa 1 linha. Detectado na conferência
imediatamente depois, restaurado 100% a partir do CSV de backup
`destino/captura_oracle_23_07_2026_17_25.csv` (que tinha os dados originais dessa oferta) —
nenhuma outra linha foi tocada. **Lição**: `atualizar_captura()` só deve ser chamado com o
dict COMPLETO de `store.capture()` (como o loop normal já faz); nunca com um subconjunto de
campos.

### ⏳ As páginas-ponte EXPIRAM — corra com o monitor (2026-07-31)

Sondagem ao vivo dos `achadinhoscomcarol.com.br` pendentes:

| Captação | Qtde | Resultado da ponte |
|---|---|---|
| 26/07 | 34 | ❌ `/promocao-encerrada` (3/3 testadas) — **perdidas** |
| 27–30/07 | 81 | ✅ ponte → `amazon.com.br/dp/<ASIN>` (7/7 testadas) |

A vitrine some poucos dias depois da oferta. Cada dia parado queima ~30 ofertas dessas.
Por isso o novo status **`oferta_expirada`** (antes essas linhas viravam `loja_desconhecida`,
motivo enganoso — o domínio até seria resolvível, a oferta é que saiu do ar):
`core/pontes.py` → `oferta_expirada(page)` (marcas de URL em `MARCAS_EXPIRADA`), consultado
pelo `_resolver_ponte` do `main.py`. Continua sendo `'9'` (definitivo), e agora grava
`DS_URL_FINAL` mesmo sem loja, para diagnóstico.

### 🌉 Páginas-ponte de divulgador — RESOLVIDO (2026-07-26)

Os 34 `achadinhoscomcarol.com.br/p/<hash>` **não são loja**: são uma vitrine de afiliado
(plataforma white-label `divulgadorinteligente.com`, Next.js). A página **não redireciona**
— ela renderiza a oferta e guarda o link da loja real no `__NEXT_DATA__`, em
`props.pageProps.product.originalValues.url`. Investigados os 34: **todos apontam para
`amazon.com.br/dp/<ASIN>`**, nenhuma falha.

Como cada divulgador tem o **seu próprio** domínio (`isOwnDomain: true`), mapear domínio a
domínio no registry não resolveria → a detecção é **por estrutura da página**:

- **`core/pontes.py`** (novo): `resolver_destino(page)` lê o `__NEXT_DATA__` da página já
  aberta e devolve `(url_da_loja, nome_da_loja)`, ou `(None, None)` se não for ponte.
  Prioriza `originalValues.url` (link original, aponta direto para o produto) e só depois
  varre os demais campos, porque o layout do JSON muda entre versões da plataforma.
- **`main.py`**: quando `resolver_loja()` devolve `None`, em vez de falhar direto ele
  **navega e tenta a ponte** (`_resolver_ponte`); se achar, troca a URL e segue o fluxo
  normal da loja de destino. `out['url']` continua sendo a URL de ORIGEM; a URL real aparece
  em `url_final`. Falhou → segue `loja_desconhecida` como antes.
- Efeito colateral aceito: domínios genuinamente desconhecidos (lixo) agora gastam uma
  navegação antes de virar `'9'`.
- **Limitação conhecida:** o gate de login da Shopee olha a URL de ORIGEM, então uma ponte
  que aponte para a Shopee não dispara o pedido de login. Hoje não ocorre (as 34 são Amazon).

Validado ao vivo em 3 (1391, 1412, 1511): ponte → Amazon, captura completa (título, preço,
preço original, nota, avaliações, categorias, vendido_por, país, 5 detalhes técnicos).
Os 34 foram devolvidos para `ST_CAPTURA='0'`.

De quebra: **`link.amazon` funciona** (testado — `link.amazon/<hash>` → `amazon.com.br/dp/...`,
mesmo produto) e já está mapeado no `registry`. Dúvida do resumo anterior encerrada.

### 🔜 O que sobrou: os 78 erros

**`loja_desconhecida` (10 — era 44)**:

| Qtde | Domínio | O que fazer |
|---|---|---|
| 2 | `www.magazinevoce.com.br` | Vitrine de divulgador do Magazine Luiza. `stores/magazineluiza.py` existe mas é **placeholder** (`output_columns_implemented()` = False). |
| 2 | `www.minhaloja.natura.com` | ✅ **RESOLVIDO em 31/07** — emite JSON-LD → entrou na `SchemaOrgStore` (ver abaixo). |
| **1** | `mercadolivre.com` (sem `.br`) | ✅ **RESOLVIDO em 31/07** — mapeado em `stores/mercadolivre.py`. |
| 2 + 1 + 1 + 1 | `promosdalyoficial.shop`, `ga.ma`, `🚨ga.ma`, `chat.whatsapp.com` | **LIXO/campanha — descartados** (decisão de 24/07). Ficam '9'. |

**`pagina_sem_produto` (66) — AUDITADOS em 26/07, todos LEGÍTIMOS.** Nada a recuperar; ficam
'9'. Não é regressão do `prepare()` do ML. Ver "🔍 Auditoria dos 66" abaixo.

**`url_vazia` (2)**: linhas sem `DS_URL_ORIGEM` na fila (ex. ID 1461) — problema na origem,
no `AgenteCapturaWhatsapp`, não aqui.

### 🌿 Natura na SchemaOrgStore + ficha técnica da epoca (2026-07-31)

**`minhaloja.natura.com` (11 pendentes + 2 erros) entrou na `SchemaOrgStore`** — é
**Salesforce Commerce Cloud** (`demandware`), 4ª plataforma diferente na mesma store, o que
confirma a escolha de 24/07 de guiar por schema.org e não por plataforma. Mudanças:

- domínio na lista da store (a loja é resolvida na URL de ORIGEM, como `blz.to`);
- galeria: o filtro de URL de imagem aceita `demandware.static` (além de `/arquivos/ids/`
  da VTEX e `sys_master` do Hybris). O filtro por SKU continua sendo quem descarta
  recomendações — o SKU (`NATBRA-231246`) aparece no nome do arquivo;
- ficha técnica: acordeão "gota olfativa" (perfumes) / "características" (demais), pares
  `<span>rótulo</span>: <span>valor</span>` → cfg `natura.com` em `_SPECS_POR_DOMINIO`. Como
  o `:` fica do lado do VALOR, o `_specs` passou a limpar `lstrip(': ')` também no valor.
  Itens sem valor ("cruelty free") caem fora sozinhos.

Validado ao vivo em 3 produtos: título, preço, nota/avaliações, categorias, descrição e
4–5 specs, 2–3 imagens. `preco_original` fica vazio (o JSON-LD da Natura não traz `highPrice`)
— mesmo caso da VTEX, a origem já tem `VL_PRECO_DE`.

**Regressão achada e corrigida na epoca:** a ficha técnica dela é **lazy-rendered** — o
`[data-specification]` só entra no DOM quando o bloco chega à viewport. Sem rolar,
`lst_Product_Detalhes_tecnicos` vinha **vazio** (0 pares onde a página tem 6–11); os 24
`epocacosmeticos` pendentes gravariam sem specs. Corrigido com um `prepare()` na
`SchemaOrgStore` (rola até o fim e volta ao topo antes de capturar). Conferido antes/depois:
epoca 0 → 11 e 0 → 8; zzmall 2 → 2 e Natura 5 → 5 (rolar não muda nada nelas).

### 🔍 Auditoria dos 66 `pagina_sem_produto` (2026-07-26)

Veredito: **os 66 estão certos**, nenhum produto a recuperar. Composição das URLs finais:
56 lista social do ML, 6 cupom Shopee, 2 coleção epoca, 2 interstício do ML.

**Os 53 `meli.la` NÃO são links de produto** — provado seguindo a cadeia de redirect:

```
meli.la/1WrTfzx
  301 -> mercadolivre.com.br/social/achadinhoscomcarol?matt_word=...&ref=<token>
  301 -> mercadolivre.com.br/social/achadinhoscomcarol/lists
```

Ou seja, o link curto aponta para o **perfil do divulgador**, não para um item: em nenhum
ponto da cadeia existe ID de produto (o `ref=` é token de afiliado). Aberto ao vivo, a página
é "Perfil social" / h1 "Minhas listas", com 9–46 produtos **diferentes** e **sem** botão
"Ir para produto" (o `prepare()` do ML procura esse botão — ele não existe aqui, então o
`prepare()` está intacto; a página de prévia de PRODUTO continua funcionando). Dois links
curtos distintos do mesmo divulgador caem na mesma lista. São de 3 divulgadores:
`achadinhoscomcarol`, `achadosdaly_`, `dediaedenoite`.

**Isso é ruído da origem**: alguém compartilhou no WhatsApp o link do PERFIL do divulgador em
vez do link do produto. 58 linhas no total (53 `meli.la` + 5 que já chegam como
`www.mercadolivre.com.br/social/dediaedenoite/lists`). Se incomodar, o filtro é barato e
pertence ao **`AgenteCapturaWhatsapp`**: descartar `/social/*/lists` antes de enfileirar.

Os outros 13: 6 cupom Shopee (`shopee.com.br/m/cupom-de-desconto`), 5 listas sociais do ML já
na origem, 2 coleções epoca (`/colecao/519`, `/colecao/764`) — todos legítimos.

**Correção feita de quebra:** os IDs 1581/1582 caíram em
`mercadolivre.com.br/gz/account-verification` (parede de verificação do ML) e foram
classificados como `pagina_sem_produto`, porque o main.py só reconhecia `verify/` (Shopee)
como bloqueio. Agora existe `MARCAS_BLOQUEIO = ('verify/', 'account-verification')`. Importa
porque `bloqueado_ou_login` é **transitório** (vale reprocessar) e `pagina_sem_produto` é
definitivo. Nestes 2 casos não muda o desfecho (a URL de origem também é link de perfil), mas
um produto de verdade que batesse nessa parede estaria sendo descartado como legítimo.

Para reprocessar uma classe depois de corrigir a causa:
```sql
UPDATE OFERTA_FILA_CAPTURA SET ST_CAPTURA='0', DS_CAPTURA=NULL
 WHERE ST_CAPTURA='9' AND DS_CAPTURA='loja_desconhecida';
COMMIT;
```
(com o monitor ligado, ele pega na varredura seguinte sozinho).

## 🔗 Integração Oracle (2026-07-19)

| Peça | Arquivo |
|------|---------|
| Conexão, leitura da fila e chamada das SPs | `core/oracle_db.py` |
| SP de sucesso (complementos) | `sql/STP_OFERTA_FILA_CAPTURA_UPDATE.STP` |
| SP de erro (marca o motivo) | `sql/STP_OFERTA_FILA_CAPTURA_ERRO.STP` |
| Ponteiro de retomada + `lojas_ativas` (leitura do config) | `core/estado.py` |
| Marca d'água nas imagens | `core/images.py` |
| Configuração (db, imagem, controle, **lojas_ativas**) | `conf/config.json` |
| Backfill de `ST_ATIVO` no histórico | `backfill_st_ativo.py` |

### Convenção de `ST_CAPTURA` / `DS_CAPTURA` / `ST_ATIVO`

| `ST_CAPTURA` | Significado | `DS_CAPTURA` |
|---|---|---|
| `'0'` | pendente — **a fila lê só estas linhas** | (vazio) |
| `'1'` | capturado com sucesso | `ok` |
| `'9'` | erro/problema na captura | o motivo (`bloqueado_ou_login`, `pagina_sem_produto`, `oferta_expirada`, `erro: TimeoutError`, …) |

`ST_ATIVO` é **ortogonal** ao `ST_CAPTURA`: diz se a loja da oferta entra em produção
(`'1'`/`'0'`, `NULL` = ainda não processada). Ver "🏷️ Lojas ativas" no topo.

**Exceção — `loja_nao_implementada` fica em `'0'`** (não vira `'9'`): a falha é nossa, não da
oferta, então a linha continua na fila e é reprocessada sozinha quando a loja passar a ser
suportada (ex.: Magazine Luiza). Controlado por `STATUS_MANTER_PENDENTE` no `main.py`.

As demais linhas processadas saem da fila, com sucesso ou não — nada fica preso repetindo. Para
reprocessar **uma classe de problema** depois de corrigir a causa, devolva as linhas para a
fila:

```sql
-- ex.: sessão da Shopee tinha expirado; refazer só essas
UPDATE OFERTA_FILA_CAPTURA SET ST_CAPTURA='0'
 WHERE ST_CAPTURA='9' AND DS_CAPTURA='bloqueado_ou_login';
```

- O ponteiro `ultimo_id_processado` **só avança em gravação bem-sucedida**, então uma queda no
  meio do lote não perde nem repete trabalho.
- Gravação é **best-effort**: falha do banco é logada e o lote continua (o CSV salva tudo).

### ⚠️ Limites de coluna

O banco é AL32UTF8 e a tabela mistura duas semânticas — a SP corta defensivamente:

| Coluna | Limite real | Efeito |
|--------|-------------|--------|
| `DS_TITULO` | 400 caracteres (**ampliada em 2026-07-19**) | cabe o título inteiro |
| `DS_CAPTURA` | 400 caracteres (**criada em 2026-07-19**) | motivo do `ST_CAPTURA` |
| `LS_*` | 600 caracteres | listas longas ainda são cortadas |
| `DS_URL_FINAL`, `DS_PRODUTO` | 350 caracteres | raramente estoura |
| `DS_PAIS_ORIGEM`, `DS_CONDICOES_*`, `DS_*_POR` | 100 **bytes** | acento custa 2 |

`DS_TITULO` era `VARCHAR2(100 BYTE)` e truncava quase todo título (cabiam ~50 letras
acentuadas). Foi ampliada para `VARCHAR2(400 CHAR)` via
`sql/ALTER_OFERTA_FILA_CAPTURA_DS_TITULO.sql` — rode esse script antes da SP em qualquer
outro ambiente. Validado: título de 194 caracteres gravado íntegro.

**Ao consultar limites, use `CHAR_LENGTH`/`CHAR_USED` de `USER_TAB_COLUMNS`, nunca
`DATA_LENGTH`** — este vem em bytes e engana (as `LS_*` aparecem como 2400 mas só aceitam
600 caracteres).

## ✅ O que está PRONTO e validado ao vivo

Scraper multi-loja: lê a fila do Oracle, identifica a loja pela URL, captura e grava
os complementos no banco + um **CSV de segurança** em `destino/captura_oracle_<data>.csv`
(50 colunas) + imagens (com marca d'água) em `destino/img/<ID_OFERTA>/`.

| Loja | Status | Último lote (38 linhas) |
|------|--------|--------------------------|
| **Amazon** | ✅ funcionando | 12/12 ok |
| **Shopee** | ✅ funcionando | 14/14 ok (todos os campos-core cheios) |
| **Mercado Livre** | ✅ funcionando | 10/10 ok |
| **schemaorg** (JSON-LD) | ✅ funcionando | epoca, zzmall, belezanaweb (`blz.to`), **Natura** |
| **Magazine Luiza** | ⏳ placeholder | sem links no CSV atual para testar |

- Preços **normalizados** nas 3 lojas: sem `R$`, decimal com `.` (ex.: `27.69`, `10.99 - 11.99`).
- `status_captura`: `ok`, `pagina_sem_produto` (cupom/lista), `bloqueado_ou_login` (captcha),
  `loja_nao_implementada`, `url_vazia`, `loja_desconhecida`, `oferta_expirada`
  (página-ponte cuja promoção acabou — ver "⏳ As páginas-ponte EXPIRAM").

### Correções cosméticas feitas nesta sessão (2026-07-13)
- **Preço inteiro** (`preco_com_desconto_inteiro`, `preco_11/12`, `preco_recorrencia_inteiro`):
  não vem mais com vírgula colada (`"27,"` → `"27"`), mantendo milhar (`"1.234"`).
- **Nota** (`avaliacao_nota` Amazon): `"4,2 de 5 estrelas"` → `"4,2"`.
- **País de origem**: removido o rótulo colado (`"País de origem : Brasil"` → `"Brasil"`) e as
  marcas unicode invisíveis (LRM/RLM/zero-width/BOM) — a limpeza de invisíveis é **global**
  (`normalize_text`), beneficia todas as lojas/campos.
- Checagem automática do lote final: **SEM problemas** cosméticos.

## ▶️ Como rodar  (AGORA É INTERATIVO — rode no SEU terminal)

O programa pede interações (tecla **S**), então **rode você mesmo no PowerShell**, NÃO em
background:

```powershell
# fila inteira, a partir do ultimo ID processado
$env:PYTHONIOENCODING="utf-8"; .venv\Scripts\python.exe -u main.py

# MODO MONITOR: fica ligado vigiando a fila (intervalo do config.json, padrao 3 min)
$env:PYTHONIOENCODING="utf-8"; .venv\Scripts\python.exe -u main.py --monitorar
$env:PYTHONIOENCODING="utf-8"; .venv\Scripts\python.exe -u main.py --monitorar --intervalo 5

# teste curto: so as 3 primeiras ofertas pendentes
$env:PYTHONIOENCODING="utf-8"; .venv\Scripts\python.exe -u main.py --limite 3

# reprocessa TODAS as pendentes, ignorando o ponteiro salvo
$env:PYTHONIOENCODING="utf-8"; .venv\Scripts\python.exe -u main.py --desde 0

# captura sem tocar no banco (so CSV) / modo antigo lendo de um CSV de origem
$env:PYTHONIOENCODING="utf-8"; .venv\Scripts\python.exe -u main.py --sem-oracle
$env:PYTHONIOENCODING="utf-8"; .venv\Scripts\python.exe -u main.py --csv origem\11_07_2026_17_06.csv
```

Fluxo ao iniciar:
1. **Fechar navegadores** — se detectar Chrome aberto, pede fechar tudo e pressionar **S**
   (`F` = força o fechamento; `Q` = sai). Garante que a única janela seja a de automação.
2. **Login Shopee** (só se o lote tiver links da Shopee) — abre a janela de automação, você
   loga **manualmente** e confirma com **S**. A sessão fica salva no perfil.
3. Segue a captura da lista completa.

### 🔁 Modo monitor (`--monitorar`)

Em vez de processar um lote e sair, o programa fica ligado varrendo
`OFERTA_FILA_CAPTURA` a cada N minutos. Achou pendente, captura na hora; não achou, dorme
até a próxima varredura. **Ctrl+C** para parar.

- **Intervalo**: `conf/config.json` → `monitor.intervalo_minutos` (padrão **3**; aceita
  decimal, ex. `0.5` = 30 s). `--intervalo N` sobrescreve pontualmente.
- **Login Shopee é decidido UMA vez, no arranque** (pergunta `S`/`N`): o loop não para mais
  para pedir login. Sem login, ofertas da Shopee caem em `bloqueado_ou_login` — a sessão dura
  ~1 dia, então religue o monitor com login quando ela expirar.
- **Lê a fila desde o início** (ignora `controle.ultimo_id_processado`), porque toda linha
  processada sai da fila sozinha ('1' ou '9') e uma linha devolvida para `'0'` na mão precisa
  ser vista. `--desde N` continua mandando quando informado.
- **Linhas que continuam `'0'` de propósito** (`loja_nao_implementada`) ou cuja gravação no
  Oracle falhou são **adiadas nesta execução** (ficam num set em memória) — senão o monitor
  recapturaria a mesma linha a cada varredura. Reiniciar o programa as traz de volta.
- Cada varredura com trabalho gera seu próprio CSV de segurança
  (`destino/captura_oracle_<dd_mm_aaaa_HH_MM_SS>.csv`).
- Se a conexão Oracle cair por ociosidade (ORA-03113 e parentes), o monitor **reconecta** e
  tenta de novo na varredura seguinte, em vez de morrer. Se a aba do Chrome for fechada na
  mão, ele abre outra.
- `--monitorar` não combina com `--csv` nem com `--sem-oracle` (sem gravar, releria as mesmas
  linhas para sempre) — o programa avisa e sai.

## ⚠️ Notas operacionais IMPORTANTES

- **Chrome real com perfil dedicado** `.chrome_perfil` (via `core/browser.py`, `channel='chrome'`).
  **Não dá para usar seu Chrome pessoal** na automação: o Chrome (v136+) bloqueia
  remote-debugging no perfil padrão e os cookies dele são criptografados (App-Bound Encryption).
  Por isso o login da Shopee tem que ser feito **na janela vazia da automação**.
- **Shopee exige login manual** (passo 2 acima). O antigo `shopee_login.py` (auto-detecção) era
  **pouco confiável** — foi substituído pelo login manual com **S** dentro do `main.py`.
  Login funciona SEM stealth e com GPU ligada (senão o captcha não carrega).
- **Anti-bot da Shopee**: ele fixa um token no perfil. Se rodar bloqueado (`bloqueado_ou_login`)
  mesmo logado, o perfil pode estar marcado → resetar renomeando `.chrome_perfil` (há backup
  `.chrome_perfil.bak_20260713_093525`) e logar de novo; se persistir, é rate-limit de IP →
  aguardar um tempo. A navegação MANUAL no mesmo IP continua funcionando (bloqueio é de
  sessão/perfil, não só IP).
- Rodar sempre com `.venv/Scripts/python.exe` e `PYTHONIOENCODING=utf-8`.

## 🗂️ Estrutura

```
main.py                    # orquestrador: fila Oracle -> gates -> captura -> SP + CSV
core/
  browser.py               # Chrome real + perfil persistente (.chrome_perfil)
  registry.py              # de-para dominio->loja
  pontes.py                # vitrines de divulgador -> descobre a loja real (__NEXT_DATA__)
  base_store.py            # mecanica generica (scan/tabelas/pairs/imagens/prepare/regex)
  oracle_db.py             # conexao, ler_fila(), atualizar_captura() + conversores de tipo
  estado.py                # ponteiro de retomada no config.json
  csv_io.py                # CSV de seguranca (JSON nas listas, url_final)
  link_afiliado.py         # link OFICIAL de afiliado (SiteStripe / barra ML / painel Shopee)
  text_utils.py            # normalize_text (+ limpeza de invisiveis), normalize_price
  images.py                # download + marca d'agua (Pillow)
stores/
  amazon.py  shopee.py  mercadolivre.py  schemaorg.py  magazineluiza.py(placeholder)
sql/
  STP_OFERTA_FILA_CAPTURA_UPDATE.STP        # sucesso -> ST_CAPTURA=1 (+ ST_ATIVO)
  STP_OFERTA_FILA_CAPTURA_ERRO.STP          # falha   -> ST_CAPTURA=9 + motivo
  ALTER_OFERTA_FILA_CAPTURA_DS_TITULO.sql   # amplia DS_TITULO p/ 400 CHAR
  ALTER_OFERTA_FILA_CAPTURA_DS_CAPTURA.sql  # cria DS_CAPTURA (motivo do status)
  ALTER_OFERTA_FILA_CAPTURA_ST_ATIVO.sql    # cria ST_ATIVO (loja em producao?)
  ALTER_OFERTA_FILA_CAPTURA_DS_URL_BESAVE.sql  # cria DS_URL_BESAVE (uso futuro)
  ALTER_OFERTA_FILA_CAPTURA_AFILIADO.sql    # cria as 4 colunas DS_*_AFILIADO
  ALTER_OFERTA_AFILIADO.sql                 # idem em BESAVE.OFERTA
backfill_st_ativo.py       # preenche ST_ATIVO nas linhas ja processadas
backfill_imagens.py        # baixa SO as fotos de ofertas ja capturadas com a pasta vazia
teste_link_afiliado.py     # teste ao vivo do link de afiliado (nao grava nada)
teste_tempos.py            # perfil de tempo: fase a fase, seletor a seletor, miniatura a miniatura
ml_dump_barra.py           # dump do HTML da barra de afiliado do ML (remapear seletores)
amazon_dump_galeria.py     # dump do HTML da galeria de imagens da Amazon (idem, p/ as fotos)
conf/
  config.json              # db / imagem / controle / lojas_ativas / link_afiliado
  besave.jpg               # logo da marca d'agua
wa/oracle_db.py            # copia do projeto AgenteCapturaWhatsapp (referencia; nao usada)
shopee_login.py            # login 1x standalone (legado; o main.py ja faz login manual)
main_legado_amazon.py      # script antigo, so referencia
origem/  destino/  .chrome_perfil/
```

### Conversão de tipos (`core/oracle_db.py`)

As colunas do banco são NUMBER, mas as lojas escrevem em formatos variados:

| Origem | Vira |
|--------|------|
| `"1234.56"`, `"4,2"`, `"10.99 - 11.99"` (faixa → menor) | `1234.56`, `4.2`, `10.99` |
| `"1.234"`, `"27,"` (fragmentos de preço, sempre inteiros) | `1234`, `27` |
| `"(2.443)"`, `"1,8mil"`, `"4mil+"` (contadores) | `2443`, `1800`, `4000` |
| listas / tabelas `{key, value}` | texto unido por `" \| "` |

## 🔗 Link OFICIAL de afiliado — `DS_URL_AFILIADO` (2026-09-10)

**Não confundir com `DS_URL_BESAVE`.** São duas coisas diferentes e as duas convivem:

| Coluna | Como nasce | Sempre existe? |
|---|---|---|
| `DS_URL_BESAVE` | **calculada** em `core/afiliados.py` (troca o parâmetro de rastreio do divulgador pelo nosso, na `DS_URL_FINAL`) | sim (é só texto) |
| `DS_URL_AFILIADO` | **clicada** no widget do programa de afiliados da loja (`core/link_afiliado.py`) | só com a sessão de afiliado logada |

A calculada é a rede de segurança da oficial: quem consumir deve tratar
`NVL(DS_URL_AFILIADO, DS_URL_BESAVE)`.

### Caminho por loja (`core/link_afiliado.py`)

| Loja | Onde | O que sai |
|---|---|---|
| Amazon | SiteStripe na própria página do produto: lê `#amzn-ss-category-content` e `#amzn-ss-commission-rate-content`, clica `#amzn-ss-get-link-button` → "Copiar link de associado" | link (`https://link.amazon/…`) + **categoria** + **taxa** |
| Mercado Livre | barra de afiliado no topo do produto: lê "GANHOS x%", clica `[data-testid="generate_link_button"]` e **lê os campos** do menu (`textarea[data-testid="text-field__label_link"]` / `..._id`, preenchidos de forma assíncrona) | link (`https://meli.la/…`) + **taxa** + **código do produto** |
| Shopee | não tem widget: `affiliate.shopee.com.br/offer/custom_link` **numa aba separada**, cola a `DS_URL_BESAVE`, "Obter link" → "Copiar Link" | link (`https://s.shopee.com.br/…`) |

**Leitura do valor**: os botões copiam para a **área de transferência** — é de lá que se lê
(`navigator.clipboard`, com permissão concedida em `preparar_contexto()`). Como clipboard
depende de foco da janela, todo fluxo tem 2ª via: varrer texto/inputs do próprio diálogo por
regex. O valor só é aceito se casar com o **formato da loja** — assim um clipboard velho (da
oferta anterior) nunca vira dado bom. O clipboard é zerado antes de cada clique pelo mesmo
motivo.

### Onde entra no fluxo

`main.py` → por ÚLTIMO dentro da captura de sucesso (depois de `store.capture`, das imagens e
do `url_besave`): o fluxo clica em botões e abre outra aba, então só roda com tudo já no
bolso. **Best-effort**: loja deslogada / layout mudado → campos vazios, a captura do produto
(que já deu certo) nunca cai. O log da linha mostra `afiliado=ok` ou `afiliado=-` (o `-` só
aparece em loja QUE TEM fluxo — é "tentou e não veio", não "loja sem programa").

### Colunas (as 4 existem nas DUAS tabelas)

`OFERTA_FILA_CAPTURA` (captura grava) e `BESAVE.OFERTA` (`STP_OFERTA_PUBLICAR` copia):
`DS_URL_AFILIADO` (600 CHAR), `DS_CATEGORIA_PROD_AFILIADO` (100), 
`DS_TAXA_COMISSAO_PROD_AFILIADO` (20, **texto** — "13,00%"), `DS_ID_PRODUTO_AFILIADO` (50).
DDL em `sql/ALTER_OFERTA_FILA_CAPTURA_AFILIADO.sql` e `sql/ALTER_OFERTA_AFILIADO.sql`
(ambos já rodados). Na SP da fila os 4 usam `NVL(..., coluna)`: recaptura que falhe manda
NULL e **preserva** o que já tinha — validado em round-trip.

⚠️ O parâmetro da SP é `P_DS_TAXA_COMISSAO_PROD_AFIL` (abreviado): o nome completo passaria
dos 30 caracteres que o Oracle 11g aceita num identificador. A COLUNA tem o nome completo
(30 em ponto).

### Logins (3 gates novos no arranque)

Com a captura ligada, depois do gate da Shopee (loja/comprador) vêm 3 perguntas: **Shopee
Afiliados** (`custom_link` — é outra sessão, não a da loja), **Amazon Associados**
(SiteStripe) e **Mercado Livre Afiliados**. Responder `N` segue em frente — só aquela loja
fica sem `DS_URL_AFILIADO`. Desligar tudo: `--sem-link-afiliado` ou
`conf/config.json → link_afiliado.habilitado = false`.

### ✅ Validado ao vivo (11/09) — as 3 lojas, depois de UMA VARREDURA REAL

Primeira varredura de produção (172 pendentes) mostrou o que o teste de 1 oferta por loja
não pegava. Resultado final, com as correções aplicadas:

| Loja | url_afiliado | categoria | taxa | id_produto |
|---|---|---|---|---|
| Amazon | `https://link.amazon/B0gdIB1Hg` | Beleza | 13,00% | — (não tem) |
| Mercado Livre | `https://meli.la/12tdGmM` | — (não tem) | 16% | `JD7H7W-BTZF` |
| Shopee | `https://s.shopee.com.br/9KhxMLMk8u` | — (não tem) | — (não tem) | — (não tem) |

#### 🔴 O bug que custou a varredura: escopo do ML aberto demais

Eu ancorava o escopo do Mercado Livre em `ancestor::nav` — que é o **header do próprio site**,
não a barra de afiliado. Os "botões com ícone" ali dentro incluem a **lupa da busca**: o loop
que clicava em botão por posição disparava a busca do Mercado Livre. Sintomas (todos o mesmo
bug): nenhuma oferta ML trazia link, buscas apareciam na tela e **cada página levava ~2 min**.

**A lição**: em barra injetada por app de terceiro, subir ancestrais é chute. O certo foi
rodar `ml_dump_barra.py` (mesmo papel do `shopee_dump.py`) e olhar o HTML de verdade.

#### O que o dump revelou (`destino/ml_barra_dump.html`, 11/09)

O menu "Compartilhar" tem `data-testid` **estáveis** — nada de classe `andes-*` volátil:

| Elemento | Seletor |
|---|---|
| campo do link | `textarea[data-testid="text-field__label_link"]` |
| campo do ID | `textarea[data-testid="text-field__label_id"]` |
| copiar link / ID | `button[data-testid="copy-button__label_link"]` / `..._id` |
| "GANHOS x%" | `.toolbar__actions` (fora do menu) |

E o achado principal: **os dois `<textarea>` estavam VAZIOS** 2,5s depois de abrir o menu — o
ML gera link e ID de forma **assíncrona**. Por isso o fluxo hoje **lê o valor do campo**
(`_valor_campo`, até 10s de espera), com o botão de copiar só como reserva. O sucesso do
primeiro teste tinha sido acidental: os cliques errados gastavam tempo suficiente para os
campos encherem antes da última tentativa.

#### Três tempos que não podem ser conferidos "na hora" (cada um custou uma rodada)

1. **A barra** é injetada segundos depois da página carregar → `_esperar_widget()`
   (20s no ML, 15s na Amazon — a 1ª oferta Amazon da execução falhou com 10s).
2. **O menu** é um tooltip montado ~2,5s depois do clique → `_esperar_visivel(ML_CAMPO_LINK)`
   (12s). Conferir logo após o clique acusa "menu não abriu" com o menu vindo.
3. **Os campos** enchem depois do menu existir → `_valor_campo()` insiste até 10s.

A taxa (`GANHOS x%`) exige o **rótulo**: sem ele, um `-20%` de badge na mesma barra viraria
comissão. Faltando, o log imprime o texto que leu da barra.

⚠️ O link da Amazon **muda a cada clique** (`B08GZgfYY` → `B0fyYLGMI` → `B0fq9Mjlw` →
`B0gdIB1Hg` no mesmo produto): o SiteStripe gera um encurtado novo toda vez. Todos apontam
para o mesmo produto com a nossa tag — não é bug, e não adianta comparar links entre capturas.

### 🚫 Anúncio pausado (Mercado Livre) — descarte novo

Anúncio que o vendedor tirou do ar **carrega como página de produto normal** (tem título, tem
preço) mas exibe a tarja `.andes-message__text` "Anúncio pausado". Hook novo
`BaseStore.status_descarte(page)`: achando isso, a oferta vira `ST_CAPTURA='9'` com
`DS_CAPTURA='anuncio_pausado'` e o loop pula. Diferente de `pagina_sem_produto()` (que diz
"isto nem é página de produto") — aqui o produto existe e foi o ANÚNCIO que saiu do ar.

### 🔌 Corta-circuito por loja

5 ofertas seguidas sem link e o fluxo daquela loja se desliga até o próximo arranque, com
aviso no log. Sem isso, uma sessão de afiliado que caia no meio da madrugada faria **toda**
oferta do ML pagar 20s de espera pelo resto da varredura, sem chance de sucesso.

### Validar ao vivo antes de soltar na fila

```
python teste_link_afiliado.py --da-fila 1      # 1 oferta real de cada loja
python teste_link_afiliado.py <url do produto>
python ml_dump_barra.py <url do ML>            # quando o ML mudar o menu de novo
```
Nenhum dos dois grava nada (nem Oracle, nem CSV). O `teste_` também mostra `DESCARTE =
anuncio_pausado` quando for o caso.

**Histórico NÃO foi backfilado** (decisão de 10/09): são 21.957 ofertas com `ST_CAPTURA='1'`
e cada uma exigiria reabrir a página — o mesmo cenário que acionou o bloqueio anti-bot do ML
no backfill de `QT_OPINIOES`. Só ofertas capturadas a partir de agora saem com o link.

## 🕐 PENDENTE: backfill de QT_OPINIOES/DS_AVALIACAO_GERAL no histórico ML (2026-09-02)

O usuário notou que a maioria das ~9.845 ofertas Mercado Livre já capturadas (antes de
2026-09-02) não tem `QT_OPINIOES`/`DS_AVALIACAO_GERAL` — correto, esses 2 campos só existem
a partir de hoje e **não dá pra derivar do que já está gravado** (diferente do
`DS_URL_BESAVE`): precisa REABRIR a página de verdade.

**Script pronto**: `backfill_qt_opinioes.py` (`--limite N`) — navega para `DS_URL_FINAL` de
cada oferta ML pendente (`QT_OPINIOES IS NULL AND DS_AVALIACAO_GERAL IS NULL`), rescaneia só
os 2 seletores novos e faz `UPDATE` direto (só essas 2 colunas, sem tocar em mais nada).
Idempotente/retomável.

**⚠️ Achado ao testar em lote maior (2026-09-02, sessão interrompida — usuário precisou
desligar)**: primeiro teste de 15 ofertas rodou limpo (14/15 ok). Escalando pra 50, a partir
de ~15-20 ofertas seguidas começou uma sequência de `TimeoutError` (34 de 50), terminando em
`TargetClosedError` (o navegador fechou sozinho). **Mesmo padrão da rajada anti-bot já
diagnosticada** na investigação dos "erro: Error" do meli.la (ver seção acima) — bater
repetido no Mercado Livre em sequência rápida aciona bloqueio/timeout. **Não confirmado
ainda** se é captcha explícito, rate-limit silencioso, ou o profile `.chrome_perfil`
ficando marcado (como já aconteceu com a Shopee).

**Estado**: 65 ofertas tentadas hoje (27 com dado capturado), **9.769 ainda faltam**. Nenhum
processo Chrome/Python ficou rodando — seguro ter desligado a máquina.

**Próximos passos, quando retomar**:
1. Investigar se a página de uma oferta que deu `TimeoutError` hoje carrega normal agora
   (indica bloqueio temporário) ou segue travando (indica outra causa).
2. Rodar em lotes BEM menores (10-15 por vez, como o 1º teste que funcionou) com pausa
   entre lotes, em vez de tentar 50+ de uma vez.
3. Se persistir, considerar as mesmas táticas já usadas p/ Shopee: resetar o
   `.chrome_perfil` (renomear) se ele ficar "marcado", ou aceitar que esse backfill
   específico precisa rodar espalhado em várias sessões ao longo de dias (9.769 páginas é
   MUITO mais lento que os backfills de banco puro — ~11s/oferta observado, ~30h se fosse
   tudo de uma vez, o que por si só já pede rodar em pedaços).

## ⏸️ Sessão 24→25/09 — onde paramos (retomar daqui)

### Backfill do link oficial + recaptura completa (`backfill_url_afiliado.py`)
- Retomado depois da queda do PC em 24/09. Código íntegro, fila reconstruída pelo banco.
- Progresso: OFERTA com `DS_URL_AFILIADO` foi de 4.414 → **5.551** (de 25.883) em 25/09 00:57.
  48 ofertas estão em `conf/backfill_url_afiliado_tentativas.json` (puladas; `--retentar`
  tenta de novo).
- Para rodar ~4h (madrugada): **`--lote 400`** (~35s/oferta com as pausas anti-bot ≈ 100/h).
  Calibrar pela duração média do log: `lote = 14400 ÷ (duração média + 11)`.
- Continua valendo: rodar no terminal do usuário (gates de login pedem Enter), nunca junto
  do `main.py` (perfil `.chrome_perfil` é um só).

### OFERTA.ST_ATIVO / DT_DESATIVACAO (novo, 24/09)
- Colunas criadas pelo usuário (`ST_ATIVO NUMBER`, `DT_DESATIVACAO DATE`). Regra: tudo que
  este programa inclui/altera em OFERTA fica `ST_ATIVO=1`, `DT_DESATIVACAO=NULL`
  (recapturar REATIVA). Desativar é um processo separado, ainda a fazer.
- Alterados: `sql/STP_OFERTA_PUBLICAR.STP` (UPDATE e INSERT do MERGE) e o `UPDATE OFERTA`
  do modo só-link em `backfill_url_afiliado.py`.
- Histórico: as 25.883 linhas já estão com `ST_ATIVO=1` (usuário rodou o UPDATE).
- ⚠️ **PENDENTE**: na conferência de 25/09 00:5x, a SP compilada no banco (22:24) **ainda era
  a versão antiga** (nenhuma linha com `ST_ATIVO` em `ALL_SOURCE`). Recompilar a partir de
  `sql/STP_OFERTA_PUBLICAR.STP` e depois rodar de novo
  `UPDATE OFERTA SET ST_ATIVO = 1 WHERE ST_ATIVO IS NULL` para as ofertas que entraram
  nesse meio-tempo. Conferir: `SELECT COUNT(*) FROM ALL_SOURCE WHERE NAME='STP_OFERTA_PUBLICAR'
  AND UPPER(TEXT) LIKE '%ST_ATIVO%'` deve dar > 0.

### Limpeza de disco
- Apagados `.chrome_perfil.bak_20260713_093525` e `.chrome_perfil_ml_tentativa_20260903`
  (~387 MB). Opcional: limpar só os caches do `.chrome_perfil` (Cache, Code Cache,
  Service Worker, GPUCache ≈ 530 MB) com o Chrome fechado — nunca `Network`,
  `Local Storage` nem `IndexedDB` (são os logins).
- A pasta `user_data` (2,27 GB) é do projeto **AgenteCapturaWhatsapp** (perfil do WhatsApp
  Web), não daqui; ~1,4 GB são caches apagáveis, mas `IndexedDB` guarda a sessão — tratar
  naquele projeto.

## 📌 Pendências menores (quando der)

- **Rodar o primeiro lote ao vivo** com `--limite 3` e conferir os dados no banco.
- Ajustar `marca_dagua_opacidade` no `conf/config.json` se a marca ficar fraca demais
  (0.4 fica bem sutil em fotos coloridas; o padrão do outro projeto era 0.30).
- Implementar **Magazine Luiza** (falta você mandar os seletores + ter links dela).
- cap 35 (Amazon): produto sem preço capturado — investigar o layout de preço dele.
- **Amazon `/promotion/psp/...` passa como `ok`** (achado em 11/09): 3 das 303 ofertas Amazon
  da varredura do dia (`25757`, `25786`, `25989`) são páginas de PROMOÇÃO, não de produto —
  saíram com `ST_CAPTURA='1'` e pasta de imagens vazia. O `pagina_sem_produto` da Amazon não
  reconhece esse formato de URL. Conferir o que elas gravaram em `BESAVE.PRODUTO`/`OFERTA` e
  provavelmente barrar o caminho `/promotion/` no `AmazonStore`.
- Cosmético Shopee: linha "Categoria" do `lst_Product_Detalhes_tecnicos` vem redundante com
  `lst_categorias` — remover se você quiser (ainda não decidido).
- Limpar subsets de teste em `origem/subset_*.csv` se não forem mais úteis (o backup
  `.chrome_perfil.bak_*` já foi apagado em 24/09).
```
