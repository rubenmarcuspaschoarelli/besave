# BSV-40 · Worker: envio de ofertas ao canal do Telegram

**Papel:** Backend Rust · **Pasta:** `apps/worker/` (+ `docs/CONTRATO.md` §11, `packages/contract/package.json`) ·
**Depende de:** BSV-16 (`besave.io` no ar), BSV-14 (cliente Telegram, trava, logs).
CONTRATO.md §2, §3, §5, §6, §7; AD-006, AD-031, AD-032, AD-036, AD-047, AD-048, AD-063, AD-070

## Contexto
Metade do tráfego deve vir de canais. O canal público `@besaveofertas` existe; `besave.io/{id}` já faz 301
para `/oferta/{id}/`. Os critérios de envio são do dono e mudam com frequência, por isso vivem numa
tabela do Oracle, não no código.

## Objetivo
Um executável `besave-envio`, agendado a cada 5 min, que posta um lote de ofertas (padrão 2) por
execução no canal, distribuído ao longo da janela até a cota do dia, e edita o post quando a oferta
expira. O `besave-ciclo` passa a registrar quando cada oferta foi ao ar no site.

## Saídas
1. **Oracle:** `apps/worker/sql/bsv-40.sql` já existe e foi rodado pelo dono; use-o como está (mudança
   de DDL = avisar no PR). Contém:
   - `OFERTA.DT_PUBLICACAO_SITE` (DATE, nula até a oferta ir ao ar no site).
   - `CANAL_ENVIO` (`ID_CANAL` 1 = `@besaveofertas`) e `PARAMETROS_ENVIO` (por canal): `QT_MAX_DIA` 180 ·
     `QT_POR_EXECUCAO` 2 · `NR_HORA_INICIO` 8 · `NR_HORA_FIM` 22 · `NR_HORA_SOM_INICIO` 9 ·
     `NR_HORA_SOM_FIM` 21 · `PC_DESCONTO_MIN` 30 · `NR_HORAS_OFERTA_MAX` 24 · `NR_DIAS_REPETICAO` 5 ·
     `PC_QUEDA_REPETICAO` 10 · `PC_DESCONTO_DESTAQUE` 30.
   - `ENVIO_TELEGRAM` (sequence `SQ_ENVIO_TELEGRAM`; único `ID_CANAL`+`ID_OFERTA`; `NR_MESSAGE_ID` nulo
     até o Telegram confirmar; `DT_EDICAO`).
   Colunas `DATE` em hora local `BESAVE_ORACLE_TZ` (-03:00), como o resto do worker.
2. **`besave-ciclo`:** depois de publicar o manifest (MANIFEST §6 passo 5), `UPDATE OFERTA SET
   DT_PUBLICACAO_SITE = SYSDATE WHERE ID_OFERTA IN (…) AND DT_PUBLICACAO_SITE IS NULL` para os ids do
   conjunto publicado (lotes de 1000). Novo método em `FonteOfertas` (com fake). Falha aqui → WARN e
   `publicacao_site_falhas` no relatório; não falha o ciclo (o site já foi publicado; só atrasa o canal).
3. **CONTRATO §11 `OfertaCanal`** (versão 1.4.0): `id`, `id_produto`, `loja`, `titulo`, `destaque`
   (`DS_OFERTA_DESTAQUE`, opcional), `preco_de`, `preco_por`, `desconto_pct`, `cupom`, `recorrencia`
   (`ST_RECORRENCIA = 1`: preço do Programe e Poupe), `dt_oferta`. Só consumida pelo envio; sem JSON
   publicado, então sem schema novo. Mesmas regras de rejeição do §9.
4. Binário `besave-envio` (mesmo crate), `--env-file`, trava própria (`envio.lock`), log diário próprio,
   alerta de falha com o bot de alertas (estado `alerta-envio.json`), códigos de saída 0/1/2 (BSV-14);
   `--sim` imprime a mensagem e a foto escolhidas sem enviar nem gravar.
5. `scripts/registrar-tarefa-envio.ps1` (tarefa "Besave Envio", 5 min, mesmas regras da BSV-14). README.

## Regras
1. **Janela, cota e ritmo** (horário de Brasília, -03:00 fixo): fora de `[INICIO, FIM)` não envia (a
   "fila" é implícita: às 8 h as candidatas são as das últimas 24 h ainda não enviadas). Com `L =
   QT_POR_EXECUCAO`, `esperado = min(QT_MAX_DIA, L + floor(QT_MAX_DIA × minutos_desde_INICIO /
   minutos_da_janela))`; a execução envia um lote de até `L` só se `esperado − enviados_hoje ≥ L`
   (com os padrões: 2 posts a cada ~9–10 min, 180 no dia; depois de uma parada, recupera no máximo um
   lote por execução). Entre posts do lote, ≥ 1 s. `disable_notification = true` fora de
   `[SOM_INICIO, SOM_FIM)`.
2. **Candidatas:** `ST_ATIVO = 1`, `DT_PUBLICACAO_SITE` preenchida (página já no ar), `DT_OFERTA ≥ agora −
   NR_HORAS_OFERTA_MAX`, publicável pelas regras do worker (§9 + URL de afiliado), não enviada a este
   canal, e (`desconto ≥ PC_DESCONTO_MIN` ou `pd` nulo).
3. **Repetição:** mesmo `ID_PRODUTO` enviado há menos de `NR_DIAS_REPETICAO` dias só entra se
   `preco_por ≤ último × (1 − PC_QUEDA_REPETICAO/100)`; aí a mensagem leva "📉 Caiu mais o preço!!!".
4. **Ordem:** maior desconto (`pd` nulo = 0) → com cupom → `dt_oferta` mais recente → `id` maior.
5. **Foto:** `img/ofertas/{id}.webp` (natural; ausente → `img/placeholder/{slug}.webp`), centralizada num
   quadrado 800×800 de fundo branco, JPEG, enviada por upload (`sendPhoto` multipart), sem gravar no S3.
6. **Legenda** (`parse_mode=HTML`, texto escapado, ≤ 1024 caracteres; título cortado se preciso):
   ```
   <b>{titulo}</b>
   {destaque}
   🔥 <b>-{pct}%</b>  <s>R$ {de}</s>  <b>R$ {por}</b>  🔁 <i>(Recorrência)</i>
   📉 <b>Caiu mais o preço!!!</b>
   🎟️ Cupom: <code>{cupom}</code>
   Promoção {Loja}: <a href="https://besave.io/{id}?utm_source=telegram">besave.io/{id}</a>
   ```
   Linhas opcionais somem quando vazias; `-{pct}%` só se `pct ≥ PC_DESCONTO_DESTAQUE`; `<s>de</s>` só se
   `pd`. Preço em `R$ 1.234,56`. Lojas: Amazon, Mercado Livre, Shopee.
7. **Sem envio duplicado:** grava a linha em `ENVIO_TELEGRAM` (sem `message_id`) antes de enviar; envio
   ok → grava `NR_MESSAGE_ID`; envio que falha → apaga a linha. Falha no Oracle antes do envio → não envia.
8. **Expiradas:** a cada execução, até 20 posts com `ST_ATIVO = 0` e `DT_EDICAO` nula ganham
   `editMessageCaption`: "⛔ <b>Oferta encerrada</b>" no topo, legenda original riscada, sem link; grava `DT_EDICAO`.
9. **Limites do Telegram:** no máximo 1 chamada por segundo; 429 → respeita `retry_after`, encerra a
    execução com sucesso e continua na próxima.
10. Bot próprio: `TELEGRAM_CANAL_BOT_TOKEN` (≠ bot de alertas), no `.env`; nunca em log nem em `Debug`.
    Parâmetros lidos uma vez por execução. Sem dependência nova além de, se preciso, encoder JPEG do crate
    `image` (feature) — justificar.

## Fora de escopo
Avisos programados (BSV-41), WhatsApp, mais de um canal em produção (o modelo já suporta N), métricas de
clique, apagar posts.

## Critério de aceite
- Fakes (Oracle, Telegram, relógio), padrões 180/2: 07:59 → 0; 08:00 → 2; 08:05 → 0; 08:10 → 2;
  21:59 com 180 enviados → 0; 22:00 → 0; um dia simulado com execuções a cada 5 min → 180 posts
  (± 2), nenhum fora de 8–22 h; parada de 1 h → a execução seguinte envia só 1 lote; 08:30 →
  `disable_notification = true`, 09:00 → false; ≥ 1 s entre os posts do lote.
- `besave-ciclo`: ids publicados com `DT_PUBLICACAO_SITE` nula ganham a data uma vez (segunda execução
  → 0 updates); falha no update → WARN, código 0, manifest publicado; 2.500 ids → 3 lotes.
- Filtros: inativa, `DT_PUBLICACAO_SITE` nula, `dt` de 25 h, desconto 29% → fora; `pd` nulo → dentro;
  já enviada → fora.
- Repetição: mesmo produto há 4 dias com queda de 9% → fora; 10% → dentro com "Caiu mais o preço!!!";
  há 5 dias → dentro sem a frase.
- Ordem: 50% sem cupom vs 50% com cupom → com cupom; empate total → mais recente.
- Foto: saída 800×800 JPEG, fundo branco nas bordas, proporção preservada; sem imagem → placeholder.
- Legenda: casos com e sem `pd`, `pct` 29% (sem selo) e 45%, recorrência, cupom, destaque, título com
  `<&>` escapado, título longo cortado para caber em 1024; link com `utm_source=telegram`.
- Sem duplicata: Telegram falha → linha apagada; Oracle falha antes → 0 chamadas ao Telegram.
- Expirada → 1 edição, `DT_EDICAO` gravada; segunda execução → 0; 25 expiradas → 20 numa execução.
- 429 com `retry_after` → execução termina com 0, nada gravado além do já confirmado.
- `cargo fmt --check`, `clippy -D warnings`, `cargo test` sem rede.
- **Real (dono):** DDL já rodado; `besave-ciclo` novo preenche `DT_PUBLICACAO_SITE` (1º ciclo: todas as
  publicadas); bot admin do canal; `--sim` mostra mensagem e foto coerentes; registrar a tarefa; ao longo
  de um dia: lotes de 2 a cada ~10 min, ~180 posts, só entre 8 h e 22 h, silenciosos
  fora de 9–21 h; tocar no cupom copia o código; link abre a página da oferta; uma oferta desativada pelo
  robô vira "Oferta encerrada" no canal; prints sem token.

## Definition of done
PR com README (bot, admin do canal, parâmetros, tarefa), CONTRATO §11 e versão 1.4.0, prints do canal,
`validation.md` do Verifier independente, testes verdes.
