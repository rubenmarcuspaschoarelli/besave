# BSV-40 Validation

## Validation: BSV-40 - PASS

**Veredito: PASS** — re-verificação após o ciclo de correção 1 (commit `8255a04`, só testes): os 33 mutantes morrem, gate verde. Execução real do dono continua bloqueando o merge.

**Data**: 2026-10-06
**Verificou**: Verifier independente, sub-agente; autor ≠ verificador. Não alterou código nem testes.
**Spec**: `docs/specs/BSV-40.md` (critério de aceite do dono) e `.specs/features/BSV-40/spec.md` (requisitos do autor)
**Faixa do diff**: `origin/develop..HEAD` = `e7f5166..8255a04` (9 commits: T1–T8 + correção 1 `8255a04` em `apps/worker/tests/envio_execucao.rs`, sem código de produção)
**Histórico**: 1ª verificação (até `38d3a79`) FAIL — M29 sobreviveu; ciclo de correção 1 → PASS.

---

## Tarefas

| Task | Status | Notas |
| ---- | ------ | ----- |
| T1–T8 | ✅ Concluídas | todas marcadas em `tasks.md`; 1 commit cada |
| Correção 1 | ✅ Concluída | `8255a04`: `limite_429_na_edicao`, `erro_na_edicao_falha_sem_marcar` |

---

## Critérios de aceite (ancorados na spec)

| Critério (spec do dono / req.) | Resultado definido pela spec | Evidência `arquivo:linha` – asserção | Status |
| --- | --- | --- | --- |
| 07:59 → 0; 08:00 → 2; 08:05 → 0; 08:10 → 2; 21:59 c/ 180 → 0; 22:00 → 0 (JAN-01/03) | exatamente esses valores | `apps/worker/tests/envio_janela.rs:20-25` – `assert_eq!(lote_devido(&p(), hora(8, 0), 0), 2)` etc. | ✅ |
| Fórmula `esperado − enviados ≥ L`, teto `QT_MAX_DIA` (JAN-02) | fronteira `= L` envia; `L−1` não; teto 180 | `apps/worker/tests/envio_janela.rs:40-44` | ✅ |
| Dia simulado a cada 5 min → 180 ± 2, nenhum fora de 8–22 h (JAN-04) | 178..=182, hora local ∈ [8,22) | `apps/worker/tests/envio_execucao.rs:91` – `(178..=182).contains(&posts.len())`; `:94` – `(8..22).contains(&h)` | ✅ |
| Parada de 1 h → só 1 lote (JAN-05) | 2 posts | `apps/worker/tests/envio_execucao.rs:115` – `assert_eq!(…, 2)` | ✅ |
| 08:30 → `disable_notification = true`; 09:00 → false (JAN-06) | true / false | `apps/worker/tests/envio_janela.rs:69-72`; `apps/worker/tests/envio_execucao.rs:129-130`; campo no multipart `apps/worker/tests/envio_http.rs:57` | ✅ |
| ≥ 1 s entre posts do lote (JAN-07) | ≥ 1000 ms | `apps/worker/tests/envio_execucao.rs:160` – `par[1].ms - par[0].ms >= 1000` | ✅ |
| Ciclo: data gravada uma vez; 2ª execução → 0 updates (CIC-01) | 3 marcadas, depois 0 | `apps/worker/tests/publicacao_site.rs:67`, `:73` | ✅ |
| Falha no update → WARN, código 0, manifest publicado (CIC-03) | `Codigo::Ok`, WARN, `publicacao_site_falhas=1`, manifest existe | `apps/worker/tests/publicacao_site.rs:99-107` | ✅ |
| 2.500 ids → 3 lotes (CIC-02) | 3 statements | `apps/worker/tests/publicacao_site.rs:86` – `assert_eq!(fonte.lotes_publicacao_site(), 3)` | ✅ |
| `BESAVE_DESTINO_LOCAL` não grava (CIC-04, decisão do autor) | `publicacao_site_marcadas=0` | `apps/worker/tests/cli_ciclo.rs:298-299` | ✅ |
| UPDATE só em data nula, `SYSDATE` | SQL | `apps/worker/tests/publicacao_site.rs:114-116` | ✅ |
| Filtros: inativa, `DT_PUBLICACAO_SITE` nula, `dt` 25 h → fora (FIL-01) | só a válida | `apps/worker/tests/envio_selecao.rs:55` – `vec![6]`; limite 24 h entra `:64` | ✅ |
| Desconto 29% → fora; `pd` nulo → dentro (FIL-02) | `[2, 3]` (30% e nulo) | `apps/worker/tests/envio_selecao.rs:97` | ✅ |
| Já enviada → fora (FIL-01) | `vec![2]` | `apps/worker/tests/envio_selecao.rs:81` | ✅ |
| §9 + URL de afiliado + `id_produto` | rejeições nomeadas | `apps/worker/tests/envio_modelo.rs:113` | ✅ |
| Repetição: 4 dias, queda 9% → fora; 10% → dentro com a frase (REP-01) | vazio / `caiu = true` | `apps/worker/tests/envio_selecao.rs:106`, `:112-113`, fronteira exata `:118`, `:121` | ✅ |
| Repetição há 5 dias → dentro sem a frase (REP-02) | `caiu = false` | `apps/worker/tests/envio_selecao.rs:130-131` | ✅ |
| Ordem: 50% sem cupom vs com cupom → com cupom; empate → mais recente (ORD-01) | `[1]`, `[1]` | `apps/worker/tests/envio_selecao.rs:183`, `:187`; ordem completa `:174` | ✅ |
| Foto 800×800 JPEG, bordas brancas, proporção (FOT-01) | 800×800, branco nos cantos, faixa 400±4 / 200±4 | `apps/worker/tests/envio_foto.rs:58`, `:67-78`, `:84`, `:97` | ✅ |
| Sem imagem → placeholder (FOT-02) | `OrigemFoto::Placeholder(area)` | `apps/worker/tests/envio_foto.rs:127-128`, `:133` | ✅ |
| Legenda com/sem `pd`, 29% sem selo, 45% com selo, recorrência, cupom, destaque (LEG-01/02) | layout exato da regra 6 | `apps/worker/tests/envio_legenda.rs:31-36` (igualdade exata), `:51-61`, `:74-77`, `:90-97` | ✅ |
| Título com `<&>` escapado (LEG-01) | `&lt;` `&gt;` `&amp;` | `apps/worker/tests/envio_legenda.rs:109-112` | ✅ |
| Título longo cortado para caber em 1024 (LEG-03) | ≤ 1024 e termina em `…` | `apps/worker/tests/envio_legenda.rs:126-130` | ✅ |
| Link com `utm_source=telegram` (LEG-04) | `https://besave.io/{id}?utm_source=telegram` | `apps/worker/tests/envio_legenda.rs:35`; `apps/worker/tests/envio_execucao.rs:194-197` | ✅ |
| Telegram falha → linha apagada (DUP-01) | 1 linha restante (a confirmada) | `apps/worker/tests/envio_execucao.rs:217-218`; linha antes do envio `:264-265` | ✅ |
| Oracle falha antes → 0 chamadas ao Telegram (DUP-02) | `chamadas().is_empty()` | `apps/worker/tests/envio_execucao.rs:277-278` | ✅ |
| Expirada → 1 edição, `DT_EDICAO`; 2ª execução → 0 (EXP-01) | 1 / 0 | `apps/worker/tests/envio_execucao.rs:293-308` | ✅ |
| 25 expiradas → 20 numa execução (EXP-02) | 20, 5, 0 | `apps/worker/tests/envio_execucao.rs:332-343` | ✅ |
| 429 com `retry_after` → código 0, só o confirmado gravado (LIM-01) | `Ok`, `retry_after=37`, 1 linha confirmada | `sendPhoto`: `apps/worker/tests/envio_execucao.rs:371-378`; `editMessageCaption`: `apps/worker/tests/envio_execucao.rs:443-452` – `assert_eq!(rel.editadas, 1)`, `assert_eq!(rel.retry_after, Some(30))`, 1 `DT_EDICAO`, `pausa_ate = agora + 30` | ✅ |
| Pausa respeitada (LIM-02) | 0 chamadas durante a pausa | `apps/worker/tests/envio_execucao.rs:389-390` | ✅ |
| Erro não-400/429 na edição → código 1, sem marcar (decisão do autor, regra 8) | `Codigo::Falha`, fase `edicao_telegram`, nenhuma `DT_EDICAO` | `apps/worker/tests/envio_execucao.rs:464-466` | ✅ |
| `--env-file`, trava `envio.lock`, log próprio, códigos 0/2 (BIN-01) | 2 com argumento inválido; 0 com trava ocupada | `apps/worker/tests/cli_envio.rs:80`, `:89`, `:140` | ✅ |
| Token ausente → 2; nunca em log nem `Debug` (BIN-02) | código 2; texto sem token | `apps/worker/tests/cli_envio.rs:105`, `:129`; `apps/worker/tests/envio_http.rs:31` | ✅ |
| `--sim` não envia nem grava (BIN-03) | 0 chamadas, envios inalterados | `apps/worker/tests/envio_http.rs:139-140` (função `simular`; o caminho do binário precisa de Oracle) | ✅ |
| Script da tarefa "Besave Envio" (BIN-04) | registrar a cada 5 min | sem teste automatizado (PowerShell); `apps/worker/scripts/registrar-tarefa-envio.ps1:47` lido | ⚠️ revisão manual / dono |
| Contrato 1.4.0, §11 (CON-01) | `1.4.0` | `apps/worker/tests/envio_modelo.rs:39`; `docs/CONTRATO.md:7`, `:245`; `packages/contract/package.json:3` | ✅ |
| `fmt`, `clippy -D warnings`, `cargo test` sem rede | verde | ver Gate | ✅ |
| **Real (dono)**: DDL, 1º ciclo preenchendo `DT_PUBLICACAO_SITE`, bot admin, `--sim`, tarefa, dia real, cupom copiável, link, "Oferta encerrada", prints sem token | — | — | ⏳ PENDENTE do dono (bloqueia o merge) |

---

## Sensor de discriminação

Worktree temporário fora do repositório (`git worktree add <REDACTED-temp> HEAD`), um mutante por vez, restaurado com `git checkout -- <arquivo>` entre mutantes; worktree removido com `git worktree remove --force`. `git status --porcelain` da worktree real: vazio antes e depois (idêntico).

| # | Arquivo:linha | Mutação | Testes rodados | Resultado |
| - | ------------- | ------- | -------------- | --------- |
| M01 | `apps/worker/src/envio/janela.rs:36` | `esperado − enviados ≥ L` → `>` | envio_janela, envio_execucao | ✅ MORTO |
| M02 | `apps/worker/src/envio/janela.rs:24` | fim da janela `m >= fim` → `m > fim` | envio_janela, envio_execucao | ✅ MORTO |
| M03 | `apps/worker/src/envio/janela.rs:44` | silêncio `m >= SOM_FIM` → `>` | envio_janela, envio_execucao | ✅ MORTO |
| M04 | `apps/worker/src/envio/janela.rs:29` | sem teto `.min(QT_MAX_DIA)` | envio_janela, envio_execucao | ✅ MORTO |
| M05 | `apps/worker/src/envio/selecao.rs:53` | desconto mínimo `>=` → `>` | envio_selecao | ✅ MORTO |
| M06 | `apps/worker/src/envio/selecao.rs:76` | repetição `dt_envio > limite` → `>=` (5 dias exatos) | envio_selecao | ✅ MORTO |
| M07 | `apps/worker/src/envio/selecao.rs:109` | queda `<=` → `<` | envio_selecao | ✅ MORTO |
| M08 | `apps/worker/src/envio/selecao.rs:61` | ordem do cupom invertida | envio_selecao | ✅ MORTO |
| M09 | `apps/worker/src/envio/selecao.rs:43` | `DT_PUBLICACAO_SITE` não exigida | envio_selecao, envio_execucao | ✅ MORTO |
| M10 | `apps/worker/src/envio/rodada.rs:182` | não cancelar a linha quando o Telegram falha | envio_execucao | ✅ MORTO |
| M11 | `apps/worker/src/envio/rodada.rs:166-173` | enviar antes de reservar | envio_execucao | ✅ MORTO |
| M12 | `apps/worker/src/envio/rodada.rs:24` | limite de edições 20 → 25 | envio_execucao | ✅ MORTO |
| M13 | `apps/worker/src/envio/rodada.rs:121` | ignorar `pausa_ate` | envio_execucao | ✅ MORTO |
| M14 | `apps/worker/src/envio/rodada.rs:26` | intervalo de 1 s removido | envio_execucao | ✅ MORTO |
| M15 | `apps/worker/src/envio/rodada.rs:188-189` | 429 no `sendPhoto` vira falha | envio_execucao | ✅ MORTO |
| M16 | `apps/worker/src/envio/rodada.rs:279` | `pausa_ate` sem `retry_after` | envio_execucao | ✅ MORTO |
| M17 | `apps/worker/src/envio/rodada.rs:229-231` | não gravar `DT_EDICAO` | envio_execucao | ✅ MORTO |
| M18 | `apps/worker/src/envio/legenda.rs:141` | título sem escape | envio_legenda | ✅ MORTO |
| M19 | `apps/worker/src/envio/legenda.rs:122` | corte de título removido | envio_legenda | ✅ MORTO |
| M20 | `apps/worker/src/envio/legenda.rs:81` | selo `>=` → `>` | envio_legenda | ✅ MORTO |
| M21 | `apps/worker/src/envio/legenda.rs:54` | link sem `utm_source` (1ª tentativa acertou o comentário de doc: descartada e refeita no `format!`) | envio_legenda, envio_execucao | ✅ MORTO |
| M22 | `apps/worker/src/envio/foto.rs:48` | foto sem centralizar (x = 0) | envio_foto | ✅ MORTO |
| M23 | `apps/worker/src/envio/foto.rs:49` | foto sem centralizar (y = 0) | envio_foto | ✅ MORTO |
| M24 | `apps/worker/src/execucao.rs:130` | `marcar_publicacao_site` sem lotes de 1000 | publicacao_site | ✅ MORTO |
| M25 | `apps/worker/src/ciclo.rs:335` | gravar `DT_PUBLICACAO_SITE` com `BESAVE_DESTINO_LOCAL` | cli_ciclo | ✅ MORTO |
| M26 | `apps/worker/src/envio/selecao.rs:44` | idade `d >= desde` → `>` | envio_selecao | ✅ MORTO |
| M27 | `apps/worker/src/envio/selecao.rs:57` | não excluir já enviadas | envio_selecao, envio_execucao | ✅ MORTO |
| M28 | `apps/worker/src/envio/selecao.rs:91-92` | repetição ignora as escolhidas no mesmo lote | envio_selecao | ✅ MORTO |
| M29 | `apps/worker/src/envio/rodada.rs:207` | 429 no `editMessageCaption` tratado como falha (código 1, alerta) | envio_execucao | ❌ sobreviveu na 1ª verificação → ✅ MORTO após `8255a04` (`envio_execucao.rs:443`) |
| M30 | `apps/worker/src/envio/http.rs:98` | `disable_notification` invertido no multipart | envio_http | ✅ MORTO |
| M31 | `apps/worker/src/envio/rodada.rs:160` | silêncio invertido na execução | envio_execucao | ✅ MORTO |
| M32 | `apps/worker/src/envio/rodada.rs:227` | erro não-400 na edição marcado como descartado/editado (sem falha) | envio_execucao | ✅ MORTO (`envio_execucao.rs:464`) |
| M33 | `apps/worker/src/envio/rodada.rs:212-213` | 429 na edição não encerra a execução (segue editando e marca) | envio_execucao | ✅ MORTO (`envio_execucao.rs:452`) |

**Profundidade**: P0 (dados/canal público; ≥ 5 mutantes manuais). **Resultado**: 1ª verificação 30/31; re-verificação 33/33 mortos — PASS. Re-verificação em novo worktree temporário (descartado); `git status --porcelain` igual ao do início (só este `validation.md` não rastreado).

---

## Gate

- Comando (na worktree real, `CARGO_TARGET_DIR=<REDACTED>`, `CARGO_BUILD_JOBS=2`): `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`
- Resultado (re-verificação, HEAD `8255a04`): exit 0. `fmt` ok; `clippy` sem avisos; **372 passados, 0 falhos, 3 ignorados** (os 3 `#[ignore]` são anteriores à BSV-40; o diff não adiciona nenhum). 1ª verificação (`38d3a79`): 370 passados.
- Testes antes: 305 (+3 ignorados). Depois: 372. Delta: **+67** (envio_execucao 16, envio_selecao 11, envio_legenda 9, envio_http 7, envio_janela 6, envio_modelo 6, envio_foto 4, cli_envio 4, publicacao_site 4) + 2 asserções novas em `cli_ciclo.rs`. Nenhum teste removido ou enfraquecido.
- Nenhum teste toca rede, Oracle ou AWS (fakes `FakeEnvio`, `FakeCanal`, `RelogioFake`, `FakeFonte`; CLI para antes do Oracle).

---

## Qualidade de código

| Princípio | Status |
| --------- | ------ |
| Escopo: só `apps/worker/`, `docs/CONTRATO.md` §11, `packages/contract/package.json`/lock | ✅ |
| `sql/bsv-40.sql` intocado | ✅ |
| Dependência nova: só a feature `jpeg` do `image` (autorizada pela regra 10) | ✅ |
| Token fora de log/`Debug`; erros HTTP limpam o token | ✅ |
| Asserções nos valores da spec (não na implementação) | ✅ |
| Diretrizes: `CLAUDE.md`, `apps/worker/CLAUDE.md` (traits com fake, sem `unwrap` fora de teste) | ✅ |

---

## Lacunas (ranqueadas)

1. ~~**[FAIL] 429 no `editMessageCaption` sem teste**~~ — **resolvida** em `8255a04` (`apps/worker/tests/envio_execucao.rs:437-467`); M29, M32 e M33 mortos.
2. **[spec-precision] Origem da foto** — a spec diz `img/ofertas/{id}.webp`; o código lê o arquivo do robô `BESAVE_IMAGENS_DIR/{id}/{id}.webp` (`apps/worker/src/envio/foto.rs:26-29`), mesmo conteúdo, sem S3. Premissa declarada pelo autor; confirmar com o dono.
3. **[spec-precision] Desconto mínimo arredondado** — o filtro usa `desconto_pct` arredondado (`apps/worker/src/envio/selecao.rs:53`): 29,5% vira 30% e entra. A spec não diz se arredonda; coerente com CONTRATO §4.1.
4. **[real] SQL do envio sem teste** — `apps/worker/src/envio/oracle.rs` (binds nomeados repetidos `:desloc`, `ROWNUM`, conversão de fuso, nomes `DS_OFERTA_DESTAQUE`/`ST_RECORRENCIA`) só se prova na execução real.
5. **[menor] `--sim` do binário** — só a função `simular` é testada (`apps/worker/tests/envio_http.rs:116`); o caminho do executável depende de Oracle.
6. **[cosmético] Pastas temporárias** de `envio_foto.rs`/`cli_envio.rs` não são apagadas ao fim dos testes.

## Correção proposta

### Fix 1: teste de 429 na edição — ✅ aplicado em `8255a04` e re-verificado
- **Onde**: `apps/worker/tests/envio_execucao.rs`.
- **Teste**: 2 posts confirmados de ofertas expiradas; `FakeCanal` roteirizado com `[Ok(()), Err(ErroCanal::Limite(30))]`; rodar às 23:00. Esperado: `Ok`, `rel.editadas == 1`, `rel.retry_after == Some(30)`, só a primeira linha com `dt_edicao` gravada, a segunda ainda `None`; `EstadoEnvio::depois` → `pausa_ate = agora + 30`. Opcional: `Err(ErroCanal::Http(502))` na edição → `Falha` com `fase == "edicao_telegram"` e `DT_EDICAO` não gravada.
- **Done when**: M29 (trocar `Err(ErroCanal::Limite(s)) =>` por `… if false =>` em `rodada.rs:207`) passa a ser morto.
- **Prioridade**: Major.

---

## Pendências do dono (execução real — bloqueiam o merge)

DDL rodado; `besave-ciclo` novo preenchendo `DT_PUBLICACAO_SITE` (1º ciclo: todas as publicadas); bot admin do canal; `--sim` com mensagem e foto coerentes; tarefa "Besave Envio" registrada; um dia real: lotes de 2 a cada ~10 min, ~180 posts, só 8–22 h, silenciosos fora de 9–21 h; cupom copiável; link abre a página; oferta desativada vira "Oferta encerrada"; prints sem token.

---

## Rastreabilidade

| Requisito | Novo status |
| --------- | ----------- |
| JAN-01..07, CIC-01..04, FIL-01..02, REP-01..02, ORD-01, FOT-01..02, LEG-01..04, DUP-01..02, EXP-01..02, LIM-01..02, BIN-01..03, CON-01 | ✅ Verificado |
| BIN-04 | ⏳ Execução real do dono |

## Resumo

**Geral**: ✅ Pronto do lado do código; merge bloqueado só pela execução real do dono.
**Critérios**: 35/36 com evidência; 1 manual (BIN-04); 2 lacunas de precisão de spec (lacunas 2–3).
**Sensor**: 33/33 mortos.
**Gate**: 372 passados, 0 falhos.
