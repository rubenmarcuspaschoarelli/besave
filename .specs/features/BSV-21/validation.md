# BSV-21 Validation (Iteração 3 — ajustes da revisão do dono)

**Date**: 2026-09-29
**Spec**: `.specs/features/BSV-21/spec.md` (EARS) + `docs/specs/BSV-21.md` (critério de aceite do dono)
**Diff range**: `0c8b5b9..HEAD` — commits `a9c2f45..1fa2744` mais o commit dos ajustes do dono (reconstrução do índice, remoção de `tempo_render_ms > 0`)
**Verifier**: sub-agente independente (autor ≠ verificador). Toda a evidência foi recoletada do código e de execuções frescas; a iteração 1 não foi usada como prova

## Veredito: ✅ PASS (com 2 resíduos aceitos pelo dono: M21 e M13)

**Result**: PASS

**Revisão do dono (2026-09-29)**: aprovado com 2 ajustes, aplicados na iteração 3:
1. Índice `_estado/paginas.json` ausente ou ilegível → além de reenviar tudo, o conjunto anterior de páginas é
   reconstruído com `listar("oferta/")` (`src/site.rs:107`, chamado só nesse caminho em `src/site.rs:137`), e as páginas de
   ids fora do conjunto atual são removidas. Teste `tests/ciclo.rs:448` `indice_corrompido_reconstroi_do_bucket_e_remove_orfa`:
   `:468` `p.remocoes() == ["oferta/9999/index.html"]`, `removidas == 1`, `publicadas == 3`, `indice_gravado`, índice
   sem `9999` e com hash16 para 5412/5413/5420. A restrição "só nesse caminho" é garantida por `tests/ciclo.rs:484`
   `indice_valido_nao_lista_nem_remove_pagina_fora_dele` (página fora do índice válido não é tocada).
2. A asserção `tempo_render_ms > 0` foi removida (instável em release). Fica só `tempo_render_ms <= elapsed`
   (`tests/paginas.rs:262`), então **M13 volta a sobreviver, e isso foi aceito pelo dono** (campo informativo).

O dono aceitou explicitamente: PAG-07 por composição, M21 como resíduo, e o índice regravado só quando muda.

Os dois gaps Major da iteração 1 (M11 CSS, M12 robots na virada de DNS) foram fechados por testes que matam os mutantes. Também foram mortos
M13, M19 e M20, e as 4 mutações novas nos trechos alterados. O gate está verde (205 testes na iteração 2; 207 na 3).

Sobram dois pontos, os dois avaliados e aceitos com justificativa (ver "Decisões da iteração 2"):
- **PAG-07 no nível do `gerar`:** está coberto por composição, não por um teste de ponta a ponta.
- **M21:** o `--dry-run` do binário não tem discriminação. É um delegador de 2 linhas.

---

## Histórico

| Iteração | Commit | Resultado | Resumo |
| -------- | ------ | --------- | ------ |
| 1 | `ad3c91d` | ❌ FAIL | Gate: 200 passaram. Sensor: 17/23 mortos. Vivos: **M11** (CSS alterado não sobe), **M12** (robots não sobe quando `BESAVE_INDEXAVEL` muda), M13 (`tempo_render_ms=0`), M19 (fatiamento `IN` do Oracle), M20 (ATIVA sem página entra no sitemap), M21 (`--dry-run` do binário). Precisão: PAG-07 sem "manifest não gravado"; `para_pagina(..).ok()` sem log |
| 2 | `1fa2744` | ✅ PASS | Gate: 205 passaram. Sensor: 9/10 mortos (6 re-rodadas + 4 novas). M21 aceito como resíduo |
| 3 | ajustes do dono | ✅ PASS | Gate: 207 passaram, 0 falharam, 3 ignorados. Sensor do trecho novo: 2/2 mortos (R1, R2). M13 volta a viver por decisão do dono |

### O que o `1fa2744` mudou (conferido no `git show`)

- `tests/ciclo.rs:466` `virada_para_indexavel_regrava_robots_e_sitemaps`: lista exata das novas gravações
  (`sitemap-1.xml`, `sitemap.xml`, `robots.txt`, `_estado/paginas.json`) e robots exato com `Allow: /` e
  `Sitemap: https://www.besave.com.br/sitemap.xml`.
- `tests/ciclo.rs:497` `css_com_hash_diferente_e_reenviado`: `_css` adulterado, então `:515` exige exatamente
  `["assets/besave.css", "_estado/paginas.json"]`, e `:519` exige `novo["_css"] == atual`.
- `tests/site.rs:235` `pagina_acima_do_orcamento_aborta_sem_indice`: `PaginaAcimaDoOrcamento{id:7001}` via `publicar_site`,
  sem `_estado/paginas.json` (`:250`), sem `sitemap.xml` e sem a página.
- `tests/site.rs:257` `ativa_sem_pagina_fica_fora_do_sitemap`: `falhas == [5413]` e `:267` `!sitemap.contains("/oferta/5413/")`.
- `src/oracle.rs` `blocos_in` puro (dedup + blocos de 1 000), usado pelo `OracleFonte::produtos`. Teste em `tests/oracle.rs:157-166`:
  2 500 ids com repetidos → `[1000, 1000, 500]`, primeiro 1, último 2 500, entrada vazia → vazio.
- `tests/paginas.rs:264` `assert!(rel.tempo_render_ms > 0)` (300 renders).
- `src/geracao.rs:140` `inspect_err(|r| warn!(id, motivo, "card sem página"))`: fecha o risco do `.ok()` silencioso.
- Nenhuma asserção antiga foi removida ou afrouxada neste commit; o diff de testes só acrescenta.

---

## Spec-Anchored Acceptance Criteria (estado atual)

### P1: Páginas

| Req | Resultado da spec | `file:line` + asserção | Resultado |
| --- | ----------------- | ---------------------- | --------- |
| PAG-01 | `"oferta/5412/index.html"` | `tests/paginas.rs:53` `assert_eq!(chave_pagina(5412), "oferta/5412/index.html")` | ✅ |
| PAG-02 | 1 upload por página; hash16 por id | `tests/paginas.rs:62-74` lista exata de gravações, ids `[5412,5413,5420]`, `all(hex16)`; bytes = render `:79` | ✅ |
| PAG-03 | hash igual → não sobe, `inalteradas` | `tests/paginas.rs:105-110` `(3,0,3)` | ✅ (M1 morto na iteração 1) |
| PAG-04 | render determinístico | `tests/paginas.rs:118-122` | ✅ |
| PAG-05 | ATIVA→ENCERRADA → só ela sobe | `tests/paginas.rs:134` `gravacoes[marca..] == ["oferta/5413/index.html"]`; `tests/ciclo.rs:357` | ✅ |
| PAG-06 | remover + sai do índice + `removidas` | `tests/paginas.rs:148-152` | ✅ (M3 morto) |
| PAG-07 | `PaginaAcimaDoOrcamento{id,bytes}`; índice e manifest não gravados | `tests/paginas.rs:163`, borda `:174-181`; sem índice `tests/site.rs:250`; o `?` do `gerar` antes da KVS/manifest (`src/geracao.rs:192`) é o mesmo caminho provado por SIT-14 `tests/geracao.rs:686-688` | ✅ por composição (ver Decisões) |
| PAG-08 | loga, conta, não sobe, segue | `tests/paginas.rs:201-206` | ✅ (M15 morto) |
| PAG-09 | lotes ≤ 64; headers | `tests/paginas.rs:247` `lotes == [64, 64, 2]`; `:80-87` | ✅ (M8 morto) |
| PAG-10 | 7 campos no relatório | `tests/paginas.rs:90-95`; `tempo_render_ms` só `:262` `<= elapsed` | ✅ presença; ⚠️ M13 vivo, aceito pelo dono (instável em release) |
| PAG-11 | 30k ≤ 60 s release | `tests/paginas.rs:270-281` `#[ignore]` | ✅ existe (fora do gate; não rodado por este Verifier) |

### P1: Produtos em lote

| Req | Resultado da spec | `file:line` + asserção | Resultado |
| --- | ----------------- | ---------------------- | --------- |
| PRD-01 | só ids achados | `tests/fonte.rs:61-64` | ✅ |
| PRD-02 | `produtos` ≤ 10, `produto` = 0 para 10 000 | `tests/geracao.rs:714`, `:719` | ✅ (M9a/M9b mortos) |
| PRD-03 | `IN` ≤ 1 000 binds | `tests/oracle.rs:140-143` SQL; `tests/oracle.rs:163` `[1000, 1000, 500]` | ✅ (M19, N1 mortos) |
| PRD-04 | `--dry-run` usa `produtos` | `tests/geracao.rs:740-741` em `contar_paginas`; `src/main.rs:213` só delega | ✅ na lib; ⚠️ binário sem discriminação (M21, aceito) |

### P1: CSS, sitemap, robots, índice

| Req | Resultado da spec | `file:line` + asserção | Resultado |
| --- | ----------------- | ---------------------- | --------- |
| SIT-01 | 3 páginas + CSS + 2 sitemaps + robots + índice | `tests/ciclo.rs:295-314` lista exata e ordem, CSS byte a byte, robots exato | ✅ |
| SIT-02 | segunda execução → só os manifests | `tests/ciclo.rs:330`; pré-existente `tests/ciclo.rs:76-79` intacto | ✅ (M7 morto) |
| SIT-03 | só ATIVA; loc/lastmod exatos | `tests/site.rs:120-127`; ENCERRADA fora `tests/ciclo.rs:349`; ATIVA sem página fora `tests/site.rs:267` | ✅ (M4, M17, M20 mortos) |
| SIT-04 | encerrada sai do sitemap no mesmo ciclo | `tests/ciclo.rs:361` | ✅ |
| SIT-05 | expurgo: página, índice, sitemap | `tests/ciclo.rs:378-386`; com imagens `tests/geracao.rs:591-592` | ✅ |
| SIT-06 | 46k → 45 000 + 1 000 + index; parse; ≤ 50 MB | `tests/site.rs:64-88` | ✅ (M5a/M5b mortos) |
| SIT-07 | remove `sitemap-{n}` obsoleto | `tests/ciclo.rs:402` | ✅ (M14 morto) |
| SIT-08 | `User-agent: *\nDisallow: /\n` | `tests/site.rs:139`; `tests/dry_run.rs:278-281` | ✅ (M6 morto) |
| SIT-09 | `Allow: /` + `Sitemap: {base}/sitemap.xml` | `tests/site.rs:146-151`; virada no ciclo `tests/ciclo.rs:466` (robots exato, regravado) | ✅ (M12, N3, N4 mortos) |
| SIT-10 | CSS com headers; reenviado quando o hash muda | `tests/headers.rs:86`; `tests/ciclo.rs:515`, `:519` | ✅ (M11, N2 mortos) |
| SIT-11 | índice ilegível → sobe tudo, segue; (dono) reconstrói do bucket e expurga órfãs | `tests/ciclo.rs:424-437`; `tests/ciclo.rs:448-479`; só nesse caminho `tests/ciclo.rs:484-498` | ✅ (M16, R1, R2 mortos) |
| SIT-12 | `application/json`, `no-store` | `tests/headers.rs:88` | ✅ |
| SIT-13 | ordem MANIFEST §6 | `tests/geracao.rs:640` `ordem.windows(2).all(w0 < w1)` | ✅ (M10 morto) |
| SIT-14 | falha de upload de página → sem manifest | `tests/geracao.rs:686-688` | ✅ |
| SIT-15 | env inválida nomeada; base padrão | `tests/site.rs:190-194`, `:158`; binário `tests/dry_run.rs:333` | ✅ |

### P2

| Req | Resultado da spec | `file:line` + asserção | Resultado |
| --- | ----------------- | ---------------------- | --------- |
| PLN-01 | uma linha por tipo, contagem + 5 exemplos | `tests/plano.rs:396` linhas exatas; `:411` | ✅ (M18 morto) |

**Status**: 30/31 exatos; 1 com resíduo aceito (PRD-04 no binário).

### Edge cases
- [x] 0 ativas → `urlset` vazio + index: `tests/site.rs:106-109`
- [x] 45 000 exatas → 1 arquivo: `tests/site.rs:97-99`
- [x] base com `/` final: `tests/site.rs:214`
- [x] 30 720 bytes aceito: `tests/paginas.rs:174`

### AC do dono (`docs/specs/BSV-21.md`)
Todos cobertos em CI, exceto a execução real do dono (curl, Lighthouse, `--publicar --sim`, relatório real), que é fora do CI e **bloqueia o merge**.

---

## Decisões da iteração 2 (avaliação pedida pelo coordenador)

**PAG-07 sem teste no nível do `gerar`: aceito.**
- **Não há como chegar lá pelo `gerar`.** Conferi em `src/conversao.rs:78-79`, `:136`, `:183`: `para_pagina` corta o título em 400 e a descrição em 600, então nenhum campo textual de `LinhaOferta` sozinho leva o HTML a 30 KB. Um teste de ponta a ponta exigiria uma fixture artificial ou uma porta de injeção no template, ou seja, código só para o teste.
- **A cadeia está provada por partes:**
  1. `publicar_paginas` devolve o erro nomeado (`tests/paginas.rs:163`).
  2. `publicar_site` aborta antes do índice e dos sitemaps (`tests/site.rs:235-252`).
  3. O `gerar` propaga qualquer `ErroSite` com `?` em `src/geracao.rs:192`, antes de `sincronizar_redirects` e do manifest. SIT-14 prova esse mesmo `?` (`tests/geracao.rs:686-688`: sem manifest, sem índice, KVS vazia).
- **Um mutante que só engolisse `PaginaAcimaDoOrcamento` no `gerar`** exigiria um `match` específico, que hoje não existe. Risco residual baixo.

**M21 (`--dry-run` do binário): aceito como resíduo.**
- **A lógica está na lib e é discriminada:** `src/main.rs:212-215` só chama `contar_paginas` e imprime, e `contar_paginas` tem teste (`tests/geracao.rs:727-742`).
- **O binário não tem contador observável:** a `FakeFonte` roda dentro do subprocesso. Discriminar exigiria instrumentar o binário só para o teste.
- **O que o mutante injeta** (voltar a chamar `produto` por linha) é código novo, não a regressão de uma linha existente.
- **Recomendação:** o autor registra no PR que PRD-04 é garantido pela lib (`contar_paginas`) e que o `main` só delega.

**`tempo_render_ms > 0`:** pode ficar instável numa máquina muito rápida em release, mas o gate roda em debug e 300 renders levam dezenas de ms. Aceitável.

---

## Discrimination Sensor (iteração 2)

Scratch: `git worktree add --detach %TEMP%\bsv21-sensor2 HEAD` (`1fa2744`), `CARGO_TARGET_DIR=%TEMP%\bsv21-target`.
Cada mutação: aplicar → `cargo test -q --test <alvos>` → reverter. Depois: `git worktree remove --force`, `git worktree prune`,
`git worktree list` sem o scratch. `git status --porcelain` do tree real: vazio antes e depois → **isolamento OK**. Sem `git stash`.

| # | Local | Mutação | Testes | Resultado |
| - | ----- | ------- | ------ | --------- |
| M11 | `src/site.rs` (comparação `_css`) | CSS sobe só se `anterior.css.is_none()` | ciclo, site, geracao, headers | ✅ Morto (`css_com_hash_diferente_e_reenviado`) |
| M12 | `src/site.rs` (comparação `_robots`) | robots sobe só se `anterior.robots.is_none()` | ciclo, site, geracao, dry_run | ✅ Morto (`virada_para_indexavel_regrava_robots_e_sitemaps`) |
| M13 | `src/paginas.rs:115` | `tempo_render_ms = 0` | paginas, geracao, dry_run | ✅ Morto na iteração 2; ⚠️ vivo na iteração 3 porque o dono pediu para remover a asserção `> 0` (aceito) |
| M19 | `src/oracle.rs` `blocos_in` | blocos de 2 000 | oracle, fonte | ✅ Morto (`ids_de_produto_em_blocos_de_mil_sem_repetir`) |
| M20 | `src/site.rs:254` | sitemap sem o filtro "tem página no índice" | ciclo, paginas, site, geracao | ✅ Morto (`ativa_sem_pagina_fica_fora_do_sitemap`) |
| M21 | `src/main.rs:213` | `--dry-run` volta a chamar `produto` por linha | dry_run | ⚠️ Sobreviveu (resíduo aceito, ver acima) |
| N1 | `src/oracle.rs` `blocos_in` | sem dedup (só ordena) | oracle | ✅ Morto |
| N2 | `src/site.rs` | índice mantém o `_css` antigo (`novo.css = anterior.css`) | ciclo, site | ✅ Morto (4 testes) |
| N3 | `src/site.rs` | sitemap ignora `cfg.base` (base fixa) | ciclo, site, dry_run | ✅ Morto (`virada_para_indexavel…`) |
| N4 | `src/site.rs` | índice mantém o `_robots` antigo | ciclo, site | ✅ Morto (4 testes) |

### Iteração 3: trecho novo (reconstrução do índice)

Scratch: `git worktree add --detach %TEMP%sv21-sensor3 HEAD`, com os 3 arquivos alterados copiados. Rodei `cargo test -q --test ciclo indice_`, depois
`git worktree remove --force` + `prune`. O `git status --porcelain` do tree real ficou igual antes e depois → isolamento OK.

| # | Local | Mutação | Resultado |
| - | ----- | ------- | --------- |
| R1 | `src/site.rs:137` | sem reconstrução (`EstadoSite::default()` quando não há índice) | ✅ Morto (`indice_corrompido_reconstroi_do_bucket_e_remove_orfa`) |
| R2 | `src/site.rs` (braço `Some(Some(e))`) | reconstrói também com índice válido (lista `oferta/` em toda execução) | ✅ Morto (`indice_valido_nao_lista_nem_remove_pagina_fora_dele`) |

**Iteração 2**: 9/10 mortos. **Acumulado**: 17 mortos na iteração 1 + 9 aqui; o único vivo é M21, aceito.
O `warn!` novo em `src/geracao.rs:140` é só log e não foi mutado (a spec não exige asserção de log).

---

## Gate Check

- **Comando** (em `apps/worker/`): `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` → **exit 0**
- **Resultado (iteração 3)**: 207 passaram, 0 falharam, 3 ignorados. Na iteração 2 foram 205; +2 testes do ajuste 1 do dono. Os ignorados são (`#[ignore]` de desempenho: ciclo 30k, imagens, PAG-11)
- **Contagem**: 160 `#[test]` em `0c8b5b9` → 210 (207 rodados + 3 ignorados)
- **Integridade**: no ticket todo, a única asserção pré-existente trocada foi `tests/plano.rs:278` (`3 → 4`, por causa da página
  expurgada, com lista exata). A allowlist de `falha_na_kvs_nao_grava_manifest` foi ampliada (`tests/geracao.rs:459-466`), mas a
  perda é compensada por `:487` (chunk `1-` obrigatório) e `:491-495` (resto restrito à página, ao `sitemap-1.xml` e ao índice)

---

## Avaliação das Assumptions

| Decisão | Avaliação |
| ------- | --------- |
| Índice regravado só quando muda | Correto. A AC do dono permite, e o `apps/worker/CLAUDE.md` (idempotência) exige. O teste pré-existente `tests/ciclo.rs:76-79` continua exigindo só os manifests. Registrar no PR que a regra 2 ("regravado ao fim") foi lida como "quando muda" |
| Expurgo de página antes da KVS/manifest | Aceitável e coberto (`tests/plano.rs:283-287`). O risco de órfãs após índice ilegível foi **resolvido** pelo ajuste 1 do dono (reconstrução por `listar("oferta/")`); o README foi atualizado |
| Falha de render mantém o hash anterior | Correto (M15 morto). ATIVA nova com render falho fica fora do sitemap (M20 morto) |
| Gate de 30 KB durante os uploads | Aceitável; índice não gravado (`tests/site.rs:250`) |
| `para_pagina(..).ok()` | Resolvido: agora loga `card sem página` com o id (`src/geracao.rs:140`) |
| Demais (sitemap-1, lastmod UTC, ordem por id, env, roxmltree) | OK |

---

## Code Quality

| Princípio | Status |
| --------- | ------ |
| Mínimo / cirúrgico / sem scope creep | ✅ (`blocos_in` extraído só para testar, e o `OracleFonte` o usa: sem duplicação) |
| Segue os padrões (thiserror na lib, sem `unwrap` fora de teste, fakes) | ✅ |
| Resultado ancorado na spec | ✅ |
| Cobertura por camada | ✅ (Oracle I/O continua fora do CI pela matriz; a parte pura agora é testada) |
| Todo teste mapeia um requisito | ✅ |
| Guidelines (`CLAUDE.md`, `apps/worker/CLAUDE.md`; sem rede/Oracle/AWS em teste) | ✅ |

---

## Requirement Traceability Update

| Requirement | Status |
| ----------- | ------ |
| PAG-01..11, PRD-01..03, SIT-01..15, PLN-01 | ✅ Verified |
| PRD-04 | ✅ Verified (lib); resíduo M21 no binário aceito |

---

## Summary

**Overall**: ✅ Ready para PR. O merge continua bloqueado pela execução real do dono: `--publicar --sim`, `curl -I /oferta/<id>/`,
`robots.txt`, `sitemap.xml`, segunda execução com 0 páginas, Lighthouse ≥ 95 e relatório real no PR.

**Spec-anchored**: 30/31 exatos; PRD-04 (M21) e PAG-10 (M13) com resíduo aceito pelo dono. **Sensor**: iteração 3 com 2/2 mortos no trecho novo; vivos no total: M13 e M21, os dois aceitos. **Gate**: 207 passaram, 0 falharam.

**Registrado no corpo da PR** (pedido do dono): PAG-07 por composição, M21 como resíduo, índice regravado só quando muda.
