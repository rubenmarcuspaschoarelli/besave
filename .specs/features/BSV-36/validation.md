# BSV-36 — Validação

## Validation: BSV-36 — PASS (iteração 2 de 3)

**Veredito:** PASS. O commit `f39f7e6` fecha as lacunas 1 e 2 da iteração 1. A mutação que gravava no Oracle um valor diferente do `dp` publicado (W9) agora morre, assim como W13 e as variantes do SELECT. Ficam 2 sobreviventes. Os dois são linhas de ligação dentro de métodos de `OracleFonte` que só rodam com conexão Oracle viva, e o teste real do dono (que bloqueia o merge) pega os dois. Ver "Resíduo aceito".

- **Quem verificou:** Verifier independente, sub-agente; autor ≠ verificador. Não alterou código nem testes. A única escrita no worktree real é este arquivo.
- **Data:** 2026-10-07
- **Diff verificado:** `31a86f4..f39f7e6` (4 commits: 357c31a, e9a3694, f671459 e a correção f39f7e6, que mexe só em `apps/worker/src/oracle.rs` +21/−7 e `apps/worker/tests/oracle.rs` +58).

### Gates da iteração 2

| gate | saída |
| ---- | ----- |
| worker `cargo fmt --check` | exit 0 |
| worker `cargo clippy --all-targets -- -D warnings` | exit 0 |
| worker `cargo test` (`CARGO_TARGET_DIR=C:\cargo-target\besave`, jobs 2) | exit 0: **435 passaram, 0 falharam, 3 ignorados** (+2 em relação à iteração 1: os dois testes novos em `tests/oracle.rs`) |
| contrato, site | não mudaram desde f671459; valem os resultados da iteração 1 (validate OK; site 70/70, lint, check e build ok) |

### Lacunas da iteração 1, conferidas

| Lacuna | Evidência `arquivo:linha` + asserção | Situação |
| ------ | ------------------------------------ | -------- |
| 1. binds do UPDATE (GRV-01, W9/W13) | `apps/worker/src/oracle.rs:153` `binds_publicacao_site` (função pura), usada em `apps/worker/src/oracle.rs:234`; teste `apps/worker/tests/oracle.rs:211-218`: `binds_publicacao_site(1_791_374_437, -10_800) == [1_791_374_400-10_800, 1_791_244_800-10_800, 1_791_374_400-10_800]` (instante truncado, limite 2026-10-06 e fuso −03:00) e `:220-223` com relógio antigo `[…, -10_800, …]` | ✅ Fechada |
| 2. leitura da coluna (DP-01, W10) | `apps/worker/src/oracle.rs:160` `COL_DT_PUBLICACAO_SITE = 15`, usada em `apps/worker/src/oracle.rs:200`; teste `apps/worker/tests/oracle.rs:199-205`: 16 colunas, `cols[14] == "DS_URL_AFILIADO"`, `cols[COL_DT_PUBLICACAO_SITE] == "ROUND((DT_PUBLICACAO_SITE - DATE '1970-01-01') * 86400) - :desloc"` | ✅ Fechada para o SQL e a posição. A linha `r.get(...)` em si continua sem teste (ver resíduo) |

Conferi o sinal do fuso: `:desloc` = `fuso_segundos` = local − UTC (−10 800 em Brasília). A leitura faz `local − desloc` = UTC e o bind faz `UTC + fuso` = local, então as duas pontas são coerentes.

Com isso, o GRV-01 passa a ✅. Ficam 18/18 ACs com evidência.

### Sensor da iteração 2 (worktree temporário em f39f7e6, sem `git stash`)

| # | Arquivo | Mutação | Resultado | Teste que matou |
| - | ------- | ------- | --------- | --------------- |
| R9 (= W9) | `apps/worker/src/oracle.rs:156` | binds `[min, instante, instante]` | ✅ Morto | `tests/oracle.rs:211` grv_01_binds |
| R13 (= W13) | `apps/worker/src/oracle.rs:156` | limite inferior sem `+ fuso` | ✅ Morto | `tests/oracle.rs:211` |
| R14 | `apps/worker/src/oracle.rs:155` | instante sem `+ fuso` | ✅ Morto | `tests/oracle.rs:211` |
| R15 | `apps/worker/src/oracle.rs:156` | limite superior `instante + 60` | ✅ Morto | `tests/oracle.rs:211` |
| R10b | `apps/worker/src/oracle.rs:107-108` | SELECT sem `DT_PUBLICACAO_SITE` | ✅ Morto | `tests/oracle.rs:199` |
| R10c | `apps/worker/src/oracle.rs:160` | `COL_DT_PUBLICACAO_SITE = 14` | ✅ Morto | `tests/oracle.rs:201` |
| R10d | `apps/worker/src/oracle.rs:108` | coluna lida sem `epoch_utc!` (sem conversão para UTC) | ✅ Morto | `tests/oracle.rs:201` |
| R7 (= W7) | `apps/worker/src/oracle.rs:141` | `SET … = SYSDATE` | ✅ Morto | `tests/publicacao_site.rs:120` |
| R10a (= W10) | `apps/worker/src/oracle.rs:200` | `dt_publicacao_site: None` em vez de `r.get(COL…)` | ❌ Sobreviveu (resíduo aceito) | — |
| R16 | `apps/worker/src/oracle.rs:234` | `binds_publicacao_site(agora, 0)` (chamada sem fuso) | ❌ Sobreviveu (resíduo aceito) | — |

**Placar da iteração 2:** 8 de 10 mortos. No acumulado das iterações 1 e 2, o único caminho de produção ainda sem discriminação são as 2 linhas de ligação acima. Isolamento: o `git status --porcelain` do worktree real era `?? .specs/features/BSV-36/validation.md` antes e depois; o worktree temporário foi removido e foi feito `git worktree prune`.

### Resíduo aceito (por que não bloqueia o PASS)

- R10a e R16 estão dentro de `impl FonteOfertas for OracleFonte`, cujos métodos exigem `oracle::Connection` viva. A matriz de cobertura da tasks.md declara essa camada "build gate only", e o repositório não tem dublê da conexão.
- Os dois são pegos pelo critério real do dono, que bloqueia o merge ("segundo ciclo → `chunks_escritos=0`"):
  - **R10a:** todo `dp` vira o instante do ciclo, então os chunks mudam em todo ciclo.
  - **R16:** grava UTC como se fosse hora local, e a releitura fica 3 h no futuro. O valor cai fora da faixa, vem WARN e a coluna é regravada a cada ciclo, então os chunks também mudam sempre.
- O caso perigoso da iteração 1 (W9, em que o banco ficava estável com valor errado e o teste real não percebia) agora está coberto.

### Lacunas restantes (não bloqueiam)

1. **[Processo] Execução real do dono** continua bloqueando o merge. No roteiro: primeiro ciclo regrava os chunks (anotar tempo e `bytes_totais`); segundo ciclo → `chunks_escritos=0` (pega R10a e R16); `SELECT ID_OFERTA, DT_PUBLICACAO_SITE` de uma oferta nova, conferido contra o `dp` do chunk (hora local = UTC − 3 h).
2. **[Info] Margem do ORC-01** em ~10 B (218–221 B contra 230); o gate do chunk está em ~33 KB de 60 KB.
3. **[Info] Instabilidade do vitest em execução fria** (uma vez, 2/70); acompanhar no CI.
4. **[Info] Lacunas de precisão da spec** registradas na iteração 1 (prova da conversão TZ sem Oracle; ORC-01 medido pelo gerador TS).

---

## Histórico — iteração 1 (diff `31a86f4..f671459`)

Veredito da iteração 1: reprovado (3 mutantes sobreviventes no `OracleFonte`). Mantido abaixo sem alterações, exceto este cabeçalho.

**Veredito da época:** reprovado. Os 18 ACs têm teste com valor da spec e os gates estão verdes, mas 3 mutantes sobreviveram no `OracleFonte`. Um deles (W9, binds do `UPDATE` trocados) grava no Oracle de produção um valor diferente do `dp` publicado, e é justamente o que o GRV-01 proíbe. As correções são pequenas (lacunas 1 e 2).

- **Quem verificou:** Verifier independente, sub-agente; autor ≠ verificador. Não herdou o contexto do autor. Não alterou código nem testes. A única escrita no worktree real é este arquivo.
- **Data:** 2026-10-07
- **Spec:** `.specs/features/BSV-36/spec.md` (do dono: `docs/specs/BSV-36.md`)
- **Diff verificado:** `31a86f4..f671459` (357c31a contrato+card, e9a3694 UPDATE/leitura Oracle, f671459 site); 36 arquivos, +842/−105. `origin/develop` é ancestral de HEAD.

---

## Conclusão das tarefas

| Task | Status | Notas |
| ---- | ------ | ----- |
| T1 contrato 1.5.0 + `dp` no card | ✅ Feito | — |
| T2 leitura/gravação `DT_PUBLICACAO_SITE` | ⚠️ Parcial | O fake está coberto; o caminho Oracle real (binds, coluna 16) não tem teste. Ver lacunas 1 e 2 |
| T3 site `dp` + `maioresDescontos` + orçamento | ✅ Feito | — |

---

## Gates (o runner decide)

| gate | comando | saída |
| ---- | ------- | ----- |
| contrato | `npm ci && npm run validate` | `contrato OK`: 4/4 fixtures PASS; `chunk-invalido.json` rejeitado com 5 erros em 5 registros (o id 5, sem `dp`, falha sozinho) |
| worker fmt | `cargo fmt --check` | ok |
| worker clippy | `cargo clippy --all-targets -- -D warnings` | exit 0 |
| worker test | `cargo test` (`CARGO_TARGET_DIR=C:\cargo-target\besave`, jobs 2) | **433 passaram, 0 falharam, 3 ignorados** (os ignorados já existiam: `ciclo`, `imagens`, `paginas`) |
| site | `corepack pnpm install --frozen-lockfile` / `lint` / `check` / `test` / `build` | todos exit 0; check: 0 erros, 0 avisos; **70/70 testes** em 6 arquivos; build ok |

Observação: na primeira execução fria do vitest no worktree temporário, 2 testes falharam (68/70). Duas execuções seguintes deram 70/70, e no worktree real foi 70/70. É provável que sejam timeouts sob carga. Não afeta o veredito, mas vale acompanhar se aparecer no CI.

---

## Checagem por AC, ancorada na spec

| AC | Resultado definido na spec | Evidência `arquivo:linha` + asserção | Situação |
| -- | -------------------------- | ------------------------------------ | -------- |
| CON-01 | card sem `dp` → inválido | `packages/contract/fixtures/chunk-invalido.json:6` (id 5 sem `dp`) + `packages/contract/validate.mjs:31-36`: cada registro precisa falhar sozinho (`if (card(r)) … falhas++`); schema `packages/contract/schema/oferta-card.schema.json:8` com `"dp"` em `required` | ✅ |
| CON-02 | `chunk-ok` com `dp` e `manifest-ok` 1.5.0 válidos | `packages/contract/fixtures/chunk-ok.json:2-4`, `packages/contract/fixtures/manifest-ok.json:2`; `npm run validate` → PASS; `apps/site/src/lib/dados/tipos.test.ts:35` `expect(m.contrato).toBe('1.5.0')` | ✅ |
| CON-03 | pacote 1.5.0; manifest publica `contrato: "1.5.0"` | `apps/worker/tests/envio_modelo.rs:39` `assert_eq!(versao_contrato().unwrap(), "1.5.0")`; `apps/worker/tests/geracao.rs:108` `assert_eq!(m.contrato, pkg["version"])` | ✅ |
| CON-04 | §3 documenta `dp` e 230 B; §10.6 respondida | `docs/CONTRATO.md:72` (média ≤ 230 B, AD-074), `docs/CONTRATO.md:84` (linha `dp`), `docs/CONTRATO.md:241-242` (§10.6 respondida); `docs/MANIFEST.md:171` | ✅ (documento, conferido por leitura) |
| DP-01 | coluna na faixa → `dp` = valor em UTC | `apps/worker/tests/card.rs:383` `assert_eq!(c.dt_publicacao, "2026-10-07T11:30:00Z")`; `:385` `"2026-10-06T15:02:17Z"` (segundos preservados); `apps/worker/tests/publicacao_site.rs:197` `publicados[&2] == "2026-10-06T15:02:00Z"` | ✅ para a projeção. A conversão local→UTC pelo `BESAVE_ORACLE_TZ` está no SQL (`epoch_utc!`) e não tem teste (lacuna 2) |
| DP-02 | nula → instante do ciclo truncado ao minuto | `apps/worker/tests/card.rs:404` `"2026-10-07T12:00:00Z"` com `agora` = 12:00:37; `apps/worker/tests/publicacao_site.rs:196` | ✅ |
| DP-03 | futura → instante + WARN com o id; oferta publicada | `apps/worker/tests/card.rs:412-418` `expect("data futura não rejeita")`, `dt_publicacao == "2026-10-07T12:00:00Z"`, linha com `WARN` && `5413` && `DT_PUBLICACAO_SITE`; `apps/worker/tests/publicacao_site.rs:198` | ✅ |
| DP-04 | anterior a 2026-10-06T00:00Z → instante + WARN | `apps/worker/tests/card.rs:426-432` (`1_791_244_800 - 1`); `apps/worker/tests/publicacao_site.rs:199` | ✅ |
| GRV-01 | UPDATE grava o instante (= `dp`) em nula/fora da faixa; não toca as que estão na faixa | `apps/worker/tests/publicacao_site.rs:201` `publicacao_site_marcadas == 3`; `:203-206` `gravadas == {1,3,4 → AGORA_DP}`; `:207-209` `iso_utc(d) == publicados[id]`; `:210` id 2 mantém `NO_AR` | ⚠️ Provado só contra o `FakeFonte`, que reimplementa a regra. A montagem de binds do Oracle real não tem teste: o mutante W9 sobrevive (lacuna 1) |
| GRV-02 | SQL faz bind do instante, sem `SYSDATE`, um bind por id | `apps/worker/tests/publicacao_site.rs:120` `!sql.contains("SYSDATE")`; `:121-124` `SET … + :1 / 86400`; `:126-133` faixa `:2`/`:3`; `:134` `ID_OFERTA IN (:4, :5, :6)` | ✅ |
| IDE-01 | 2º ciclo: mesmo `dp`, 0 chunks | `apps/worker/tests/publicacao_site.rs:221` `dps(&p) == primeiro`; `:222` `chunks_escritos == 0`; `:223` `publicacao_site_marcadas == 0`; `:224-227` só os 2 manifests | ✅ |
| ORC-01 | média de 1 000 cards realistas ≤ 230 B; chunk br ≤ 60 KB | `apps/site/src/lib/dados/gerador.test.ts:102` `toBeLessThanOrEqual(230)`; `:106` `≤ 60 * 1024` (sementes 1–3); `apps/worker/tests/card.rs:102` `media <= 230.0` (fixture de 3 cards). Medido: 218,1 / 219,5 / 220,6 B; 32,9–33,3 KB br | ✅ (margem ~10 B; ver lacuna 4) |
| SIT-01 | `recentes` = `dp` desc, `id` desc, contra a ordem de `dt` | `apps/site/src/lib/dados/catalogo.test.ts:147` `toEqual([3, 1, 5, 2])` (por `dt` seria `[5,2,1,3]`; 5 e 2 empatam em `dp`) | ✅ |
| SIT-02 | sem `dp` → usa `dt` | `apps/site/src/lib/dados/catalogo.test.ts:156` `toEqual([1, 4, 2])` | ✅ |
| SIT-03 | ≤ n ativas, `dp ≥ agora−24h`, desconto desc, depois `dp` desc | `apps/site/src/lib/dados/catalogo.test.ts:175` `toEqual([11, 16, 15, 10, 14])` (10 e 14 empatam em 50% e saem por `dp`; 15 está em exatamente 24 h); `:179` `n=2 → [11, 16]` | ✅ |
| SIT-04 | `dp` de 25 h fica de fora | `apps/site/src/lib/dados/catalogo.test.ts:183` `not.toContain(12)` (e `:175` lista exata) | ✅ |
| SIT-05 | expirada fica de fora | `apps/site/src/lib/dados/catalogo.test.ts:187` `not.toContain(13)` (e `:175`) | ✅ |
| SIT-06 | gerador: `dp` em todo card, `dp ≥ dt`, válido no schema 1.5.0 | `apps/site/src/lib/dados/gerador.test.ts:94-95`; `:27` `validarChunk(cards) === true` (schema com `dp` obrigatório) | ✅ |

**Situação:** 17/18 ✅. GRV-01 fica ⚠️ porque o comportamento de produção não é discriminado pelos testes.

### Edge cases

- [x] Coluna igual ao instante do ciclo é aceita (limite inclusivo): `apps/worker/tests/card.rs:396` + `:398` sem WARN. O mutante W3 morre aqui.
- [x] `agora` fora do minuto cheio → `dp` termina em `:00`: `apps/worker/tests/card.rs:404` (agora = 12:00:37).
- [x] Falha no UPDATE → exit 0 com `publicacao_site_falhas`: `apps/worker/tests/publicacao_site.rs:104` `cod == Codigo::Ok`, `:110` `publicacao_site_falhas=1`.

### Lacunas de precisão da spec

- **DP-01 "local → UTC por `BESAVE_ORACLE_TZ`"**: a regra vive no SQL (`epoch_utc!`) e no `+ fuso_segundos` dos binds, e o critério não diz como provar isso sem Oracle. A matriz da tasks.md marca "Oracle real: none", o que deixa GRV-01 sem prova no caminho real.
- **ORC-01**: o dono pede "fixture de 1.000 cards realistas". A Assumption trocou isso pelo gerador TS (`gerarCards`), com serialização em JS. A ordem de chaves e o UTF-8 batem com o serde do worker, então aceito, mas a medida não vem do worker.

---

## Sensor de discriminação

Worktree temporário (`git worktree add --detach`) fora do repo, mutação aplicada e revertida por script e testes rodados ali. O `git status --porcelain` do worktree real estava vazio antes e continuou vazio depois (diff = ∅). Ao final, o worktree foi removido e foi feito `git worktree prune`. Nada de `git stash`.

| # | Arquivo | Mutação | Resultado | Teste que matou |
| - | ------- | ------- | --------- | --------------- |
| W1 | `apps/worker/src/conversao.rs:118` | `dp` nulo usa `DT_OFERTA` | ✅ Morto | `card.rs:404` dp_02 |
| W2 | `apps/worker/src/conversao.rs:89` | sem truncar ao minuto | ✅ Morto | `card.rs:404/413/427` |
| W3 | `apps/worker/src/conversao.rs:109` | limite superior exclusivo (`..`) | ✅ Morto | `card.rs:398` dp_01_limites |
| W4 | `apps/worker/src/conversao.rs:96` | sem limite inferior com relógio real | ✅ Morto | `card.rs:427` dp_04 |
| W5 | `apps/worker/src/conversao.rs:111` | `warn!` → `debug!` | ✅ Morto | `card.rs:414/428` |
| W6 | `apps/worker/src/fonte.rs:184` | UPDATE do fake só em nulas | ✅ Morto | `publicacao_site.rs:201/221` |
| W7 | `apps/worker/src/oracle.rs:141` | SQL volta a `SYSDATE` | ✅ Morto | `publicacao_site.rs:120` |
| W8 | `apps/worker/src/execucao.rs:132` | `marcar_publicadas_site(…, instante + 60)` | ✅ Morto | `publicacao_site.rs:76/203/221` |
| W9 | `apps/worker/src/oracle.rs:226` | binds `[&min, &instante, &instante]` (grava 2026-10-06 em vez do instante) | ❌ **Sobreviveu** | — |
| W10 | `apps/worker/src/oracle.rs:188` | `ofertas()` ignora a coluna 16 (`None`) | ❌ **Sobreviveu** | — |
| W11 | `apps/worker/src/fonte.rs:145` | fake não reflete a gravação na leitura | ✅ Morto | `ciclo.rs:84/110/343` |
| W12 | `apps/worker/src/geracao.rs:423` | ciclo ignora a coluna (sempre instante) | ✅ Morto | `ciclo.rs:84/110/343` |
| W13 | `apps/worker/src/oracle.rs:225` | limite inferior do UPDATE sem `+ fuso` | ❌ **Sobreviveu** | — |
| C1 | `packages/contract/schema/oferta-card.schema.json:8` | `dp` opcional | ✅ Morto | `validate.mjs:34` (id 5 válido sozinho) |
| C2 | `packages/contract/package.json:3` | versão 1.4.0 | ✅ Morto | `envio_modelo.rs:39` |
| S1 | `apps/site/src/lib/dados/catalogo.ts:133` | `recentes` por `dt` | ✅ Morto | `catalogo.test.ts:147/156/175/179` |
| S2 | `apps/site/src/lib/dados/catalogo.ts:85` | sem janela de 24 h | ✅ Morto | `catalogo.test.ts:175/179/183` |
| S3 | `apps/site/src/lib/dados/catalogo.ts:84` | `lista({mostrarExpiradas: true})` | ✅ Morto | `catalogo.test.ts:175/179/187` |
| S4 | `apps/site/src/lib/dados/catalogo.ts:90` | desempate por `id` em vez de `dp` | ✅ Morto | `catalogo.test.ts:175` |
| S5 | `apps/site/src/lib/dados/catalogo.ts:85` | `<` → `<=` (24 h exatas fora) | ✅ Morto | `catalogo.test.ts:175` |
| S6 | `apps/site/src/lib/dados/gerador.ts:186` | gerador com `dp < dt` | ✅ Morto | `gerador.test.ts:95` |
| S7 | `apps/site/src/lib/dados/catalogo.ts:133` | sem `dp` não cai em `dt` | ✅ Morto | `catalogo.test.ts:156` (+ CAT-04) |
| S8 | `apps/site/src/lib/dados/catalogo.ts:85` | janela por `dt` | ✅ Morto | `catalogo.test.ts:175/179` |
| S9 | `apps/site/src/lib/dados/catalogo.ts:81` | janela de 48 h | ✅ Morto | `catalogo.test.ts:175/179/183` |

**Profundidade:** expandida, porque a integridade de dado vai ao Oracle de produção. **Placar: 21/24 mortos.** Os 3 sobreviventes estão no `impl FonteOfertas for OracleFonte`.

Impacto dos sobreviventes no mundo real:
- **W9:** toda oferta nova é gravada com `2026-10-06 00:00` local enquanto o card publicou o instante. No ciclo seguinte o `dp` muda para 2026-10-06 e o chunk é regravado uma vez. Depois a oferta estabiliza com `dp` errado, no fundo de "recentes", que é o problema que o ticket resolve. O canal (BSV-40) também passaria a ver a oferta como publicada em 06/10. A execução real do dono **não pega isso** de forma confiável: o terceiro ciclo volta a dar 0 chunks.
- **W10:** todo ciclo usaria o instante para todas as ofertas, e os chunks mudariam sempre. A execução real pega ("2º ciclo → 0 chunks" falharia).
- **W13:** o limite inferior desloca 3 h (UTC vs. local). Na prática não tem efeito.

---

## Qualidade de código

| Princípio | Situação |
| --------- | -------- |
| Código mínimo / sem scope creep | ✅ (`validar_card` separado de `para_card` para que página e canal não emitam WARN; justificado) |
| Mudanças cirúrgicas, só nas pastas autorizadas (regra 10: contrato + worker + site) | ✅ |
| Segue os padrões (`DATE '1970-01-01' + :n/86400` do envio, `blocos_in`, `iso_utc`) | ✅ |
| Asserção ancorada na spec | ✅ (valores ISO exatos, listas de ids exatas) |
| Cobertura por camada | ⚠️ A camada Oracle foi declarada "none" na matriz, mas carrega a regra do GRV-01 |
| Todo teste mapeia para AC/edge | ✅ |
| Sem dependência nova | ✅ (`node:zlib` é built-in) |
| Diretrizes seguidas: `CLAUDE.md`, `apps/worker/CLAUDE.md`, `apps/site/CLAUDE.md` | ✅ |

Notas de leitura (não bloqueiam):
- `apps/worker/src/oracle.rs:273` `linha_oferta` devolve `dt_publicacao_site: None`, e só `ofertas()` sobrescreve com `r.get(15)`. Funciona, mas o acoplamento "15 colunas em `linha_oferta`, a 16ª lida fora" é frágil, e a parte de fora é exatamente a que W10 mostra sem teste.
- `apps/site/src/lib/dados/catalogo.ts:84-85`: o `break` depende de `lista()` vir em `recentes`. Correto hoje (o padrão de `ordenar` é `'recentes'`), e o comentário explica.

---

## Lacunas ranqueadas

1. **[Major] GRV-01 sem prova no caminho Oracle: binds do UPDATE** (`apps/worker/src/oracle.rs:221-226`, mutantes W9 e W13). **Correção:** extrair uma função pura, por exemplo `pub fn binds_publicacao_site(agora: i64, fuso_segundos: i64) -> [i64; 3]` (instante local, mínimo local, máximo local), usada por `marcar_publicadas_site`. Testar em `tests/publicacao_site.rs` com `agora` fora do minuto cheio e fuso −10800: `[instante−10800, 1_791_244_800−10800, instante−10800]`, mais o caso sem limite inferior (`[…, 0−10800 ou 0+fuso, …]`). Assim W9 e W13 morrem.
2. **[Minor] Leitura de `DT_PUBLICACAO_SITE` sem teste** (`apps/worker/src/oracle.rs:188` e `SQL_OFERTAS` em `oracle.rs:101-111`, mutante W10). **Correção:** em `tests/oracle.rs` (que já testa `SQL_OFERTAS` em `:118` e `:134`), afirmar que a 16ª coluna é `epoch_utc!("DT_PUBLICACAO_SITE")`, ou seja, contém `DT_PUBLICACAO_SITE` convertida com `:desloc` depois de `DS_URL_AFILIADO`. Opcionalmente, mover o índice 15 para uma constante usada pelo teste. A execução real do dono também pega W10, então isso é defesa em profundidade.
3. **[Minor/processo] Execução real do dono continua bloqueando o merge** (spec, Success Criteria): primeiro ciclo regrava todos os chunks uma vez (anotar tempo e `bytes_totais`), segundo ciclo → `chunks_escritos=0`, e `pnpm medir` mostrando `dp`. Acrescentar ao roteiro um `SELECT ID_OFERTA, DT_PUBLICACAO_SITE` de 1 ou 2 ofertas novas comparado ao `dp` do chunk (pega W9 mesmo sem a lacuna 1).
4. **[Info] Margem do orçamento ORC-01 ~10 B** (`apps/site/src/lib/dados/gerador.test.ts:102`, medido 218–221 B contra o limite de 230). O `dp` custa ~28 B por card. Se títulos reais crescerem, o gate continua sendo o chunk ≤ 60 KB (hoje ~33 KB), então não há ação agora.
5. **[Info] Instabilidade do vitest em execução fria** (2/70 falharam uma vez no worktree temporário e passaram nas 2 execuções seguintes). Acompanhar no CI.

---

## Atualização de rastreabilidade (proposta; o Verifier não edita spec.md)

| Requisito | Novo status |
| --------- | ----------- |
| CON-01..04, DP-01..04, GRV-02, IDE-01, ORC-01, SIT-01..06 | ✅ Verificado |
| GRV-01 | ❌ Precisa de correção (lacuna 1) |

## Resumo

- **Checagem ancorada na spec:** 17/18 ACs batem com o resultado da spec; 1 ⚠️ (GRV-01) e 2 lacunas de precisão de spec.
- **Gates:** contrato OK; worker 433 passaram / 0 falharam / 3 ignorados, fmt e clippy limpos; site 70/70, lint, check e build ok.
- **Sensor:** 24 injetados, 21 mortos, 3 sobreviventes (W9, W10, W13, todos em `OracleFonte`).
- **Próximo passo:** tarefa de correção com as lacunas 1 e 2 (testes de função pura, sem Oracle), depois nova verificação.

---

## Gate determinístico

`python .claude/skills/tlc-spec-driven/scripts/validate_state.py BSV-36` → exit 1:

```
  ERROR BSV-36: validation.md verdict is FAIL - route the ranked gaps to fix tasks, then re-verify (feature is not done)

validate_state: 1 error(s) across [BSV-36]
```

Esperado com o veredito FAIL: a feature fica pendente até as lacunas 1 e 2 serem corrigidas e o Verifier rodar de novo.

## Gate determinístico — iteração 2

`python .claude/skills/tlc-spec-driven/scripts/validate_state.py BSV-36` → exit 0:

```
validate_state: 0 error(s) across [BSV-36]
```
