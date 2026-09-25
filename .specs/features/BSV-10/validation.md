# BSV-10 Validation

**Verdict**: PASS ✅ (fix iteration 1 of 3: 18/18 ACs covered, 18/18 mutants killed, gate green)

**Date**: 2026-09-25
**Spec**: `.specs/features/BSV-10/spec.md` + `docs/specs/BSV-10.md`
**Diff range**: `bd160b4..HEAD` (8 commits, `97d452c`..`7742587`; files only under `apps/worker/` and `.specs/features/BSV-10/`). `7742587` changes only `apps/worker/tests/pagina.rs` (+32 lines); `apps/worker/src/` is identical to `c3d044d`.
**Verifier**: independent sub-agent (author ≠ verifier)

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 modelo serde | ✅ Done | `97d452c` |
| T2 mapeamento | ✅ Done | `347ee83` |
| T3 para_card | ✅ Done | `dbe7abd` |
| T4 para_pagina | ✅ Done | `ad4286e` |
| T5 FakeFonte | ✅ Done | `198b0a9` |
| T6 OracleFonte | ✅ Done | `cf5e03a` |
| T7 dry-run + README | ✅ Done | `c3d044d` |
| Fix 1 + Fix 2 (tests) | ✅ Done | `7742587` |

---

## Spec-Anchored Acceptance Criteria

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| CONV-01 sinônimo → enum após normalizar | `MERCADOLIVRE` → `MERCADO_LIVRE`; `Família & filhos` → `FAMILIA` | `apps/worker/tests/mapeamento.rs:22` - `assert_eq!(m.loja("MERCADOLIVRE"), Some(Loja::MercadoLivre))`; `:31` - `m.area("Família & filhos") == Some(Area::Familia)`; `:14` - `normalizar("  Família   &  filhos ") == "FAMILIA & FILHOS"`; `apps/worker/tests/card.rs:101` - `c.loja == Loja::MercadoLivre` (via `para_card`) | ✅ PASS |
| CONV-02 l/a/p sem mapeamento | `LojaSemMapeamento` / `AreaSemMapeamento` / `PublicoSemMapeamento` | `apps/worker/tests/card.rs:140`, `:145` - `Err(Rejeicao::LojaSemMapeamento)`; `:154` - `Err(Rejeicao::AreaSemMapeamento)`; `:163` - `Err(Rejeicao::PublicoSemMapeamento)` | ✅ PASS |
| CONV-03 pp nulo ou ≤ 0 | `PrecoPorInvalido` | `apps/worker/tests/card.rs:109-116` - `None, 0.0, -5.0, 0.004` → `Err(Rejeicao::PrecoPorInvalido)` | ✅ PASS |
| CONV-04 título vazio após trim | `TituloVazio` | `apps/worker/tests/card.rs:125-130` - `None`, `"   "` → `Err(Rejeicao::TituloVazio)` | ✅ PASS |
| CONV-05 DT_OFERTA nula | `DataNula` | `apps/worker/tests/card.rs:172` - `Err(Rejeicao::DataNula)` | ✅ PASS |
| CONV-06 pd ≤ pp | `pd: null`, sem rejeitar | `apps/worker/tests/card.rs:184-185` - `c.preco_de == None` e JSON contém `"pd":null` para pd = pp e pd < pp; `:191` - pd > pp mantém `Some(8991)` | ✅ PASS |
| CONV-07 título > 200 | card: 197 cortado na última fronteira + `…`; página integral | `apps/worker/tests/card.rs:203` - `t == format!("{}…", "abcdefghi ".repeat(19).trim_end())`; `:214` - sem espaço `"á"*197 + "…"`; `:225` - 200 chars inalterado; `apps/worker/tests/pagina.rs:69` - `para_pagina(..).titulo == longo` | ✅ PASS |
| CONV-08 centavos half up | `19.995` → `2000` | `apps/worker/tests/card.rs:230` - `assert_eq!(centavos(19.995), 2000)` (+ `19.994`→1999, `0.005`→1) | ✅ PASS |
| CONV-09 ST_ATIVO 0/1 | inativa: `x:1`, `ENCERRADA`; ativa: sem `x`, `ATIVA` | `apps/worker/tests/card.rs:245-246` - `c.x == Some(1)`, JSON termina em `,"x":1}`; `:249-250` - `x == None`, JSON sem `"x"`; `apps/worker/tests/pagina.rs:81-89` - `Status::Encerrada` / `"status":"ENCERRADA"` / `Status::Ativa` | ✅ PASS |
| CONV-10 linhas equivalentes às fixtures | JSON compacto idêntico byte a byte a `chunk-ok.json` e `oferta-pagina-ok.json` | `apps/worker/tests/card.rs:74-77` - `to_string(&cards) == compactar(fixture("chunk-ok.json"))`; `apps/worker/tests/pagina.rs:55-58` - `to_string(&p) == compactar(fixture("oferta-pagina-ok.json"))` | ✅ PASS |
| CONV-11 orçamento de bytes | cada card ≤ 220 B; média das 3 ≤ 160 B | `apps/worker/tests/card.rs:92` - `*t <= 220`; `:95` - `media <= 160.0` | ✅ PASS |
| CONV-12 round-trip das fixtures | chunk/página/manifest reserializados idênticos | `apps/worker/tests/modelo.rs:13`, `:20`, `:27` - `to_string(..) == compactar(&txt)` | ✅ PASS |
| FONTE-01 filtro de expurgo na fake | 8 dias fora; 6 dias sai; ativa sai; limite 7 dias inclusivo | `apps/worker/tests/fonte.rs:36` - `ids == vec![1, 3, 4, 6]` (2 = 8 dias fora, 3 = 6 dias, 4 = exatamente 7 dias, 5 = inativa sem data fora) | ✅ PASS |
| FONTE-02 produto(id) | produto ou `None` | `apps/worker/tests/fonte.rs:47-48` - `Some(p)` / `None` | ✅ PASS |
| FONTE-03 credenciais só por env + filtro no SQL | lê só `BESAVE_ORACLE_DSN/USER/PASS`; SQL `ST_ATIVO = 1 OR DT_DESATIVACAO >= SYSDATE - 7` | `apps/worker/tests/oracle.rs:55-57` - lê as 3 variáveis, fuso padrão `-03:00`; SQL por inspeção estática `apps/worker/src/oracle.rs:76` (não executável sem Oracle, conforme spec: "só compila no CI e roda com o dono") | ✅ PASS (SQL: evidência estática) |
| FONTE-04 variável ausente | erro nomeando a variável, sem panic | `apps/worker/tests/oracle.rs:35` - `ConfigAusente(v)` com `v == faltando` para cada uma das 3; `:46-49` vazia = ausente; `apps/worker/tests/dry_run.rs:71-72` - binário sai ≠ 0, ≠ 101, stderr contém `BESAVE_ORACLE_DSN` | ✅ PASS |
| DRY-01 `--dry-run` com fake | imprime `lidas`, `validas`, uma linha por motivo; exit 0 | `apps/worker/tests/dry_run.rs:26-46` - `status.success()`, `lidas: 10`, `validas: 3`, `rejeitadas: 7`, `"  {r}: 1"` para os 7 motivos; execução manual confirmada (saída abaixo) | ✅ PASS |
| DRY-02 rejeição logada e segue | `id` + motivo via `tracing`, sem panic | `apps/worker/tests/dry_run.rs:55` - stderr contém `id=1003 motivo=loja sem mapeamento`; continuidade provada por `validas: 3` após rejeições | ✅ PASS |

### Ticket "Critério de aceite" (docs/specs/BSV-10.md)

| Item | Evidence | Result |
| ---- | -------- | ------ |
| `cargo test` sem Oracle | 42 testes verdes; nenhum teste abre conexão (`tests/oracle.rs` só testa `ConfigOracle::de`) | ✅ |
| Cada motivo de rejeição | `card.rs:116,130,140,154,163,172`; `pagina.rs:119` (`IdProdutoAusente`) | ✅ |
| `pd ≤ pp` | `card.rs:184` | ✅ |
| Truncamento de título | `card.rs:203,214` | ✅ |
| Inativa há 8 dias não sai da fake | `fonte.rs:36` (id 2 ausente) | ✅ |
| `centavos(19.995) == 2000` | `card.rs:230` | ✅ |
| `MERCADOLIVRE` → `MERCADO_LIVRE` | `mapeamento.rs:22`, `card.rs:101` | ✅ |
| `ST_ATIVO = 0` → `x`/`ENCERRADA` | `card.rs:245`, `pagina.rs:81` | ✅ |
| Card ≤ 220 B, média ≤ 160 | `card.rs:92,95` | ✅ |
| clippy limpo | gate abaixo | ✅ |
| `BESAVE_FONTE=fake cargo run -- --dry-run` imprime relatório | execução manual: `lidas: 10 / validas: 3 / rejeitadas: 7` + 7 linhas por motivo, exit 0 | ✅ |
| Oracle real | fora do alcance do Verifier (dono roda) | ⏭️ |

**Status**: ✅ All ACs covered. No spec-precision gap in the numbered ACs.

Observações de precisão (não bloqueiam):
- CONV-07: `truncar` (`apps/worker/src/conversao.rs:230-240`) sempre corta no último espaço dentro dos 197 primeiros caracteres, mesmo quando o 198º é espaço (palavra inteira cabia). Conforme a Assumption "corta no último espaço"; aceitável.
- Edge "cupom só espaços → `cupom: null`" tem assert direto só no card (`card.rs:260`); na página o valor vem de `card.cupom` (`conversao.rs:138`), e o mutante M14 prova que o fixture da página pega desvio.

---

## Discrimination Sensor

Scratch: `git worktree add --detach <scratchpad>/verif-wt HEAD`, uma mutação por vez, `cargo test -q`, restauração por `git checkout -- <file>`; worktree removida ao fim. Porcelain do tree real: vazio antes e depois.

| # | File:line | Mutation | Killed? |
| - | --------- | -------- | ------- |
| M1 | `apps/worker/src/conversao.rs:101` | `pd > pp` → `pd >= pp` | ✅ Killed (`preco_de_menor_ou_igual_vira_null_sem_rejeitar`) |
| M2 | `apps/worker/src/conversao.rs:225` | remove dígito half-up `+ (d3 >= 5)` | ✅ Killed (`centavos_half_up`) |
| M3 | `apps/worker/src/conversao.rs:234` | `max - 3` → `max - 2` | ✅ Killed (`titulo_longo_sem_espaco_corta_seco_em_197`) |
| M4 | `apps/worker/src/fonte.rs:48` | expurgo `d >= limite` → `d > limite` | ✅ Killed (`expurgo_de_7_dias`) |
| M5 | `apps/worker/src/conversao.rs:107` | `x` invertido (ativa recebe `x:1`) | ✅ Killed (fixture chunk + `inativa_tem_x_1_e_ativa_nao_tem_x`) |
| M6 | `apps/worker/src/mapeamento.rs:71` | normalização sem remover acento | ✅ Killed (3 testes de mapeamento) |
| M7 | `apps/worker/src/conversao.rs:91` | área sem mapeamento → `PublicoSemMapeamento` | ✅ Killed (`rejeita_area_sem_mapeamento`) |
| M8 | `apps/worker/src/conversao.rs:147` | `status` invertido | ✅ Killed (fixture página + `inativa_encerrada_ativa_ativa`) |
| M9 | `apps/worker/src/fonte.rs:48` | fake ignora `ST_ATIVO = 1` | ✅ Killed (`expurgo_de_7_dias`, dry-run) |
| M10 | `apps/worker/src/oracle.rs:29` | variável vazia aceita | ✅ Killed (`variavel_vazia_conta_como_ausente`) |
| M11 | `apps/worker/src/main.rs:65` | remove `warn!` da rejeição | ✅ Killed (`rejeicao_e_logada_com_id_e_motivo`) |
| M12 | `apps/worker/src/conversao.rs:158` | `desconto_pct` floor em vez de half up | ❌ Survived (iteração 0) → ✅ Killed (iteração 1: `desconto_pct_meia_para_cima_limitado_a_99`) |
| M13 | `apps/worker/src/conversao.rs:142` | `nota` sem arredondar a 1 casa | ❌ Survived (iteração 0) → ✅ Killed (iteração 1: `nota_uma_casa_e_fora_de_0_a_5_vira_null`) |
| M14 | `apps/worker/src/conversao.rs:138` | página usa `DS_CUPOM` cru (sem trim/maiúsculas) | ✅ Killed (fixture página) |
| M15 | `apps/worker/src/conversao.rs:81` | `pp > 0` → `pp >= 0` | ✅ Killed (`rejeita_preco_por_ausente_zero_ou_negativo`) |
| M16 | `apps/worker/src/conversao.rs:159` | `.clamp(0, 99)` removido | ✅ Killed (iteração 1: `desconto_pct_meia_para_cima_limitado_a_99`) |
| M17 | `apps/worker/src/conversao.rs:159` | `.clamp(0, 99)` → `.clamp(0, 100)` | ✅ Killed (iteração 1: `desconto_pct_meia_para_cima_limitado_a_99`) |
| M18 | `apps/worker/src/conversao.rs:141` | `nota` sem filtro de faixa 0..5 | ✅ Killed (iteração 1: `nota_uma_casa_e_fora_de_0_a_5_vira_null`) |

**Sensor depth**: expanded (18 manual mutations; conversão é caminho de integridade de dados)
**Result**: iteração 0: 13/15 killed. Iteração 1 (fresh worktree at `7742587`, M12, M13, M16, M17 and M18 re-injected): 5/5 killed. Total 18/18 killed - PASS ✅. Porcelain do tree real igual ao baseline (`?? .specs/features/BSV-10/validation.md`) antes e depois.

Na iteração 0, os dois sobreviventes cobriam regras do CONTRATO §4.1 (`desconto_pct = round((1 - por/de)*100)`; `nota` com 1 casa decimal) e da tabela de Assumptions da spec. O fixture da página usa 29990/19990 (33,34 %) e nota 4.6, valores em que floor e round coincidem e que já têm 1 casa, então nenhum teste discriminava. O commit `7742587` fecha os dois (ver Fix Plans).

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code | ✅ |
| Surgical changes (só `apps/worker/` e `.specs/features/BSV-10/`) | ✅ |
| No scope creep (sem chunks/S3/HTML; só `--dry-run`) | ✅ |
| Matches patterns (`thiserror` na lib: `Rejeicao`, `ErroFonte`, `ErroMapeamento`; `anyhow` no bin; `tracing` + `EnvFilter` por `RUST_LOG`) | ✅ |
| Sem `unwrap`/`expect`/`panic!` em `apps/worker/src/` (grep vazio) | ✅ |
| Deps = lista do ticket (`anyhow, clap, oracle, serde, serde_json, thiserror, tracing, tracing-subscriber, unicode-normalization`), `unicode-normalization` usada em `mapeamento.rs:8` | ✅ |
| Credenciais só por env (`oracle.rs:26-40`); `ConfigOracle` sem `Debug`; `.env` no `.gitignore` | ✅ |
| README da crate (fake + Oracle, Instant Client ≥ 19) | ✅ |
| Spec-anchored outcome check | ✅ |
| Per-layer coverage (domínio 1:1 com CONV; fake; config Oracle; binário via processo) | ✅ |
| Every test maps to a requirement (`data_iso_8601_utc` → Assumption de datas/§1.4; `id_produto_ausente` → Assumption `IdProdutoAusente`) | ✅ |
| Guidelines: `CLAUDE.md`, `docs/specs/BSV-10.md` Regras 1–7 | ✅ |
| Discrimination sensor | ✅ 18/18 killed |

---

## Edge Cases

- [x] Título > 200 sem espaço → corte seco em 197 + `…` (`card.rs:214`)
- [x] `pd` nulo → card `pd: null` (fixture 5413, `card.rs:74`) e página `desconto_pct: null` (`pagina.rs:101`)
- [x] Cupom só espaços → `c` ausente (`card.rs:260-261`); `cupom: null` na página por derivação (`conversao.rs:138`, M14)
- [x] `ST_ATIVO = 0` e `DT_DESATIVACAO` nula → fora da fake (`fonte.rs:30,36`, id 5)

---

## Gate Check

- **Gate command** (em `apps/worker`): `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`
- **Result**: fmt OK; clippy OK (0 warnings); **42 passed, 0 failed, 0 skipped** (card 17, dry_run 4, fonte 2, mapeamento 5, modelo 3, oracle 3, pagina 8), re-run at `7742587`
- **Test count before feature**: 0 (crate não existia em `bd160b4`)
- **Test count after feature**: 42
- **Delta**: +42
- **Skipped tests**: none
- **Failures**: none

Dry-run manual (`BESAVE_FONTE=fake cargo run -q -- --dry-run`, exit 0):
```
lidas: 10
validas: 3
rejeitadas: 7
  preco_por ausente ou <= 0: 1
  titulo vazio: 1
  loja sem mapeamento: 1
  area sem mapeamento: 1
  publico sem mapeamento: 1
  dt_oferta nula: 1
  id_produto ausente: 1
```

---

## Fix Plans

### Fix 1: `desconto_pct` half up não é discriminado (M12) — ✅ Resolved in `7742587`

- **Root cause**: nenhum teste usa um par `pd/pp` cuja fração seja ≥ .5 (fixture dá 33,34 %).
- **Fix task**: em `apps/worker/tests/pagina.rs`, teste `desconto_pct_arredonda_meia_para_cima`: `preco_de 100.00, preco_por 66.50` → `desconto_pct == Some(34)` (33,5 → 34); e `preco_de 100.00, preco_por 0.01` → `Some(99)` (limite do schema, 99,99 → 100 → clamp 99).
- **Verify**: re-injetar M12 (`(100 * (pd - pp)) / pd`) e confirmar que o teste falha.
- **Priority**: Minor
- **Evidence**: `apps/worker/tests/pagina.rs:133` - `pct(100.00, 66.50) == Some(34)`; `:134` - `pct(100.00, 66.51) == Some(33)`; `:135` - `pct(100.00, 0.01) == Some(99)`

### Fix 2: `nota` com 1 casa decimal não é discriminada (M13) — ✅ Resolved in `7742587`

- **Root cause**: fixture usa `4.6`, já com 1 casa; não há teste de nota fora de 0..5 nem com 2+ casas.
- **Fix task**: em `apps/worker/tests/pagina.rs`, teste `nota_uma_casa_e_faixa`: `nota 4.66` → `Some(4.7)`; `nota 5.5` → `None`; `nota -1.0` → `None`.
- **Verify**: re-injetar M13 (`.map(|n| n)`) e confirmar que o teste falha.
- **Priority**: Minor
- **Evidence**: `apps/worker/tests/pagina.rs:148` - `nota(4.66) == Some(4.7)`; `:149` - `nota(4.64) == Some(4.6)`; `:150` - `nota(5.5) == None`; `:151` - `nota(-1.0) == None`

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| CONV-01..CONV-12 | Implemented | ✅ Verified |
| FONTE-01, FONTE-02, FONTE-04 | Implemented | ✅ Verified |
| FONTE-03 | Implemented | ✅ Verified (config por teste; SQL por inspeção) |
| DRY-01, DRY-02 | Implemented | ✅ Verified |
| Assumption `desconto_pct` half up + clamp 0..99 | ❌ Needs test | ✅ Verified (`pagina.rs:133-135`) |
| Assumption `nota` 1 casa / 0..5 | ❌ Needs test | ✅ Verified (`pagina.rs:148-151`) |

---

## Summary

**Overall**: ✅ Ready (PASS after fix iteration 1 of 3)

**Spec-anchored check**: 18/18 ACs matched spec outcome; 0 spec-precision gaps
**Sensor**: 18/18 mutations killed (M12/M13 survived in iteration 0 and are killed in iteration 1)
**Gate**: 42 passed, 0 failed; fmt and clippy clean

**What works**: conversão linha → card/página byte a byte com as fixtures; todos os motivos de rejeição; `pd ≤ pp`; truncamento; centavos half up; `desconto_pct` half up com teto 99; `nota` com 1 casa e faixa 0..5; expurgo de 7 dias na fake; config Oracle por env sem panic; dry-run com relatório e log por rejeição.

**Issues found**: none open. Observações não bloqueantes: CONV-07 com o 198º caractere espaço (ver acima); a execução do SQL de expurgo só tem evidência estática até o dono rodar contra o Oracle.

**Next steps**: dono roda `--dry-run` contra o Oracle real (critério de aceite fora do alcance do Verifier).
