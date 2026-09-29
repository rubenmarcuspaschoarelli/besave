# BSV-13 Validation (Iteration 4 — Owner-Authorized, Post-Redesign)

**Date**: 2026-09-26
**Spec**: `.specs/features/BSV-13/spec.md` (re-read fresh, including the amended PAR-01..03 and the
"Revisado pelo dono" Assumptions row)
**Diff range**: `60b0ab4..HEAD` (`apps/worker` only) — commits `3af767a..bbf4d33`
**Commits under fresh scrutiny this iteration**:
- `b9955f6` (`test(worker): assert maior_small/maior_grande track the max across ids`) — iteration
  3's fix, never independently re-verified until now.
- `bbf4d33` (`feat(worker): batch image publish, parallel on PublicadorS3`) — the owner-mandated
  parallelism redesign.
**Verifier**: independent sub-agent (author ≠ verifier), 4th fix→re-verify iteration, explicitly
authorized by the project owner beyond the skill's normal 3-iteration bound, specifically to cover
(a) the redesign and (b) the un-reverified iteration-3 fix. No prior report trusted; all evidence
re-collected from source and from fresh command runs.

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1: Area::Outros | ✅ Done | Re-confirmed unchanged since iter. 3 |
| T2: chaves/origem/assinatura | ✅ Done | Re-confirmed unchanged since iter. 3 |
| T3: cópia direta + falha não-webp | ✅ Done | Re-confirmed unchanged since iter. 3 |
| T4: recodificação + imagem grande | ✅ Done | Re-confirmed unchanged since iter. 3 |
| T5: reaproveitamento + placeholders | ✅ Done | Re-confirmed unchanged since iter. 3 |
| T6: integração em gerar() + expurgo | ✅ Done | Re-confirmed unchanged since iter. 3; `geracao.rs` verified **not** touched by `bbf4d33` |
| T7: paralelismo S3 (redesenhado) | ✅ Done, independently verified | `bbf4d33` redesign confirmed real: trait defaults, `PublicadorS3` overrides, `imagens.rs` batching in blocks of 64, old `publicar_imagens_paralelo`/`ResultadoImagem`/`publicar_imagem_paralela` machinery actually deleted |
| Fix round (iter. 3 → 4): `maior_small`/`maior_grande` multi-id `.max()` (`b9955f6`) | ✅ Done, verified true | Independently re-run the exact mutation that surfaced this gap in iteration 3 — confirmed killed (Sensor #1) |

---

## `geracao.rs` Untouched — Owner's Hard Constraint

Confirmed two independent ways:
1. `git show bbf4d33 --stat` (full command output below) lists exactly 7 changed files:
   `.specs/features/BSV-13/spec.md`, `.specs/features/BSV-13/tasks.md`, `apps/worker/README.md`,
   `apps/worker/src/aws.rs`, `apps/worker/src/imagens.rs`, `apps/worker/src/publicador.rs`,
   `apps/worker/tests/imagens.rs`. `apps/worker/src/geracao.rs` is **not** in this list.
2. Read `apps/worker/src/geracao.rs` in full (248 lines) at current `HEAD`: `gerar()` at
   `apps/worker/src/geracao.rs:79-222` still calls `imagens::publicar_imagens(&ids_publicaveis,
   dir_imagens, pub_)?` at line 124 exactly as before, unconditionally on the generic `pub_: &mut
   dyn Publicador` parameter — no branching on the concrete `Publicador` implementation, no new
   parameter, no signature change. The parallelism the owner asked for ("ligue o paralelismo sem
   mudar gerar()") is entirely a property of which concrete `Publicador` is passed in at the call
   site in `main.rs`, invisible to `gerar()` itself.

**Result**: ✅ Constraint held exactly as claimed.

---

## Spec-Anchored Acceptance Criteria

All 22 requirement IDs re-derived independently from the current `spec.md` and current
source/tests (file:line + assertion re-confirmed from source this iteration, not carried from the
prior report).

| Requirement | Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| ----------- | --------- | --------------------- | ------------------------ | ------ |
| AREA-01 | `Area::Outros` round-trips `"OUTROS"` | Exact string round-trip | `apps/worker/tests/modelo.rs:33-37` `area_outros_round_trip_serde` — `assert_eq!(json, "\"OUTROS\"")`; `assert_eq!(de, Area::Outros)` | ✅ PASS |
| AREA-02 | `DS_COMUNIDADE="Outros"` → `para_card` produces `a:"OUTROS"` | `area == Area::Outros`, `Ok(_)` | `apps/worker/tests/card.rs:153-158` `area_outros_nao_e_rejeitada` — `assert_eq!(para_card(&l, &m()).unwrap().area, Area::Outros)` | ✅ PASS |
| AREA-03 | ≥1 active `OUTROS` offer → `manifest.areas["OUTROS"]`=count; manifest schema-valid | Exact count + schema-valid | `apps/worker/tests/geracao.rs:159-171` `area_outros_conta_no_manifest_e_valida_contra_schema` — `assert_eq!(m.areas, BTreeMap::from([(Area::Outros, 1)]))` + `validar_schema(...)` (real `jsonschema` crate validation, confirmed by reading `tests/comum/mod.rs:49-75`, not a stub) | ✅ PASS |
| AREA-04 | `Mapeamento::carregar` loads without error | `Ok(_)` | `apps/worker/tests/mapeamento.rs:8-10` (`m()` helper via `.unwrap()`, used by every test in the file); full-suite green | ✅ PASS |
| CHV-01 | `chave_small`/`chave_grande` exact strings | `"img/ofertas/{id}-small.webp"` / `"img/ofertas/{id}.webp"` | `apps/worker/tests/imagens.rs:65-68` `chaves_do_bucket` | ✅ PASS |
| CHV-02 | `origem(dir,id)` exact tuple | `(dir/id/id-small.webp, dir/id/id.webp)` | `apps/worker/tests/imagens.rs:71-87` `origem_monta_os_dois_caminhos` | ✅ PASS |
| CPY-01 | In-budget fixture → identical bytes, Meta, `publicadas` counted | Exact bytes/Meta/count | `apps/worker/tests/imagens.rs:128-146` `copia_direta_dentro_do_orcamento` | ✅ PASS |
| CPY-02 | Non-WebP signature → `falhas` w/ `NaoWebp`, no key, loop continues | Exact `falhas` vec, no keys, next id processed | `apps/worker/tests/imagens.rs:150-166` `arquivo_nao_webp_vira_falha_e_o_loop_continua` — `assert_eq!(rel.falhas, vec![(5413, MotivoFalhaImagem::NaoWebp)])`; asserts id 5414 still published | ✅ PASS |
| ORC-01 | `ajustar_small` → ≤25600B, valid WebP, side ≤320px | Exact bounds | `apps/worker/tests/imagens.rs:168-185` `ajustar_small_cabe_no_orcamento_e_no_lado_maximo` | ✅ PASS |
| ORC-02 | Oversized small → `reprocessadas` counted; boundary exact | `reprocessadas==1`; 25600B does NOT reprocess, 25601B does | `apps/worker/tests/imagens.rs:188-206` + `:231-261` (exact-limit test) | ✅ PASS |
| ORC-03 | Grande >300000B unmodified + WARN; `maior_grande`=largest **across all published ids in the run** | Exact bytes, exact multi-id max | `apps/worker/tests/imagens.rs:287-300` `imagem_grande_acima_do_aviso_publica_sem_alteracao` (single-id case) **+ `apps/worker/tests/imagens.rs:208-229` `maior_small_e_maior_grande_refletem_o_maior_entre_varios_ids` (multi-id `.max()` case, id 9100 processed first with the larger value, id 9101 processed second with a smaller one — asserts the report does NOT regress to the last-processed id's smaller value)** | ✅ **PASS — gap closed, mutation-confirmed this iteration (Sensor #1)** |
| REU-01 | Both keys exist → skip, count; exactly one → NOT reaproveitada | Conjunction semantics | `apps/worker/tests/imagens.rs:302-322` + `:324-347` `apenas_uma_chave_existente_nao_e_reaproveitada` | ✅ PASS |
| REU-02 | Missing/partial source → `sem_origem`, no error, no write | Exact counts, no keys | `apps/worker/tests/imagens.rs:349-369` `sem_pasta_ou_com_um_so_arquivo_conta_sem_origem` | ✅ PASS |
| REU-03 | 10 placeholders published once via 1 batch call, reused after | 10 writes, then 0 more, via `existem`+`gravar_lote` | `apps/worker/tests/imagens.rs:371-391` `placeholders_publicados_uma_vez_e_reaproveitados_depois` — `assert_eq!(p.gravacoes().len(), gravacoes_1a_chamada)`; production code `apps/worker/src/imagens.rs:183-201` `publicar_placeholders` confirmed to call `existem`/`gravar_lote` exactly once each, not 10 unitary calls | ✅ PASS |
| REU-04 | 2nd identical run → `publicadas==0`, `reaproveitadas==N` | Exact counts | `apps/worker/tests/imagens.rs:393-409` `segunda_execucao_completa_nao_publica_nada_de_novo` | ✅ PASS |
| GER-01 | `publicar_imagens` runs before any chunk write | Image-write index < first-chunk-write index | `apps/worker/tests/geracao.rs:489-513` `imagens_publicadas_antes_de_qualquer_chunk` — `assert!(imagem < primeiro_chunk, ...)` | ✅ PASS |
| GER-02 | `Relatorio` carries all `RelatorioImagens` fields | Fields present and correct, incl. multi-id `bytes`/`maior_*` | `apps/worker/tests/geracao.rs:516-530` `relatorio_inclui_contagens_de_imagens` (integration) + field-level evidence in `apps/worker/tests/imagens.rs:141` (`bytes`), `:204-205` (`maior_small` single-id), `:221-228` (`maior_small`/`maior_grande` **multi-id max**, mutation-confirmed) | ✅ PASS |
| GER-03 | Id dropped from source → both image keys removed | Both keys absent after purge | `apps/worker/tests/geracao.rs:534-548` `expurgo_remove_as_duas_chaves_de_imagem` | ✅ PASS |
| GER-04 | `sem_origem` id still publishes card/page normally | No new rejection | `apps/worker/tests/geracao.rs:551-567` `sem_origem_de_imagem_nao_bloqueia_a_oferta` | ✅ PASS |
| PAR-01 | `existem`/`gravar_lote` default sequential in trait; `PublicadorS3` overrides both with ≤16-in-flight pool; `publicar_imagens` uses them in blocks of 64 — **without changing `gerar()`'s signature or body** | Exact mechanism, `gerar()` untouched | `apps/worker/src/publicador.rs:124-139` (trait defaults, loop via `existe`/`gravar`); `apps/worker/src/aws.rs:207-236` (`existem` override, `Semaphore::new(MAX_EM_VOO)` at `:218`, `JoinSet` pool) + `:238-262` (`gravar_lote` override, same pool); `MAX_EM_VOO = 16` at `:267`; `apps/worker/src/imagens.rs:203-223` (`TAMANHO_BLOCO = 64`, `publicar_imagens` chunks `ids` and calls `processar_bloco` per block); `git show bbf4d33 --stat` confirms `geracao.rs` absent from the changed-files list | ✅ **PASS — code review + mutation-confirmed (Sensors #3, #4, #5)** |
| PAR-02 | `PublicadorLocal`/`PublicadorMemoria` stay sequential, inheriting the trait default with no overrides | No pool in generic path | `apps/worker/src/publicador.rs:170-218` (`impl Publicador for PublicadorLocal`) and `:268-298` (`impl Publicador for PublicadorMemoria`) — neither `impl` block defines `existem` or `gravar_lote`, confirming both inherit the sequential trait default unchanged; `git diff bbf4d33^..bbf4d33` touches only the trait's default-method bodies, never these two `impl` blocks | ✅ PASS (code review, confirmed via diff + full-file read) |
| PAR-03 | 5000 ids ⇒ ≤80 `existem` calls and ≤80 `gravar_lote` calls against a spy, not 20 000 unitary calls | Exact ≤80/≤80 bound | `apps/worker/tests/imagens.rs:414-448` (`ContadorDeLotes` spy, counts batch-level calls only — verified below) + `:450-475` `cinco_mil_ids_usam_no_maximo_80_chamadas_em_lote` | ✅ **PASS — independently re-derived as an exact (not merely lenient) bound; see PAR-03 Deep-Dive below** |

**Status**: 22/22 requirements have `file:line` evidence matching the spec-defined outcome. 0
requirements structurally uncovered. 0 spec-precision gaps. The one gap that survived iteration 3
(`maior_small`/`maior_grande` multi-id semantics, tied to ORC-03/GER-02) is now closed and
independently mutation-confirmed.

---

## PAR-03 Deep-Dive (full independent evidence, per instructions)

**Spy correctness** — read `ContadorDeLotes` line by line (`apps/worker/tests/imagens.rs:414-448`):
it wraps a real `PublicadorMemoria` (`dentro`), delegates `existe`/`ler`/`gravar`/`remover`/`listar`
straight through, and overrides only `existem`/`gravar_lote` to increment a counter **once per
call** (`existem_chamadas.set(existem_chamadas.get() + 1)` at line 438; `gravar_lote_chamadas += 1`
at line 442) before doing the real work by iterating and calling the inner `PublicadorMemoria`'s
per-key methods. This counts **batches**, not keys or unitary `existe`/`gravar` calls — confirmed
by reading the increment sites directly, not inferred from the assertion.

**Math sanity check** — independently recomputed the expected call count rather than trusting
"≤80" as given:
- `publicar_imagens` always calls `publicar_placeholders` once first (`apps/worker/src/imagens.rs:217`),
  which does exactly 1 `existem` call (10 keys) and, on a fresh destination, exactly 1 `gravar_lote`
  call (all 10 missing) — `apps/worker/src/imagens.rs:190,197-199`.
- `ids.chunks(TAMANHO_BLOCO)` with `TAMANHO_BLOCO = 64` on 5000 ids yields `⌈5000/64⌉ = 79` blocks
  (78 full blocks of 64 = 4992, plus one final block of 8).
- Each block makes exactly 1 `existem` call (`apps/worker/src/imagens.rs:241`) and, since every id
  in the test has fresh valid origin (no reaproveitamento, no failures), exactly 1 `gravar_lote`
  call per block (`a_gravar` is never empty) — `apps/worker/src/imagens.rs:292-294`.
- **Exact expected total: 79 (blocks) + 1 (placeholders) = 80 for both `existem` and `gravar_lote`.**

This means the test's "≤80" bound is not a loosely generous ceiling — it is the *exact* value the
current block size produces. There is zero slack: the bound is tight to the actual algorithm, which
rules out the concern that the test would trivially "pass by coincidence" at some looser threshold.
The test passed with `rel.publicadas == 5000` confirmed in the same run (gate section below).

**Discriminates on block size** — confirmed by Sensor #2 below: shrinking `TAMANHO_BLOCO` to `1` in
an isolated scratch drove `existem_chamadas` to `5001`, and the test failed loudly. The test is a
real, block-size-sensitive gate, not an unconditionally-true assertion.

---

## Discrimination Sensor

**Isolation**: `git worktree add --detach C:\Users\Ruben\AppData\Local\Temp\bsv13-verify-iter4-scratch HEAD`
(`HEAD` = `bbf4d33`). Each mutation applied via `Edit` directly on the scratch copy, `cargo test`
run per mutation in the scratch, reverted before the next mutation, worktree removed with
`git worktree remove --force` when all 5 mutations were done. `git status --porcelain` on the real
worktree (`C:\Users\Ruben\orca\workspaces\besave\rub-9-bsv-13-worker-imagens-webp`) was **empty**
immediately before creating the scratch worktree and **empty** again immediately after its
removal — both checked directly, not assumed.

| # | File:line | Mutation | Tests run | Killed? |
| - | --------- | -------- | --------- | ------- |
| 1 (re-run of iteration 3's exact gap, this iteration's primary target) | `src/imagens.rs:286-287` | `rel.maior_small = rel.maior_small.max(bytes_s.len() as u64); rel.maior_grande = rel.maior_grande.max(bytes_g.len() as u64);` → plain overwrite (drop `.max()`) | `cargo test --test imagens` | ✅ **Killed** — `maior_small_e_maior_grande_refletem_o_maior_entre_varios_ids` failed: `assertion left == right failed: não pode regredir para o valor do último id processado — left: 1000, right: 3000` |
| 2 (fresh, targets PAR-03's own tightness) | `src/imagens.rs:206` | `const TAMANHO_BLOCO: usize = 64;` → `= 1;` | `cargo test --test imagens` | ✅ **Killed** — `cinco_mil_ids_usam_no_maximo_80_chamadas_em_lote` failed: `esperava <= 80 chamadas de existem (blocos de 64), teve 5001` |
| 3 (fresh, mandated sensor (a)) | `src/publicador.rs:128-130` | `existem` default `chaves.iter().map(\|c\| self.existe(c)).collect()` → `Ok(vec![true; chaves.len()])` | `cargo test --test imagens --test geracao` | ✅ **Killed** — 5 tests failed in `geracao.rs` (`expurgo_remove_as_duas_chaves_de_imagem`, `imagens_publicadas_antes_de_qualquer_chunk`, `relatorio_inclui_contagens_de_imagens`, `sem_origem_de_imagem_nao_bloqueia_a_oferta`, `relatorio_com_contagens`) — everything now "already exists," so nothing is ever published |
| 4 (fresh, mandated sensor (b) — re-run of an old-code mutation against the new location) | `src/imagens.rs:246` | `if existe_small[i] && existe_grande[i]` → `if existe_small[i] \|\| existe_grande[i]` | `cargo test --test imagens` | ✅ **Killed** — `apenas_uma_chave_existente_nao_e_reaproveitada` failed: `left: 1, right: 0` — confirms this exact conjunction mutation, killed in an earlier iteration against the pre-redesign code, is **still killed** after the logic moved into the new `processar_bloco` function |
| 5 (fresh, my choice — targets the redesign's new batch-write path directly) | `src/publicador.rs:134-138` | `gravar_lote` default: `for (chave, bytes, meta) in itens` → `for (chave, bytes, meta) in itens.iter().take(1)` (only the first item of any batch actually gets written) | `cargo test --test imagens --test geracao` | ✅ **Killed** — 2 tests failed in `geracao.rs` (`expurgo_remove_as_duas_chaves_de_imagem`: `assertion failed: p.existe("img/ofertas/5412.webp")` — the grande key silently never got written since it's the 2nd item of its pair in the batch; `falha_na_kvs_nao_grava_manifest`) |

**Sensor depth**: lightweight-plus (5 mutations: 1 re-run of iteration 3's un-reverified gap, 4
fresh — 2 explicitly requested by the caller's brief plus 1 requested-choice plus the PAR-03
tightness check)
**Result**: 5/5 killed, 0 survived — ✅ **PASS**

**Isolation verified**: `git worktree remove --force` succeeded cleanly; `git status --porcelain`
on the real worktree was empty both before the scratch worktree was created and after its removal.

---

## Payload/Conjunction Check (`RelatorioImagens`)

| Field | Asserted on value (not just presence)? | Evidence |
| ----- | ----------------------------------- | -------- |
| `publicadas` | ✅ Yes | Exact `u64` values throughout `tests/imagens.rs` and `tests/geracao.rs` |
| `reaproveitadas` | ✅ Yes | Including the "exactly one key" test asserting `0` |
| `sem_origem` | ✅ Yes | `tests/imagens.rs`, `tests/geracao.rs` |
| `reprocessadas` | ✅ Yes, boundary-discriminated | Exact-limit=0, limit+1=1 |
| `falhas` | ✅ Yes (full `Vec` content) | Exact `(id, NaoWebp)` tuples |
| `bytes` | ✅ Yes, nonzero computed value | `tests/imagens.rs:141` |
| `maior_small` | ✅ **Now asserted across multiple ids, max semantics** | `tests/imagens.rs:204-205` (single-id) + `:221-224` (multi-id max, mutation-confirmed Sensor #1) |
| `maior_grande` | ✅ **Now asserted across multiple ids, max semantics** | `tests/imagens.rs:299` (single-id) + `:225-228` (multi-id max, mutation-confirmed Sensor #1) |

**Result**: 8/8 fields hit the conjunction/value bar. The two previously-flagged fields
(`maior_small`/`maior_grande`) now have real multi-id, mutation-confirmed coverage.

---

## Edge Cases (spec.md)

- [x] `BESAVE_IMAGENS_DIR`/`--imagens-dir` absent → error naming the variable, no panic. `apps/worker/tests/dry_run.rs:154-169` `gerar_sem_imagens_dir_nomeia_a_variavel` — re-confirmed present, unchanged since iteration 3.
- [x] Small oversized + grande invalid (non-WebP) → id atomic, appears only in `falhas`. `apps/worker/tests/imagens.rs:263-285` `grande_invalida_marca_falha_mesmo_com_small_acima_do_orcamento` — re-confirmed.
- [x] Empty publishable-ids list → still publishes/reuses the 10 placeholders. `placeholders_publicados_uma_vez_e_reaproveitados_depois` calls `publicar_imagens(&[], ...)` — re-confirmed, and now this list also exercises the redesign's single batched `existem`/`gravar_lote` call for all 10 placeholders instead of 10 unitary pairs.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / surgical changes | ✅ — `bbf4d33` touches exactly the 7 files needed for the redesign (`aws.rs`, `imagens.rs`, `publicador.rs`, their tests, README, spec/tasks docs); `geracao.rs` untouched as required |
| No scope creep | ✅ — the redesign is a net simplification: it *removes* `publicar_imagens_paralelo`, `ResultadoImagem`, `publicar_imagem_paralela` (confirmed absent from current `aws.rs`) rather than adding surface area |
| Matches patterns | ✅ — trait-default pattern mirrors existing `Publicador` methods; `Semaphore`+`JoinSet` pool pattern reused verbatim from the pre-redesign code, now applied to 2 methods instead of 1 |
| No abstractions for single-use code | ✅ — `existem`/`gravar_lote` are used by every `Publicador` implementation, not single-use |
| Spec-anchored outcome check | ✅ — all 22 ACs verified against literal spec text, including the amended PAR-01..03 |
| Every test maps to a spec AC / edge case / Done-when | ✅ |
| Documented guidelines followed | `apps/worker/CLAUDE.md` (gate command, image-failure-never-blocks rule, no-`unwrap`-outside-tests) — followed; `cargo clippy --all-targets -- -D warnings` clean confirms no new lint debt from the async pool refactor |

---

## Gate Check

- **Gate command**: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` (run from `apps/worker/`, on the real, unmutated worktree)
- **Result**: fmt clean (exit 0), clippy clean with `-D warnings` (exit 0), tests: **135 passed, 0 failed, 2 ignored**
  - Breakdown: card 19, chunks 4, ciclo 8 (+1 ignored, `trinta_mil_cards_em_ate_30_segundos`), dry_run 12, fonte 2, geracao 20, headers 4, imagens 19 (+1 ignored, `cinco_mil_ids_em_ate_5_segundos`), mapeamento 5, modelo 4, oracle 9, pagina 9, plano 4, publicador 5, redirects 11, unittests (lib+bin) 0, doctests 0. Sum = 135 passed + 2 ignored = 137 total.
- **Test count before this iteration's changes** (iteration-3 baseline, per that report): 133 passed, 1 ignored (134 total)
- **Test count after** (`b9955f6` + `bbf4d33` combined): 135 passed, 2 ignored (137 total)
- **Delta**: **+3 tests** — `b9955f6` added `maior_small_e_maior_grande_refletem_o_maior_entre_varios_ids` (not ignored, +1 passed); `bbf4d33` added `cinco_mil_ids_usam_no_maximo_80_chamadas_em_lote` (not ignored, +1 passed) and `cinco_mil_ids_em_ate_5_segundos` (`#[ignore]`, +1 ignored). Reconciles exactly: 133+2=135 passed, 1+1=2 ignored.
- **Failures**: none
- **Ignored perf test** (`cargo test --test imagens -- --ignored`): `cinco_mil_ids_em_ate_5_segundos` — **passed** (internal assertion `tempo <= Duration::from_secs(5)` held). Harness-reported total wall time for the whole test (which includes writing 5000 id folders × 2 files = 10 000 fixture files to a temp dir **before** the timed section starts) varied 8.30s–17.82s across two consecutive runs on this machine — noise from disk I/O for fixture setup, not from the timed `publicar_imagens` call itself, and consistent with the test's own documented `#[ignore]` justification ("instável sob carga no CI, roda localmente"). The assertion itself passed both times.

---

## Fix Plans

None. No surviving mutants, no uncovered ACs, no spec-precision gaps.

---

## Requirement Traceability Update

| Requirement | Previous Status (iter. 3) | New Status (iter. 4) |
| ----------- | -------------------------- | ---------------------- |
| AREA-01..04 | ✅ Verified | ✅ Verified (re-confirmed, unchanged) |
| CHV-01, CHV-02 | ✅ Verified | ✅ Verified (re-confirmed, unchanged) |
| CPY-01, CPY-02 | ✅ Verified | ✅ Verified (re-confirmed, unchanged) |
| ORC-01 | ✅ Verified | ✅ Verified (re-confirmed, unchanged) |
| ORC-02 | ✅ Verified | ✅ Verified (re-confirmed, unchanged) |
| ORC-03 | ⚠️ Verified, sub-gap: multi-id `maior_grande` semantics unconfirmed | ✅ **Verified — gap closed, mutation-confirmed (Sensor #1)** |
| REU-01..04 | ✅ Verified | ✅ Verified (re-confirmed, unchanged) |
| GER-01 | ✅ Verified | ✅ Verified (re-confirmed, unchanged) |
| GER-02 | ⚠️ Verified, sub-gap: multi-id `maior_small`/`maior_grande` semantics unconfirmed | ✅ **Verified — gap closed, mutation-confirmed (Sensor #1)** |
| GER-03, GER-04 | ✅ Verified | ✅ Verified (re-confirmed, unchanged) |
| PAR-01 | ✅ Verified (code review, pre-redesign: exposed-not-wired) | ✅ **Verified — redesign confirmed wired into `--publicar`, `gerar()` untouched, code review + mutation-confirmed** |
| PAR-02 | ✅ Verified (code review) | ✅ Verified — confirmed `PublicadorLocal`/`PublicadorMemoria` still have no overrides |
| PAR-03 | (new requirement this iteration) | ✅ **Verified — spy correctness confirmed, exact-bound math independently recomputed (80 = 80, zero slack), block-size discrimination mutation-confirmed (Sensor #2)** |

---

## Summary

**Overall**: ✅ **Ready**

**Spec-anchored check**: 22/22 requirements have `file:line` evidence matching the spec-defined
outcome. 0 spec-precision gaps. 0 requirements structurally uncovered.
**Sensor**: 5/5 mutations killed, 0 survived.
**Gate**: 135 passed, 0 failed, 2 justified-ignored (fmt clean, clippy clean); ignored perf test
passes (internal 5s bound held; harness total 8.3–17.8s dominated by fixture-write I/O, not the
timed code path).

**What works**:
1. **`geracao.rs` is verified untouched** by the redesign commit, confirmed both via `git show
   bbf4d33 --stat` (absent from the 7 changed files) and by reading the full current file — `gerar()`
   still calls `imagens::publicar_imagens` on a generic `&mut dyn Publicador` with no branching,
   exactly the owner's "ligue o paralelismo sem mudar gerar()" requirement.
2. **The `maior_small`/`maior_grande` multi-id gap from iteration 3 is genuinely closed.**
   Independently re-running the exact mutation that surfaced it (`.max()` → plain overwrite) against
   the current code now fails `maior_small_e_maior_grande_refletem_o_maior_entre_varios_ids` — proof
   the fix discriminates, not just that a new assertion exists.
3. **PAR-03's "≤80" bound is a real, tight bound, not lenient coincidence.** Independent math
   (⌈5000/64⌉=79 blocks + 1 placeholder call = exactly 80) shows zero slack between the test's
   threshold and the algorithm's actual output; a `TAMANHO_BLOCO=1` mutation drove the real count to
   5001 and killed the test, confirming genuine block-size sensitivity.
4. **The redesign's new code is discriminated on 3 independent fronts**: the trait-default
   `existem` (mutated to always-true, killed 5 `geracao.rs` tests), the `processar_bloco`
   conjunction (mutated `&&`→`||`, still killed after the logic moved into the new function), and
   the trait-default `gravar_lote` (mutated to silently drop all but the first item of a batch,
   killed 2 `geracao.rs` tests by losing the "grande" half of an image pair).
5. **Old parallel-path cruft genuinely removed, not just hidden**: `publicar_imagens_paralelo`,
   `ResultadoImagem`, and `publicar_imagem_paralela` are absent from the current `aws.rs` (confirmed
   by reading the full file); the redesign is a net code reduction that also fixes the "exposed but
   never wired" gap PAR-01/02 had in the pre-redesign report.

**Issues found**: none.

**Next steps**: None required for BSV-13's automated gate. Per spec.md's own Success Criteria
(unchanged, not owned by this Verifier), the one remaining manual step is the owner's real-AWS dry
run (`--publicar --sim` against a real `BESAVE_IMAGENS_DIR`, `curl -I` checks for `200`/
`image/webp`/`immutable` headers) — explicitly out of scope for `cargo test` per spec.md's Out of
Scope table ("Teste de upload real contra S3/CloudFront — Dono roda depois").
