# BSV-12c Validation (rodada 2)

**Verdict:** PASS

**Date**: 2026-09-30
**Spec**: `.specs/features/BSV-12c/spec.md` (17 ACs: IDX-01..07, REC-01..06, CON-01..02, REL-01..02) + `docs/specs/BSV-12c.md`
**Diff range**: `b767ace..d7c63a6` (4209657 trait, e011ea3 índice, 33612a2 binário + README, 42867fb testes da rodada 1, d7c63a6 ajuste do dono `If-Match`), pasta `apps/worker/`
**Verifier**: independente (autor ≠ verificador), rodada 2 de no máximo 3

O código está pronto. As lacunas 1, 4 e 5 da rodada 1 estão fechadas, os 17 ACs têm evidência com o valor exato da spec, e o sensor matou todos os mutantes executáveis offline, exceto um residual (M17b) que só é alcançável com a KVS real. O PASS vale para o código. **O merge continua bloqueado pela execução real do dono** (regra "real run before merge"; ver "Pendências do dono").

---

## Task Completion

Sem `tasks.md`. A rastreabilidade da spec mapeia Step 1 (4209657), Step 2 (e011ea3), Step 3 (33612a2) e Step 4 (d7c63a6, CON-01/02). Os cinco commits existem no range; 42867fb só adiciona testes.

---

## Fechamento das lacunas da rodada 1

| # | Lacuna | Evidência | Status |
| --- | --- | --- | --- |
| 1 | Falha de leitura do índice sem teste | `apps/worker/tests/indice_redirects.rs:406-431` `LeituraQuebrada` faz `ler(INDICE)` devolver `Err(Aws{GetObject})`; `:436` `erro_ao_ler_o_indice_aborta_sem_escrever`; `:440-443` `matches!(erro, ErroGeracao::Redirects(ErroRedirects::Indice(_)))`; `:444` `listar_chamadas() == 0`; `:445` `aplicados().is_empty()`; `:446` `gravacoes().is_empty()`. Código: `apps/worker/src/redirects.rs:158` `.map_err(ErroRedirects::Indice)?`. M11 agora morre (executado) | ✅ Fechada |
| 4 | `redirects_motivo_reconstrucao: -` sem teste | A lógica saiu de `main.rs` para `RelatorioRedirects::motivo_texto` (`apps/worker/src/redirects.rs:118-121`), chamada em `apps/worker/src/main.rs:186`. Teste `apps/worker/tests/indice_redirects.rs:452` `motivo_texto_e_traco_no_modo_indice`: `:456` `== "indice_ausente"`, `:458` modo `Indice`, `:459` `== "-"`. M13 morre. Residual: o binário em si nunca imprime `-` nos testes (M17b), porque o `--gerar` local sempre reconstrói (assunção da spec); só o `--publicar` real chega ao modo indice | ✅ Fechada (residual justificado) |
| 5 | Índice ausente do plano | `apps/worker/tests/plano.rs:425` `plano_mostra_o_indice_da_kvs_sem_listar`: `:429` `(gravar, remover, aplicar) == (0, 0, 0)`; `:430` 0 `listar` com índice válido; `:440` `Gravar { cache_control == "no-store" }` para `_estado/redirects.json`; `:443` índice antes de `manifest.prev.json` | ✅ Fechada |
| 2 | Sensor incompleto | M10–M18 executados nesta rodada (tabela abaixo) | ✅ Fechada |
| 6 | 2 `DescribeKeyValueStore` com diff | Resolvida pelo ajuste d7c63a6: `RedirectsKvs::aplicar` não descreve mais (`apps/worker/src/aws.rs:396-460`, só `describe` no caminho sem lotes, `:430-431`, inalcançável a partir de `aplicar_diff`); CON-02 prende o contrato | ✅ Fechada |
| 3 | Execução real | Fora do alcance offline | ⏳ Pendente (dono) |

### Relocação do REC-05

`reconstrucao_loga_warn_com_o_motivo` saiu de `tests/indice_redirects.rs` (33612a2) para `apps/worker/tests/indice_redirects_log.rs:63`, binário de teste com um teste só. Comparei as duas versões linha a linha: mesmo `warns_de` (subscriber `fmt` com nível `WARN`, filtro `WARN` + `redirects`), mesmas três fases e mesmas asserções (`:70` `w.len() == 1`, `:71` contém `indice_ausente`; `:76` vazio em modo indice; `:80` `w.len() == 1`, `:81` contém `etag_divergente`). A única diferença é o `rodar` local, que usa `comum::linha` direto. A justificativa (cache de interesse dos callsites do `tracing` com testes paralelos sem subscriber) é plausível e o isolamento num binário próprio é a correção padrão. **Não enfraquecido**; M15 e M15b morrem nele.

---

## Spec-Anchored Acceptance Criteria

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --- | --- | --- | --- |
| IDX-01: índice válido, nada mudou | 0 `listar`, 1 `descrever`, 0 `aplicar`, `modo = indice` | `apps/worker/tests/indice_redirects.rs:77` `listar_chamadas() - listar == 0`; `:78` `descrever_chamadas() - descrever == 1`; `:79` `aplicados().len() - aplicados == 0`; `:80` `modo == Indice`; `:81` `motivo == None` | ✅ PASS |
| IDX-02: 3 novas, 1 alterada, 2 removidas | 1 `aplicar`, exatamente 4 puts e 2 deletes | `apps/worker/tests/indice_redirects.rs:105` `aplicados().len() == aplicados + 1`; `:107-115` `put == [(1001,…-nova),(1007,…),(1008,…),(1009,…)]`; `:116` `del == [1005, 1006]`; `:104` 0 `listar` | ✅ PASS |
| IDX-03: índice pós-diff | `ETag`/`ItemCount` pós-escrita + hash16 por id publicado | `apps/worker/tests/indice_redirects.rs:125` `i["kvs_etag"] == depois.etag`; `:126` `kvs_item_count == 7`; `:134` `urls == esperado` com `h16` independente (SHA-256, 8 bytes, hex, `:49-51`) | ✅ PASS |
| IDX-04: nada mudou | não grava `_estado/redirects.json` | `apps/worker/tests/indice_redirects.rs:83-87` `!gravadas(&p, marca).contains(INDICE)` | ✅ PASS |
| IDX-05: headers | `application/json`, `no-store` | `apps/worker/tests/indice_redirects.rs:158` `content_type == "application/json"`; `:159` `cache_control == "no-store"`; `:160` sem `content_encoding`. Plano: `apps/worker/tests/plano.rs:440` | ✅ PASS |
| IDX-06: sem URL em claro | nenhuma ocorrência de `http` | `apps/worker/tests/indice_redirects.rs:171` `!texto.contains("http")`; `:172` `!contains("amzn")`; `:173` 4 entradas | ✅ PASS |
| IDX-07: expurgo em modo indice | ids do índice; 0 `listar` no ciclo inteiro; id que sai → as duas imagens removidas | `apps/worker/tests/indice_redirects.rs:187` `modo == Indice`; `:188-192` `listar_chamadas() == listar` no ciclo inteiro (expurgo incluído); `:194-199` `chave_small(1003)` e `chave_grande(1003)` removidas; `:200-202` 1001/1002 não | ✅ PASS |
| REC-01: índice ausente | 1 `listar`, `reconstrucao`/`indice_ausente`, índice gravado; ciclo seguinte `indice` | `apps/worker/tests/indice_redirects.rs:212` `listar_chamadas() == 1`; `:213-214` modo/motivo; `:215` `existe(INDICE)`; `:218` 2º ciclo `Indice`; `:219` ainda 1 `listar`. KVS já populada: `:234-235` 0 puts/dels, nenhum `aplicar` | ✅ PASS |
| REC-02: `ETag` difere | `etag_divergente`; KVS = conjunto publicado | `apps/worker/tests/indice_redirects.rs:252-253` modo/motivo; `:254` +1 `listar`; `:255` `(puts, dels) == (1, 0)`; `:256-261` `kvs.listar() == {1001..1003 → URL}` | ✅ PASS |
| REC-03: `ETag` igual, `ItemCount` difere | `item_count_divergente` | `apps/worker/tests/indice_redirects.rs:279-283` modo/motivo; `:284` `aplicados().last() == (vec![], vec![9999])` | ✅ PASS |
| REC-04: índice ilegível | `indice_ilegivel`, sem abortar, índice regravado | `apps/worker/tests/indice_redirects.rs:291` três lixos (não-JSON, sem campos, `[]`); `:299-304` modo/motivo; `:305` manifest gravado; `:306` índice regravado com `kvs_item_count == 3` | ✅ PASS |
| REC-05: `WARN` com o motivo | 1 `WARN` com o motivo; modo indice sem `WARN` | `apps/worker/tests/indice_redirects_log.rs:70-71` 1 linha com `indice_ausente`; `:76` vazio em modo indice; `:80-81` 1 linha com `etag_divergente` | ✅ PASS |
| REC-06: gravar índice falha | erro, sem `manifest.json` | `apps/worker/tests/indice_redirects.rs:345-348` `matches!(ErroGeracao::Redirects(ErroRedirects::Indice(_)))`; `:349` mensagem cita a chave; `:350` `!existe("manifest.json")`; `:355` ciclo seguinte `IndiceAusente` | ✅ PASS |
| CON-01: KVS muda entre `carregar_base` e `aplicar` | `ErroRedirects::Concorrencia`; diff não aplicado; índice e manifest não gravados; ciclo seguinte `etag_divergente` | `apps/worker/tests/indice_redirects.rs:466` `kvs_alterada_entre_leitura_e_escrita_e_concorrencia`: `:477-482` `matches!(ErroGeracao::Redirects(ErroRedirects::Concorrencia{..}))`; `:484-488` `aplicados().len() == aplicados`; `:489` `kvs.listar() == antes`; `:490` índice com os mesmos bytes; `:492-496` nenhuma gravação de `INDICE` nem `manifest*`; `:500` 2º ciclo `motivo == EtagDivergente`; `:501` 1004 chega à KVS | ✅ PASS |
| CON-02: ciclo com diff | `descrever()` exatamente 1 vez | `apps/worker/tests/indice_redirects.rs:506` `ciclo_com_diff_descreve_a_kvs_uma_vez`: `:512` `puts == 1` (tem diff); `:513` `descrever_chamadas() - descrever == 1` | ✅ PASS |
| REL-01: `modo`/`motivo` com textos exatos | `indice`/`reconstrucao`; quatro motivos; motivo só na reconstrução | `apps/worker/tests/indice_redirects.rs:380-381` Display dos modos; `:391-402` conjunto exato dos 4 textos; `:81` `motivo == None` em modo indice; `apps/worker/tests/geracao.rs:312` literal do relatório | ✅ PASS |
| REL-02: binário imprime modo e motivo | `redirects_modo: <modo>`, `redirects_motivo_reconstrucao: <motivo \| ->` | `apps/worker/tests/dry_run.rs:340` `gerar_fake_imprime_modo_e_motivo_dos_redirects`: `:352` `\nredirects_modo: reconstrucao\n`; `:360` `\nredirects_motivo_reconstrucao: indice_ausente\n`. Ramo `-`: `apps/worker/tests/indice_redirects.rs:459` `motivo_texto() == "-"`, ligado em `apps/worker/src/main.rs:186` | ✅ PASS (ramo `-` do binário só na execução real) |

Edge cases da spec:

- [x] Conjunto publicado vazio em modo indice → todos os ids viram delete: `apps/worker/tests/indice_redirects.rs:145-148` `aplicados().last() == (vec![], vec![1001,1002,1003])`; `:149` KVS vazia.
- [x] `aplicar` falha → erro sem índice nem manifest: `apps/worker/tests/indice_redirects.rs:369-374`; `apps/worker/tests/geracao.rs:472`.
- [x] Id com hash diferente vira put: id 1001, `apps/worker/tests/indice_redirects.rs:101`, `:110`.
- [x] Assunção "falha de leitura do índice → erro, sem escrita": `apps/worker/tests/indice_redirects.rs:436-447`.
- [x] Assunção `RedirectsMemoria` (`ETag` muda a cada escrita, `aplicar` checa `ETag`): `apps/worker/tests/redirects.rs:223`.

**Status**: ✅ 17/17 ACs com evidência; valores afirmados batem com a spec. 0 spec-precision gaps.

### Exigência do dono (IDX-07): 0 `listar()` no ciclo inteiro em modo indice

- Código: `apps/worker/src/geracao.rs:173` `carregar_base(&redirects, &*pub_)?`; `:174` `ids_anteriores = base_redirects.urls.keys()`; `:276` `sincronizar_com_indice(.., base_redirects, ..)`. A única chamada a `Redirects::listar()` no caminho de `gerar` é `apps/worker/src/redirects.rs:175`, no braço `Err(m)` (reconstrução). `sincronizar_com_indice` (`:272-297`) não lista.
- Testes: `apps/worker/tests/indice_redirects.rs:188-192` (ciclo inteiro), `:77`, `:104`; plano `apps/worker/tests/plano.rs:430`.
- Sensor: M3, M4 (rodada 1) e M16 (esta rodada) mortos.

✅ Mantida.

---

## Discrimination Sensor

Worktree temporário (`git worktree add --detach <scratchpad>/bsv12c-sensor2 HEAD`), baseline sem mutação 82/82 nos alvos, um mutante por vez, só os alvos relevantes (`-q --no-fail-fast`), `git checkout -- .` entre mutantes, nunca dois `cargo` ao mesmo tempo. M1–M9 vêm da rodada 1 (mesmo código nesses pontos; `src/redirects.rs` mudou de linha, não de lógica).

| # | File:line (HEAD) | Mutação | Killed? (por) |
| --- | --- | --- | --- |
| M1 | `src/redirects.rs:165` | checagem de `ETag` desligada | ✅ (rodada 1) `kvs_alterada_por_fora_…`, `reconstrucao_loga_warn_…` |
| M2 | `src/redirects.rs:166` | checagem de `ItemCount` desligada | ✅ (rodada 1) `item_count_diferente_reconstroi` |
| M3 | `src/redirects.rs:172` | braço confiável também lista | ✅ (rodada 1) 5 testes |
| M4 | `src/geracao.rs:174` | `ids_anteriores` de `redirects.listar()` | ✅ (rodada 1) 5 testes, incl. `expurgo_em_modo_indice_…` |
| M5 | `src/redirects.rs:290` | grava o índice sempre | ✅ (rodada 1) `indice_valido_sem_mudanca_…` + 6 de `ciclo.rs` |
| M6 | `src/redirects.rs:290` | nunca grava o índice | ✅ (rodada 1) 15 testes |
| M7 | `src/redirects.rs:286` | índice com URL em vez de hash16 | ✅ (rodada 1) 4 testes |
| M8 | `src/redirects.rs:163-164` | troca `indice_ausente` ↔ `indice_ilegivel` | ✅ (rodada 1) vários |
| M9 | `src/redirects.rs:280` | índice com o estado de antes da escrita | ✅ (rodada 1) 8 testes |
| M10 | `src/redirects.rs:291-292` | erro de gravação do índice engolido (`let _ =`) | ✅ `falha_ao_gravar_indice_aborta_antes_do_manifest` |
| M11 | `src/redirects.rs:158` | erro de leitura do índice vira ausente (`unwrap_or(None)`) | ✅ `erro_ao_ler_o_indice_aborta_sem_escrever` (sobrevivia na rodada 1) |
| M12 | `src/redirects.rs:100` | texto `item_count_divergente` → `itemcount_divergente` | ✅ `modo_e_motivo_tem_os_textos_da_spec` |
| M13 | `src/redirects.rs:120` | `-` trocado por string vazia em `motivo_texto` | ✅ `motivo_texto_e_traco_no_modo_indice` |
| M14 | `src/redirects.rs:165-168` | `ItemCount` checado antes do `ETag` | ✅ `reconstrucao_loga_warn_com_o_motivo`, `kvs_alterada_entre_leitura_e_escrita_e_concorrencia` |
| M15 | `src/redirects.rs:174` | `WARN` removido | ✅ `reconstrucao_loga_warn_com_o_motivo` |
| M15b | `src/redirects.rs:174` | `WARN` sem o campo `motivo` | ✅ `reconstrucao_loga_warn_com_o_motivo` |
| M16 | `src/geracao.rs:174` | base do expurgo vazia em modo indice | ✅ `expurgo_em_modo_indice_vem_do_indice_sem_listar`, `expurgo_remove_as_duas_chaves_de_imagem` |
| M17 | `src/main.rs:183` | `redirects_modo` com `{:?}` | ✅ `gerar_fake_imprime_modo_e_motivo_dos_redirects` |
| M17b | `src/main.rs:186` | binário ignora `motivo_texto` e imprime vazio no `None` | ⚠️ Sobrevive. **Residual justificado**: o binário só chega ao modo indice com `--publicar` contra a KVS real; o `--gerar` usa `RedirectsMemoria::new()` a cada execução e sempre reconstrói (assunção da spec). A lógica do `-` é testada em `motivo_texto` (M13 morre). Conferir na execução real |
| M18 | `src/redirects.rs:295` | `motivo` descartado no relatório | ✅ 9 testes, incl. `indice_ausente_reconstroi_…`, `relatorio_com_contagens` |
| M19 (a) | `src/redirects.rs:452` | `RedirectsMemoria::aplicar` ignora o `ETag` | ✅ `kvs_alterada_entre_leitura_e_escrita_e_concorrencia` |
| M20 (b) | `src/redirects.rs:279` | `If-Match` com `descrever()` novo em vez de `base.estado.etag` | ✅ `ciclo_com_diff_descreve_a_kvs_uma_vez`, `indice_valido_sem_mudanca_…` (contagem de `descrever`) |
| M21a (c) | `src/redirects.rs:279` | índice gravado (estado da base) quando `aplicar` falha | ✅ `falha_na_kvs_nao_grava_indice`, `falha_na_kvs_nao_grava_manifest`, `kvs_alterada_entre_leitura_e_escrita_e_concorrencia` |
| M21b (c) | `src/redirects.rs:279-293` | índice gravado antes de `aplicar` (e não depois) | ✅ 12 testes, incl. `diff_de_seis_chaves_…`, `kvs_entre_chunks_e_manifest`, CON-01 |
| M22 (e, análogo offline) | `src/redirects.rs:453` | `RedirectsMemoria` devolve `Kvs` em vez de `Concorrencia` | ✅ `kvs_alterada_entre_leitura_e_escrita_e_concorrencia` |
| M23 (d) | `src/aws.rs:396-460` | `RedirectsKvs::aplicar` volta a chamar `DescribeKeyValueStore` | ➖ Não testável sem AWS: nenhum teste instancia `RedirectsKvs` (só `src/main.rs:127`). Não conta como lacuna; a execução real mostra (tempo de `t_redirects` e CloudTrail) |
| M24 (e) | `src/aws.rs:446-455` | `ConflictException` mapeada para `Kvs` em vez de `Concorrencia` | ➖ Não testável sem AWS (mesmo motivo). Impacto limitado: qualquer erro de `aplicar` aborta antes do índice e do manifest (M21a prova o caminho), só muda a variante/mensagem |
| M25 | `src/aws.rs:441` | lotes seguintes reutilizam o `ETag` inicial em vez do devolvido | ➖ Não testável sem AWS. Só aparece com diff > 50 chaves (`LOTE_KVS`) |

**Sensor depth**: expandido (integridade da KVS).
**Result**: 27 mutantes no plano; 24 executados (9 da rodada 1 + 15 nesta), **23 mortos, 1 sobrevivente residual justificado (M17b)**; 3 classificados como não testáveis offline (M23–M25). ✅ PASS

Observação de discriminação: o CON-01 injeta a escrita concorrente *dentro* de `aplicar` (`com_escrita_concorrente`, `src/redirects.rs:449-451`). Por isso M20 (ETag de um `descrever()` novo) não é pego pelo CON-01; quem o mata é a contagem de `descrever` (CON-02, IDX-01). Hoje está coberto; se um dia o contador sair, a proteção de "não absorver escrita externa entre `carregar_base` e `aplicar`" fica sem teste.

Isolamento: `git status --porcelain` da árvore real antes = `?? .specs/features/BSV-12c/validation.md`; scratch limpo depois de cada mutante; `git worktree remove --force` + `git worktree prune`; `git worktree list` sem o scratch; árvore real depois = só `?? .specs/features/BSV-12c/validation.md`.

---

## Code Quality

| Principle | Status |
| --- | --- |
| Minimum code / surgical changes | ✅ `motivo_texto` substitui o `match` de `main.rs` (testável sem binário); `Concorrencia` é a única variante nova |
| No scope creep | ✅ Function, agendamento, `PublicadorPlano` fora |
| Matches patterns (`thiserror`, sem `unwrap` fora de teste) | ✅ |
| Sem dependência nova | ✅ `Cargo.toml` fora do diff |
| Asserted values match spec | ✅ |
| Every test maps to a spec requirement | ✅ 18 testes em `indice_redirects.rs` (IDX/REC/CON/REL + edges + assunção de leitura); 1 em `indice_redirects_log.rs` (REC-05); `plano_mostra_o_indice_…` (assunção `--publicar` sem `--sim`); `memoria_expoe_…` (assunção `RedirectsMemoria`); `gerar_fake_imprime_…` (REL-02) |
| Guidelines: `CLAUDE.md`, `apps/worker/CLAUDE.md` | ✅ |

Revisão do ajuste d7c63a6 (`src/aws.rs:396-460`): o 1º `UpdateKeys` usa o `ETag` de `carregar_base`; os seguintes encadeiam `r.e_tag()`; `Concorrencia` carrega o `ETag` recusado; sem lotes, `descrever()` (caminho morto a partir de `aplicar_diff`, inofensivo). `sincronizar_redirects` (legado, fora de `gerar`) passou a descrever antes de listar, coerente com o novo contrato.

### Testes com expectativa alterada

| Teste | Mudança | Julgamento |
| --- | --- | --- |
| SIT-01 `primeira_execucao_publica_…` (`tests/ciclo.rs:307`) | lista exata ganha `_estado/redirects.json` | ✅ Legítima (IDX-05); lista continua exata |
| ORD-02 `kvs_entre_chunks_e_manifest` (`tests/geracao.rs:442`) | sequência KVS → índice → `manifest.prev.json` → `manifest.json` | ✅ Legítima (REC-06); igualdade exata; M21b a mata |
| `relatorio_com_contagens` (`tests/geracao.rs:279`, literal `:312`) | ganha `modo: Reconstrucao`, `motivo: Some(IndiceAusente)` | ✅ Legítima; comparação exata do struct; M18 a mata |
| `memoria_expoe_…` (`tests/redirects.rs:223`) | `aplicar` recebe o `ETag` corrente | ✅ Mudança de assinatura; asserções iguais |
| `impl Redirects` de teste (`tests/geracao.rs:429`, `tests/plano.rs:57`) | repassam `etag` | ✅ Só delegação |
| REC-05 movido para `tests/indice_redirects_log.rs` | mesmas asserções | ✅ Não enfraquecido (ver acima) |

Nenhuma asserção enfraquecida.

---

## Gate Check

- **Comando** (em partes, `CARGO_TARGET_DIR=C:\cargo-target\besave`, `CARGO_BUILD_JOBS=4`, em `apps/worker`, HEAD `d7c63a6`): `cargo fmt --check` → exit 0; `cargo clippy --all-targets -- -D warnings` → exit 0; `cargo test -q --no-fail-fast` → exit 0.
- **Resultado**: **237 passed, 0 failed, 3 ignored** (ignorados preexistentes de desempenho: `tests/ciclo.rs:215`, `tests/imagens.rs:480`, `tests/paginas.rs:267`; nenhum `#[ignore]` no diff; `--ignored` não executado).
- **Test count**: 215 antes da feature (BSV-13b) → 232 na rodada 1 → **237** agora. Delta da rodada: +5 (`erro_ao_ler_o_indice_…`, `motivo_texto_e_traco_…`, `plano_mostra_o_indice_…`, CON-01, CON-02); REC-05 só mudou de binário.

---

## Pendências do dono (bloqueiam o merge, não o código)

1. Duas `--publicar --sim` reais: 1ª → `redirects_modo: reconstrucao`, `redirects_motivo_reconstrucao: indice_ausente`; 2ª → `redirects_modo: indice`, **`redirects_motivo_reconstrucao: -`** (cobre o residual M17b), `t_redirects` < 5 s, total < 60 s; `curl -I https://<cf>/ir/<id novo>` → 302; tempos por fase colados no PR.
2. Uma 3ª execução depois de um diff (ex.: oferta nova): confirma que o `ETag`/`ItemCount` devolvidos pela `UpdateKeys` batem com o `DescribeKeyValueStore` do ciclo seguinte. Se não baterem, todo ciclo cai em `etag_divergente`/`item_count_divergente`: o resultado continua correto, mas o ganho de tempo some.
3. `ConflictException` como resposta a `If-Match` desatualizado é **inferência da documentação** (`API_kvs_UpdateKeys` lista `ConflictException` 409 "Resource is not in expected state" e não nomeia outro erro). Confirmar: se a AWS devolver outro erro (ex.: `ValidationException`), o ciclo aborta do mesmo jeito (sem índice nem manifest) e o próximo reconstrói; só a mensagem sai como `KVS UpdateKeys` em vez de `Concorrencia`. Teste possível: rodar o worker e, entre `carregar_base` e `aplicar`, escrever uma chave à mão na KVS.
4. M23 (sem `DescribeKeyValueStore` dentro de `aplicar`): conferir no CloudTrail ou pelo tempo de um ciclo com diff que há 1 `DescribeKeyValueStore` por ciclo.

---

## Requirement Traceability Update

| Requirement | Previous | New |
| --- | --- | --- |
| IDX-01..07 | Done | ✅ Verified |
| REC-01..06 | Done | ✅ Verified |
| CON-01, CON-02 | Done | ✅ Verified |
| REL-01 | Done | ✅ Verified |
| REL-02 | Done | ✅ Verified (ramo `-` do binário na execução real) |
| Assunção "leitura do índice falha → erro" | ❌ sem evidência | ✅ Verified |

---

## Lições (para o dono)

Não registradas em `lessons.json` (regra dos worktrees de ticket). Sugestões:

1. Quando um ramo de saída do binário é inalcançável offline, extrair a formatação para uma função pura e testá-la; o ramo do binário vai para o checklist da execução real.
2. Teste de concorrência otimista deve injetar a escrita externa no ponto que o mutante "reler o ETag na hora" não enxerga (entre a leitura da base e a escrita), não dentro da própria escrita; senão a proteção depende só de um contador de chamadas.
3. Teste que captura `tracing` com `with_default` deve ficar num binário de teste próprio: o cache de interesse dos callsites é global ao processo e outros testes em paralelo o envenenam.

---

## Summary

**Overall**: ✅ Código pronto; merge bloqueado pela execução real do dono.
**Spec-anchored check**: 17/17 ACs batem com a spec; 0 spec-precision gaps.
**Sensor**: 24 executados, 23 mortos, 1 residual justificado (M17b); 3 não testáveis offline (M23–M25).
**Gate**: 237 passed, 0 failed, 3 ignored.
