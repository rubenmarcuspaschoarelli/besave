# BSV-15 Validation

**Date**: 2026-10-01
**Spec**: `.specs/features/BSV-15/spec.md` (ticket: `docs/specs/BSV-15.md`)
**Diff range**: `e24a757..29f3d18` (99e45a7, 7211ffb, e338c5e, 29f3d18)
**Verifier**: independent sub-agent (author ≠ verifier)

**Verdict (current, round 3 at `f93662c`)**: PASS. 22/22 ACs are spec-anchored and the gates are green.
The round-2 sensor (14 mutants, re-run on `f93662c`) killed all 14. See "Round 3" at the end. The owner's real run still blocks the merge.

Round 1 verdict was FAIL. Two surviving mutants (AVI-05 recovery state, VER-04 "status ≠ 200") mean the tests do not pin down those
spec outcomes. Both fixes are test-only and small. The code behaves as the spec says. Owner's real run is still pending (merge blocker).

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 | ✅ Done | 99e45a7 |
| T2 | ✅ Done | e338c5e (+ 7211ffb fmt fix in `tests/iam.tftest.hcl`, whitespace only) |
| T3 | ⚠️ Done in code, not in bookkeeping | 29f3d18. In `tasks.md` the T3 "Done when" boxes are unchecked and Status is still `In Progress` |

---

## Spec-Anchored Acceptance Criteria

Test file abbreviations: `TH` = `infra/lambdas/vigia/test_handler.py`, `TV` = `infra/tests/vigia.tftest.hcl`.

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| VER-01 | age ≤ LIMIAR_MIN → ok | `TH:101-104` 10 min → `"sem_aviso"`, `enviadas == []`; `TH:143-146` exactly 30 min → `"sem_aviso"` | ✅ PASS |
| VER-02 | age > LIMIAR_MIN or HeadObject fails → frescor problem | `TH:106-109` 31 min → `"avisado"`, 1 msg containing `"31 min"`; `TH:155-160` missing → `"manifest.json inacessível no S3"` | ✅ PASS |
| VER-03 | 200 + JSON with `versao` → ok | `TH:101-104` (default http = 200 `{"versao":…}`) → no message | ✅ PASS |
| VER-04 | timeout/network/status ≠ 200/body without `versao` → availability problem, distinct text | `TH:182-186` 403 → `"HTTP 403"`, `assertNotIn` frescor texts; `TH:188-206` timeout, network, no versao, non-JSON, non-object | ⚠️ GAP: only 403 is tested for "status ≠ 200". Mutants M9/M9b survive |
| VER-05 | GET timeout 10 s | `TH:218-222` `timeouts == [10]`; `TH:237-243` `urlopen(... timeout=10)` | ✅ PASS |
| AVI-01 | ok + no problem → no message, no write | `TH:102-104` `puts == []` | ✅ PASS |
| AVI-02 | 1 msg; state `{alerta, desde=min(LastModified \| agora), ultimo_aviso=agora}` | `TH:107-114` exact `desde 14:50Z`, `ultimo_aviso 15:21Z`; `TH:179` `desde == agora` for availability; `TH:216` min of both problems | ✅ PASS |
| AVI-03 | alert, < 3 h → nothing | `TH:116-119`; `TH:277` 2h59 → `"sem_aviso"` | ✅ PASS |
| AVI-04 | alert, ≥ 3 h → 1 reminder, `ultimo_aviso=agora`, `desde` kept | `TH:121-130` exact `desde`/`ultimo_aviso`; `TH:278` exactly 3 h → `"avisado"` | ✅ PASS |
| AVI-05 | message `✅ Besave: site atualizado de novo (parado por <dur>)`; state `{ok, desde: agora, ultimo_aviso: agora}` | `TH:135` exact message `"(parado por 3h40)"`; `TH:303` `"20 min"`; `TH:136` asserts **only** `situacao == "ok"` | ⚠️ GAP: `desde`/`ultimo_aviso` of the recovery state are not asserted. Mutant M15 survives |
| AVI-06 | Telegram/SSM failure → error log, no write, retry next cycle | `TH:311-317` `assertLogs ERROR`, `puts == []`, next run `"avisado"`; `TH:319-329` recovery failure keeps `alerta`; `TH:331-340` SSM failure | ✅ PASS |
| AVI-07 | messages HH:MM Brasília; state ISO UTC | `TH:394-399` `"11:15"` present, `"14:15"` absent; `TH:112-114` `...Z` | ✅ PASS |
| AVI-08 | no token/chat_id/ARN/affiliate URL in messages and logs | `TH:378-392` messages; `TH:362-374` send-failure log without token/chat | ✅ PASS (see risk R2 for logs of *uncaught* exceptions) |
| INF-01 | Lambda name/runtime/handler/archive_file/env | `TV:9-31` incl. exact env `tomap({...})` | ✅ PASS |
| INF-02 | `rate(10 minutes)` → Lambda via role that can only invoke it | `TV:38-61` exact policy equality + trust | ✅ PASS |
| INF-03 | `/aws/lambda/besave-vigia`, 14 days | `TV:68-71` | ✅ PASS |
| INF-04 | exact policy | `TV:74-117` `jsondecode(policy) == {...}` (exact equality) | ✅ PASS |
| INF-05 | no `aws_ssm_parameter` resource/data | `TV:140-143` + `infra/tests/inspecao/main.tf:31-33` | ✅ PASS |
| INF-06 | distribution/buckets/worker policy unchanged | `TV:146-149` (vigia.tf has 8 resources, none `aws_cloudfront_*`/`aws_s3_*`/`aws_iam_user`); `git diff --stat e24a757..HEAD` touches no `s3.tf`/`cloudfront.tf`/`iam.tf`; existing suites still green | ✅ PASS |
| INF-07 | 0 retries in Scheduler and async invoke | `TV:124-129` | ✅ PASS |
| OPS-03 | CI `infra` job runs Python tests | `.github/workflows/ci.yml:108-110` (job `working-directory: infra`, ci.yml:98) | ✅ PASS |
| OPS-04 | README: SSM params, `lambda invoke`, cost | `infra/README.md:109-110`, `:128`, `:141-150` | ✅ PASS |

Edge cases (spec):
- [x] Exactly LIMIAR_MIN → ok (`TH:143-146`, mutant M3 killed)
- [x] Both problems → both listed (`TH:208-216`)
- [x] Invalid state → treated as ok (`TH:257-263`)
- [x] Recovery fails on Telegram → stays `alerta`, next healthy cycle sends recovery (`TH:319-329`)

Ticket ACs (`docs/specs/BSV-15.md`): the sequence 10 → 31 → still stale → +3 h → fresh is `TH:99-139`
(0 / 1 / 0 / reminder / "voltou" with duration). 403/timeout → availability is `TH:182-190`. Telegram failure
→ no advance is `TH:307-317`. fmt/validate/test are clean. The real `plan`/`apply`/`invoke`/40-min outage run by the owner is **pending**.

Ticket deviation: deliverable 1 says "só biblioteca padrão". The handler uses the runtime's `boto3` for S3/SSM. This is the owner's decision (spec Assumptions, 01/10) and should become an AD. A new Terraform provider `hashicorp/archive` 2.8.1 is required by the ticket's `archive_file`, and CLAUDE.md rule 7 says the PR must justify it.

---

## Discrimination Sensor

Run in a scratch `git worktree` (detached HEAD) under the session scratchpad, with `.terraform` copied in.
Python mutants ran `python -m unittest discover -s lambdas/vigia`. TF mutants ran the full `terraform test`.
I confirmed that the TF kills are assertion failures, for example "grupo de log … com 14 dias", "policy do vigia difere do mínimo da spec" and the runtime assert. The unmutated scratch was green.

| # | File:line | Mutation | Result |
| - | --------- | -------- | ------ |
| M1 | `handler.py:142` | reminder `>=` → `>` | ✅ Killed |
| M2 | `handler.py:19` | LEMBRETE 3 h → 2h59 | ✅ Killed |
| M3 | `handler.py:86` | frescor `>` → `>=` | ✅ Killed |
| M4 | `handler.py:139` | alert `desde = agora` | ✅ Killed |
| M5 | `handler.py:166` | write state even when Telegram fails | ✅ Killed |
| M6 | `handler.py:20` | TIMEOUT_S 10 → 15 | ✅ Killed |
| M7 | `handler.py:148` | recovery duration from `ultimo_aviso` | ✅ Killed |
| M8 | `handler.py:145` | reminder resets `desde` | ✅ Killed |
| M9 | `handler.py:101` | `status != 200` → `status >= 400` | ❌ Survived |
| M9b | `handler.py:101` | accept 204 as ok | ❌ Survived |
| M10 | `handler.py:118` | AccessDenied on missing state re-raised | ✅ Killed |
| M11 | `handler.py:165` | log `e.url` (token URL) on send failure | ✅ Killed |
| M12 | `handler.py:58` | times in UTC instead of Brasília | ✅ Killed |
| M13 | `handler.py:151` | ok→ok writes state | ✅ Killed |
| M14 | `handler.py:210` | `WithDecryption=False` | ✅ Killed |
| M15 | `handler.py:149` | recovery state `{**estado, situacao: ok}` (keeps old `desde`/`ultimo_aviso`) | ❌ Survived |
| T1 | `vigia.tf:27` | retention 14 → 30 | ✅ Killed |
| T2 | `vigia.tf:157` | Scheduler retry 0 → 1 | ✅ Killed |
| T3 | `vigia.tf:114` | invoke config retry 0 → 2 | ✅ Killed |
| T4 | `vigia.tf:51` | extra `s3:ListBucket` | ✅ Killed |
| T5 | `vigia.tf:146` | `rate(5 minutes)` | ✅ Killed |
| T6 | `vigia.tf:61` | PutObject on `_estado/*` | ✅ Killed |
| T7 | `vigia.tf:102` | `LIMIAR_MIN = "60"` | ✅ Killed |
| T8 | `vigia.tf:91` | `python3.11` | ✅ Killed |
| T9 | `vigia.tf:12` | add `data "aws_ssm_parameter"` | ✅ Killed |
| T10 | `vigia.tf:81` | extra `logs:CreateLogGroup` | ✅ Killed |
| T11 | `vigia.tf:139` | Scheduler role invoke `Resource = "*"` | ✅ Killed |

**Sensor depth**: expanded (27 mutants)
Result (round 1, historical): 24/27 killed, 3 survived; gaps fixed in `3d06caf`
**Isolation**: real tree `git status --porcelain` was empty before and after; the scratch worktree was removed and pruned.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code | ✅ (`handler.py` ~210 lines: dataclass config, small pure functions) |
| Surgical changes | ✅ (only the `iam.tftest.hcl` tab→space change outside the feature, needed by `fmt -check`) |
| No scope creep | ✅ |
| Matches patterns | ✅ (mock provider + `tests/inspecao`, same as BSV-4/21) |
| Spec-anchored outcome check | ⚠️ AVI-05 state and VER-04 non-403 statuses not pinned |
| Per-layer coverage | ✅ AVI/VER map 1:1 to tests; INF via exact equality |
| No unclaimed tests | ✅ (`test_limiar_configuravel`, `test_config_do_ambiente`, `HttpGetReal`, `LambdaHandler` support INF-01 env / VER-05 / AVI-06) |
| Guidelines | `CLAUDE.md` rules 1, 5, 7, 11 |

---

## Gate Check

- **Commands** (in `infra/`): `terraform fmt -check -recursive` (exit 0), `terraform validate` (Success), `terraform test` (9 passed, 0 failed), `python -m unittest discover -s lambdas/vigia -v` (32 OK), `cd functions && npm test` (14 pass)
- **Test count before feature**: 7 tf runs, 0 Python, 14 Node. **After**: 9 tf runs (+2), 32 Python (+32), 14 Node
- **Skipped / failures**: none. No test was weakened: the `iam.tftest.hcl` change is whitespace only.

---

## Real-world risks (not visible to tests)

- **R1 (low, verified by reasoning)**: Without `s3:ListBucket`, S3 returns 403 for a missing key. The code expects `AccessDenied` from GetObject and `"403"` from HeadObject (no body on HEAD), which is right. The cost is that a *real* permission error on `_estado/vigia.json` is also treated as "no state". During an outage that would send ⚠️ every 10 min (spam), not silence. The policy is pinned by exact equality, so the chance is low.
- **R2 (low)**: Uncaught exceptions write a traceback with the botocore message into the logs. These come from `put_object` at `handler.py:167` and from non-403 errors re-raised at `handler.py:119`. An AccessDenied message includes the assumed-role ARN, which AVI-08 says logs must not contain. If `put_object` fails after a successful send, the next cycle repeats the message.
- **R3 (uncertain)**: `archive_file` stores the file mode in the zip. Windows and Linux report different modes (0666 vs 0644), so `output_base64sha256` may differ between OSes despite `.gitattributes` LF. The result would be a `source_code_hash` change when planning from another OS. Fix: `output_file_mode = "0644"` in `data.archive_file.vigia` (`vigia.tf:19-23`).
- **R4 (low)**: The urllib `timeout` applies per socket operation, not in total. A slow trickle can exceed 10 s. Lambda `timeout = 30` bounds it.
- **R5 (info)**: For the AWS-managed `aws/ssm` key, the key policy already allows use through SSM for principals in the account, so the explicit `kms:Decrypt` is probably redundant. It is harmless and the ticket asks for it (uncertain).
- **R6 (info)**: README `put-parameter --value "$TOKEN"` keeps the token out of history, but it is visible in the process list while the command runs. Acceptable on a single-user machine.
- Checked and OK: HeadObject `LastModified` is a tz-aware datetime (botocore `tzutc`), so `agora - modificado` is valid. Logs go to the pre-created group (no `CreateLogGroup` needed). The Scheduler Lambda target is an async invoke, and the event-invoke-config retry 0 applies. The site bucket uses default SSE-S3 with no Deny statements.

---

## Fix Plans

### Fix 1 (Major): AVI-05 recovery state not asserted
- **Root cause**: `TH:136` checks only `situacao`.
- **Fix task**: in `test_sequencia_completa`, assert `c.s3.estado() == {"situacao": "ok", "desde": "2026-10-01T18:30:00Z", "ultimo_aviso": "2026-10-01T18:30:00Z"}`.
- **Done when**: mutant M15 is killed.

### Fix 2 (Minor): VER-04 "status ≠ 200" only exercised with 403
- **Fix task**: in `Disponibilidade`, add `test_status_diferente_de_200` over `(204, b'{"versao":1}')` and `(500, b"")`, asserting `"HTTP 204"`/`"HTTP 500"` in the message.
- **Done when**: mutants M9/M9b are killed.

### Fix 3 (Minor, bookkeeping)
- Tick the T3 "Done when" boxes and set Status `Done` in `tasks.md`.

### Fix 4 (Optional, risks)
- R3: `output_file_mode = "0644"`.
- R2: wrap `put_object` and log `codigo_erro(e)`.

---

## Requirement Traceability Update

| Requirement | Previous | New |
| ----------- | -------- | --- |
| VER-01..03, VER-05, AVI-01..04, AVI-06..08, INF-01..07, OPS-03, OPS-04 | Done | ✅ Verified |
| VER-04 | Done | ❌ Needs Fix (test precision) |
| AVI-05 | Done | ❌ Needs Fix (test precision) |

---

## Summary

**Overall**: ❌ Not Ready (test-only fixes; implementation matches spec)

**Spec-anchored check**: 20/22 ACs matched; 2 gaps (AVI-05, VER-04)
**Sensor**: 24/27 killed
**Gate**: all green

**Next steps**: Fix 1-3 → re-verify; then the owner's real run (SSM params, `plan` only `to add`, `apply`, `lambda invoke`, 40-min outage) before merge.

---

## Round 2 (fix commit `3d06caf`)

**Diff range**: `82aa7ab..3d06caf` (whole feature: `e24a757..3d06caf`)

### Gate
In `infra/`:
- `terraform fmt -check -recursive`: exit 0.
- `terraform validate`: Success.
- `terraform test`: 9 passed, 0 failed.
- `python -m unittest discover -s lambdas/vigia`: 35 OK (+3).
- `npm test`: 14 pass.
- No test removed or weakened.

### Round-1 gaps
| Gap | Evidence | Status |
| --- | -------- | ------ |
| 1. AVI-05 recovery state | `infra/lambdas/vigia/test_handler.py:136-138` `assertEqual(c.s3.estado(), {"situacao": "ok", "desde": "2026-10-01T18:30:00Z", "ultimo_aviso": "2026-10-01T18:30:00Z"})` | ✅ Closed (M15 killed) |
| 2. VER-04 status ≠ 200 | `infra/lambdas/vigia/test_handler.py:190-194` 204 → `"HTTP 204"`, 500 → `"HTTP 500"` | ✅ Closed (M9, M9b killed) |
| 3. tasks.md T3 | `.specs/features/BSV-15/tasks.md` Status `Done`, T3 boxes ticked | ✅ Closed |
| R2. ARN in logs | `infra/lambdas/vigia/handler.py:168-179` PutObject → `"falha_estado"` + log of the code only; `:118-120` unexpected GetObject → `RuntimeError(f"...{codigo}") from None`; tests `test_handler.py:273-288`, `:290-304` | ⚠️ Mostly closed (N7 survives) |
| R3. zip mode | `infra/vigia.tf:24` `output_file_mode = "0644"` | ⚠️ Implemented but not asserted (T12/T13 survive) |
| R1 | accepted by the owner as is | — |

AVI-05 and VER-04 now match the spec-defined outcome, so 22/22 ACs are spec-anchored.

### Discrimination sensor (round 2)
Ran in a fresh scratch worktree (detached `3d06caf`) with `.terraform` copied in. Every mutant was applied and then the original file was restored.
The unmutated scratch was green before the run. Afterwards the scratch was removed and pruned, and the real tree's `git status --porcelain` was empty before and after.

| # | File:line | Mutation | Result |
| - | --------- | -------- | ------ |
| M9 | `handler.py:102` | `status != 200` → `status >= 400` | ✅ Killed |
| M9b | `handler.py:102` | accept 204 | ✅ Killed |
| M15 | `handler.py:150` | recovery state keeps old `desde`/`ultimo_aviso` | ✅ Killed |
| N1 | `handler.py:179` | PutObject failure returns `"avisado"` | ✅ Killed |
| N2 | `handler.py:179` | PutObject failure re-raises | ✅ Killed |
| N3 | `handler.py:178` | PutObject failure logs `e` (message with ARN) | ✅ Killed |
| N4 | `handler.py:178` | PutObject failure not logged | ✅ Killed |
| N5 | `handler.py:120` | `RuntimeError` message includes `str(e)` | ✅ Killed |
| N6 | `handler.py:120` | `from None` → `from e` | ✅ Killed |
| N7 | `handler.py:120` | `from None` removed (implicit `__context__` chaining) | ❌ Survived |
| N8 | `handler.py:120` | unexpected GetObject error swallowed as `{}` | ✅ Killed |
| N9 | `handler.py:119` | GetObject failure logs `e` | ✅ Killed |
| T12 | `vigia.tf:24` | `output_file_mode` removed | ❌ Survived |
| T13 | `vigia.tf:24` | `output_file_mode = "0666"` | ❌ Survived |

Result (round 2, historical): 11/14 killed, 3 survived; gaps fixed in `f93662c`

Why they survive:
- **N7**: `test_handler.py:304` asserts only `__cause__ is None`. Without `from None`, `__cause__` is still `None`, but `__context__` holds the botocore `ClientError` and is no longer suppressed. A standard traceback would print it ("During handling of the above exception…"), message and ARN included.
  Whether the Lambda Python runtime prints the chained context is **uncertain**: I could not fetch the `awslambdaric` source offline. If the runtime does not print it, the mutant is equivalent in production. The test still does not guard what it claims to guard.
- **T12/T13**: `infra/tests/vigia.tftest.hcl` has no assertion on `data.archive_file.vigia.output_file_mode`.

### Fix plans (round 2)
- **Fix 5 (Minor)**:
  - Change: in `test_erro_inesperado_ao_ler_estado_nao_vaza_mensagem` (`test_handler.py:304`), add `self.assertTrue(ctx.exception.__suppress_context__)`. An alternative that checks the rendered output is `self.assertNotIn("arn:", "".join(traceback.format_exception(ctx.exception)))`.
  - Done when: N7 is killed.
- **Fix 6 (Minor)**:
  - Change: in `infra/tests/vigia.tftest.hcl` (`run "vigia"`), add `assert { condition = data.archive_file.vigia.output_file_mode == "0644" ... }`.
  - Done when: T12/T13 are killed.

### Round 2 verdict (historical)
Not passed in round 2. Both fixes are test-only and one line each. All spec ACs pass, and the implementation is unchanged by these fixes.
After them, round 3 is the last allowed iteration. The owner's real run (SSM params, `plan` only `to add`, `apply`, `lambda invoke`, 40-min outage) still blocks the merge.

---

## Round 3 (fix commit `f93662c`, final iteration)

**Diff range**: `4cc0b50..f93662c` (whole feature: `e24a757..f93662c`). Test-only change; `handler.py` and `vigia.tf` are unchanged.

### Gate
In `infra/`:
- `terraform fmt -check -recursive`: exit 0.
- `terraform validate`: Success.
- `terraform test`: 9 passed, 0 failed.
- `python -m unittest discover -s lambdas/vigia`: 35 OK.
- `npm test`: 14 pass.

### Round-2 gaps
| Gap | Evidence | Status |
| --- | -------- | ------ |
| N7: chained context not suppressed | `infra/lambdas/vigia/test_handler.py:305` `assertTrue(ctx.exception.__suppress_context__)` | ✅ Closed |
| T12/T13: zip mode not asserted | `infra/tests/vigia.tftest.hcl:23` `data.archive_file.vigia.output_file_mode == "0644"` | ✅ Closed |

### Discrimination sensor (round 3)
Fresh scratch worktree (detached `f93662c`) with `.terraform` copied in. I re-ran all 14 round-2 mutants, not just the three survivors. The unmutated scratch was green before the run. Afterwards the scratch was removed and pruned, and the real tree's `git status --porcelain` was empty before and after.

| # | Mutation | Result |
| - | -------- | ------ |
| N7 | `handler.py:120` `from None` removed | ✅ Killed |
| T12 | `vigia.tf:24` `output_file_mode` removed | ✅ Killed (assertion "modo fixo no zip…") |
| T13 | `vigia.tf:24` `output_file_mode = "0666"` | ✅ Killed (same assertion) |
| M9, M9b, M15, N1-N6, N8, N9 | regression re-run | ✅ 11/11 Killed |

Across the three rounds, all 41 distinct mutants were killed in their final run (27 round 1 + 14 round 2; M9/M9b/M15 overlap).

**Result**: 14/14 killed → PASS

### Remaining (non-blocking for this verdict)
- R1 (spam when AccessDenied on the state file is real) was accepted by the owner. R4-R6 are informational.
- Ticket deviation to record as an AD: the runtime `boto3` instead of stdlib-only. New provider `hashicorp/archive` 2.8.1, to justify in the PR (CLAUDE.md rule 7).
- **Merge blocker**: the owner's real run. Create the 2 SSM params, `plan` only `to add` / `0 to change` / `0 to destroy`, `apply`, `aws lambda invoke` → `sem_aviso`, stop the worker 40 min → ⚠️, re-enable it → ✅.

### Requirement Traceability (final)
VER-01..05, AVI-01..08, INF-01..07, OPS-03, OPS-04: ✅ Verified (22/22).
