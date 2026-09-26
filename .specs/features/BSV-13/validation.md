# BSV-13 Validation (Iteration 2 — Fix Re-Verify)

**Date**: 2026-09-26
**Spec**: `.specs/features/BSV-13/spec.md` (re-read fresh, post-fix wording)
**Diff range**: `60b0ab4..HEAD` (`apps/worker` only) — commits `3af767a..6d0cf80`
**Fix commit under re-check**: `6d0cf80` (`test(worker): close verifier gaps in image budget, reuse and slug checks`)
**Verifier**: independent sub-agent (author ≠ verifier), fresh re-derivation — no prior report trusted, all evidence re-collected from source

---

## Task Completion

| Task | Status  | Notes |
| ---- | ------- | ----- |
| T1: Area::Outros | ✅ Done | AREA-01 spec-precision gap resolved (see below) |
| T2: chaves/origem/assinatura | ✅ Done | - |
| T3: cópia direta + falha não-webp | ✅ Done | - |
| T4: recodificação + imagem grande | ✅ Done | Boundary now discriminated (mutation-confirmed) |
| T5: reaproveitamento + placeholders | ✅ Done | `&&` conjunction now discriminated (mutation-confirmed) |
| T6: integração em gerar() + expurgo | ✅ Done | Missing-`BESAVE_IMAGENS_DIR` edge case now tested |
| T7: paralelismo S3 | ✅ Done | Unchanged; verified by code review per spec's own test strategy |
| Fix round (post-iteration-1 Verifier) | ✅ Done | All 5 claimed fixes verified present, correctly targeted, and effective (see Sensor + AC table). One **new**, previously-unflagged gap found independently (see Sensor #3). |

---

## Spec-Anchored Acceptance Criteria

| Requirement | Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| ----------- | --------- | --------------------- | ------------------------ | ------ |
| AREA-01 | `Area::Outros` serializes `"OUTROS"`, deserializes back (serde round-trip; AC reworded post-Verifier — no shared fixture uses `OUTROS`, confirmed by `grep -rl OUTROS packages/contract/fixtures/` → no matches) | Exact string `"OUTROS"`, round-trip | `apps/worker/tests/modelo.rs:223-229` `area_outros_round_trip_serde` — `assert_eq!(json, "\"OUTROS\"")`; `assert_eq!(de, Area::Outros)` | ✅ PASS (gap closed — new dedicated test, wording now matches what's actually testable) |
| AREA-02 | `DS_COMUNIDADE="Outros"` → `para_card` produces `a:"OUTROS"`, no rejection | `area == Area::Outros`, `Ok(_)` | `apps/worker/tests/card.rs:153-159` `area_outros_nao_e_rejeitada` — `assert_eq!(para_card(&l, &m()).unwrap().area, Area::Outros)` | ✅ PASS |
| AREA-03 | ≥1 active `OUTROS` offer → `manifest.areas["OUTROS"]`=count; manifest validates | Exact count + schema-valid | `apps/worker/tests/geracao.rs:158-172` `area_outros_conta_no_manifest_e_valida_contra_schema` — `assert_eq!(m.areas, BTreeMap::from([(Area::Outros, 1)]))` + `validar_schema("manifest.schema.json", ...)` | ✅ PASS |
| AREA-04 | `Mapeamento::carregar` loads `mapeamento.json` without error | `Ok(_)` | `apps/worker/tests/mapeamento.rs` (every test constructs `m()` via `Mapeamento::carregar(...).unwrap()`); confirmed by full-suite green run | ✅ PASS |
| CHV-01 | `chave_small`/`chave_grande` exact strings | `"img/ofertas/{id}-small.webp"` / `"img/ofertas/{id}.webp"` | `apps/worker/tests/imagens.rs:65-67` `chaves_do_bucket` | ✅ PASS |
| CHV-02 | `origem(dir,id)` exact tuple | `(dir/id/id-small.webp, dir/id/id.webp)` | `apps/worker/tests/imagens.rs:70-86` `origem_monta_os_dois_caminhos` | ✅ PASS |
| CPY-01 | In-budget fixture → identical bytes, `meta_para` Meta, `publicadas` counted | Exact bytes/Meta/count | `apps/worker/tests/imagens.rs:127-142` `copia_direta_dentro_do_orcamento` | ✅ PASS |
| CPY-02 | Non-WebP signature → `falhas` w/ `NaoWebp`, no key written, loop continues | Exact `falhas` vec, no keys, next id processed | `apps/worker/tests/imagens.rs:146-162` `arquivo_nao_webp_vira_falha_e_o_loop_continua` | ✅ PASS |
| ORC-01 | `ajustar_small` → ≤25600B, valid WebP, side ≤320px | Exact bounds | `apps/worker/tests/imagens.rs:165-181` `ajustar_small_cabe_no_orcamento_e_no_lado_maximo` | ✅ PASS |
| ORC-02 | Oversized small → `reprocessadas` counted; boundary exact | `reprocessadas==1`; exactly-25600B does NOT reprocess, 25601B does | `apps/worker/tests/imagens.rs:184-202` `small_acima_do_orcamento_e_recodificado_e_contado` (+ now asserts `rel.maior_small`) **and** `apps/worker/tests/imagens.rs:206-234` `small_no_limite_exato_nao_e_reprocessado_um_byte_a_mais_e` (new, fix #3) | ✅ PASS — boundary now mutation-confirmed (Sensor #2) |
| ORC-03 | Grande >300000B unmodified + WARN; `maior_grande`=largest | Exact bytes, exact `maior_grande` | `apps/worker/tests/imagens.rs:262-273` `imagem_grande_acima_do_aviso_publica_sem_alteracao` | ✅ PASS |
| REU-01 | **Both** keys exist at dest → skip, count `reaproveitadas`, even if source changed; exactly one key present → NOT reaproveitada | Conjunction semantics | `apps/worker/tests/imagens.rs:277-295` `id_ja_publicado_e_reaproveitado_mesmo_com_origem_trocada` **and** `apps/worker/tests/imagens.rs:300-320` `apenas_uma_chave_existente_nao_e_reaproveitada` (new, fix #2) | ✅ PASS — conjunction now mutation-confirmed (Sensor #1) |
| REU-02 | Missing/partial source folder → `sem_origem`, no error, no write | Exact counts, no keys | `apps/worker/tests/imagens.rs:323-342` `sem_pasta_ou_com_um_so_arquivo_conta_sem_origem` | ✅ PASS |
| REU-03 | 10 placeholders published once, reused after | 10 writes, then 0 more | `apps/worker/tests/imagens.rs:346-364` `placeholders_publicados_uma_vez_e_reaproveitados_depois` | ✅ PASS |
| REU-04 | 2nd identical run → `publicadas==0`, `reaproveitadas==N` | Exact counts | `apps/worker/tests/imagens.rs:367-382` `segunda_execucao_completa_nao_publica_nada_de_novo` | ✅ PASS |
| GER-01 | `publicar_imagens` runs before any chunk write | Image-write index < first-chunk-write index | `apps/worker/tests/geracao.rs:489-513` `imagens_publicadas_antes_de_qualquer_chunk` | ✅ PASS |
| GER-02 | `Relatorio` carries all `RelatorioImagens` fields (`publicadas, reaproveitadas, sem_origem, reprocessadas, falhas, bytes, maior_small, maior_grande`) | Fields present and correct | `apps/worker/tests/geracao.rs:516-531` `relatorio_inclui_contagens_de_imagens` (asserts `publicadas`/`sem_origem` only) + whole-struct `relatorio_com_contagens` (asserts all fields, but `bytes`/`maior_small`/`maior_grande` trivially 0 in that scenario) | ⚠️ **Field-level gap**: `bytes` is never asserted at a nonzero, computed value anywhere in the suite (see Sensor #3 — mutant survived) |
| GER-03 | Id dropped from source → both image keys removed | Both keys absent after purge | `apps/worker/tests/geracao.rs:534-548` `expurgo_remove_as_duas_chaves_de_imagem` | ✅ PASS |
| GER-04 | `sem_origem` id still publishes card/page normally | No new rejection | `apps/worker/tests/geracao.rs:551-567` `sem_origem_de_imagem_nao_bloqueia_a_oferta` | ✅ PASS |
| PAR-01 | `PublicadorS3` exposes ≤16-in-flight `HeadObject`/`PutObject` path | Semaphore-bounded pool of 16 | `apps/worker/src/aws.rs:212` (`MAX_EM_VOO: usize = 16`), `:234` (`publicar_imagens_paralelo`), `:246` (`Semaphore::new(MAX_EM_VOO)`) — code review per spec's own Independent Test | ✅ PASS (code review, as prescribed) |
| PAR-02 | `PublicadorLocal`/`PublicadorMemoria` stay sequential | No pool in generic path | `apps/worker/src/imagens.rs:196-253` (`publicar_imagens`, unchanged sequential `for` loop over `&mut dyn Publicador`) | ✅ PASS (code review) |

**Status**: ✅ 20/21 requirements fully covered with value-level or code-review evidence matching the spec-defined outcome exactly; **1 field-level gap** on GER-02 (`RelatorioImagens.bytes` never exercised at a nonzero value — mutation-confirmed, see Sensor #3). No spec-precision gaps remain (AREA-01 resolved).

---

## Discrimination Sensor

**Isolation**: temporary detached `git worktree add --detach <scratch> HEAD` at `C:/Users/Ruben/AppData/Local/Temp/claude/bsv13-verify-scratch`, mutations applied one at a time via `Edit`, reverted before the next, `cargo test` run per mutation, worktree removed with `git worktree remove --force` when done. Baseline `git status --porcelain` on the real worktree was `?? .specs/features/BSV-13/validation.md` (this report, untracked) before the sensor run and identical after — no other change leaked.

| # | File:line | Mutation | Tests run | Killed? |
| - | --------- | -------- | --------- | ------- |
| 1 (rerun, iter-1 gap #2) | `src/imagens.rs:206` | `existe(chave_s)? && existe(chave_g)?` → `\|\|` | `cargo test --test imagens` | ✅ **Killed** — `apenas_uma_chave_existente_nao_e_reaproveitada` failed (`reaproveitadas`: left 1, right 0) |
| 2 (rerun, iter-1 gap #3) | `src/imagens.rs:220` | `bytes_s.len() > ORCAMENTO_SMALL` → `>=` | `cargo test --test imagens` | ✅ **Killed** — `small_no_limite_exato_nao_e_reprocessado_um_byte_a_mais_e` failed (`reprocessadas`: left 1, right 0) |
| 3 (fresh) | `src/imagens.rs:247` | `rel.bytes += (bytes_s.len() + bytes_g.len()) as u64;` → `rel.bytes += 0;` | `cargo test --test imagens --test geracao --test plano --test ciclo` | ❌ **Survived** — no test anywhere asserts `RelatorioImagens.bytes`/`Relatorio.imagens.bytes` at a nonzero, computed value; the only literal appears as `bytes: 0` in a whole-struct compare where the scenario has zero publications |
| 4 (fresh) | `src/geracao.rs:201` | `ids_anteriores.difference(&ids_publicaveis)` → `ids_publicaveis.difference(&ids_anteriores)` (swapped operands — expurgo removes the wrong set) | `cargo test --test geracao --test plano --test ciclo` | ✅ **Killed** — `expurgo_remove_as_duas_chaves_de_imagem` failed (5412's images were not removed) |
| 5 (fresh) | `src/geracao.rs:124` | `imagens::publicar_imagens(&ids_publicaveis, ...)` → `imagens::publicar_imagens(&[], ...)` (wiring: pass empty id list instead of the real one) | `cargo test --test geracao --test plano --test ciclo` | ✅ **Killed** — 5 test failures (`imagens_publicadas_antes_de_qualquer_chunk`, `relatorio_com_contagens`, `relatorio_inclui_contagens_de_imagens`, `sem_origem_de_imagem_nao_bloqueia_a_oferta`, `expurgo_remove_as_duas_chaves_de_imagem`) |

**Sensor depth**: lightweight-plus (5 mutations: the 2 surviving mutants from iteration 1, re-run to confirm the fix, plus 3 fresh ones of my own choosing)
**Result**: 4/5 killed, **1 survived** — ❌ **FAIL** per validate.md's surviving-mutant rule

**Isolation verified**: `git worktree remove --force` succeeded; `git status --porcelain` on the real worktree was `?? .specs/features/BSV-13/validation.md` both before and after the entire sensor run (confirmed via direct diff of captured output).

**Note on iteration-1's 2 surviving mutants**: both are now confirmed **killed** by the fix commit's new tests. The fix commit's claims for gaps #2 and #3 are verified true, independently re-derived (not taken on the diff's word).

---

## Payload/Conjunction Check (`RelatorioImagens`)

| Field | Asserted on value (not just presence)? | Evidence |
| ----- | ----------------------------------- | -------- |
| `publicadas` | ✅ Yes | `tests/imagens.rs:137,159,196,293(→now 317 for new test),377,380` — exact `u64` values |
| `reaproveitadas` | ✅ Yes | `tests/imagens.rs:292,313,381` — including the new "exactly one key" test asserting `0` |
| `sem_origem` | ✅ Yes | `tests/imagens.rs:335`; `tests/geracao.rs:530,563` |
| `reprocessadas` | ✅ Yes, **and now boundary-discriminated** | `tests/imagens.rs:194,220,231` (fix #3: exact-limit=0, limit+1=1) |
| `falhas` | ✅ Yes (full `Vec` content) | `tests/imagens.rs:156,250` (fix #1: exact `(id, NaoWebp)` even when small is also oversized) |
| `maior_small` | ✅ **Now asserted at nonzero** (fix #5) | `tests/imagens.rs:200-201` — `assert_eq!(rel.maior_small, publicado.len() as u64); assert!(rel.maior_small > 0)` — mutation-untested directly this round but logically tied to the same accumulation site as `bytes` |
| `maior_grande` | ✅ Yes | `tests/imagens.rs:272` |
| `bytes` | ❌ **Never asserted at a nonzero value** | Only literal is `bytes: 0` in `tests/geracao.rs` whole-struct compare (trivial, zero-publication scenario). **Mutation-confirmed gap (Sensor #3).** GER-02's AC text explicitly names `bytes` as a required field of `RelatorioImagens` — this is a genuine, spec-anchored omission, not scope creep to flag. |

**Result**: 7/8 fields hit the conjunction/value bar; `bytes` is a new, previously-unflagged gap.

---

## Edge Cases (spec.md, amended)

- [x] `BESAVE_IMAGENS_DIR`/`--imagens-dir` absent + `--gerar`/`--publicar` → error naming the variable, no panic. **Now tested**: `apps/worker/tests/dry_run.rs:154-175` `gerar_sem_imagens_dir_nomeia_a_variavel` — builds its own `Command` (does not reuse the `rodar()` helper, which unconditionally sets the var), `env_remove("BESAVE_IMAGENS_DIR")`, asserts failure, `status.code() != Some(101)` (no panic), stderr contains `"BESAVE_IMAGENS_DIR"`, and `manifest.json` was not created. Cross-checked against `src/main.rs:74-76`: the `bail!` for missing `imagens_dir` runs before `fonte`/Oracle is touched, so the test's minimal env (`BESAVE_FONTE=fake`, no Oracle vars) is sufficient — confirmed by reading the exact `if`-order in `main()`. **Gap closed.**
- [x] Small valid-but-oversized + grande invalid (non-WebP) → id atomic, appears **only** in `falhas` (amended wording; the old wording demanding a dual `reprocessadas`+`falhas` outcome was corrected as spec overreach, not a code bug — signature validation runs for both keys with an early `continue` before the budget branch, confirmed by reading `src/imagens.rs:216-219` vs `:220-237`). **Now tested**: `apps/worker/tests/imagens.rs:239-258` `grande_invalida_marca_falha_mesmo_com_small_acima_do_orcamento` — small deliberately oversized (`webp_ruido(400,400)`, confirmed `> ORCAMENTO_SMALL`), grande deliberately non-WebP (JPEG signature); asserts `falhas == [(id, NaoWebp)]`, `reprocessadas == 0`, `publicadas == 0`, neither key written. **Gap closed**, and the spec.md wording change is verified accurate against the actual code (not just asserted).
- [x] Empty publishable-ids list → still publishes/reuses the 10 placeholders, other counts at 0. `tests/imagens.rs:346-364` `placeholders_publicados_uma_vez_e_reaproveitados_depois` calls `publicar_imagens(&[], ...)` twice; all 10 keys exist after call 1, 0 additional writes after call 2.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / surgical changes | ✅ — fix commit touches only `spec.md`, `tasks.md`, and 3 test files; no production code changed |
| No scope creep | ✅ |
| Matches patterns (thiserror, tracing, `dyn Publicador`, existing test helper style) | ✅ |
| Spec-anchored outcome check | ✅ no remaining spec-precision gaps (AREA-01 resolved) |
| Every test maps to a spec AC / edge case / Done-when | ✅ all 5 new tests + AREA-01 test map 1:1 to the 5 fix items claimed in the commit message and `tasks.md`'s T7 "Fix" note |
| Documented guidelines followed | `apps/worker/CLAUDE.md` (gate command, image-failure-never-blocks rule) — followed |

---

## Gate Check

- **Gate command**: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` (run from `apps/worker/`)
- **Result**: fmt clean (exit 0), clippy clean with `-D warnings` (exit 0), tests: **133 passed, 0 failed, 1 ignored**
  - Breakdown: lib unittests 0, bin unittests 0, card 19, chunks 4, ciclo 8 (+1 ignored, `trinta_mil_cards_em_ate_30_segundos` — pre-existing perf test, justified `#[ignore]` for CI stability, unrelated to this feature), dry_run 12, fonte 2, geracao 20, headers 4, imagens 17, mapeamento 5, modelo 4, oracle 9, pagina 9, plano 4, publicador 5, redirects 11, doctests 0
- **Test count before this fix commit** (iteration-1 baseline): 128 passed, 1 ignored (129 total)
- **Test count after this fix commit**: 133 passed, 1 ignored (134 total)
- **Delta**: +5 new tests — exactly matches the 5 tests the fix commit's diff adds (`imagens.rs` +3, `dry_run.rs` +1, `modelo.rs` +1); no test deletions, no weakened assertions found
- **Failures**: none

---

## Fix Plans (if issues found)

### Fix 1 (new, this iteration): Assert `RelatorioImagens.bytes` at a nonzero, computed value
- **Root cause**: `src/imagens.rs:247` (`rel.bytes += (bytes_s.len() + bytes_g.len()) as u64;`) has no test that observes its effect — every test either doesn't inspect `.bytes` or hits the trivial `bytes: 0` case where nothing was published. Confirmed by mutation: replacing the accumulation with a no-op left the entire suite green.
- **Fix task**: extend an existing single-id-published test (e.g. `copia_direta_dentro_do_orcamento` in `apps/worker/tests/imagens.rs`) with `assert_eq!(rel.bytes, (pequena.len() + grande.len()) as u64);`, or add a small dedicated test summing across 2+ published ids to also confirm accumulation (not just single-id correctness).
- **Priority**: Minor (same tier as the now-fixed `maior_small` gap — a reporting/observability field, not a correctness-of-publishing gap; `bytes` does not gate any decision in `publicar_imagens`).

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | ---------------- | ----------- |
| AREA-01 | ⚠️ Verified with spec-precision gap | ✅ Verified — gap closed |
| AREA-02, AREA-03, AREA-04 | ✅ Verified | ✅ Verified |
| CHV-01, CHV-02 | ✅ Verified | ✅ Verified |
| CPY-01, CPY-02 | ✅ Verified | ✅ Verified |
| ORC-01, ORC-03 | ✅ Verified | ✅ Verified |
| ORC-02 | ⚠️ Verified, boundary undiscriminated | ✅ Verified — boundary now mutation-confirmed |
| REU-01 | ⚠️ Verified, conjunction undiscriminated | ✅ Verified — conjunction now mutation-confirmed |
| REU-02, REU-03, REU-04 | ✅ Verified | ✅ Verified |
| GER-01 | ✅ Verified | ✅ Verified |
| GER-02 | ✅ Verified | ⚠️ Verified with field-level gap (`bytes` unasserted, mutation-confirmed) |
| GER-03, GER-04 | ✅ Verified | ✅ Verified |
| PAR-01, PAR-02 | ✅ Verified (code review) | ✅ Verified (code review) |

---

## Summary

**Overall**: ⚠️ Issues — very close to done; 1 minor, mutation-confirmed gap remains

**Spec-anchored check**: 21/21 requirements have file:line or code-review evidence matching the spec-defined outcome; 0 spec-precision gaps (AREA-01 resolved this round)
**Sensor**: 4/5 mutations killed (both of iteration-1's surviving mutants now confirmed killed), 1 new survivor found independently — ❌ FAIL per validate.md's surviving-mutant rule
**Gate**: 133 passed, 0 failed, 1 justified-ignored (fmt clean, clippy clean)

**What works**: All 5 of the fix commit's claimed test additions were verified to exist exactly where claimed, to exercise the scenario they claim (read line-by-line, not just by name), and to be effective — both previously-surviving mutants (REU-01's `&&`, ORCAMENTO_SMALL's boundary) are now confirmed killed by re-running the exact same mutations from iteration 1. AREA-01's spec wording fix is independently verified accurate (no fixture uses `OUTROS`, confirmed by direct grep). The atomic-id edge case is independently confirmed against the actual code logic (`e_webp` check precedes and short-circuits before the budget branch). 2 additional fresh mutations (expurgo-direction swap, images-wiring-to-empty-list) were tried on feature-new code in `geracao.rs` and both were killed convincingly, giving good confidence in the core integration logic.

**Issues found**:
1. `RelatorioImagens.bytes` (explicitly named in GER-02's AC text) is never asserted at a nonzero value anywhere in the suite — confirmed by mutation (dropping the accumulation entirely leaves all 133 tests green). This is the same class of gap as the now-fixed `maior_small`, just on the sibling `bytes` field, missed by both the fix commit and iteration-1's Verifier.

**Next steps**: Route Fix 1 above as a fix task (extend one existing test with a `rel.bytes` assertion — small, single-line-of-risk change). This is iteration 2 of the bounded 3-iteration fix→re-verify loop; one more iteration is available before escalating to the user.
