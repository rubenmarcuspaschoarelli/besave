# BSV-13b Validation

**Verdict:** PASS

**Date**: 2026-09-30
**Spec**: `.specs/features/BSV-13b/spec.md` (LST-01..07, TMP-01..02) + `docs/specs/BSV-13b.md`
**Diff range**: `9a9b6e3..35fb697` (ef0b6d4, 3184693, e2e4d00, 35fb697), pasta `apps/worker/`
**Verifier**: independente (autor ≠ verificador)

Critério real do dono (duas `--publicar --sim`, 2ª < 2 min, `aws s3 ls` antes/depois, tempos por fase no PR) e hipótese da anomalia com `file:line` no PR **não são verificáveis aqui** e continuam bloqueando o merge (regra "real run before merge").

---

## Task Completion

Sem `tasks.md` (ticket pequeno, 3 steps na tabela de rastreabilidade da spec). Os 3 commits de código correspondem a Step 1 (3184693, LST-07), Step 2 (e2e4d00, LST-01..06) e Step 3 (35fb697, TMP-01..02).

---

## Spec-Anchored Acceptance Criteria

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --- | --- | --- | --- |
| LST-01: 5000 ids com as duas chaves | 0 `existe`, 0 `existem`, ≤ 10 `listar`, `publicadas=0`, `reaproveitadas=5000` | `apps/worker/tests/imagens.rs:523` `assert_eq!(p.existe_chamadas(), 0)`; `:524` `assert_eq!(p.existem_chamadas(), 0)`; `:526` `p.listar_chamadas() <= 10`; `:530` `assert_eq!(rel.publicadas, 0)`; `:531` `assert_eq!(rel.reaproveitadas, 5000)`; `:533` nenhuma gravação nova | ✅ PASS |
| LST-02: id sem chave | publicado, as duas chaves gravadas | `apps/worker/tests/imagens.rs:554` `assert_eq!(rel.publicadas, 3)`; `:559`/`:563` `novas.contains(&chave_small/grande(id))` para 7001; `:566-567` bytes do destino = origem | ✅ PASS |
| LST-03: id com só uma chave | publicado, **as duas** chaves regravadas | mesmo teste, ids 7002 (só small) e 7003 (só grande): `apps/worker/tests/imagens.rs:559`, `:563` | ✅ PASS |
| LST-04: placeholder existente / ausente | existente não regravado; ausente gravado | `apps/worker/tests/imagens.rs:585-588` `&p.gravacoes()[antes..] == [chave_placeholder(ausente)]` (exato); `:590` sem `existe`/`existem` | ✅ PASS |
| LST-05: `listar` falha (cada prefixo) | `ErroGeracao::Imagens(ErroImagens::Listagem{prefixo})`, sem `manifest.json` | `apps/worker/tests/geracao.rs:789-793` `matches!(… Listagem { prefixo: pr, .. } if *pr == prefixo)` para `img/ofertas/` e `img/placeholder/`; `:795` mensagem contém o prefixo; `:796` `!existe("manifest.json")`; `:798` nenhuma gravação `img/` | ✅ PASS |
| LST-06: chave estranha | contada em `chaves_estranhas`, não vale como imagem, não removida | `apps/worker/tests/imagens.rs:614` `assert_eq!(rel.chaves_estranhas, 4)`; `:615` `publicadas == 1` (a `5412_small.webp` não completa o par); `:617` `remocoes().is_empty()`; `:619` todas ainda existem | ✅ PASS |
| LST-07: contadores separados | `listar`, `existe`, `existem` contados à parte; `existem` não infla `existe` | `apps/worker/tests/publicador.rs:151` `existe_chamadas()==1`; `:152` `existem_chamadas()==2`; `:153` `listar_chamadas()==3` | ✅ PASS |
| TMP-01: 9 medidas em ms no `Relatorio`, sub ≤ fase | presença (não valores) + `imagens_listagem ≤ imagens`, `redirects_listagem ≤ redirects` | `apps/worker/tests/geracao.rs:811-821` desestruturação exaustiva de `Tempos` (campo a mais/menos não compila); `:822` `imagens_listagem <= imagens`; `:823` `redirects_listagem <= redirects` | ✅ PASS |
| TMP-02: binário imprime uma linha por medida + `imagens_chaves_estranhas` | 9 linhas `t_<fase>: <n> ms` | `apps/worker/tests/dry_run.rs:363` linha com prefixo existe; `:366` sufixo ` ms`; `:368` valor `u64`; `:370` `imagens_chaves_estranhas: 0` | ✅ PASS (só `--gerar`; ver lacuna 3) |

Critérios do `docs/specs/BSV-13b.md` que não dependem de AWS: todos mapeados acima + gate abaixo.

### Regras da spec do dono

| Regra | Evidência | Result |
| --- | --- | --- |
| `publicar_imagens` não chama `existe`/`existem` | `apps/worker/src/imagens.rs:314` decide por `existentes.ofertas.contains(..)`; `:210` placeholders por `existentes.placeholders`; único `existe` restante em `gerar` é de chunk (`apps/worker/src/geracao.rs:239`) | ✅ |
| `existem` continua no trait e com pool no S3 | `apps/worker/src/publicador.rs:144` (default); `apps/worker/src/aws.rs:211` (pool `MAX_EM_VOO`), `aws.rs` sem diff | ✅ |
| Listagem que falha → erro nomeado, aborta antes do manifest | `apps/worker/src/imagens.rs:234` `map_err(.. ErroImagens::Listagem { prefixo, fonte })`; `apps/worker/src/geracao.rs:206` antes de chunks/manifest | ✅ |
| Nada persistido em `_estado/` | `grep _estado apps/worker/src/imagens.rs` → vazio; conjunto só em memória (`imagens.rs:222-226`) | ✅ |
| Sem dependência nova, sem mudança de contrato/MANIFEST/headers | `git diff --stat 9a9b6e3..HEAD -- Cargo.toml Cargo.lock packages docs/CONTRATO.md docs/MANIFEST.md` vazio; `std::time::Instant`/`Cell` apenas | ✅ |
| `gerar()` só mudou para tempos e mecanismo de existência | diff de `apps/worker/src/geracao.rs`: `Instant`s, decorator `ListagemCronometrada` (`:99-116`, só mede `listar`), `ImagensExistentes::listar` + `publicar_imagens_com` (`:206-208`), variante `ErroGeracao::Imagens` | ✅ |
| `--publicar` sem `--sim` (plano) lista no destino real | `apps/worker/src/plano.rs:90` `listar` delega ao destino | ✅ |

**Status**: ✅ 9/9 ACs cobertos, valores afirmados batem com a spec.

---

## Discrimination Sensor

Worktree temporário (`git worktree add --detach <scratchpad>/mut HEAD`), mutações aplicadas lá, `cargo test --no-fail-fast --test imagens --test geracao --test publicador --test dry_run`, arquivo restaurado entre mutantes; worktree removido ao final.

| # | File:line | Mutação | Killed? (por) |
| --- | --- | --- | --- |
| M1 | `src/imagens.rs:314` | `&&` → `\|\|` (reaproveita com só uma chave) | ✅ `id_novo_e_id_com_uma_so_chave_gravam_as_duas`, `apenas_uma_chave_existente_nao_e_reaproveitada`, `chaves_estranhas_…` |
| M2 | `src/imagens.rs:311` | volta a chamar `pub_.existem` por bloco | ✅ `cinco_mil_ids_existentes_decididos_so_por_listagem` |
| M3 | `src/imagens.rs:234` | erro de `listar` engolido como `Vec::new()` | ✅ `listagem_de_imagens_falhando_aborta_sem_manifest` |
| M4 | `src/imagens.rs` `chave_de_oferta_valida` | sempre `true` (estranha conta como válida) | ✅ `chaves_estranhas_contadas_ignoradas_e_mantidas` |
| M5 | `src/imagens.rs:242` | `estranhas += 0` (não conta) | ✅ `chaves_estranhas_contadas_ignoradas_e_mantidas` |
| M6 | `src/imagens.rs:210` | filtro de placeholder removido (regrava existentes) | ✅ `placeholder_existente_…`, `cinco_mil_…`, `placeholders_publicados_uma_vez_…`, `falha_na_kvs_…` |
| M7 | `src/geracao.rs:308-309` | troca `imagens` ↔ `imagens_listagem` (sub > fase-mãe) | ✅ `relatorio_traz_tempo_por_fase` (dependente de tempo: mata quando a fase de imagens leva ≥ 1 ms além da listagem) |
| M8 | `src/main.rs:221` | não imprime `t_orfaos` | ✅ `gerar_fake_imprime_tempo_por_fase` |
| M9 | `src/imagens.rs:245` | placeholders listados em `img/ofertas/` | ✅ `placeholder_existente_…`, `listagem_de_imagens_falhando_…` e outros |
| M10 | `src/publicador.rs:314` | `existem` incrementa contador de `existe` | ✅ `memoria_conta_listar_existe_e_existem_separadamente` |
| M11 | `src/geracao.rs:313` | `redirects_listagem` + 1e6 (sub > fase-mãe) | ✅ `relatorio_traz_tempo_por_fase` |
| M12 | `src/imagens.rs:242` | chave estranha também inserida no conjunto `ofertas` | ⚪ Sobreviveu — **equivalente**: a busca é por chave exata `img/ofertas/{id}[-small].webp`, que por construção nunca é "estranha"; não há comportamento observável a detectar |

**Sensor depth**: expandido (12 mutações; caminho de custo/integridade de publicação)
**Result**: 11/11 não equivalentes mortos; 1 equivalente — ✅ PASS

Isolamento: `git status --porcelain` da árvore real vazio antes e depois; `git worktree list` sem o scratch.

---

## Code Quality

| Principle | Status |
| --- | --- |
| Minimum code / surgical changes | ✅ (`aws.rs`, contrato, MANIFEST intocados) |
| No scope creep | ✅ (KVS, agendamento, `_estado/` fora) |
| Matches patterns (`thiserror` na lib, sem `unwrap` fora de teste) | ✅ (`ms()` usa `try_from(..).unwrap_or(u64::MAX)`) |
| Asserted values match spec | ✅ |
| Every new test maps to an AC | ✅ (8 testes novos: LST-01..07, TMP-01, TMP-02; `relatorio_com_contagens` só recebeu campos novos) |
| Guidelines: `CLAUDE.md`, `apps/worker/CLAUDE.md` | ✅ |

---

## Edge Cases

- [x] `5412_small.webp` + `5412.webp` → id publicado: `apps/worker/tests/imagens.rs:602-615`.
- [x] Lista de ids vazia → só decisão de placeholders: `apps/worker/tests/imagens.rs:583`.

---

## Gate Check

- **Comando**: `cd apps/worker && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` (sem rede)
- **Resultado**: fmt OK, clippy OK, **215 passed, 0 failed, 3 ignored** (ignorados preexistentes, nenhum `#[ignore]` no diff)
- **Test count antes**: 207 · **depois**: 215 · **Delta**: +8

---

## Lacunas (ranqueadas; nenhuma bloqueia o PASS de código)

1. **Critério real e DoD pendentes (bloqueia merge, não o código)**: duas `--publicar --sim`, 2ª < 2 min, `aws s3 ls` agrupado por data antes/depois, tempos por fase no PR e hipótese da anomalia com `file:line` (spec do dono, Solução 5). Nada disso está no branch; é trabalho do dono/PR.
2. **TMP-01 é pouco discriminante quanto a valores** (por decisão da spec, "presença, não valores"): com a fixture pequena quase tudo mede 0 ms, e `≤` passa com 0 = 0. M7 morreu só porque a fase de imagens levou ≥ 1 ms além da listagem; uma medida zerada ou trocada entre fases irmãs (ex.: `t_chunks` ↔ `t_paginas`) não seria detectada. `apps/worker/tests/geracao.rs:822-823`. Precisão da spec: aceita.
3. **TMP-02 testado só em `--gerar`**: `--publicar` usa a mesma `imprimir_relatorio` (`apps/worker/src/main.rs:138` e `:167`), mas não há teste; exigiria AWS. O teste também não verifica que cada linha aparece **uma** vez (`apps/worker/tests/dry_run.rs:363` usa `find`).
4. **Imprecisão factual da spec do dono**: "`existem` continua no trait (chunks usam)". Chunks usam `existe` (`apps/worker/src/geracao.rs:239`); depois deste diff, `existem` não tem nenhum chamador em produção. Mantê-lo cumpre a regra, mas o dono deveria saber que agora é código morto no caminho de produção.
5. **Comentário desatualizado**: `apps/worker/src/publicador.rs:140-141` diz que o `existem` default é "usado por `PublicadorLocal`/`PublicadorMemoria`", mas `PublicadorMemoria` passou a sobrescrevê-lo (`publicador.rs:313`). Cosmético.
6. **LST-01 exercita `publicar_imagens` (atalho), não `gerar`**: o caminho de `gerar` (`publicar_imagens_com`, `apps/worker/src/geracao.rs:206-208`) é coberto indiretamente (M2 na função compartilhada `processar_bloco` foi morto); não há asserção de contadores ponta a ponta em `gerar`.

---

## Requirement Traceability Update

| Requirement | Previous | New |
| --- | --- | --- |
| LST-01..07 | Done | ✅ Verified |
| TMP-01..02 | Done | ✅ Verified |

---

## Summary

**Overall**: ✅ Pronto no código; merge ainda bloqueado pela execução real do dono.
**Spec-anchored check**: 9/9 ACs batem com a spec; 0 spec-precision gaps bloqueantes (TMP-01/02 são presença por definição).
**Sensor**: 11/11 mortos (+1 equivalente).
**Gate**: 215 passed, 0 failed.
