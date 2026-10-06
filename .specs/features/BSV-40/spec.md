# BSV-40 — Envio de ofertas ao canal do Telegram

Fonte: `docs/specs/BSV-40.md` (escopo), CONTRATO §2, §3, §5, §6, §7, §9; MANIFEST §6.
Pasta: `apps/worker/` (+ `docs/CONTRATO.md` §11, `packages/contract/package.json`). DDL: `apps/worker/sql/bsv-40.sql` (já rodado pelo dono; usado como está).

## Problem Statement

O canal `@besaveofertas` existe e `besave.io/{id}` já redireciona para a página da oferta, mas nada
posta no canal. O envio precisa respeitar critérios do dono que mudam com frequência (tabela
`PARAMETROS_ENVIO`), nunca postar oferta cuja página ainda não está no ar, nunca duplicar e editar o
post quando a oferta expira.

## Goals

- [ ] `besave-envio` agendado a cada 5 min posta ~180 ofertas/dia em lotes de 2, só entre 8 h e 22 h (Brasília).
- [ ] `besave-ciclo` grava `DT_PUBLICACAO_SITE` uma vez por oferta publicada.
- [ ] Zero posts duplicados; post de oferta expirada vira "Oferta encerrada".

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Avisos programados | BSV-41 |
| WhatsApp, mais de um canal em produção | spec (o modelo já suporta N canais) |
| Métricas de clique, apagar posts | spec |
| Mudança de DDL | DDL já rodado; usar como está |
| Editar `docs/DECISOES.md` | só o dono (AD-060); propostas no PR |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Origem da foto | Arquivo do robô em `BESAVE_IMAGENS_DIR/{id}/{id}.webp` (o mesmo que o ciclo copia para `img/ofertas/{id}.webp`); ausente/ilegível/sem pasta → placeholder da área embutido no binário (`img/placeholder/{slug}.webp`) | Mesmo conteúdo da chave S3 sem rede nem credencial AWS no envio; "sem gravar no S3" | n |
| Quadrado 800×800 | Imagem escalada para caber (para cima ou para baixo) mantendo proporção, centralizada sobre branco; alfa composto sobre branco; JPEG qualidade 85 | Spec regra 5 | n |
| Dependência | Feature `jpeg` do crate `image` (já dependência): traz `zune-jpeg`/`zune-core` (já em cache, puro Rust) | Única exceção autorizada pela spec regra 10 | n |
| Multipart do `sendPhoto` | Montado à mão sobre o `hyper` já usado no alerta | Nenhum crate novo | n |
| Canal processado | `BESAVE_ENVIO_CANAL` (padrão `1`); canal ausente ou `ST_ATIVO = 0` → nada a fazer, código 0 | Modelo N canais, produção com 1 | n |
| Datas de `ENVIO_TELEGRAM` | `DT_ENVIO`/`DT_EDICAO` gravadas com o relógio do worker convertido para hora local (`BESAVE_ORACLE_TZ`), não `SYSDATE` | Mesmo relógio da regra de cota; testável. `DT_PUBLICACAO_SITE` usa `SYSDATE`, como a spec manda | n |
| "Enviados hoje" | Linhas de `ENVIO_TELEGRAM` do canal com `DT_ENVIO` ≥ 00:00 de Brasília (linhas apagadas por falha não contam) | Regra 1 | n |
| Filtro das candidatas | SQL pré-filtra (ativa, `DT_PUBLICACAO_SITE` não nula, idade, não enviada); o Rust refaz todos os filtros (inclusive "não enviada", via `enviadas(ids)`) | A regra fica testável no fake; o SQL só reduz volume | n |
| Repetição dentro do mesmo lote | Oferta escolhida entra no histórico em memória: segunda oferta do mesmo produto no lote passa pela regra de queda | Regra 3 vale para qualquer envio anterior | n |
| Preço de comparação na repetição | Último envio (mais recente) do produto na janela de `NR_DIAS_REPETICAO`; comparação em centavos inteiros: `pp × 100 ≤ ultimo × (100 − PC_QUEDA)` | Regra 3 sem float | n |
| Desconto | `round((1 − pp/pd) × 100)` inteiro, a mesma função de `OfertaPagina.desconto_pct`; `pd` nulo = 0 na ordem | CONTRATO §4.1 | n |
| Título na legenda | Título integral (trim); cortado com `…` na fronteira de palavra só se a legenda passar de 1024 | Regra 6 | n |
| Limite de 1024 | Medido em unidades UTF-16 do HTML bruto (≥ caracteres visíveis que o Telegram conta) | Conservador: nunca estoura | n |
| Destaque | `DS_OFERTA_DESTAQUE` trim; vazio → ausente; > 200 caracteres → cortado com `…` | Garante que só o título precise de corte | n |
| Legenda encerrada | `⛔ <b>Oferta encerrada</b>` + linhas da legenda original (sem a linha do link e sem "Caiu mais") em texto puro dentro de um único `<s>…</s>`, recalculada da linha atual de OFERTA | Não há coluna com a legenda enviada; texto puro evita aninhar `<code>` em `<s>` | n |
| 429 | Cancela a linha da oferta da vez, grava `pausa_ate = agora + retry_after` em `envio-estado.json` e termina com 0; execuções antes de `pausa_ate` saem com 0 sem chamar o Telegram | "Respeita `retry_after`" mesmo quando ele passa de 5 min | n |
| Falha não-429 no `sendPhoto` | Apaga a linha, para a execução, código 1 e alerta (bot de alertas, `alerta-envio.json`) | Sem duplicata; falha visível | n |
| Falha no `editMessageCaption` | 400 (mensagem apagada/não modificada) → WARN e grava `DT_EDICAO` (não tenta para sempre); outros → para, código 1 | Regra 8 | n |
| Ordem dentro da execução | Lote de envios primeiro, depois até 20 edições; edições rodam também fora da janela | Edição não notifica | n |
| `--sim` | Lê o Oracle, não chama Telegram nem grava nada no Oracle; imprime decisão (devido/enviados hoje) e, para as próximas `L` candidatas (mesmo fora da janela), a legenda e a origem da foto; grava o JPEG em `%TEMP%\besave-envio-sim\{id}.jpg` | Dono confere mensagem e foto antes de ligar a tarefa | n |
| `DT_PUBLICACAO_SITE` com `BESAVE_DESTINO_LOCAL` | Não grava (ensaio não publica o site) | Senão o envio postaria oferta sem página | n |
| Versão do contrato | 1.4.0 em `package.json` e `package-lock.json`; fixtures e site seguem em 1.3.3 (mesmo major) | `OfertaCanal` não vai para JSON publicado | n |
| `DS_OFERTA_DESTAQUE`, `ST_RECORRENCIA` | Lidas de OFERTA como a spec nomeia; não verificadas contra o banco nesta sessão | Execução real do dono confirma | n |

Open questions: nenhuma bloqueante; nomes `DS_OFERTA_DESTAQUE`/`ST_RECORRENCIA` confirmados na execução real.

---

## User Stories

### P1: Janela, cota e ritmo ⭐ MVP

**User Story**: Como dono, quero ~180 posts por dia espalhados entre 8 h e 22 h, sem rajadas.

**Acceptance Criteria**:

1. JAN-01: WHEN the local time (Brasília, -03:00) is outside `[NR_HORA_INICIO, NR_HORA_FIM)` THEN `besave-envio` SHALL send 0 posts.
2. JAN-02: The envio SHALL compute `esperado = min(QT_MAX_DIA, L + floor(QT_MAX_DIA × minutos_desde_INICIO / minutos_da_janela))` and SHALL send a batch of up to `L` only WHEN `esperado − enviados_hoje ≥ L`.
3. JAN-03: WHEN defaults 180/2 are used THEN 07:59 → 0, 08:00 → 2, 08:05 (2 sent) → 0, 08:10 (2 sent) → 2, 21:59 with 180 sent → 0, 22:00 → 0.
4. JAN-04: WHEN a full day is simulated with runs every 5 min THEN the envio SHALL post 180 (± 2) messages, none outside 08:00–22:00.
5. JAN-05: WHEN a run follows a 1 h stop THEN it SHALL send only one batch.
6. JAN-06: WHILE local time is outside `[NR_HORA_SOM_INICIO, NR_HORA_SOM_FIM)` the envio SHALL send with `disable_notification = true` (08:30 → true, 09:00 → false).
7. JAN-07: The envio SHALL keep ≥ 1 s between consecutive Telegram calls (posts of a batch and edits).

**Independent Test**: fakes de Oracle, Telegram e relógio; um dia simulado.

### P1: `DT_PUBLICACAO_SITE` no ciclo ⭐ MVP

**User Story**: Como dono, quero que o canal só divulgue oferta cuja página já está no ar.

**Acceptance Criteria**:

1. CIC-01: WHEN `besave-ciclo` publishes the manifest THEN it SHALL set `DT_PUBLICACAO_SITE = SYSDATE` for the published ids whose date is null, and a second run SHALL update 0 rows.
2. CIC-02: The ciclo SHALL send the ids in batches of at most 1 000 (2 500 ids → 3 batches).
3. CIC-03: IF the update fails THEN the ciclo SHALL log WARN, report `publicacao_site_falhas`, keep the manifest published and exit with code 0.
4. CIC-04: WHERE `BESAVE_DESTINO_LOCAL` is set the ciclo SHALL NOT update `DT_PUBLICACAO_SITE`.

**Independent Test**: `FakeFonte` registra as datas e conta lotes.

### P1: Seleção das candidatas ⭐ MVP

**User Story**: Como dono, quero que só ofertas boas, recentes e com página no ar vão ao canal, na melhor ordem.

**Acceptance Criteria**:

1. FIL-01: The envio SHALL exclude offers that are inactive, have null `DT_PUBLICACAO_SITE`, have `DT_OFERTA` older than `NR_HORAS_OFERTA_MAX` (25 h with 24), fail CONTRATO §9 or lack affiliate URL / `id_produto`, or were already sent to the channel.
2. FIL-02: The envio SHALL exclude offers with discount below `PC_DESCONTO_MIN` (29% with 30) and SHALL include offers with null `pd`.
3. REP-01: IF the same `ID_PRODUTO` was sent less than `NR_DIAS_REPETICAO` days ago THEN the offer SHALL be included only when `preco_por ≤ último × (1 − PC_QUEDA_REPETICAO/100)` (9% drop → out, 10% → in), and the caption SHALL carry "📉 Caiu mais o preço!!!".
4. REP-02: WHEN the last send of the product was `NR_DIAS_REPETICAO` days ago or more THEN the offer SHALL be included without the phrase.
5. ORD-01: The envio SHALL order by discount desc (null `pd` = 0) → with coupon first → `dt_oferta` desc → `id` desc.

### P1: Foto e legenda ⭐ MVP

**User Story**: Como dono, quero posts uniformes, legíveis e com link rastreável.

**Acceptance Criteria**:

1. FOT-01: The envio SHALL produce an 800×800 JPEG with the image centered, aspect ratio preserved and white borders.
2. FOT-02: IF the offer image is absent THEN the envio SHALL use the area placeholder.
3. LEG-01: The caption SHALL follow the layout of spec rule 6 with `parse_mode=HTML`, escaped text, price as `R$ 1.234,56` and store names Amazon / Mercado Livre / Shopee.
4. LEG-02: The caption SHALL show `<s>R$ de</s>` only WHEN `pd` is present, `-{pct}%` only WHEN `pct ≥ PC_DESCONTO_DESTAQUE` (29% → no badge, 45% → badge), `🔁 <i>(Recorrência)</i>` only WHEN recorrência, the coupon line only WHEN coupon, the highlight line only WHEN highlight.
5. LEG-03: IF the caption exceeds 1024 characters THEN the envio SHALL cut the title so the caption fits.
6. LEG-04: The link SHALL be `https://besave.io/{id}?utm_source=telegram`.

### P1: Sem duplicata, expiradas e limites ⭐ MVP

**User Story**: Como dono, quero nunca ver post duplicado e ver "Oferta encerrada" quando a oferta morre.

**Acceptance Criteria**:

1. DUP-01: The envio SHALL insert the `ENVIO_TELEGRAM` row before sending, write `NR_MESSAGE_ID` after success, and delete the row WHEN the send fails.
2. DUP-02: IF the Oracle insert fails THEN the envio SHALL make 0 Telegram calls for that offer.
3. EXP-01: WHEN a sent offer has `ST_ATIVO = 0` and null `DT_EDICAO` THEN the envio SHALL call `editMessageCaption` once (with "⛔ <b>Oferta encerrada</b>", struck original text, no link) and write `DT_EDICAO`; the next run SHALL edit 0.
4. EXP-02: WHEN 25 sent offers expire THEN one run SHALL edit 20.
5. LIM-01: WHEN Telegram answers 429 with `retry_after` THEN the run SHALL end with code 0, delete the unconfirmed row and keep only what was already confirmed.
6. LIM-02: WHILE `pausa_ate` from a previous 429 is in the future the envio SHALL make 0 Telegram calls and exit 0.

### P2: Binário e operação

**User Story**: Como dono, quero agendar o envio como o ciclo e testar antes com `--sim`.

**Acceptance Criteria**:

1. BIN-01: `besave-envio` SHALL accept `--env-file <arq>` and `--sim`, use its own lock (`envio.lock`), daily log (`besave-envio.AAAA-MM-DD.log`), alert state (`alerta-envio.json`) and exit codes 0/1/2 (BSV-14).
2. BIN-02: IF `TELEGRAM_CANAL_BOT_TOKEN` is absent and `--sim` is not given THEN the envio SHALL exit with code 2; the token SHALL never appear in logs or `Debug`.
3. BIN-03: WHEN `--sim` is given THEN the envio SHALL print the chosen captions and photos and SHALL NOT call Telegram nor write to Oracle.
4. BIN-04: `scripts/registrar-tarefa-envio.ps1` SHALL register the task "Besave Envio" every 5 min with the BSV-14 rules.
5. CON-01: CONTRATO SHALL gain §11 `OfertaCanal` and version 1.4.0, with `packages/contract/package.json` at 1.4.0.

---

## Edge Cases

- WHEN `esperado − enviados_hoje` is exactly `L` THEN a batch SHALL be sent (JAN-02 boundary).
- WHEN the last send of the product was exactly `NR_DIAS_REPETICAO` days ago THEN REP-02 applies (boundary).
- WHEN discount equals `PC_DESCONTO_MIN` THEN the offer SHALL be included (FIL-02 boundary).
- WHEN fewer candidates than `L` exist THEN the envio SHALL send the available ones.
- IF the title contains `<&>` THEN the caption SHALL escape them.

Dimensions: estado/persistência (DUP-01, EXP-01, CIC-01); chamada externa e rate limit (JAN-07, LIM-01, LIM-02); falha parcial (DUP-02, CIC-03); transição de estado ativa→expirada (EXP-01); concorrência entre execuções: trava `envio.lock` (BIN-01); segredo: BIN-02. Auth de usuário/pagamento: N/A because não há usuário final.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| JAN-01 | Janela, cota e ritmo | Execute | Pending |
| JAN-02 | Janela, cota e ritmo | Execute | Pending |
| JAN-03 | Janela, cota e ritmo | Execute | Pending |
| JAN-04 | Janela, cota e ritmo | Execute | Pending |
| JAN-05 | Janela, cota e ritmo | Execute | Pending |
| JAN-06 | Janela, cota e ritmo | Execute | Pending |
| JAN-07 | Janela, cota e ritmo | Execute | Pending |
| CIC-01 | DT_PUBLICACAO_SITE | Execute | Pending |
| CIC-02 | DT_PUBLICACAO_SITE | Execute | Pending |
| CIC-03 | DT_PUBLICACAO_SITE | Execute | Pending |
| CIC-04 | DT_PUBLICACAO_SITE | Execute | Pending |
| FIL-01 | Seleção | Execute | Pending |
| FIL-02 | Seleção | Execute | Pending |
| REP-01 | Seleção | Execute | Pending |
| REP-02 | Seleção | Execute | Pending |
| ORD-01 | Seleção | Execute | Pending |
| FOT-01 | Foto e legenda | Execute | Pending |
| FOT-02 | Foto e legenda | Execute | Pending |
| LEG-01 | Foto e legenda | Execute | Pending |
| LEG-02 | Foto e legenda | Execute | Pending |
| LEG-03 | Foto e legenda | Execute | Pending |
| LEG-04 | Foto e legenda | Execute | Pending |
| DUP-01 | Sem duplicata, expiradas, limites | Execute | Pending |
| DUP-02 | Sem duplicata, expiradas, limites | Execute | Pending |
| EXP-01 | Sem duplicata, expiradas, limites | Execute | Pending |
| EXP-02 | Sem duplicata, expiradas, limites | Execute | Pending |
| LIM-01 | Sem duplicata, expiradas, limites | Execute | Pending |
| LIM-02 | Sem duplicata, expiradas, limites | Execute | Pending |
| BIN-01 | Binário e operação | Execute | Pending |
| BIN-02 | Binário e operação | Execute | Pending |
| BIN-03 | Binário e operação | Execute | Pending |
| BIN-04 | Binário e operação | Execute | Pending |
| CON-01 | Binário e operação | Execute | Pending |

## Success Criteria

- [ ] `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` verdes, sem rede.
- [ ] Execução real do dono (bloqueia o merge): ~180 posts no dia, só 8–22 h, silenciosos fora de 9–21 h, expirada vira "Oferta encerrada".
