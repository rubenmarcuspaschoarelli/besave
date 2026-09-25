# BSV-11 Validation

**Verdict**: PASS ✅ (iteração 1 de 3, re-verificação: 27/27 ACs com evidência, gate verde com 77 testes, 22 mutantes distintos mortos nas duas passadas; os dois gaps da iteração 0 foram fechados em `b25f5b4`)

> Histórico: iteração 0 = FAIL (M09 `>` → `>=` sobreviveu; manifest anterior inválido só testado com JSON quebrado). Re-verificado por um Verifier novo e independente.

**Date**: 2026-09-25
**Spec**: `.specs/features/BSV-11/spec.md` + `docs/specs/BSV-11.md`
**Diff range**: `7485eba..HEAD` (6 commits, `8d09704`..`b25f5b4`; arquivos só em `apps/worker/` e `.specs/features/BSV-11/`)
**Verifier**: sub-agente independente (author ≠ verifier)

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 Publicador | ✅ Done | `8d09704` |
| T2 Chunks | ✅ Done | `e9ac66f` |
| T3 gerar + manifest | ✅ Done | `66011d4` |
| T4 Ciclo incremental | ✅ Done | `90eff4f` |
| T5 `--gerar` + README | ✅ Done | `273cdec` |
| Fix 1 + Fix 2 (iteração 1) | ✅ Done | `b25f5b4` (`checar_orcamento` + 2 testes) |

---

## Spec-Anchored Acceptance Criteria

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| PUB-01 `gravar` local | bytes em `raiz/chave` (pastas criadas) + headers em `raiz/chave.meta.json` | `apps/worker/tests/publicador.rs:70` - `fs::read(raiz/"data/chunks/5-abc.json.br") == [1,2,3]` (pasta aninhada criada); `:78` - sidecar `== {"content_type":"application/json","content_encoding":"br","cache_control":"public, max-age=31536000, immutable"}`; `:89` - sidecar do manifest com `content_encoding: null` | ✅ PASS |
| PUB-02 `ler`/`existe` | bytes ou `None`; `existe` true/false na mesma condição | `apps/worker/tests/publicador.rs:17-18` - ausente: `!existe`, `ler == None`; `:27-28` - presente: `existe`, `ler == Some(b"um")`; `:42-43` - após remover volta a `false`/`None`; roda para Local (`:54`) e Memória (`:59`) | ✅ PASS |
| PUB-03 `listar(prefixo)` | chaves com `/` que começam com o prefixo, sem `.meta.json` | `apps/worker/tests/publicador.rs:32` - `listar("data/chunks/") == ["data/chunks/0-b.json.br","data/chunks/1-a.json.br"]` (Local tem sidecars no disco); `:36` - `listar("data/chunks/1-") == ["data/chunks/1-a.json.br"]` | ✅ PASS |
| PUB-04 `remover` | apaga objeto e sidecar | `apps/worker/tests/publicador.rs:42-44` - objeto some de `existe`/`ler`/`listar`; `:106-107` - `!exists()` do objeto e do `.meta.json`; `:48` - chave ausente não é erro | ✅ PASS |
| PUB-05 `PublicadorMemoria` | mesmo contrato + headers por chave | `apps/worker/tests/publicador.rs:59` - `contrato(&mut PublicadorMemoria::new())`; `:116-118` - `meta(chunk) == Some(META_CHUNK)`, `meta(manifest) == Some(META_MANIFEST)`, `meta("ausente") == None` | ✅ PASS |
| CHK-01 partição | 999, 1000, 1999, 2000 → n 0, 1, 1, 2 | `apps/worker/tests/chunks.rs:27-30` - chaves `[0,1,2]`, `ids(&chunks[&1]) == [1000,1999]` | ✅ PASS |
| CHK-02 ordem por id | crescente, qualquer entrada | `apps/worker/tests/chunks.rs:39` - entrada invertida → `[5412,5413,5420]`; `:29` - entrada embaralhada | ✅ PASS |
| CHK-03 JSON + hash da fixture | JSON = fixture compactada; hash `89590e56ef6361dc` | `apps/worker/tests/chunks.rs:45` - `String::from_utf8(json) == compactar(fixture("chunk-ok.json"))`; `:49` - `hash == "89590e56ef6361dc"`; `apps/worker/tests/geracao.rs:101` - via `gerar`: `arquivo == "data/chunks/5-89590e56ef6361dc.json.br"` | ✅ PASS |
| CHK-04 round-trip Brotli + schema | descomprimido = JSON do chunk, válido contra `chunk.schema.json` | `apps/worker/tests/chunks.rs:58` - `bruto == json`; `:59` - `validar_schema("chunk.schema.json", …)`; `apps/worker/tests/geracao.rs:106-110` - chunk gravado por `gerar` descomprime na fixture e valida | ✅ PASS |
| CHK-05 chave + headers do chunk | `data/chunks/{n}-{hash16}.json.br`, `application/json`, `br`, `public, max-age=31536000, immutable` | `apps/worker/tests/geracao.rs:135-137` - prefixo `data/chunks/{n}-`, sufixo `.json.br`, 16 chars de hash, `meta(arquivo) == Some(META_CHUNK)`; valores da constante fixados por `apps/worker/tests/publicador.rs:78` | ✅ PASS |
| MAN-01 schema | `manifest.json` válido contra `manifest.schema.json` | `apps/worker/tests/geracao.rs:52` - `validar_schema("manifest.schema.json", …)` (com `format` checado) | ✅ PASS |
| MAN-02 cabeçalho | `contrato` = version do package.json; `versao` = `YYYYMMDDhhmmss` UTC; `gerado_em` ISO UTC; `busca: null` | `apps/worker/tests/geracao.rs:71` - `m.contrato == pkg["version"]`; `:72` - `m.versao == 20_260_924_124_000`; `:73` - `gerado_em == "2026-09-24T12:40:00Z"`; `:74` - `busca == None` | ✅ PASS |
| MAN-03 chunks | ordenados por `n`; `ids` min/max reais; `qtd`; `bytes` comprimido; `arquivo` = chave gravada | `apps/worker/tests/geracao.rs:82` - `n == [1,5]`; `:83`,`:85` - `ids == [1001,1500]`, `[5412,5420]`; `:84`,`:86` - `qtd == 2`, `3`; `:89` - `c.bytes == p.ler(&c.arquivo).len()` (chave gravada existe e o tamanho é o comprimido) | ✅ PASS |
| MAN-04 `areas` / `total_ofertas` | só cards sem `x`; total = cards publicados | `apps/worker/tests/geracao.rs:122` - `areas == {TECH:3, ELAS:1}` (PETS expirada ausente); `:123` - `total_ofertas == 5` (inclui a expirada) | ✅ PASS |
| MAN-05 manifest por último + headers | última gravação; `public, max-age=300, stale-while-revalidate=60` | `apps/worker/tests/geracao.rs:131` - `gravacoes().last() == "manifest.json"`; `:132` - `meta == Some(META_MANIFEST)`; valor fixado por `apps/worker/tests/publicador.rs:89` | ✅ PASS |
| MAN-06 orçamento | > 61 440 B → `ChunkAcimaDoOrcamento`, nada gravado | `apps/worker/tests/geracao.rs:151-156` - `matches!(ChunkAcimaDoOrcamento{n:0, bytes} if bytes > 61_440)`, `gravacoes().is_empty()`, `!existe("manifest.json")`; limite exato: `apps/worker/tests/geracao.rs:161` - `checar_orcamento(0, 61_440).is_ok()`; `:162-168` - `checar_orcamento(3, 61_441)` `matches!` `Err(ChunkAcimaDoOrcamento { n: 3, bytes: 61_441 })`; `gerar` chama `checar_orcamento` em `apps/worker/src/geracao.rs:117` (checagem em `:190-195`) | ✅ PASS (M09/M19 agora morre) |
| MAN-07 falha em chunk | erro, sem `manifest.json` | `apps/worker/tests/geracao.rs:200-201` - `matches!(erro, ErroGeracao::Publicador(_))`, `!existe("manifest.json")` | ✅ PASS |
| MAN-08 `Relatorio` | lidas, válidas, rejeitadas por motivo, escritos/reaproveitados/removidos, bytes totais, maior chunk, versao | `apps/worker/tests/geracao.rs:210-226` - igualdade estrutural completa: `lidas 7`, `validas 5`, `{PrecoPorInvalido:1, IdProdutoAusente:1}`, `2/0/0`, `bytes_totais` = soma do manifest, `maior_chunk`, `versao 20260924124000` | ✅ PASS |
| CIC-01 idempotência | 2ª execução: 0 escritos, 0 removidos, nenhuma chave `data/chunks/` gravada | `apps/worker/tests/ciclo.rs:53-55` - `escritos == 0`, `removidos == 0`, `reaproveitados == 3`; `:56` - gravações da 2ª execução `== ["manifest.prev.json","manifest.json"]` | ✅ PASS |
| CIC-02 mudança no chunk 5 | só o novo chunk 5 gravado; demais `arquivo` iguais | `apps/worker/tests/ciclo.rs:78-80` - `novo_5 != antigo_5`, `escritos == 1`, gravações `== [novo_5, prev, manifest]`; `:88-89` - chunks 1 e 7 iguais | ✅ PASS |
| CIC-03 órfão dura 1 ciclo | antigo continua após a execução em que saiu; removido na seguinte | `apps/worker/tests/ciclo.rs:91-92` - `removidos == 0`, `existe(antigo_5)`; `:95-99` - 3ª: `removidos == 1`, `!existe(antigo_5)`, `listar == chunks do manifest` | ✅ PASS |
| CIC-04 `manifest.prev.json` | cópia do anterior | `apps/worker/tests/ciclo.rs:111` - ausente na 1ª execução; `:115` - `ler("manifest.prev.json") == primeiro` (bytes idênticos) | ✅ PASS |
| CIC-05 expurgo | hash do chunk muda; faixa vazia some | `apps/worker/tests/ciclo.rs:139-141` - `c5.arquivo != anterior`, `ids == [5412,5413]`, nenhum `n == 9` | ✅ PASS |
| CIC-06 30 000 cards | ≤ 10 s com `PublicadorMemoria` | `apps/worker/tests/ciclo.rs:180-182` - `validas == 30_000`, `31` chunks, `tempo <= 10s` (medido: suíte `ciclo` inteira em 2,91 s, perfil dev) | ✅ PASS |
| CLI-01 `--gerar --saida` | cria `manifest.json`, `manifest.json.meta.json`, ≥ 1 `.json.br`, relatório, exit 0 | `apps/worker/tests/dry_run.rs:87-121` - `status.success()`, arquivos existem, `lidas: 10`, `validas: 3`, `rejeitadas: 7`, `chunks_escritos: 1`, `maior_chunk: n=5 bytes=`, `versao:`, `tempo:` | ✅ PASS |
| CLI-02 `--gerar` + `--dry-run` | erro sem panic | `apps/worker/tests/dry_run.rs:132-134` - `!success`, `code != 101`, sem `manifest.json` | ✅ PASS |
| CLI-03 `--gerar` sem `--saida` | erro sem panic | `apps/worker/tests/dry_run.rs:140-142` - `!success`, `code != 101`, stderr contém `--saida` | ✅ PASS |

**Status**: 27/27 ACs com evidência `file:line` e valor alinhado ao spec; o limite exato de MAN-06 agora é discriminado.

### Ticket "Critério de aceite" (`docs/specs/BSV-11.md`)

| Item | Evidence | Result |
| ---- | -------- | ------ |
| Partição 999/1000/1999/2000 e ordem por id | `chunks.rs:27-30`, `:39` | ✅ |
| Round-trip + schema; `chunk-ok.json` → hash literal | `chunks.rs:49`, `:59`; `geracao.rs:101` | ✅ |
| Manifest valida; `areas` ignora `x:1`; `ids` reais; `bytes` comprimido | `geracao.rs:52`, `:122`, `:83-89` | ✅ |
| 2ª execução → `chunks_escritos == 0` | `ciclo.rs:53` | ✅ |
| Mudança no chunk 5 → só ele; antigo removido só na 3ª | `ciclo.rs:79-99` | ✅ |
| Expurgo muda hash; faixa vazia some | `ciclo.rs:139-141` | ✅ |
| Chunk > 61 440 B (títulos de 200 chars) → erro, sem manifest | `geracao.rs:143-156` (999 cards com título aleatório de 200 chars) | ✅ |
| 30 000 cards ≤ 10 s | `ciclo.rs:182` | ✅ |
| `cargo run -- --gerar --saida` com fake | `dry_run.rs:83-121` | ✅ |
| Relatório coerente com `--dry-run` contra o Oracle real | dono roda; não verificável aqui | ⏭️ Pendente (dono) |
| `clippy -D warnings` limpo | gate abaixo | ✅ |
| DoD: README (`--gerar`, layout, `.meta.json`) | `apps/worker/README.md` (seção "Gerar chunks e manifest") | ✅ |
| DoD: relatório de execução real no PR | depende do Oracle | ⏭️ Pendente (dono) |

### Regras do ticket (inspeção estática)

| Regra | Evidência | Result |
| ----- | --------- | ------ |
| 4. chunks → manifest; nada de manifest se chunk falha | `apps/worker/src/geracao.rs:130-160`; testes MAN-05/07 | ✅ |
| 5. órfão = fora do manifest novo **e** do anterior | `apps/worker/src/geracao.rs:162-174` | ✅ |
| 6. orçamento antes de qualquer gravação | `apps/worker/src/geracao.rs:108-126` (tudo comprimido e checado via `checar_orcamento` antes do 1º `gravar`) | ✅ |
| 8. exclusivos; `--saida` obrigatório; `bail!` antigo removido | `apps/worker/src/main.rs:20-30` (`ArgGroup` + `requires`) | ✅ |
| 9. sem `unwrap` fora de teste | `grep unwrap()/expect(/panic!` em `src/{publicador,chunks,geracao,main}.rs`: 0 ocorrências (`unwrap_or`/`unwrap_or_else` apenas) | ✅ |
| 9. `tracing` INFO resumo / DEBUG por chunk | `apps/worker/src/geracao.rs:176` (`info!` resumo), `:133`, `:137`, `:172` (`debug!` por chunk) | ✅ (sem teste; não é AC) |
| 9. erros com `thiserror` na lib | `ErroPublicador` (`publicador.rs:9`), `ErroChunk` (`chunks.rs:10`), `ErroGeracao` (`geracao.rs:23`); `anyhow` só em `main.rs` | ✅ |
| 10. dependências | `brotli`, `sha2`, `hex` (permitidas); `jsonschema` dev-only sem default-features, justificado no spec | ✅ |

**SPEC_DEVIATIONs registrados**: `apps/worker/src/chunks.rs:37` (`serializar_chunk` → `Result`) e `:46` (`comprimir_br` → `Result`). Ambos justificados pela regra 9 e também na tabela de Assumptions do spec. Aceitos.

---

## Discrimination Sensor

Scratch: `git worktree add --detach <scratchpad>/verif HEAD`, um mutante por vez, `cargo test --no-fail-fast` (suíte inteira), restauração do arquivo depois de cada um. Worktree removido com `git worktree remove --force`; `git status --porcelain` do tree real vazio antes e depois (baseline igual). Suíte re-executada no tree real depois: 75/75.

| Mutation | File:line | Description | Killed? |
| -------- | --------- | ----------- | ------- |
| M01 | `apps/worker/src/chunks.rs:27` | partição `(id + 1) / 1000` (off-by-one) | ✅ Killed (`particao_por_faixa_de_mil`) |
| M02 | `apps/worker/src/chunks.rs:31` | remove `sort_by_key(id)` | ✅ Killed (`chunk_ordenado_por_id`, `particao_por_faixa_de_mil`, `manifest_chunks_com_ids_reais…`) |
| M03 | `apps/worker/src/geracao.rs:122` | hash sobre os bytes comprimidos | ✅ Killed (`fixture_vira_um_chunk_com_hash_deterministico`) |
| M04 | `apps/worker/src/geracao.rs:116` | `bytes` = tamanho do JSON cru | ✅ Killed (`manifest_chunks_com_ids_reais_e_bytes_comprimidos`, `trinta_mil…`) |
| M05 | `apps/worker/src/geracao.rs:104` | `areas` conta expirados | ✅ Killed (`areas_contam_so_ativas_e_total_conta_todas`) |
| M06 | `apps/worker/src/geracao.rs:130` | grava `manifest.json` antes dos chunks | ✅ Killed (`falha_em_chunk_nao_grava_manifest`, `segunda_execucao…`, `mudanca_no_chunk_5…`) |
| M07 | `apps/worker/src/geracao.rs:131` | não pula chunk existente | ✅ Killed (`segunda_execucao…`, `mudanca_no_chunk_5…`) |
| M08 | `apps/worker/src/geracao.rs:165` | órfãos ignoram o manifest anterior | ✅ Killed (`mudanca_no_chunk_5…`) |
| M09 | `apps/worker/src/geracao.rs:117` | orçamento `>` → `>=` | ❌ Survived |
| M10 | `apps/worker/src/geracao.rs:117` | verificação de orçamento desativada | ✅ Killed (`chunk_acima_do_orcamento_falha_sem_gravar_nada`) |
| M11 | `apps/worker/src/geracao.rs:158` | não grava `manifest.prev.json` | ✅ Killed (`manifest_prev_e_copia_do_anterior` + 2) |
| M12 | `apps/worker/src/geracao.rs:151` | `total_ofertas` = só ativos | ✅ Killed (`areas_contam_so_ativas_e_total_conta_todas`) |
| M13 | `apps/worker/src/geracao.rs:123` | `ids = [min, min]` | ✅ Killed (`manifest_chunks_com_ids_reais…`, `expurgo_muda_hash…`) |
| M14 | `apps/worker/src/publicador.rs:129` | `listar` devolve sidecars | ✅ Killed (`local_cumpre_o_contrato`, `gerar_fake_cria_arvore…`) |
| M15 | `apps/worker/src/publicador.rs:115` | `remover` não apaga o sidecar | ✅ Killed (`local_remover_apaga_o_sidecar`) |
| M16 | `apps/worker/src/main.rs:20` | `ArgGroup` com `multiple(true)` (`--gerar` + `--dry-run` aceitos) | ✅ Killed (`gerar_e_dry_run_juntos_saem_com_erro`) |
| M17 | `apps/worker/src/main.rs:26` | remove `requires = "saida"` | ✅ Killed (`gerar_sem_saida_sai_com_erro`) |
| M18 | `apps/worker/src/geracao.rs:169` | órfãos nunca removidos | ✅ Killed (`mudanca_no_chunk_5…`) |

**Sensor depth**: expandido (integridade de dados publicados: ≥ 5 mutações cobrindo todos os ramos novos)
**Result (iteração 0)**: 17/18 killed - FAIL ❌ (M09 sobreviveu)

### Iteração 1 (re-verificação, HEAD `b25f5b4`)

Scratch: `git worktree add --detach <scratchpad>/verif2 HEAD`; mutações aplicadas em modo binário (CRLF preservado), uma por vez, `cargo test --no-fail-fast` (suíte inteira) com `CARGO_TARGET_DIR` separado no scratchpad (caminho 8.3 curto, por causa do limite de 260 chars do `link.exe`); arquivo restaurado byte a byte no fim. M00 = baseline sem mutação (verde). Worktree removido com `git worktree remove --force`; `git status --porcelain` do tree real = só `?? .specs/features/BSV-11/validation.md`.

| Mutation | File:line | Description | Killed? |
| -------- | --------- | ----------- | ------- |
| M00 | — | baseline, sem mutação | (verde, 0 falhas) |
| M19 (= M09) | `apps/worker/src/geracao.rs:191` | orçamento `>` → `>=` em `checar_orcamento` | ✅ Killed (`orcamento_aceita_61440_e_recusa_61441`) |
| M20 | `apps/worker/src/geracao.rs:117` | `gerar` deixa de chamar `checar_orcamento` | ✅ Killed (`chunk_acima_do_orcamento_falha_sem_gravar_nada`) |
| M21 | `apps/worker/src/geracao.rs:192` | erro com `n: 0` fixo em vez do `n` real | ✅ Killed (`orcamento_aceita_61440_e_recusa_61441`) |
| M22 | `apps/worker/src/geracao.rs:142` | `maior_chunk` com `min_by_key` | ✅ Killed (`relatorio_com_contagens`) |
| M23 | `apps/worker/src/geracao.rs:84` | manifest anterior ilegível vira `None` (`.unwrap_or(None)`) em vez de erro | ✅ Killed (`manifest_anterior_invalido_falha_sem_gravar`, `manifest_anterior_json_sem_forma_de_manifest_falha_sem_gravar`) |

**Result**: 5/5 killed na iteração 1; acumulado: 22 mutantes distintos, todos mortos (M09 re-testado como M19) - PASS ✅

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code | ✅ (`PublicadorMemoria::gravacoes` é extra ao spec, mas é o que permite testar MAN-05/CIC-01) |
| Surgical changes | ✅ (só `apps/worker/` e `.specs/features/BSV-11/`) |
| No scope creep | ✅ (sem S3, HTML, imagens, busca) |
| Matches patterns | ✅ (mesmo estilo de BSV-10: `thiserror`, fixtures do contrato, relatório `chave: valor`) |
| Spec-anchored outcome check | ✅ (valores literais: hash, versao, gerado_em, areas, total, ids) |
| Per-layer Coverage Expectation | ✅ domínio 1:1; binário cobre happy + 2 erros |
| Every test maps to a spec requirement | ✅ (`fonte_vazia_gera_manifest_vazio` e `manifest_anterior_invalido_falha_sem_gravar` = edge cases) |
| Documented guidelines followed: `CLAUDE.md`, `docs/specs/BSV-11.md` regras 1-10 | ✅ |

---

## Edge Cases

- [x] Fonte sem oferta válida → `chunks: []`, `total_ofertas: 0`, `areas: {}` - `apps/worker/tests/geracao.rs:234-236`
- [x] Área só com expiradas → ausente de `areas`, card no chunk com `x:1` - `apps/worker/tests/geracao.rs:122` (PETS ausente) + `:86` (`qtd == 3` no chunk 5) + CHK-03 (fixture com `x:1`)
- [x] Chunk já existe → reaproveitado, não regravado - `apps/worker/tests/ciclo.rs:55-56`
- [x] `manifest.json` anterior inválido → `ManifestAnteriorInvalido`, nada gravado - JSON quebrado: `apps/worker/tests/ciclo.rs:155-159`; JSON válido fora do shape de `Manifest` (`{"versao":1}`): `apps/worker/tests/ciclo.rs:186-200` - `matches!(erro, ErroGeracao::ManifestAnteriorInvalido(_))` (`:197`), `gravacoes() == ["manifest.json"]` (`:200`, só a gravação do setup)

---

## Gate Check

- **Gate command**: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` (em `apps/worker`)
- **Result**: exit 0; 77 passed, 0 failed, 0 skipped (re-verificação, HEAD `b25f5b4`; fmt e clippy limpos)
- **Test count before feature** (`7485eba`): 47
- **Test count after feature**: 77
- **Delta**: +30 (publicador 5, chunks 4, geracao 11, ciclo 7, dry_run +3)
- **Skipped tests**: nenhum
- **Failures**: nenhuma

---

## Fix Plans

> Status: Fix 1 e Fix 2 aplicados em `b25f5b4` e verificados na iteração 1 (M19 morto; teste novo em `ciclo.rs:186`). Mantidos abaixo como histórico.

### Fix 1: limite do orçamento não discriminado (M09)

- **Root cause**: o único teste de MAN-06 usa um chunk muito acima de 61 440 B; nenhum teste fixa que exatamente 61 440 B é aceito ("mais de 61 440" no spec, `bytes.maximum: 61440` no schema).
- **Fix task**: extrair a checagem para uma função pública pura em `apps/worker/src/geracao.rs`, p.ex. `pub fn checar_orcamento(n: u64, bytes: u64) -> Result<()>`, usada em `gerar`; em `apps/worker/tests/geracao.rs` afirmar `checar_orcamento(0, 61_440).is_ok()` e `matches!(checar_orcamento(0, 61_441), Err(ChunkAcimaDoOrcamento { n: 0, bytes: 61_441 }))`.
- **Verify**: re-rodar o mutante `>` → `>=` e confirmar que morre.
- **Priority**: Minor

### Fix 2 (opcional, recomendado): manifest anterior com JSON válido fora do shape

- **Root cause**: `ciclo.rs:150` usa `{nao e json`; o spec diz "não é um `Manifest` válido". O caminho `serde_json::from_slice::<Manifest>` cobre os dois casos, mas só o sintático é provado.
- **Fix task**: acrescentar um caso com `b"{\"versao\":1}"` no mesmo teste, esperando `ManifestAnteriorInvalido` e `gravacoes() == ["manifest.json"]`.
- **Priority**: Minor

---

## Spec-precision gaps

- Nenhum AC com resultado indefinido. Observações: `total_ofertas` e o conjunto de chaves de `areas` foram decididos na tabela de Assumptions (não confirmados, `n`); os testes seguem essas decisões. O critério "relatório coerente com o `--dry-run`" contra o Oracle real depende do dono.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| PUB-01..05 | Implemented | ✅ Verified |
| CHK-01..05 | Implemented | ✅ Verified |
| MAN-01..05, MAN-07, MAN-08 | Implemented | ✅ Verified |
| MAN-06 | Implemented | ✅ Verified (limite 61 440/61 441 testado, iteração 1) |
| CIC-01..06 | Implemented | ✅ Verified |
| CLI-01..03 | Implemented | ✅ Verified |

---

## Summary

**Overall**: ✅ PASS

**Spec-anchored check**: 27/27 ACs com evidência; 0 spec-precision gaps
**Sensor**: iteração 0 17/18; iteração 1 5/5 (inclui o antigo sobrevivente M09) → 0 sobreviventes
**Gate**: 77 passed, 0 failed

**What works**: Publicador local/memória, partição/hash/Brotli com hash literal da fixture, manifest válido contra schema, ordem de escrita, reaproveitamento, órfãos com 1 ciclo de proteção, `manifest.prev.json`, orçamento pré-gravação, CLI exclusiva, 30k cards em < 3 s.

**Issues found**: nenhuma em aberto (M09 e o caso de manifest anterior fora do shape foram fechados em `b25f5b4`).

**Next steps**: dono roda `--gerar` contra o Oracle e cola o relatório no PR (itens ⏭️ acima).
