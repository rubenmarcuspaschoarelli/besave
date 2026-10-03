# BSV-12 Validation

**Verdict**: PASS ✅ (iteração 1, re-verificação após os ajustes de revisão T8–T11: 31/31 ACs com evidência, gate verde com 108 testes, 28/29 mutantes mortos; o único sobrevivente está no dublê de teste `PublicadorMemoria`, sem caminho de produção compilável que o exercite; fix task Minor F1, não bloqueante)

**Date**: 2026-09-25
**Spec**: `.specs/features/BSV-12/spec.md` + `docs/specs/BSV-12.md`
**Diff range**: `1653949..4adc852` (13 commits: `7a4b377`..`dee0099`, relatório `da528ad`, ajustes `ee26729`..`4adc852`; arquivos só em `apps/worker/` e `.specs/features/BSV-12/`)
**Iterações**: 0 (`dee0099`, PASS, 27 ACs, 18/18 mutantes) → 1 (`4adc852`, ajustes do dono: URL-04, KVS-08, KVS-09, PLN-04 e docs)
**Verifier**: sub-agente independente (author ≠ verifier)

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 `DS_URL_AFILIADO` + rejeição | ✅ Done | `5af3ce5` |
| T2 `meta_para` | ✅ Done | `c0326f3` |
| T3 `Redirects` + `sincronizar_redirects` | ✅ Done | `a8cd252` |
| T4 `gerar` sincroniza KVS antes do manifest | ✅ Done | `eb81af7` |
| T5 Plano | ✅ Done | `2537371` |
| T6 `PublicadorS3` + `RedirectsKvs` | ✅ Done | `f7f94fb` |
| T7 `--publicar [--sim]` + README | ✅ Done | `dee0099` |
| T8 URL vazia em `para_card` + `ValorVazio` na KVS | ✅ Done | `80c65f2` |
| T9 lotes mistos de `UpdateKeys` (`lotes_kvs`) | ✅ Done | `13a1837` |
| T10 plano contra destinos em memória + `Plano::linhas()` | ✅ Done | `0992a37` |
| T11 docs: regra da KVS e idempotência | ✅ Done | `4adc852` |

---

## Spec-Anchored Acceptance Criteria

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| URL-01 SQL + campo | `SQL_OFERTAS` seleciona `DS_URL_AFILIADO`; `LinhaOferta.url_afiliado: String` | `apps/worker/tests/oracle.rs:134` - `SQL_OFERTAS.contains("DS_URL_AFILIADO")`; campo usado em `tests/pagina.rs:31`, `tests/card.rs:33`, `tests/comum/mod.rs` (compila só se o campo é `String`); NULL → `""` por revisão: `apps/worker/src/oracle.rs:139` - `r.get::<_, Option<String>>(14)?.unwrap_or_default()` (coluna 14 = `, DS_URL_AFILIADO` em `src/oracle.rs:97`) | ✅ PASS (mapeamento de coluna só por revisão; exige Oracle) |
| URL-02 `para_pagina` sem URL | `Err(Rejeicao::UrlAfiliadoAusente)` para `""` e só espaços | `apps/worker/tests/pagina.rs:125-135` - `assert_eq!(para_pagina(&l, None, &m()), Err(Rejeicao::UrlAfiliadoAusente))` para `["", "   "]`; `tests/card.rs:289` idem. A checagem agora vem de `para_card` (`src/conversao.rs:101`), chamado na 1ª linha de `para_pagina` (`src/conversao.rs:130`); a chamada duplicada saiu do corpo de `para_pagina`. Comportamento preservado (teste inalterado desde `dee0099`, verde; mutante N01 o derruba) | ✅ PASS |
| URL-03 `gerar` sem URL | card não publicado; rejeição contada | `apps/worker/tests/geracao.rs:283-290` - `rejeitadas == {UrlAfiliadoAusente: 1}`, `validas == 1`, `total_ofertas == 1`, `chunks[0].ids == [2001, 2001]` (URL `" "`). `publicavel` (`src/geracao.rs:213-219`) delega a `para_card` (`:214`); a chamada a `url_afiliado` saiu dela. Comportamento preservado (N01 derruba este teste) | ✅ PASS |
| URL-04 `para_card` sem URL | `Err(Rejeicao::UrlAfiliadoAusente)` para `""` e só espaços | `apps/worker/tests/card.rs:276-294` - `assert_eq!(para_card(&l, &m), Err(Rejeicao::UrlAfiliadoAusente))` (`:284`) para `["", "   ", "\t\n"]`, e o mesmo para `para_pagina` (`:289`); implementação `src/conversao.rs:101` - `url_afiliado(l)?` | ✅ PASS |
| HDR-01 tabela MANIFEST §4 | os 3 headers literais de cada linha | `apps/worker/tests/headers.rs:25-73` - 17 chaves cobrindo as 10 linhas (manifest, chunks, busca, `oferta/*/index.html` `max-age=600, stale-while-revalidate=300`, área e área/público, 4 prefixos de `img/`, `_app/` js/css/json, `index.html`, `sitemap.xml`, `sitemap-0.xml`, `robots.txt`); `:72` - `assert_eq!(meta_para(chave), esperado)` com `Meta` literal completo | ✅ PASS |
| HDR-02 `manifest.prev.json` | headers do `manifest.json` | `apps/worker/tests/headers.rs:78-79` - `meta_para("manifest.prev.json") == meta_para("manifest.json")` e `is_some()` | ✅ PASS |
| HDR-03 chave fora da tabela | `None` | `apps/worker/tests/headers.rs:84-94` - `""`, `segredo.env`, `data/outro/x.json`, `oferta/5412/foto.jpg`, `img/ofertas/5412.png`, `_app/binario.exe`, `manifest.json.bak` → `None` | ✅ PASS |
| HDR-04 `gerar` usa a mesma `Meta` | `meta` gravada == `meta_para(chave)` | `apps/worker/tests/headers.rs:127` - `assert_eq!(p.meta(&c), meta_para(&c))` para toda gravação de dois ciclos (inclui chunk, `manifest.prev.json`, `manifest.json`, `:118-125`) | ✅ PASS |
| KVS-01 diff put | put {2→c, 3→d}, del {}; KVS {1→a,2→c,3→d} | `apps/worker/tests/redirects.rs:25` - `aplicados() == [([(2,"c"),(3,"d")], [])]`; `:26` - `(puts,dels,total) == (2,0,3)`; `:27-30` - `listar() == {1→a,2→c,3→d}` | ✅ PASS |
| KVS-02 diff del | del {2,3}, put {} | `apps/worker/tests/redirects.rs:33` - `aplicados()[1] == ([], [2,3])`; `:34` - `(0,2,1)`; `:35` - `listar() == {1→a}` | ✅ PASS |
| KVS-03 repetição | 0 puts, 0 dels, `aplicar` não chamado | `apps/worker/tests/redirects.rs:44` - `(puts,dels) == (0,0)`; `:45` - `aplicados().len() == 1` | ✅ PASS |
| KVS-04 valor > 1 024 B | `ValorGrandeDemais` com o id, sem `aplicar` | `apps/worker/tests/redirects.rs:70` - 1 024 B aceito; `:75-79` - `matches!(erro, ValorGrandeDemais { id: 7, bytes: 1025 })`; `:81` - `aplicados().len() == 1`; `:82` - `LIMITE_VALOR_BYTES == 1024` | ✅ PASS |
| KVS-05 total > 5 242 880 | `KvsAcimaDoLimite`, sem `aplicar` | `apps/worker/tests/redirects.rs:87` - `LIMITE_KVS_BYTES == 5*1024*1024`; `:93-96` - `matches!(erro, KvsAcimaDoLimite { bytes: 6_024_000 })` (chave + valor); `:97` - `aplicados().is_empty()`; `:101` - 5 020 000 B aceito | ✅ PASS |
| KVS-06 > 40 000 entradas | `WARN` com o total; sincroniza | `apps/worker/tests/redirects.rs:152` - `AVISO_ENTRADAS == 40_000`; `:158-160` - logs contêm `WARN` e `40001`, `listar().len() == 40_001`; `:166` - 40 000 exatos sem `WARN` | ✅ PASS |
| KVS-07 formato | chave = id decimal, valor = URL | `apps/worker/tests/redirects.rs:52-55` - `chaves() == {"5412" → "https://amzn.to/x"}` (estado bruto) | ✅ PASS |
| KVS-08 valor vazio | `ErroRedirects::ValorVazio { id }`, sem `aplicar` | `apps/worker/tests/redirects.rs:171-183` - para `["", "  "]`: `matches!(erro, ErroRedirects::ValorVazio { id: 9 })` (`:176`), `aplicados().is_empty()` (`:180`), `listar() == {1→a}` (`:181`); implementação `src/redirects.rs:60-62` (depois do `trim`, antes de qualquer escrita) | ✅ PASS |
| KVS-09 lotes de `UpdateKeys` | 120 chaves → 3 lotes (50, 50, 20) na ordem do diff; puts e deletes dividem o lote da fronteira; `RedirectsKvs::aplicar` faz 1 `UpdateKeys` por lote | `apps/worker/tests/redirects.rs:189` - `LOTE_KVS == 50`; `:194` - `lotes.len() == 3` para 70 puts + 50 dels; `:197` - `tamanhos == [(50,0),(20,30),(0,20)]`; `:198-204` - lote 2 == `LoteKvs { puts: put[50..], dels: del[..30] }`; `:207-208` - concatenação dos lotes == diff original (ordem); `:212-215` - 120 puts → `[50,50,20]`; `:216-217` - diff vazio → 0 lotes, 50 dels → 1 lote. Adaptador por revisão (sem rede): `src/aws.rs:260` - `for lote in lotes_kvs(put, del)` monta um par `(puts, dels)` por lote (`:282`); `:297-310` - um `update_keys().kvs_arn(..).if_match(etag).set_puts(puts).set_deletes(dels).send()` por par, ETag encadeado a partir de `describe_key_value_store` (`:290-295`). A `LOTE_KVS` local e os lotes separados puts→dels foram removidos | ✅ PASS (lotes: teste; 1 chamada/lote: revisão) |
| ORD-01 quem entra na KVS | todo card publicado (inclui expirado), nenhum rejeitado | `apps/worker/tests/geracao.rs:297-303` - `listar() == {1001,1500,5412,5413,5420}` com URLs (5420 expirado incluso; 1700 `preco_por` nulo e 1800 sem `id_produto` fora) | ✅ PASS |
| ORD-02 ordem | chunks → KVS → `manifest.prev.json` → `manifest.json` | `apps/worker/tests/geracao.rs:360` - `ultimo_chunk < kvs_em`; `:361` - `t[kvs_em..] == ["KVS","manifest.prev.json","manifest.json"]` | ✅ PASS |
| ORD-03 falha na KVS | `ErroGeracao::Redirects`; `manifest.json` não gravado | `apps/worker/tests/geracao.rs:374-376` - `matches!(erro, ErroGeracao::Redirects(_))`, `!existe("manifest.json")`, só chunks gravados; `:386-395` - 2º ciclo: manifest anterior intacto e nenhuma gravação fora de `data/chunks/` | ✅ PASS |
| ORD-04 `Relatorio` | puts e dels da KVS | `apps/worker/tests/geracao.rs:249-253` - `redirects: RelatorioRedirects { puts: 5, dels: 0, total: 5 }`; `apps/worker/tests/ciclo.rs:236`, `:239` - `(0,0)` e `(0,1)`; `apps/worker/tests/plano.rs:192-193` | ✅ PASS |
| ORD-05 expurgo | chave apagada na execução seguinte | `apps/worker/tests/ciclo.rs:233` - 5420 presente antes; `:239` - `(puts,dels) == (0,1)` após 7 dias; `:240-243` - chaves `== [1001,5412,5413,7001]` | ✅ PASS |
| PLN-01 plano não escreve | 0 `gravar`/`remover`/`aplicar` no destino | `apps/worker/tests/plano.rs:117` - `(p.gravar, p.remover, kvs.aplicar) == (0,0,0)`; `:118-120` - manifest, chaves e KVS do destino inalterados | ✅ PASS |
| PLN-02 conteúdo do plano | cada gravação (bytes, `Cache-Control`), remoção, putKey, deleteKey | `apps/worker/tests/plano.rs:146-151` - chunks 2 e 5 com `bytes > 0` e `immutable`; `:164-167` - últimas = `manifest.prev.json`/`manifest.json` com `max-age=300, stale-while-revalidate=60`; `:169-180` - exatamente 1 `Remover` = órfão; `:182-191` - `redirects == [PutKey{2001,url}, DeleteKey{5413}]`; `:196-221` - `Display` de cada operação | ✅ PASS |
| PLN-03 `--sim` | escritas chegam; plano vazio | `apps/worker/tests/plano.rs:229-230` - `objetos`/`redirects` vazios; `:231-233` - `gravar >= 4`, `remover == 1`, `aplicar == 1`; `:234-238` - órfão apagado, KVS `== [1001,2001,5412]` | ✅ PASS |
| PLN-04 plano contra memória + texto impresso | históricos de gravações/remoções do publicador e de `aplicar` da KVS inalterados; `Plano::linhas()` lista `gravar`, `remover`, `putKey`, `deleteKey` previstos | `apps/worker/tests/plano.rs:245-295` - `publicar(…, sim=false)` direto sobre `PublicadorMemoria`/`RedirectsMemoria` com histórico prévio (`:253`): `gravacoes().len()` (`:262`), `remocoes().len()` (`:263`) e `aplicados().len()` (`:264`) iguais aos de antes; `linhas()` com `S3:` antes de `KVS …` (`:272`), `gravar data/chunks/2-`/`5-` (`:276-277`), `gravar manifest.prev.json (` e `gravar manifest.json (` (`:279-286`), `remover {orfao}` (`:287`), `== [putKey 2001 {url}, deleteKey 5413]` (`:288-294`). Binário: `src/main.rs:101-102` - `for linha in pb.plano.linhas() { println!("{linha}") }` (a impressão em si só roda contra AWS; revisão) | ✅ PASS (ver F1: `remocoes()` sem controle positivo) |
| AWS-01 `PublicadorS3` | HeadObject (404→false), GetObject (ausente→None), PutObject com 3 headers, DeleteObject, ListObjectsV2 paginado | Sem teste por design (sem rede). Revisão (linhas em `4adc852`): `apps/worker/src/aws.rs:110-123` - `head_object`, `is_not_found()` → `Ok(false)` (`:120`); `:126-149` - `get_object`, `is_no_such_key()` → `Ok(None)` (`:137`); `:151-166` - `put_object` com `.content_type(meta.content_type)` (`:159`), `.set_content_encoding(…)`, `.cache_control(meta.cache_control)` (`:161`); `:169-180` - `delete_object`; `:183-203` - `list_objects_v2().prefix(..).into_paginator()` (`:191`). `ler` só é chamado para `manifest.json`, nunca para chunk (regra 2) | ✅ PASS (revisão) |
| AWS-02 `RedirectsKvs` | ListKeys paginado; UpdateKeys em lotes ≤ 50 com `IfMatch` do ETag corrente | `apps/worker/src/aws.rs:231-254` - `list_keys().into_paginator()` (`:238`), chave não numérica ignorada com `warn!` (`:250`); lotes de `lotes_kvs` com `LOTE_KVS = 50` (`src/redirects.rs:110`, testado em KVS-09); `:290-295` - ETag inicial de `describe_key_value_store`; `:297-310` - `.if_match(etag)`, `etag = resposta.e_tag()` encadeado | ✅ PASS (revisão) |
| AWS-03 env ausente | erro nomeando a variável, sem panic, sem rede | `apps/worker/tests/dry_run.rs:173-175` - `--publicar` sem env: `!success`, `code != 101`, stderr contém `BESAVE_BUCKET`; `:179-185` - com bucket: stderr contém `BESAVE_KVS_ARN` e não `BESAVE_BUCKET`. `ConfigAws::do_env()` (`src/main.rs:66`) roda antes de `ContextoAws::carregar` (`:92`) | ✅ PASS |
| AWS-04 `--sim` sem `--publicar` | erro, sem panic | `apps/worker/tests/dry_run.rs:189-193` - `--sim` e `--dry-run --sim`: `!success`, `code != 101`, stderr contém `--publicar` (`src/main.rs:59`) | ✅ PASS |
| AWS-05 sem credencial | nenhum campo de credencial em config, CLI ou log | `apps/worker/src/aws.rs:30-35` - `ConfigAws { bucket, kvs_arn }` só; `:69` - `aws_config::load_from_env()` (cadeia padrão); `src/main.rs` `Args` sem flag de credencial; prints só bucket e ARN (`src/main.rs:98-100`) | ✅ PASS (revisão) |

**Status**: 31/31 ACs com evidência `file:line` (27 da iteração 0 + URL-04, KVS-08, KVS-09, PLN-04); valores asseridos batem com o spec. AWS-01/02/05 e a parte "1 `UpdateKeys` por lote" de KVS-09 cobertas por revisão (sem rede nos testes, decisão do spec). `tests/{pagina,geracao,ciclo,headers,dry_run,oracle}.rs` inalterados desde `dee0099`; `tests/{card,redirects,plano}.rs` só ganharam testes no fim (e `card.rs` a URL na fixture, exigida agora por `para_card`).

### Ticket "Critério de aceite" (`docs/specs/BSV-12.md`)

| Item | Evidence | Result |
| ---- | -------- | ------ |
| `meta_para` tabular, 3 headers por prefixo | `headers.rs:25-73` | ✅ |
| {1→a,2→b} → {1→a,2→c,3→d} → {1→a} → repetição no-op | `redirects.rs:21-46` | ✅ |
| Falha injetada na KVS → erro, sem manifest | `geracao.rs:366-395` | ✅ |
| `--publicar` sem `--sim` não escreve (espião e memória) | `plano.rs:108-121`, `plano.rs:262-264` | ✅ |
| `cargo test` sem credenciais e sem rede | gate abaixo; `dry_run.rs:151-162` remove `AWS_*` do env do processo | ✅ |
| Execução real contra AWS (`curl -I`, `/ir/<id>` 302, 2ª execução zero escritas) | dono roda após BSV-4 | ⏭️ Pendente (dono) |
| DoD: README (`--publicar`, envs, plan/sim) | `apps/worker/README.md:83-142` (exemplo de plano no formato de `Plano::linhas()`, `:112-120`) | ✅ |
| DoD: saída do plano e execução real no PR | depende de BSV-4 | ⏭️ Pendente (dono) |
| Ajuste do dono: "a KVS espelha o conjunto publicado" | `apps/worker/src/redirects.rs:51-52` (doc de `sincronizar_redirects`); `apps/worker/README.md:138-139` | ✅ |
| Ajuste do dono: frase de idempotência | `apps/worker/CLAUDE.md:9` - "rodar duas vezes sem mudança não sobe nenhum objeto além de manifest.json e manifest.prev.json"; coerente com `README.md:140-141` | ✅ |

### Regras do ticket (inspeção estática)

| Regra | Evidência | Result |
| ----- | --------- | ------ |
| 2. `existe` = HeadObject; nunca GetObject de chunk | `aws.rs:110-123`; `gerar` compara chunk por `existe` (`geracao.rs:140`) | ✅ |
| 3. chunks → KVS → manifest → órfãos | `geracao.rs:140-146` chunks, `:155` KVS, `:168`/`:170` manifests, `:172-184` órfãos | ✅ |
| 4. só o diff; erros nomeados, sem panic | `redirects.rs:53-106` (inclui `ValorVazio` `:60-62`) | ✅ |
| 5. plano sai com 0; `--sim` executa | `plano.rs:153-178` (`publicar`), `main.rs:97-103` | ✅ |
| 6. credenciais só pela cadeia do SDK | `aws.rs:69` | ✅ |
| 7. retry do SDK, sem loop próprio | `aws.rs` sem `retry`/`sleep`; o único `for` novo itera lotes (`:260`, `:297`) | ✅ |
| 8. deps permitidas; async só na borda | `Cargo.toml` sem mudança em T8–T11; `lotes_kvs` síncrono no domínio | ✅ |
| Sem `unwrap`/`expect`/`panic!` fora de teste | grep em `src/{aws,plano,redirects,publicador,geracao,conversao,main}.rs`: 0 | ✅ |

---

## Discrimination Sensor

**Iteração 0 (M01–M18, HEAD `dee0099`; linhas daquele commit).** Scratch `git worktree add --detach <scratchpad>/v12 HEAD`; baseline 104/104; um mutante por vez (`sensor.py`), `cargo test --no-fail-fast` com `CARGO_TARGET_DIR` do tree real; worktree removido; porcelain do tree real inalterado.

| Mutation | File:line | Description | Killed? |
| -------- | --------- | ----------- | ------- |
| M01 | `apps/worker/src/geracao.rs:155` | KVS sincronizada depois de `manifest.json` | ✅ Killed |
| M02 | `apps/worker/src/redirects.rs:52` | sem `trim()` da URL | ✅ Killed |
| M03 | `apps/worker/src/publicador.rs:79-82` | `oferta/*/index.html` com `public, max-age=300` | ✅ Killed |
| M04 | `apps/worker/src/plano.rs:148` | `if sim` → `if sim \|\| true` | ✅ Killed |
| M05 | `apps/worker/src/redirects.rs:82` | diff nunca gera dels | ✅ Killed |
| M06 | `apps/worker/src/redirects.rs:63` | limite de 5 MB desligado | ✅ Killed |
| M07 | `apps/worker/src/redirects.rs:55` | `ValorGrandeDemais` `>` → `>=` | ✅ Killed |
| M08 | `apps/worker/src/geracao.rs:218` | `publicavel` sem checagem de URL | ✅ Killed (código removido em T8; coberto agora por N01) |
| M09 | `apps/worker/src/conversao.rs:133` | `para_pagina` sem checagem de URL | ✅ Killed (código removido em T8; coberto agora por N01) |
| M10 | `apps/worker/src/redirects.rs:85` | `aplicar` chamado sem diff | ✅ Killed |
| M11 | `apps/worker/src/redirects.rs:66` | `WARN` com `>=` 40 000 | ✅ Killed |
| M12 | `apps/worker/src/geracao.rs:103` | KVS só com cards ativos | ✅ Killed |
| M13 | `apps/worker/src/plano.rs:119-120` | `RedirectsPlano` descarta `DeleteKey` | ✅ Killed |
| M14 | `apps/worker/src/main.rs:59` | `--sim` aceito sem `--publicar` | ✅ Killed |
| M15 | `apps/worker/src/aws.rs:53` | `kvs_arn` lido de `BESAVE_BUCKET` | ✅ Killed |
| M16 | `apps/worker/src/redirects.rs:61` | limite total só com o valor | ✅ Killed |
| M17 | `apps/worker/src/geracao.rs:155` | `Relatorio.redirects` não preenchido | ✅ Killed |
| M18 | `apps/worker/src/publicador.rs:70` | `manifest.prev.json` sem headers | ✅ Killed |

**Iteração 1 (N01–N11, HEAD `4adc852`, só o comportamento novo de T8–T10).** Scratch novo `git worktree add --detach <scratchpad>/v12b HEAD`; baseline sem mutação = 108/108. Scripts `sensor2.py`/`sensor3.py` (substituição literal, um mutante por vez, arquivo restaurado byte a byte), `cargo test --no-fail-fast` com `CARGO_TARGET_DIR` = `apps/worker/target` do tree real. N03, N07 e N08 não compilaram na 1ª forma (borrow checker) e foram reescritos em forma compilável antes de contar. Worktree removido (`git worktree remove --force` + `prune`); `git status --porcelain` do tree real idêntico ao baseline (vazio) antes deste relatório.

| Mutation | File:line | Description | Killed? |
| -------- | --------- | ----------- | ------- |
| N01 | `apps/worker/src/conversao.rs:101` | `para_card` sem `url_afiliado(l)?` | ✅ Killed (`url_afiliado_vazia_rejeita_card_e_pagina`, `url_afiliado_vazia_rejeita_a_pagina`, `sem_url_de_afiliado_nao_publica_o_card`) |
| N02 | `apps/worker/src/redirects.rs:60-62` | checagem `ValorVazio` removida | ✅ Killed (`valor_vazio_e_erro_nomeado_sem_aplicar`) |
| N03 | `apps/worker/src/redirects.rs:133-139` | puts e deletes em lotes separados (resto de puts vira lote próprio) | ✅ Killed (`diff_de_120_chaves_vira_3_lotes_mistos`) |
| N04 | `apps/worker/src/redirects.rs:110` | `LOTE_KVS = 49` | ✅ Killed (`diff_de_120_chaves_vira_3_lotes_mistos`) |
| N05 | `apps/worker/src/redirects.rs:110` | `LOTE_KVS = 51` | ✅ Killed (`diff_de_120_chaves_vira_3_lotes_mistos`) |
| N06 | `apps/worker/src/redirects.rs:125` | fronteira em 51 com a constante intacta | ✅ Killed (`diff_de_120_chaves_vira_3_lotes_mistos`) |
| N07 | `apps/worker/src/plano.rs:168-170` | modo plano grava no `Publicador` real (KVS ainda planejada) | ✅ Killed (`plano_contra_memoria_registra_zero_escritas_e_lista_previsto`, `plano_nao_chama_escrita_no_destino`, `plano_lista_gravacoes_remocoes_e_chaves`) |
| N08 | `apps/worker/src/plano.rs:168-170` | modo plano aplica na KVS real (S3 ainda planejado) | ✅ Killed (mesmos 3) |
| N09 | `apps/worker/src/plano.rs:140` | `Plano::linhas()` omite os redirects | ✅ Killed (`plano_contra_memoria_registra_zero_escritas_e_lista_previsto`) |
| N10 | `apps/worker/src/plano.rs:81-85` | `PublicadorPlano::remover` não registra `Remover` | ✅ Killed (`plano_lista_gravacoes_remocoes_e_chaves`, `plano_contra_memoria_…`) |
| N11 | `apps/worker/src/publicador.rs:264` | `PublicadorMemoria::remover` não registra em `remocoes` | ❌ Survived (1ª rodada falhou só `trinta_mil_cards_em_ate_10_segundos`, por tempo; isolado: 108/108 verdes) → F1 |

Não mutados (sem teste por design; revisão acima): `src/aws.rs:258-313` (`RedirectsKvs::aplicar` sobre `lotes_kvs`) e `src/main.rs:101-102` (impressão de `linhas()`); exigem AWS.

**Sensor depth**: expandido (integridade do redirect de afiliado e proteção contra escrita)
**Result**: 28/29 killed (iteração 0: 18/18; iteração 1: 10/11) - PASS ✅ com ressalva Minor F1. N11 está no dublê de teste: `PublicadorPlano` guarda `&dyn Publicador` (`src/plano.rs:49-50`) e `remover` exige `&mut self`, então nenhuma mutação de produção compilável leva uma remoção do plano ao destino sem também desviar `gravar` (N07, morto por `gravacoes()`). Risco baixo; F1 dá controle positivo à asserção `remocoes()` de PLN-04.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code | ✅ (`lotes_kvs`/`LoteKvs` extraídos para o domínio só para testar KVS-09 sem rede; `PublicadorMemoria::remocoes` e `Plano::linhas` são o mínimo para PLN-04) |
| Surgical changes | ✅ (T8–T11 só em `apps/worker/` e `.specs/features/BSV-12/`; `url_afiliado` movida para `para_card` e removida dos dois pontos que a duplicavam) |
| No scope creep | ✅ |
| Matches patterns | ✅ (`thiserror`, fakes em memória, testes no fim dos arquivos existentes) |
| Spec-anchored outcome check | ✅ (valores literais: `ValorVazio { id: 9 }`, `[(50,0),(20,30),(0,20)]`, linhas `putKey 2001 …`/`deleteKey 5413`) |
| Per-layer Coverage Expectation | ✅ domínio 1:1 (URL, HDR, KVS, ORD, PLN); adaptadores AWS e impressão do binário por revisão, como no matrix |
| Every test maps to a spec requirement | ✅ (os 4 testes novos mapeiam 1:1 para URL-04, KVS-08, KVS-09, PLN-04) |
| Documented guidelines followed: `CLAUDE.md`, `apps/worker/CLAUDE.md`, `docs/specs/BSV-12.md` regras 1-8 | ✅ |

---

## Edge Cases

- [x] Fonte sem card válido → KVS vazia (dels de todas as numéricas) - `apps/worker/tests/redirects.rs:110-114`
- [x] Chave não numérica → ignorada por `listar`, nunca apagada - `apps/worker/tests/redirects.rs:109-114`; adaptador `src/aws.rs:250`
- [x] URL com espaços → valor trimado - `apps/worker/tests/redirects.rs:61-63`
- [x] URL só de espaços → barrada antes da KVS: no card (`tests/card.rs:284`) e, em defesa, no sync (`tests/redirects.rs:176`)
- [x] Diff vazio → nenhum lote / nenhum `aplicar` - `tests/redirects.rs:216`, `:45`

---

## Gate Check

- **Gate command**: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` (em `apps/worker`)
- **Result**: exit 0; 108 passed, 0 failed, 0 skipped (HEAD `4adc852`; fmt e clippy limpos)
- **Test count before feature** (`1653949`): 77
- **Test count iteração 0** (`dee0099`): 104
- **Test count after feature** (`4adc852`): 108
- **Delta**: +31 (iteração 0: +27; iteração 1: card +1, redirects +2, plano +1); nenhum `assert`/`#[test]` removido em `tests/` (`da528ad..4adc852` só adiciona)
- **Skipped tests**: nenhum
- **Failures**: nenhuma
- **Observação**: `ciclo.rs` `trinta_mil_cards_em_ate_10_segundos` (limite de tempo em build debug) falhou 2× durante o sensor com compilação concorrente; verde no gate isolado. Pode ficar instável sob carga de CI.

---

## Spec-precision gaps

- Nenhum AC com resultado indefinido. Observações (não bloqueiam):
  1. URL-01: o mapeamento da coluna 14 (`DS_URL_AFILIADO`, NULL → `""`) só é verificável por revisão. Coberto quando o dono rodar contra o Oracle.
  2. AWS-01/02/05 e "1 `UpdateKeys` por lote" (KVS-09): só por revisão (decisão do spec: sem rede e sem mock novo). Risco para BSV-4: `HeadObject`/`GetObject` de chave ausente só devolvem 404/`NoSuchKey` se o IAM tiver `s3:ListBucket`; `ListObjectsV2` já exige essa permissão, então a política de BSV-4 deve incluí-la.
  3. Assumptions do spec seguem marcadas `n` (não confirmadas pelo dono); os testes seguem essas decisões.

---

## Fix Plans

### F1: controle positivo para `PublicadorMemoria::remocoes()` (N11)

- **Root cause**: PLN-04 afirma `remocoes().len()` inalterado, mas nenhum teste afirma que `remocoes()` registra uma remoção real; o registro pode sumir sem nenhum teste falhar.
- **Fix task**: em `apps/worker/tests/plano.rs`, após o `--sim` de `sim_escreve_no_destino_e_plano_vem_vazio`, `assert_eq!(p.dentro.remocoes(), [orfao])`.
- **Priority**: Minor (dublê de teste; o tipo `&dyn Publicador` do plano já impede vazamento de `remover` em produção). Não bloqueia.

---

## Summary

**Overall**: ✅ Ready (pendente só a execução real do dono após BSV-4; F1 opcional)

**Spec-anchored check**: 31/31 ACs com evidência e valor alinhado ao spec; 0 spec-precision gaps bloqueantes
**Sensor**: 28/29 mutações mortas (N11 sobrevive no dublê de teste → F1, Minor)
**Gate**: 108 passed, 0 failed

**What works**: rejeição de URL de afiliado vazia em `para_card` (card e página) e barreira `ValorVazio` na KVS; tabela de headers de MANIFEST §4; diff da KVS em lotes mistos de até 50 com limites nomeados e aviso; KVS entre chunks e manifest com falha preservando o manifest antigo; modo plano sem escrita, com o texto impresso testado; `--publicar`/`--sim` com erros de config sem panic; docs da regra da KVS e da idempotência.

**Next steps**: F1 (opcional); dono roda `--publicar` (plano) e `--publicar --sim` contra a AWS após BSV-4 e cola as saídas no PR.

---

## Adendo do autor (pós-verificação)

- **F1 resolvido** em `4cd59a1` (+ `aa2196f`, ajuste de clippy): `tests/plano.rs` (`sim_escreve_no_destino_e_plano_vem_vazio`) agora afirma `p.dentro.remocoes() == [orfao]` após o `--sim`. N11 reexecutado (linha `self.remocoes.push` removida de `src/publicador.rs`): `plano` falha 1/4 → **killed**. Sensor: 29/29.
