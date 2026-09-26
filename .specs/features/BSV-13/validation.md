# BSV-13 Validation (Iteration 3 — Final Fix Re-Verify, bounded loop)

> **Addendum (implementer, not the Verifier — written after this report, not independently re-verified):**
> The loop's single remaining gap (`maior_small`/`maior_grande` multi-id `.max()` semantics
> undiscriminated, `src/imagens.rs:248-249`) was fixed in commit
> `test(worker): assert maior_small/maior_grande track the max across ids`, adding
> `maior_small_e_maior_grande_refletem_o_maior_entre_varios_ids` to `apps/worker/tests/imagens.rs`
> (two ids, the first with the larger small **and** grande, published second; asserts the report
> keeps the first id's larger values rather than the last-processed one's — the exact case the
> Verifier's sensor used to kill the mutation). Full gate (`fmt`, `clippy -D warnings`, `cargo
> test`) reran green, 134 tests. This fix was **not** run through a 4th independent Verifier
> agent, per the skill's 3-iteration bound — it is small, mechanical, and directly targets the
> sensor's own reproduction steps below, but per "author ≠ verifier" the owner should treat this
> addendum as implementer self-report, not an independent PASS.

**Date**: 2026-09-26
**Spec**: `.specs/features/BSV-13/spec.md` (re-read fresh)
**Diff range**: `60b0ab4..HEAD` (`apps/worker` only) — commits `3af767a..5f281f6`
**Fix commit under re-check**: `5f281f6` (`test(worker): assert RelatorioImagens.bytes at a real published value`)
**Verifier**: independent sub-agent (author ≠ verifier), fresh re-derivation — no prior report trusted, all evidence re-collected from source. This is iteration 3 of the bounded 3-iteration fix→re-verify loop (the last before escalation).

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1: Area::Outros | ✅ Done | Re-confirmed |
| T2: chaves/origem/assinatura | ✅ Done | Re-confirmed |
| T3: cópia direta + falha não-webp | ✅ Done | Re-confirmed |
| T4: recodificação + imagem grande | ✅ Done | Re-confirmed; new sub-gap found on `maior_*` multi-id semantics (see Sensor #4) |
| T5: reaproveitamento + placeholders | ✅ Done | Re-confirmed; placeholder reuse guard independently mutation-tested (Sensor #3) |
| T6: integração em gerar() + expurgo | ✅ Done | Re-confirmed |
| T7: paralelismo S3 | ✅ Done | Unchanged; code review per spec's own test strategy |
| Fix round (iteration 2 → 3): `RelatorioImagens.bytes` | ✅ Done, verified true | Fix commit `5f281f6` confirmed real (not a placeholder) and mutation-killed independently (see Sensor #1) |

---

## Spec-Anchored Acceptance Criteria

Re-derived independently from current `spec.md` and current source/tests. Rows marked **[Re-derived]** were read line-by-line this iteration (file:line + assertion re-confirmed from source, not carried from the prior report); the rest were spot-checked against the diff (no `apps/worker/src` changes since iteration 2 — only `apps/worker/tests/imagens.rs` gained 3 lines) and match iteration 2 exactly.

| Requirement | Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| ----------- | --------- | --------------------- | ------------------------ | ------ |
| AREA-01 **[Re-derived]** | `Area::Outros` serializes `"OUTROS"`, round-trips | Exact string, round-trip | `apps/worker/tests/modelo.rs:33-38` `area_outros_round_trip_serde` — `assert_eq!(json, "\"OUTROS\"")`; `assert_eq!(de, Area::Outros)` | ✅ PASS |
| AREA-02 **[Re-derived]** | `DS_COMUNIDADE="Outros"` → `para_card` produces `a:"OUTROS"`, no rejection | `area == Area::Outros`, `Ok(_)` | `apps/worker/tests/card.rs:153-159` `area_outros_nao_e_rejeitada` — `assert_eq!(para_card(&l, &m()).unwrap().area, Area::Outros)` | ✅ PASS |
| AREA-03 **[Re-derived]** | ≥1 active `OUTROS` offer → `manifest.areas["OUTROS"]`=count; manifest validates | Exact count + schema-valid | `apps/worker/tests/geracao.rs:159-172` `area_outros_conta_no_manifest_e_valida_contra_schema` — `assert_eq!(m.areas, BTreeMap::from([(Area::Outros, 1)]))` + `validar_schema(...)` | ✅ PASS |
| AREA-04 | `Mapeamento::carregar` loads without error | `Ok(_)` | `apps/worker/tests/mapeamento.rs` (every test builds `m()` via `.unwrap()`); full-suite green | ✅ PASS |
| CHV-01 | `chave_small`/`chave_grande` exact strings | `"img/ofertas/{id}-small.webp"` / `"img/ofertas/{id}.webp"` | `apps/worker/tests/imagens.rs:65-67` `chaves_do_bucket` | ✅ PASS |
| CHV-02 | `origem(dir,id)` exact tuple | `(dir/id/id-small.webp, dir/id/id.webp)` | `apps/worker/tests/imagens.rs:70-86` `origem_monta_os_dois_caminhos` | ✅ PASS |
| CPY-01 | In-budget fixture → identical bytes, Meta, `publicadas` counted | Exact bytes/Meta/count | `apps/worker/tests/imagens.rs:128-145` `copia_direta_dentro_do_orcamento` | ✅ PASS |
| CPY-02 **[Re-derived]** | Non-WebP signature → `falhas` w/ `NaoWebp`, no key, loop continues | Exact `falhas` vec, no keys, next id processed | `apps/worker/tests/imagens.rs:150-165` `arquivo_nao_webp_vira_falha_e_o_loop_continua` — `assert_eq!(rel.falhas, vec![(5413, MotivoFalhaImagem::NaoWebp)])`; asserts 5414 (next id) still published | ✅ PASS |
| ORC-01 | `ajustar_small` → ≤25600B, valid WebP, side ≤320px | Exact bounds | `apps/worker/tests/imagens.rs:169-181` `ajustar_small_cabe_no_orcamento_e_no_lado_maximo` | ✅ PASS |
| ORC-02 **[Re-derived]** | Oversized small → `reprocessadas` counted; boundary exact | `reprocessadas==1`; 25600B does NOT reprocess, 25601B does | `apps/worker/tests/imagens.rs:188-205` + `:206-234` (exact-limit test) | ⚠️ **PASS on literal AC text; new sub-gap on `maior_small`'s multi-id "maior" semantics** (see Sensor #4) |
| ORC-03 | Grande >300000B unmodified + WARN; `maior_grande`=largest | Exact bytes, exact `maior_grande` | `apps/worker/tests/imagens.rs:263-276` `imagem_grande_acima_do_aviso_publica_sem_alteracao` | ⚠️ **PASS on literal AC text; new sub-gap on `maior_grande`'s multi-id "maior" semantics** (see Sensor #4) |
| REU-01 **[Re-derived]** | Both keys exist → skip, count; exactly one → NOT reaproveitada | Conjunction semantics | `apps/worker/tests/imagens.rs:281-298` + `apenas_uma_chave_existente_nao_e_reaproveitada` | ✅ PASS |
| REU-02 | Missing/partial source → `sem_origem`, no error, no write | Exact counts, no keys | `apps/worker/tests/imagens.rs` `sem_pasta_ou_com_um_so_arquivo_conta_sem_origem` | ✅ PASS |
| REU-03 **[Re-derived, mutation-tested]** | 10 placeholders published once, reused after | 10 writes, then 0 more | `apps/worker/tests/imagens.rs:350-367` `placeholders_publicados_uma_vez_e_reaproveitados_depois` — `assert_eq!(p.gravacoes().len(), gravacoes_1a_chamada)` | ✅ PASS — reuse guard mutation-confirmed this iteration (Sensor #3) |
| REU-04 | 2nd identical run → `publicadas==0`, `reaproveitadas==N` | Exact counts | `apps/worker/tests/imagens.rs` `segunda_execucao_completa_nao_publica_nada_de_novo` | ✅ PASS |
| GER-01 **[Re-derived]** | `publicar_imagens` runs before any chunk write | Image-write index < first-chunk-write index | `apps/worker/tests/geracao.rs:490-513` `imagens_publicadas_antes_de_qualquer_chunk` — `assert!(imagem < primeiro_chunk, ...)` | ✅ PASS |
| GER-02 **[Re-derived — the AC this iteration targets]** | `Relatorio` carries all `RelatorioImagens` fields (`publicadas, reaproveitadas, sem_origem, reprocessadas, falhas, bytes, maior_small, maior_grande`) | Fields present and correct | `apps/worker/src/imagens.rs:245-247` (production code, unchanged): `rel.bytes += (bytes_s.len() + bytes_g.len()) as u64;`. Now asserted at `apps/worker/tests/imagens.rs:134,140` `copia_direta_dentro_do_orcamento` — `let bytes_esperados = (pequena.len() + grande.len()) as u64;` (12_000+90_000=102_000, nonzero) then `assert_eq!(rel.bytes, bytes_esperados);`. Confirmed **not** a placeholder: real computed value, matches source line exactly, distinct from the trivial `bytes: 0` literal still present in `geracao.rs:304` (zero-publication scenario, correctly trivial there). | ✅ **PASS — gap closed.** Independently mutation-confirmed (Sensor #1): zeroing the accumulator in scratch now fails this exact test. |
| GER-03 **[Re-derived]** | Id dropped from source → both image keys removed | Both keys absent after purge | `apps/worker/tests/geracao.rs:535-548` `expurgo_remove_as_duas_chaves_de_imagem` | ✅ PASS |
| GER-04 | `sem_origem` id still publishes card/page normally | No new rejection | `apps/worker/tests/geracao.rs` `sem_origem_de_imagem_nao_bloqueia_a_oferta` | ✅ PASS |
| PAR-01 **[Re-derived]** | `PublicadorS3` exposes ≤16-in-flight `HeadObject`/`PutObject` path | Semaphore-bounded pool of 16 | `apps/worker/src/aws.rs:212` `const MAX_EM_VOO: usize = 16;`, `:234` `pub fn publicar_imagens_paralelo`, `:246` `Semaphore::new(MAX_EM_VOO)` — code review, per spec's own Independent Test ("revisão de `src/aws.rs`") | ✅ PASS (code review, as prescribed) |
| PAR-02 | `PublicadorLocal`/`PublicadorMemoria` stay sequential | No pool in generic path | `apps/worker/src/imagens.rs:196-253` (`publicar_imagens`, unchanged sequential `for` loop over `&mut dyn Publicador`) | ✅ PASS (code review) |

**Status**: 21/21 requirements have file:line or code-review evidence matching the literal spec-defined outcome. GER-02's previously-flagged gap (`bytes` unasserted) is **closed and mutation-confirmed**. **1 new sub-gap** found this iteration, attached to ORC-02/ORC-03: the `maior_small`/`maior_grande` fields' documented "maior entre os ids publicados nesta execução" (max-across-multiple-ids-in-one-call) semantics is never exercised by any test — every test that asserts these fields publishes exactly one id per `publicar_imagens` call, so a mutation that replaces the `.max()` accumulation with a plain overwrite is behaviorally indistinguishable and survives.

---

## Discrimination Sensor

**Isolation**: `git worktree add --detach` at `C:/Users/Ruben/AppData/Local/Temp/claude/bsv13-verify-iter3-scratch`, HEAD `5f281f6`. Mutations applied one at a time via `Edit` directly on the scratch copy, `cargo test` run per mutation, reverted via `git checkout --` before the next, worktree removed with `git worktree remove --force` when done. Baseline `git status --porcelain` on the real worktree was **empty** before the sensor run and **empty** after (confirmed both by direct check — see Isolation Verified below).

| # | File:line | Mutation | Tests run | Killed? |
| - | --------- | -------- | --------- | ------- |
| 1 (re-run of the exact gap-surfacing mutation, this iteration's fix target) | `src/imagens.rs:247` | `rel.bytes += (bytes_s.len() + bytes_g.len()) as u64;` → `rel.bytes += 0;` | `cargo test --test imagens` | ✅ **Killed** — `copia_direta_dentro_do_orcamento` failed: `assertion left == right failed: left: 0, right: 102000` |
| 2 (fresh) | `src/imagens.rs:77` (`e_webp`) | `bytes.len() >= 12 && &bytes[0..4] == b"RIFF" && &bytes[8..12] == b"WEBP"` → `bytes.len() >= 12 && (&bytes[0..4] == b"RIFF" \|\| &bytes[8..12] == b"WEBP")` | `cargo test --test imagens` | ✅ **Killed** — `assinatura_webp_rejeita_vazio_riff_sem_webp_e_jpeg` failed on the `riff_sem_webp` case (RIFF-but-not-WEBP now wrongly accepted) |
| 3 (fresh) | `src/imagens.rs:185-187` (`publicar_placeholders`) | Removed the `if !pub_.existe(&chave)?` reuse guard — placeholders always rewritten | `cargo test --test imagens` | ✅ **Killed** — `placeholders_publicados_uma_vez_e_reaproveitados_depois` failed: `left: 20, right: 10` ("2ª chamada não deveria regravar nenhum placeholder") |
| 4 (fresh) | `src/imagens.rs:248-249` | `rel.maior_small = rel.maior_small.max(bytes_s.len() as u64); rel.maior_grande = rel.maior_grande.max(bytes_g.len() as u64);` → plain overwrite (`rel.maior_small = bytes_s.len() as u64; rel.maior_grande = bytes_g.len() as u64;`, dropping `.max()`) | `cargo test --test imagens --test geracao --test plano --test ciclo` | ❌ **Survived** — all 49 tests across the 4 binaries stayed green (imagens 17/17, geracao 20/20, plano 4/4, ciclo 8/8+1 ignored). No test publishes more than one id per `publicar_imagens`/`gerar` call while asserting `maior_small`/`maior_grande`, so max-tracking and last-write-wins are indistinguishable to the current suite. |

**Sensor depth**: lightweight-plus (4 mutations: 1 re-run confirming this iteration's fix, 3 fresh — none repeated from iteration 1's or iteration 2's tables)
**Result**: 3/4 killed, **1 survived** — ❌ **FAIL** per `validate.md`'s surviving-mutant rule

**Isolation verified**: `git worktree remove --force` succeeded cleanly; `git status --porcelain` on the real worktree (`C:\Users\Ruben\orca\workspaces\besave\rub-9-bsv-13-worker-imagens-webp`) was empty immediately before creating the scratch worktree and remains empty after its removal — confirmed by direct re-check, not assumed.

**Note on this iteration's target mutation**: the exact mutation that surfaced iteration 2's `bytes` gap (Sensor #1 above) is now confirmed **killed** — the fix commit's claim is verified true, independently re-derived by re-running the identical fault, not taken on the commit message's word.

---

## Payload/Conjunction Check (`RelatorioImagens`)

| Field | Asserted on value (not just presence)? | Evidence |
| ----- | ----------------------------------- | -------- |
| `publicadas` | ✅ Yes | Exact `u64` values throughout `tests/imagens.rs` |
| `reaproveitadas` | ✅ Yes | Including the "exactly one key" test asserting `0` |
| `sem_origem` | ✅ Yes | `tests/imagens.rs`, `tests/geracao.rs` |
| `reprocessadas` | ✅ Yes, boundary-discriminated | Exact-limit=0, limit+1=1 (mutation-confirmed, iteration 2) |
| `falhas` | ✅ Yes (full `Vec` content) | Exact `(id, NaoWebp)` tuples |
| `bytes` | ✅ **Now asserted at nonzero, computed value** | `tests/imagens.rs:134,140` — `assert_eq!(rel.bytes, bytes_esperados)`, `bytes_esperados = 102_000`. **Mutation-confirmed fixed this iteration (Sensor #1).** |
| `maior_small` | ⚠️ Asserted at nonzero for a **single published id only**; max-across-multiple-ids never exercised | `tests/imagens.rs:203-204` — `assert_eq!(rel.maior_small, publicado.len() as u64); assert!(rel.maior_small > 0)`. **Mutation-confirmed gap on the multi-id case (Sensor #4).** |
| `maior_grande` | ⚠️ Same as `maior_small` | `tests/imagens.rs:275` — `assert_eq!(rel.maior_grande, grande.len() as u64)`, single id only. **Mutation-confirmed gap (Sensor #4).** |

**Result**: 6/8 fields fully hit the conjunction/value bar; `maior_small`/`maior_grande` hit it only for the trivial single-id case — the spec's own documented "maior entre os ids ... nesta execução" semantics (spec.md, Assumptions table) is unverified.

---

## Edge Cases (spec.md)

- [x] `BESAVE_IMAGENS_DIR`/`--imagens-dir` absent → error naming the variable, no panic. `apps/worker/tests/dry_run.rs` `gerar_sem_imagens_dir_nomeia_a_variavel` — re-confirmed present, unchanged since iteration 2.
- [x] Small oversized + grande invalid (non-WebP) → id atomic, appears only in `falhas`. `apps/worker/tests/imagens.rs` `grande_invalida_marca_falha_mesmo_com_small_acima_do_orcamento` — re-confirmed present, unchanged since iteration 2.
- [x] Empty publishable-ids list → still publishes/reuses the 10 placeholders. `placeholders_publicados_uma_vez_e_reaproveitados_depois` calls `publicar_imagens(&[], ...)` — re-confirmed, and this iteration's Sensor #3 independently mutation-tests the reuse guard this test relies on.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / surgical changes | ✅ — fix commit `5f281f6` touches only `apps/worker/tests/imagens.rs` (+3 lines), plus `.specs/features/BSV-13/{tasks,validation}.md`; no other production code |
| No scope creep | ✅ |
| Matches patterns | ✅ |
| Spec-anchored outcome check | ✅ — GER-02's `bytes` gap closed with a real computed value, not a placeholder |
| Every test maps to a spec AC / edge case / Done-when | ✅ — the one added assertion maps 1:1 to GER-02 / the iteration-2 fix task |
| Documented guidelines followed | `apps/worker/CLAUDE.md` (gate command, image-failure-never-blocks rule) — followed |

---

## Gate Check

- **Gate command**: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` (run from `apps/worker/`, on the real, unmutated worktree)
- **Result**: fmt clean (exit 0), clippy clean with `-D warnings` (exit 0), tests: **133 passed, 0 failed, 1 ignored**
  - Breakdown: card 19, chunks 4, ciclo 8 (+1 ignored, `trinta_mil_cards_em_ate_30_segundos`, pre-existing perf test justified `#[ignore]` for CI stability), dry_run 12, fonte 2, geracao 20, headers 4, imagens 17, mapeamento 5, modelo 4, oracle 9, pagina 9, plano 4, publicador 5, redirects 11, doctests 0. Sum = 133.
- **Test count before this fix commit** (iteration-2 baseline): 133 passed, 1 ignored (134 total)
- **Test count after this fix commit**: 133 passed, 1 ignored (134 total)
- **Delta**: **+0 new test functions** — the fix commit extends `copia_direta_dentro_do_orcamento` with 2 new lines (`bytes_esperados` + `assert_eq!`) rather than adding a new `#[test]` function. This matches the task's own expectation and `tasks.md`'s note ("adicionado `assert_eq!(rel.bytes, ...)` em `copia_direta_dentro_do_orcamento`") — reconciled, not a discrepancy.
- **Failures**: none

---

## Fix Plans (if issues found)

### Fix 1 (new, this iteration): Exercise `maior_small`/`maior_grande`'s multi-id "maior" semantics
- **Root cause**: `src/imagens.rs:248-249` computes `rel.maior_small`/`rel.maior_grande` via `.max()` across the loop over `ids`, per the spec's own Assumptions table ("maior tamanho em bytes, entre os ids publicados nesta execução"). Every test that asserts these fields (`small_acima_do_orcamento_e_recodificado_e_contado`, `imagem_grande_acima_do_aviso_publica_sem_alteracao`) publishes exactly one id, so `.max()` and a plain overwrite are behaviorally identical to the suite. Confirmed by mutation: replacing both `.max()` calls with plain assignment left `imagens`, `geracao`, `plano`, and `ciclo` (49 tests) entirely green.
- **Fix task**: add one test (or extend an existing multi-id test) that publishes ≥2 ids in a single `publicar_imagens` call with distinct `small`/`grande` byte sizes per id, and asserts `rel.maior_small`/`rel.maior_grande` equal the larger of the two (not the last-processed one) — e.g. publish ids A (small=`12_000`, grande=`50_000`) and B (small=`8_000`, grande=`90_000`) and assert `rel.maior_grande == 90_000` while B is processed after A in id order (or vice versa, to rule out "last wins").
- **Priority**: Minor — same tier as the now-fixed `bytes`/(previously) `maior_small`-single-id gaps: a reporting/observability field that does not gate any publish/reuse/reprocess decision in `publicar_imagens`.

---

## Requirement Traceability Update

| Requirement | Previous Status (iter. 2) | New Status (iter. 3) |
| ----------- | -------------------------- | ---------------------- |
| AREA-01..04 | ✅ Verified | ✅ Verified (re-confirmed) |
| CHV-01, CHV-02 | ✅ Verified | ✅ Verified |
| CPY-01, CPY-02 | ✅ Verified | ✅ Verified (re-confirmed) |
| ORC-01 | ✅ Verified | ✅ Verified |
| ORC-02 | ✅ Verified | ⚠️ Verified, new sub-gap: `maior_small` multi-id semantics unconfirmed (mutation-confirmed, Sensor #4) |
| ORC-03 | ✅ Verified | ⚠️ Verified, new sub-gap: `maior_grande` multi-id semantics unconfirmed (mutation-confirmed, Sensor #4) |
| REU-01..04 | ✅ Verified | ✅ Verified (REU-03's reuse guard now also mutation-confirmed) |
| GER-01 | ✅ Verified | ✅ Verified (re-confirmed) |
| GER-02 | ⚠️ Verified, field-level gap (`bytes` unasserted) | ✅ **Verified — gap closed and mutation-confirmed** |
| GER-03, GER-04 | ✅ Verified | ✅ Verified (re-confirmed) |
| PAR-01, PAR-02 | ✅ Verified (code review) | ✅ Verified (code review, re-confirmed) |

---

## Summary

**Overall**: ❌ **Not Ready** — the targeted fix is real and verified, but a fresh adversarial pass found one new mutation-confirmed gap.

**Spec-anchored check**: 21/21 requirements have file:line or code-review evidence matching the spec-defined outcome; GER-02's `bytes` gap is closed. 0 requirements structurally uncovered.
**Sensor**: 4 mutations injected (1 re-run of the exact iteration-2 gap, 3 fresh), 3 killed, **1 survived** — ❌ FAIL per `validate.md`'s surviving-mutant rule
**Gate**: 133 passed, 0 failed, 1 justified-ignored (fmt clean, clippy clean)

**What works**: The fix commit `5f281f6` is confirmed genuine, not cosmetic: `apps/worker/tests/imagens.rs:134,140` computes `bytes_esperados` from the actual fixture sizes (`pequena.len() + grande.len()` = 102,000, a real nonzero value derived from the test's own inputs, not a hardcoded placeholder) and asserts `rel.bytes` against it. Independently re-running the exact mutation that surfaced this gap in iteration 2 (`rel.bytes += 0` in an isolated scratch worktree) now fails this test with `left: 0, right: 102000` — direct proof the fix closes the gap it claims to close. Two additional fresh mutations targeting previously-untested code paths (`e_webp`'s signature-check conjunction, `publicar_placeholders`'s reuse guard) were both killed convincingly, adding real new coverage confidence beyond what iterations 1-2 exercised. All 21 requirement IDs were re-checked against current source and tests (9 of them re-derived line-by-line from scratch this iteration, not carried from the prior report), and no `apps/worker/src` regressions were found — the only src-adjacent diff since iteration 2 is the 3-line test addition.

**Issues found**:
1. `RelatorioImagens.maior_small`/`maior_grande`'s documented "maior entre os ids publicados nesta execução" semantics (spec.md Assumptions table; also the literal text of ORC-03's AC for `maior_grande`) is never exercised with more than one published id per call — mutation-confirmed: replacing the `.max()` accumulation at `apps/worker/src/imagens.rs:248-249` with a plain overwrite leaves all 49 relevant tests (imagens/geracao/plano/ciclo) green. This is a genuinely new finding, not a repeat of iteration 1's or 2's mutations, and not present in either prior report's sensor table.

**Next steps — escalate to human owner.** This is iteration 3 of the bounded 3-iteration fix→re-verify loop (validate.md / sub-agents.md: "if gaps remain after 3 iterations, escalate to the user rather than continuing to loop"). Do **not** dispatch a 4th fix→re-verify cycle. The gap is Minor in severity (reporting-field-only, does not affect publish/reuse/reprocess correctness, and the fix is small — one new or extended multi-id test), so the human owner may reasonably choose to accept it as a known limitation and ship, or route it as a follow-up fix outside this bounded loop. Everything else in this report (all 21 requirements, the gate, and 3 of 4 sensor mutations) is a clean, evidence-backed PASS.
