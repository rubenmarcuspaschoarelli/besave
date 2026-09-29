# BSV-21 Validation (Iteração 1)

**Date**: 2026-09-29
**Spec**: `.specs/features/BSV-21/spec.md` (EARS) + `docs/specs/BSV-21.md` (critério de aceite do dono)
**Diff range**: `0c8b5b9..HEAD` (`ad3c91d`) — 7 commits `a9c2f45..ad3c91d`, só `apps/worker/` e `.specs/features/BSV-21/`
**Verifier**: sub-agente independente (autor ≠ verificador); evidência recoletada do código-fonte e de execuções frescas

## Veredito: ❌ FAIL

O gate está verde e 29/31 requisitos têm evidência precisa. Mas o sensor deixou **6 mutantes vivos**. Dois
deles são comportamento que a spec exige e que vai quebrar em produção sem nenhum teste falhar:

- a troca de `BESAVE_INDEXAVEL` na virada de DNS não faria o `robots.txt` subir de novo;
- uma mudança no CSS após a primeira carga não faria `assets/besave.css` subir de novo.

O resto é precisão (PAG-07 no ciclo, PAG-10 `tempo_render_ms`) e cobertura do binário.

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 Produtos em lote | ✅ Done | `FakeFonte` conta chamadas; `sql_produtos`/`BLOCO_IN` testados; o laço de blocos do `OracleFonte` não tem teste (I/O, fora do CI pela matriz) |
| T2 Headers `assets/` e `_estado/` | ✅ Done | — |
| T3 Sitemaps/robots/config | ✅ Done | — |
| T4 `publicar_paginas` | ✅ Done | PAG-10 fraco (ver gaps) |
| T5 Ligar ao `gerar()` | ⚠️ Partial | falta detectar mudança de hash de CSS e de robots (mutantes M11/M12 vivos) |
| T6 Plano resume páginas | ✅ Done | — |
| T7 Binário e README | ✅ Done | README cobre `BESAVE_BASE_URL`, `BESAVE_INDEXAVEL` e `_estado/` (`apps/worker/README.md:78-89`) |

---

## Spec-Anchored Acceptance Criteria

### P1: Páginas publicadas incrementalmente

| Req | Resultado definido pela spec | `file:line` + asserção | Resultado |
| --- | ---------------------------- | ---------------------- | --------- |
| PAG-01 | `chave_pagina(5412)` = `"oferta/5412/index.html"` | `tests/paginas.rs:53` `assert_eq!(chave_pagina(5412), "oferta/5412/index.html")` | ✅ |
| PAG-02 | índice vazio → 1 upload por página e hash16 (16 hex) por id | `tests/paginas.rs:62-74` `assert_eq!(p.gravacoes(), [3 chaves])`, `indice.0.keys()==[5412,5413,5420]`, `all(hex16)`; bytes = render (`:79`) | ✅ |
| PAG-03 | hash igual → não sobe e conta em `inalteradas` | `tests/paginas.rs:105-110` `gravacoes().len()==marca`, `(renderizadas,publicadas,inalteradas)==(3,0,3)` | ✅ (M1 morto) |
| PAG-04 | mesmos bytes em chamadas repetidas | `tests/paginas.rs:118-122` `assert_eq!(t.renderizar(&o), t.renderizar(&o))` também entre dois templates | ✅ |
| PAG-05 | ATIVA→ENCERRADA → só aquela página sobe | `tests/paginas.rs:134` `&p.gravacoes()[marca..] == ["oferta/5413/index.html"]`, `:137` `(1,2)`; ciclo `tests/ciclo.rs:357` | ✅ |
| PAG-06 | `remover("oferta/{id}/index.html")`, sai do índice, conta em `removidas` | `tests/paginas.rs:148-152` `p.remocoes()==["oferta/5420/index.html"]`, `!indice2.contains_key(5420)`, `removidas==1` | ✅ (M3 morto) |
| PAG-07 | > 30 720 → `PaginaAcimaDoOrcamento{id,bytes}` e **índice e manifest não gravados** | `tests/paginas.rs:163` `matches!(.. {id:7001, bytes} if bytes > 30_720)`; borda `:174-181` (30 720 ok, 30 721 erro) | ⚠️ erro e borda ✅ (M2 morto), mas **sem teste que prove "índice e manifest não gravados"** (AC do dono: "manifest não gravado"). O teste só olha a página 7001 no nível de `publicar_paginas` |
| PAG-08 | loga id, conta em `falhas`, não sobe, segue | `tests/paginas.rs:201-206` `rel.falhas==[5412,9001]`, `gravacoes[marca..]==["oferta/5420/index.html"]`, hash anterior mantido | ✅ (M15 morto); o log não é verificado (aceitável) |
| PAG-09 | `gravar_lote` em blocos ≤ 64; headers html/`max-age=600, swr=300` | `tests/paginas.rs:247` `p.lotes == [64, 64, 2]`; headers `:80-87` | ✅ (M8 morto) |
| PAG-10 | relatório com 7 campos | `tests/paginas.rs:90-95` (contagens, `maior_html == maior`); `tempo_render_ms` só `<= elapsed` (`:262`) | ⚠️ spec-precision: `tempo_render_ms = 0` sobrevive (M13) |
| PAG-11 | 30 000 páginas ≤ 60 s em release | `tests/paginas.rs:268-279` `#[ignore]`, `assert!(tempo <= 60s)` | ✅ existe; não rodado por este Verifier (fora do gate; roda com `--release -- --ignored`) |

### P1: Produtos em lote

| Req | Resultado definido pela spec | `file:line` + asserção | Resultado |
| --- | ---------------------------- | ---------------------- | --------- |
| PRD-01 | só ids achados | `tests/fonte.rs:61-64` `achados.len()==2`, `!contains_key(&999)` | ✅ |
| PRD-02 | 10 000 ofertas → `produtos` ≤ 10, `produto` = 0 | `tests/geracao.rs:714` `chamadas_produtos() <= 10`, `:719` `chamadas_produto()==0`, produto chega à página | ✅ (M9a/M9b mortos) |
| PRD-03 | `IN` com ≤ 1 000 binds | `tests/oracle.rs:140-143` `BLOCO_IN==1000`, `ends_with("IN (:1, :2, :3)")` | ⚠️ SQL ✅; o fatiamento em `src/oracle.rs:144` não é testado (M19 vivo; I/O Oracle fora do CI pela matriz) |
| PRD-04 | `--dry-run` usa `produtos` | `tests/geracao.rs:740-741` `chamadas_produtos()==1`, `chamadas_produto()==0` (em `contar_paginas`) | ⚠️ cobre a função da lib, não o binário: `src/main.rs:213` pode voltar a chamar `produto` sem nenhum teste falhar (M21 vivo) |

### P1: CSS, sitemap, robots e índice

| Req | Resultado definido pela spec | `file:line` + asserção | Resultado |
| --- | ---------------------------- | ---------------------- | --------- |
| SIT-01 | 3 páginas + CSS + `sitemap.xml` + `sitemap-1.xml` + robots + índice | `tests/ciclo.rs:295-306` lista exata e na ordem; CSS byte a byte `:313`; robots `:314`; hash16 por id | ✅ |
| SIT-02 | segunda execução → só `manifest.prev.json`, `manifest.json` | `tests/ciclo.rs:330` `gravadas == ["manifest.prev.json","manifest.json"]`; também o pré-existente `tests/ciclo.rs:76-79` (não alterado) | ✅ (M7 morto) |
| SIT-03 | só ATIVA; `<loc>` `{base}/oferta/{id}/`; `<lastmod>` AAAA-MM-DD | `tests/site.rs:120-127` locs exatos e `lastmods==["2026-09-23","2026-09-24"]`; ENCERRADA fora `tests/ciclo.rs:349` | ✅ (M4, M17 mortos) |
| SIT-04 | encerrada sai do sitemap no mesmo ciclo | `tests/ciclo.rs:361` `!sitemap.contains("/oferta/5413/")` | ✅ |
| SIT-05 | expurgada: página removida, fora do índice e do sitemap | `tests/ciclo.rs:378-386`; junto com imagens `tests/geracao.rs:591-592` | ✅ |
| SIT-06 | 46 000 → `sitemap-1` (45 000) + `sitemap-2` (1 000) + index; parse; ≤ 50 MB | `tests/site.rs:64-88` chaves exatas, `locs.len()==45_000/1_000`, primeiro/último loc, `roxmltree::parse`, `b.len() <= 50 MiB` | ✅ (M5a/M5b mortos) |
| SIT-07 | remove `sitemap-{n}` que não é mais gerado | `tests/ciclo.rs:402` `p.remocoes()==["sitemap-2.xml"]` | ✅ (M14 morto) |
| SIT-08 | ausente/false → `User-agent: *\nDisallow: /\n` | `tests/site.rs:139`, `:160`; binário `tests/dry_run.rs:280-283` | ✅ (M6 morto) |
| SIT-09 | true → `Allow: /` + `Sitemap: {base}/sitemap.xml` | `tests/site.rs:146-151`; env `:173-175`; binário `tests/dry_run.rs:316` | ✅ |
| SIT-10 | headers de `assets/besave.css` publicado e `meta_para` | `tests/headers.rs:86` `meta_para("assets/besave.css") == css`; conteúdo publicado `tests/ciclo.rs:313` | ✅; ⚠️ "publicar **quando o hash mudar**" (regra 6 do dono) sem teste (M11 vivo) |
| SIT-11 | índice ilegível → trata como ausente, sobe tudo, segue | `tests/ciclo.rs:424-437` `publicadas==3`, lista exata, manifest existe | ✅ (M16 morto) |
| SIT-12 | `_estado/paginas.json` com `application/json`, `no-store` | `tests/headers.rs:88` | ✅ |
| SIT-13 | imagens → chunks → CSS → páginas → sitemaps → robots → índice → KVS → manifest | `tests/geracao.rs:640` `ordem.windows(2).all(w0 < w1)` sobre 12 marcos | ✅ (M10 morto) |
| SIT-14 | falha de upload de página → erro, sem manifest | `tests/geracao.rs:686-688` sem `manifest.json`, sem índice, KVS intocada | ✅ |
| SIT-15 | valor inválido nomeia a variável; base padrão | `tests/site.rs:190-194`, `:158`; binário `tests/dry_run.rs:333` | ✅ |

### P2: Plano

| Req | Resultado definido pela spec | `file:line` + asserção | Resultado |
| --- | ---------------------------- | ---------------------- | --------- |
| PLN-01 | uma linha por tipo, contagem + ≤ 5 exemplos, sem linha individual | `tests/plano.rs:396` linhas exatas (`"páginas a gravar: 30 (ex.: …5 chaves)"`); `:411` sem resumo quando não há páginas | ✅ (M18 morto) |

**Status**: 26 ✅ · 5 ⚠️ (PAG-07, PAG-10, PRD-03, PRD-04, SIT-10) · 0 sem evidência.

### AC do dono (`docs/specs/BSV-21.md`) sem cobertura exata

- "Página > 30 KB → erro nomeado, **manifest não gravado**": a parte do manifest não tem teste (ver PAG-07).
- Regra 6 "CSS … quando o hash mudar" e regra 8 "a virada de DNS liga a flag": não há teste de CSS ou robots **mudando** entre execuções (M11/M12).
- Execução real do dono (curl, Lighthouse, relatório real): fora do CI, pendente.

---

## Edge Cases

- [x] Nenhuma ativa → `sitemap-1.xml` com `urlset` vazio + index: `tests/site.rs:106-109`
- [x] Exatamente 45 000 → um arquivo: `tests/site.rs:97-99` (M5b morto)
- [x] `BESAVE_BASE_URL` com `/` final → sem `//oferta`: `tests/site.rs:214`
- [x] Página de exatamente 30 720 bytes aceita: `tests/paginas.rs:174` (M2 morto)

---

## Discrimination Sensor

Scratch: `git worktree add --detach %TEMP%\bsv21-sensor HEAD`, com `CARGO_TARGET_DIR` separado. Cada mutação foi
aplicada, testada com `cargo test -q --test <alvos>` e revertida. Depois: `git worktree remove --force`, `git worktree prune`.
Baseline do `git status --porcelain` do tree real (vazio) = estado depois (vazio) → **isolamento OK**. Nada de `git stash`.

| # | Local | Mutação | Testes | Resultado |
| - | ----- | ------- | ------ | --------- |
| M1 | `src/paginas.rs:96` | não compara hash; sempre sobe | paginas, ciclo | ✅ Morto (4 testes de ciclo) |
| M2 | `src/paginas.rs:56` | `>` → `>=` no orçamento | paginas | ✅ Morto (`orcamento_aceita_30720_e_recusa_30721`) |
| M3 | `src/paginas.rs:110` | expurgo desligado | paginas, ciclo, geracao, plano | ✅ Morto |
| M4 | `src/site.rs:254` | ENCERRADA entra no sitemap | ciclo | ✅ Morto |
| M5a | `src/site.rs:359` | `chunks(MAX_URLS_SITEMAP + 1)` | site | ✅ Morto |
| M5b | `src/site.rs:359` | `chunks(MAX_URLS_SITEMAP - 1)` | site | ✅ Morto (as duas bordas) |
| M6 | `src/site.rs:388` | robots invertido | site, ciclo | ✅ Morto |
| M7 | `src/site.rs:286` | índice sempre regravado | ciclo | ✅ Morto |
| M8 | `src/paginas.rs:16` | bloco 64 → 65 | paginas | ✅ Morto |
| M9a | `src/geracao.rs:134` | `produto` por linha | geracao | ✅ Morto |
| M9b | `src/geracao.rs:134` | `produtos(&[id])` por linha | geracao | ✅ Morto |
| M10 | `src/geracao.rs:190` | site depois da KVS | geracao | ✅ Morto (ordem, SIT-14, KVS) |
| M11 | `src/site.rs:242` | CSS sobe só se `anterior.css.is_none()` | ciclo, site, geracao, headers | ❌ **Sobreviveu** |
| M12 | `src/site.rs:279` | robots sobe só se `anterior.robots.is_none()` | ciclo, site, geracao, dry_run | ❌ **Sobreviveu** |
| M13 | `src/paginas.rs:115` | `tempo_render_ms = 0` | paginas, geracao, dry_run | ❌ **Sobreviveu** |
| M14 | `src/site.rs:270` | não remove `sitemap-{n}` obsoleto | ciclo | ✅ Morto |
| M15 | `src/paginas.rs:87` | falha de render descarta o hash anterior | paginas | ✅ Morto |
| M16 | `src/site.rs:232` | índice ilegível aborta | ciclo | ✅ Morto |
| M17 | `src/site.rs:370` | `lastmod` com 7 chars | site, ciclo | ✅ Morto |
| M18 | `src/plano.rs:128` | 6 exemplos | plano | ✅ Morto |
| M19 | `src/oracle.rs:144` | blocos de 2 000 (ORA-01795) | oracle, fonte | ❌ Sobreviveu (I/O Oracle, sem teste pela matriz; informativo) |
| M20 | `src/site.rs:254` | sitemap sem o filtro "tem página no índice" | ciclo, paginas, site, geracao | ❌ Sobreviveu (ATIVA com render falho e sem página publicada iria para o sitemap → 404 indexável) |
| M21 | `src/main.rs:213` | `--dry-run` volta a chamar `produto` por linha | dry_run | ❌ Sobreviveu (PRD-04 no binário) |

**Sensor depth**: expandido (23 mutações; dado crítico de publicação/SEO)
**Result**: 17/23 mortos — ❌ FAIL (M11, M12 são bloqueantes; M13, M20, M21 menores; M19 informativo)

---

## Gate Check

- **Comando** (em `apps/worker/`): `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` → exit 0
- **Resultado**: 200 passaram, 0 falharam, 3 ignorados
- **Ignorados** (todos `#[ignore]` de desempenho, justificados): `ciclo` 30k, `imagens` desempenho, `paginas::trinta_mil_paginas_em_ate_60_segundos` (PAG-11)
- **`#[test]` antes/depois**: 160 (`0c8b5b9`) → 203 (HEAD), **+43**
- **Integridade**: a única asserção removida é `p.remover == 3` → `== 4` (`tests/plano.rs:278`), atualizada porque a página de 5413 agora também sai; a lista exata de remoções ganhou a página (mais forte)

### Testes pré-existentes alterados

| Arquivo | Mudança | Avaliação |
| ------- | ------- | --------- |
| `tests/ciclo.rs:105-106` | lista exata ganhou `oferta/5413/index.html` e `_estado/paginas.json` | mais forte (continua lista exata) |
| `tests/ciclo.rs:65-80` (CIC idempotência) | **não alterado** | continua exigindo só os manifests: confirma a decisão "índice só se mudar" |
| `tests/geracao.rs:459-466` `falha_na_kvs_nao_grava_manifest` | allowlist ampliada com chaves do site | enfraquecimento necessário e compensado: `:487` exige chunk `1-`, e `:491-495` restringe o resto a essa página, ao `sitemap-1.xml` e ao índice (subconjunto, não lista exata) |
| `tests/geracao.rs:319-335` `relatorio_com_contagens` | `RelatorioSite` exato (exceto `tempo_render_ms`) | mais forte |
| `tests/geracao.rs:591-592` expurgo de imagem | + página removida | mais forte (regra 5 "junto do expurgo de imagens") |
| `tests/plano.rs:205-222`, `:276-287` | +1 remoção de página, lista exata | mais forte |

---

## Avaliação das Assumptions

| Decisão | Avaliação |
| ------- | --------- |
| Índice regravado só quando muda | Correto. A regra 2 do dono diz "regravado ao fim", mas a AC ("só índice/manifest") permite não regravar, e o `apps/worker/CLAUDE.md` exige idempotência. Não é necessário confirmar com o dono, só registrar no PR |
| Expurgo de página antes da KVS/manifest | Aceitável e coberto (`tests/plano.rs:283-287` mostra a ordem). Efeito colateral não registrado: se o índice ficar ilegível (SIT-11), `anterior` fica vazio e as páginas de ids expurgados naquele ciclo **nunca mais** são removidas (órfãs permanentes). Baixo risco; sugiro registrar |
| Falha de render mantém o hash anterior | Correto e testado (M15). Com M20, porém, uma ATIVA nova com render falho fica fora do índice e do sitemap só por causa do filtro `indice.contains_key`, e esse filtro não tem teste |
| Gate de 30 KB durante os uploads | Aceitável (lotes anteriores podem ter subido; páginas são idempotentes). O fato de o índice e o manifest não serem gravados nesse caminho não é provado por teste |
| `gerar` descarta em silêncio `para_pagina(..).ok()` (`src/geracao.rs:139`) | Não está na tabela. O comentário diz que `publicavel` ≡ `para_pagina`; se divergirem no futuro, a oferta ganha card e KVS sem página e sem log. Sugiro `warn!` com o id |
| Demais (sitemap-1, lastmod UTC, ordem por id, config env, roxmltree) | OK e cobertas |

---

## Code Quality

| Princípio | Status |
| --------- | ------ |
| Código mínimo / sem scope creep | ✅ (`contar_paginas` extraído para testar PRD-04: justificável) |
| Mudanças cirúrgicas | ✅ |
| Segue os padrões (thiserror na lib, sem `unwrap` fora de teste, traits com fakes) | ✅ |
| Resultado ancorado na spec | ⚠️ PAG-07 (manifest), PAG-10 (`tempo_render_ms`) |
| Cobertura por camada | ⚠️ orquestração sem teste de mudança de CSS/robots |
| Todo teste mapeia um requisito | ✅ |
| Guidelines: `CLAUDE.md`, `apps/worker/CLAUDE.md` (testes sem rede/Oracle/AWS) | ✅ |

---

## Fix Plans

### Fix 1 (Major): robots não sobe de novo quando `BESAVE_INDEXAVEL` muda — M12
- **Onde**: `tests/ciclo.rs` (novo teste); código em `src/site.rs:277-283`
- **Tarefa**: rodar `gerar` com `ConfigSite::default()`, depois com `indexavel: true` (e/ou outra `base`) e asserir que `robots.txt` está nas novas gravações, com `Allow: /` + `Sitemap: {base}/sitemap.xml`, e que o índice foi regravado. Com a base mudando, asserir também que `sitemap-1.xml` e `sitemap.xml` sobem
- **Pronto quando**: M12 (`anterior.robots.is_none()`) morre

### Fix 2 (Major): CSS alterado não sobe — M11
- **Tarefa**: gravar `_estado/paginas.json` com `"_css": "0000000000000000"` (e os demais hashes da primeira execução), rodar `gerar` e asserir que `assets/besave.css` está nas novas gravações e que o `_css` do índice passa a ser `hash16(CSS)`
- **Pronto quando**: M11 morre

### Fix 3 (Minor): PAG-07 no ciclo — "manifest não gravado"
- **Tarefa**: teste em `tests/geracao.rs` com uma linha de título/descrição que passe de 30 KB. Asserir `ErroGeracao::Site(ErroSite::Paginas(PaginaAcimaDoOrcamento{id, ..}))`, sem `manifest.json` e sem `_estado/paginas.json`, KVS intocada. Se o limite de título da conversão impedir, usar `LinhaProduto.descricao` grande

### Fix 4 (Minor): sitemap só com página publicada — M20
- **Tarefa**: em `tests/ciclo.rs`, uma ATIVA cujo render falha (ex.: `dt_oferta` que passa na conversão, mas não no template; ou falha injetada) e que não tem hash anterior não pode aparecer em `sitemap-1.xml`. Se não houver como forçar a falha pelo ciclo, testar por uma função pura de seleção das ativas

### Fix 5 (Minor): `tempo_render_ms` — M13
- **Tarefa**: em `tests/paginas.rs:254`, com 300 páginas, asserir `rel.tempo_render_ms > 0` (ou medir em µs internamente). Alternativa: registrar na spec que o valor é só informativo

### Fix 6 (Minor): PRD-04 no binário — M21
- **Tarefa**: não há contador observável no subprocesso. Opções: `main::dry_run` só delega a `contar_paginas` (hoje é assim), e aceitar o risco registrando como SPEC_DEVIATION; ou um log `debug!` com a contagem de chamadas, asserido em `tests/dry_run.rs`

### Informativo: M19 (fatiamento `IN` do Oracle)
- Pela matriz, é I/O sem teste. Se quiser cobrir sem Oracle, extraia um `fn blocos_in(ids) -> Vec<Vec<i64>>` puro (dedup + chunks de 1 000) e teste 2 500 ids → `[1000, 1000, 500]`

---

## Requirement Traceability Update

| Requirement | New Status |
| ----------- | ---------- |
| PAG-01..06, PAG-08, PAG-09, PAG-11, PRD-01, PRD-02, SIT-01..09, SIT-11..15, PLN-01 | ✅ Verified |
| PAG-07 | ⚠️ Verified (lib), falta a asserção de manifest/índice no ciclo |
| PAG-10 | ⚠️ Spec-precision gap (`tempo_render_ms`) |
| PRD-03 | ⚠️ SQL verificado; o fatiamento é I/O sem teste |
| PRD-04 | ⚠️ Verified na lib; binário sem discriminação |
| SIT-10 | ❌ Needs Fix (republicar quando o hash muda, M11) |
| Regra 8 do dono (virada da flag) | ❌ Needs Fix (M12) |

---

## Summary

**Overall**: ❌ Not Ready — 2 fixes Major (M11, M12) antes de re-verificar; o resto é Minor.

**Spec-anchored**: 26/31 exatos; 5 com precisão parcial. **Sensor**: 17/23 mortos. **Gate**: 200 passaram, 0 falharam, 3 ignorados.

**O que funciona**: incremental por hash (páginas, sitemaps, índice), expurgo, orçamento e sua borda, blocos de 64,
sitemaps 45k/46k/0 com parse, robots nos dois modos, config por env, ordem MANIFEST §6, abort antes do manifest em
falha de upload, produtos em lote, plano enxuto. Os testes pré-existentes foram fortalecidos, não enfraquecidos.

**Próximo passo**: implementador aplica Fix 1–2 (e, de preferência, 3–5); depois, iteração 2 do Verifier. A execução real
do dono (curl, Lighthouse, `--publicar --sim`) continua bloqueando o merge.
