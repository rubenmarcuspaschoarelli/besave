# BSV-12 Validation

**Verdict**: PASS ✅ (iteração 0: 27/27 ACs com evidência, gate verde com 104 testes, 18/18 mutantes mortos)

**Date**: 2026-09-25
**Spec**: `.specs/features/BSV-12/spec.md` + `docs/specs/BSV-12.md`
**Diff range**: `1653949..HEAD` (8 commits, `7a4b377`..`dee0099`; arquivos só em `apps/worker/` e `.specs/features/BSV-12/`)
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

---

## Spec-Anchored Acceptance Criteria

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| URL-01 SQL + campo | `SQL_OFERTAS` seleciona `DS_URL_AFILIADO`; `LinhaOferta.url_afiliado: String` | `apps/worker/tests/oracle.rs:134` - `SQL_OFERTAS.contains("DS_URL_AFILIADO")`; campo usado em `tests/pagina.rs:31`, `tests/comum/mod.rs` (compila só se o campo é `String`); NULL → `""` por revisão: `apps/worker/src/oracle.rs:139` - `r.get::<_, Option<String>>(14)?.unwrap_or_default()` (coluna 14 = `, DS_URL_AFILIADO` em `src/oracle.rs:97`) | ✅ PASS (mapeamento de coluna só por revisão; exige Oracle) |
| URL-02 `para_pagina` sem URL | `Err(Rejeicao::UrlAfiliadoAusente)` para `""` e só espaços | `apps/worker/tests/pagina.rs:131-135` - `assert_eq!(para_pagina(&l, None, &m()), Err(Rejeicao::UrlAfiliadoAusente))` para `["", "   "]` | ✅ PASS |
| URL-03 `gerar` sem URL | card não publicado; rejeição contada | `apps/worker/tests/geracao.rs:283-290` - `rejeitadas == {UrlAfiliadoAusente: 1}`, `validas == 1`, `total_ofertas == 1`, `chunks[0].ids == [2001, 2001]` (URL `" "`) | ✅ PASS |
| HDR-01 tabela MANIFEST §4 | os 3 headers literais de cada linha | `apps/worker/tests/headers.rs:25-73` - 17 chaves cobrindo as 10 linhas (manifest, chunks, busca, `oferta/*/index.html` `max-age=600, stale-while-revalidate=300`, área e área/público, 4 prefixos de `img/`, `_app/` js/css/json, `index.html`, `sitemap.xml`, `sitemap-0.xml`, `robots.txt`); `:72` - `assert_eq!(meta_para(chave), esperado)` com `Meta` literal completo | ✅ PASS |
| HDR-02 `manifest.prev.json` | headers do `manifest.json` | `apps/worker/tests/headers.rs:78-79` - `meta_para("manifest.prev.json") == meta_para("manifest.json")` e `is_some()` | ✅ PASS |
| HDR-03 chave fora da tabela | `None` | `apps/worker/tests/headers.rs:84-94` - `""`, `segredo.env`, `data/outro/x.json`, `oferta/5412/foto.jpg`, `img/ofertas/5412.png`, `_app/binario.exe`, `manifest.json.bak` → `None` | ✅ PASS |
| HDR-04 `gerar` usa a mesma `Meta` | `meta` gravada == `meta_para(chave)` | `apps/worker/tests/headers.rs:127` - `assert_eq!(p.meta(&c), meta_para(&c))` para toda gravação de dois ciclos (inclui chunk, `manifest.prev.json`, `manifest.json`, `:118-125`) | ✅ PASS |
| KVS-01 diff put | put {2→c, 3→d}, del {}; KVS {1→a,2→c,3→d} | `apps/worker/tests/redirects.rs:25` - `aplicados() == [([(2,"c"),(3,"d")], [])]`; `:26` - `(puts,dels,total) == (2,0,3)`; `:27-30` - `listar() == {1→a,2→c,3→d}` | ✅ PASS |
| KVS-02 diff del | del {2,3}, put {} | `apps/worker/tests/redirects.rs:33` - `aplicados()[1] == ([], [2,3])`; `:34` - `(0,2,1)`; `:35` - `listar() == {1→a}` | ✅ PASS |
| KVS-03 repetição | 0 puts, 0 dels, `aplicar` não chamado | `apps/worker/tests/redirects.rs:44` - `(puts,dels) == (0,0)`; `:45` - `aplicados().len() == 1` | ✅ PASS |
| KVS-04 valor > 1 024 B | `ValorGrandeDemais` com o id, sem `aplicar` | `apps/worker/tests/redirects.rs:70` - 1 024 B aceito; `:75-79` - `matches!(erro, ValorGrandeDemais { id: 7, bytes: 1025 })`; `:81` - `aplicados().len() == 1` (só a chamada anterior válida); `:82` - `LIMITE_VALOR_BYTES == 1024` | ✅ PASS |
| KVS-05 total > 5 242 880 | `KvsAcimaDoLimite`, sem `aplicar` | `apps/worker/tests/redirects.rs:87` - `LIMITE_KVS_BYTES == 5*1024*1024`; `:93-96` - `matches!(erro, KvsAcimaDoLimite { bytes: 6_024_000 })` (chave + valor); `:97` - `aplicados().is_empty()`; `:101` - 5 020 000 B aceito | ✅ PASS |
| KVS-06 > 40 000 entradas | `WARN` com o total; sincroniza | `apps/worker/tests/redirects.rs:152` - `AVISO_ENTRADAS == 40_000`; `:158-160` - logs contêm `WARN` e `40001`, `listar().len() == 40_001`; `:166` - 40 000 exatos sem `WARN` | ✅ PASS |
| KVS-07 formato | chave = id decimal, valor = URL | `apps/worker/tests/redirects.rs:52-55` - `chaves() == {"5412" → "https://amzn.to/x"}` (estado bruto) | ✅ PASS |
| ORD-01 quem entra na KVS | todo card publicado (inclui expirado), nenhum rejeitado | `apps/worker/tests/geracao.rs:297-303` - `listar() == {1001,1500,5412,5413,5420}` com URLs (5420 expirado incluso; 1700 `preco_por` nulo e 1800 sem `id_produto` fora) | ✅ PASS |
| ORD-02 ordem | chunks → KVS → `manifest.prev.json` → `manifest.json` | `apps/worker/tests/geracao.rs:360` - `ultimo_chunk < kvs_em`; `:361` - `t[kvs_em..] == ["KVS","manifest.prev.json","manifest.json"]` (linha do tempo comum a publicador e KVS, 2º ciclo com diff) | ✅ PASS |
| ORD-03 falha na KVS | `ErroGeracao::Redirects`; `manifest.json` não gravado | `apps/worker/tests/geracao.rs:374-376` - `matches!(erro, ErroGeracao::Redirects(_))`, `!existe("manifest.json")`, só chunks gravados; `:386-395` - 2º ciclo: manifest anterior intacto (`ler == antes`) e nenhuma gravação fora de `data/chunks/` (nem `manifest.prev.json`) | ✅ PASS |
| ORD-04 `Relatorio` | puts e dels da KVS | `apps/worker/tests/geracao.rs:249-253` - igualdade estrutural `redirects: RelatorioRedirects { puts: 5, dels: 0, total: 5 }`; `apps/worker/tests/ciclo.rs:236`, `:239` - `(0,0)` e `(0,1)`; `apps/worker/tests/plano.rs:192-193` | ✅ PASS |
| ORD-05 expurgo | chave apagada na execução seguinte | `apps/worker/tests/ciclo.rs:233` - 5420 presente antes; `:239` - `(puts,dels) == (0,1)` após 7 dias; `:240-243` - chaves `== [1001,5412,5413,7001]` | ✅ PASS |
| PLN-01 plano não escreve | 0 `gravar`/`remover`/`aplicar` no destino | `apps/worker/tests/plano.rs:117` - `(p.gravar, p.remover, kvs.aplicar) == (0,0,0)`; `:118-120` - manifest, chaves e KVS do destino inalterados (ciclo com chunk novo, órfão e diff na KVS) | ✅ PASS |
| PLN-02 conteúdo do plano | cada gravação (bytes, `Cache-Control`), remoção, putKey, deleteKey | `apps/worker/tests/plano.rs:146-147` - chunk 2 com `bytes > 0` e `immutable`; `:148-151` - chunk 5; `:164-167` - últimas = `manifest.prev.json`/`manifest.json` com `max-age=300, stale-while-revalidate=60`; `:169-180` - exatamente 1 `Remover` = órfão; `:182-191` - `redirects == [PutKey{2001,url}, DeleteKey{5413}]`; `:196-221` - texto impresso `putKey …`, `deleteKey 5413`, `remover …`, `gravar … (N B, public, max-age=31536000, immutable)` | ✅ PASS |
| PLN-03 `--sim` | escritas chegam; plano vazio | `apps/worker/tests/plano.rs:229-230` - `objetos`/`redirects` vazios; `:231-233` - `gravar >= 4`, `remover == 1`, `aplicar == 1`; `:234-238` - órfão apagado, KVS `== [1001,2001,5412]` | ✅ PASS |
| AWS-01 `PublicadorS3` | HeadObject (404→false), GetObject (ausente→None), PutObject com 3 headers, DeleteObject, ListObjectsV2 paginado | Sem teste por design (sem rede). Revisão: `apps/worker/src/aws.rs:113-126` - `head_object`, `is_not_found()` → `Ok(false)`; `:129-152` - `get_object`, `is_no_such_key()` → `Ok(None)`; `:154-169` - `put_object` com `.content_type(meta.content_type)`, `.set_content_encoding(meta.content_encoding…)`, `.cache_control(meta.cache_control)`; `:172-183` - `delete_object`; `:186-206` - `list_objects_v2().prefix(..).into_paginator().send().try_collect()`. `ler` só é chamado para `manifest.json` (`geracao.rs`), nunca para chunk (regra 2) | ✅ PASS (revisão) |
| AWS-02 `RedirectsKvs` | ListKeys paginado; UpdateKeys em lotes ≤ 50 com `IfMatch` do ETag corrente | `apps/worker/src/aws.rs:234-257` - `list_keys().into_paginator().items().send().try_collect()`, chave não numérica ignorada com `warn!`; `:19` - `LOTE_KVS = 50`; `:282-290` - ETag inicial de `describe_key_value_store`; `:291-308` - `chunks(LOTE_KVS)`, `.if_match(etag)`, `etag = resposta.e_tag()` encadeado | ✅ PASS (revisão) |
| AWS-03 env ausente | erro nomeando a variável, sem panic, sem rede | `apps/worker/tests/dry_run.rs:173-175` - `--publicar` sem env: `!success`, `code != 101`, stderr contém `BESAVE_BUCKET`; `:179-185` - com bucket: stderr contém `BESAVE_KVS_ARN` e não `BESAVE_BUCKET`. Sem rede: `ConfigAws::do_env()` em `src/main.rs:66` roda antes da fonte e de `ContextoAws::carregar` (`:92`) | ✅ PASS |
| AWS-04 `--sim` sem `--publicar` | erro, sem panic | `apps/worker/tests/dry_run.rs:189-193` - `--sim` e `--dry-run --sim`: `!success`, `code != 101`, stderr contém `--publicar` (`src/main.rs:59`) | ✅ PASS |
| AWS-05 sem credencial | nenhum campo de credencial em config, CLI ou log | `apps/worker/src/aws.rs:33-38` - `ConfigAws { bucket, kvs_arn }` só; `:67-80` - `aws_config::load_from_env()` (cadeia padrão); `src/main.rs` `Args` sem flag de credencial; logs/prints só bucket e ARN (`src/main.rs:98-100`). `grep -i "secret\|access_key\|credential\|token\|password"` em `src/{aws,main,plano,redirects}.rs`: só comentários (`aws.rs:2`, `:31`) | ✅ PASS (revisão) |

**Status**: 27/27 ACs com evidência `file:line`; valores asseridos batem com o spec. AWS-01/02/05 cobertos por revisão (sem rede nos testes, decisão do spec).

### Ticket "Critério de aceite" (`docs/specs/BSV-12.md`)

| Item | Evidence | Result |
| ---- | -------- | ------ |
| `meta_para` tabular, 3 headers por prefixo | `headers.rs:25-73` | ✅ |
| {1→a,2→b} → {1→a,2→c,3→d} → {1→a} → repetição no-op | `redirects.rs:21-46` | ✅ |
| Falha injetada na KVS → erro, sem manifest | `geracao.rs:366-395` | ✅ |
| `--publicar` sem `--sim` não escreve (espião) | `plano.rs:108-121` | ✅ |
| `cargo test` sem credenciais e sem rede | gate abaixo; `dry_run.rs:151-162` remove `AWS_*` do env do processo | ✅ |
| Execução real contra AWS (`curl -I`, `/ir/<id>` 302, 2ª execução zero escritas) | dono roda após BSV-4 | ⏭️ Pendente (dono) |
| DoD: README (`--publicar`, envs, plan/sim) | `apps/worker/README.md:83-130` | ✅ |
| DoD: saída do plano e execução real no PR | depende de BSV-4 | ⏭️ Pendente (dono) |

### Regras do ticket (inspeção estática)

| Regra | Evidência | Result |
| ----- | --------- | ------ |
| 2. `existe` = HeadObject; nunca GetObject de chunk | `aws.rs:113-126`; `gerar` compara chunk por `existe` (`geracao.rs:140`) | ✅ |
| 3. chunks → KVS → manifest → órfãos | `geracao.rs:140-146` chunks, `:155` KVS, `:168`/`:170` manifests, `:172-184` órfãos | ✅ |
| 4. só o diff; erros nomeados, sem panic | `redirects.rs:52-87` | ✅ |
| 5. plano sai com 0; `--sim` executa | `plano.rs:140-165` (`publicar`), `main.rs:97-103` | ✅ |
| 6. credenciais só pela cadeia do SDK | `aws.rs:67-80` | ✅ |
| 7. retry do SDK, sem loop próprio | `aws.rs` sem `loop`/`retry`/`sleep` (grep: 0) | ✅ |
| 8. deps permitidas; async só na borda | `Cargo.toml`: `aws-config`, `aws-sdk-s3`, `aws-sdk-cloudfrontkeyvaluestore` (sem default features), `tokio` só `rt`; `gerar` síncrono, `block_on` em runtime `current_thread` compartilhado (`aws.rs:59-80`) | ✅ |
| Sem `unwrap`/`expect`/`panic!` fora de teste | grep em `src/{aws,plano,redirects,publicador,geracao,main}.rs`: 0 | ✅ |

---

## Discrimination Sensor

Scratch: `git worktree add --detach <scratchpad>/v12 HEAD`; baseline sem mutação no scratch = 104/104 verdes. Um mutante por vez aplicado por script (`sensor.py`, substituição literal), `cargo test --no-fail-fast` (suíte inteira) com `CARGO_TARGET_DIR` = `apps/worker/target` do tree real (reuso das deps AWS já compiladas), arquivo restaurado byte a byte depois de cada um. Worktree removido com `git worktree remove --force`. `git status --porcelain` do tree real: vazio antes; depois, só `?? .specs/features/BSV-12/validation.md` (este relatório). Nenhum arquivo de produção ou teste do tree real foi tocado.

| Mutation | File:line | Description | Killed? |
| -------- | --------- | ----------- | ------- |
| M01 | `apps/worker/src/geracao.rs:155` | KVS sincronizada depois de `manifest.json` (passo movido para após `:170`) | ✅ Killed (`falha_na_kvs_nao_grava_manifest`, `kvs_entre_chunks_e_manifest`) |
| M02 | `apps/worker/src/redirects.rs:52` | sem `trim()` da URL | ✅ Killed (`url_e_trimada`) |
| M03 | `apps/worker/src/publicador.rs:79-82` | `oferta/*/index.html` com `public, max-age=300` | ✅ Killed (`tabela_do_manifest_md_secao_4`) |
| M04 | `apps/worker/src/plano.rs:148` | `if sim` → `if sim \|\| true` (plano escreve no destino) | ✅ Killed (`plano_nao_chama_escrita_no_destino`, `plano_lista_gravacoes_remocoes_e_chaves`) |
| M05 | `apps/worker/src/redirects.rs:82` | diff nunca gera dels | ✅ Killed (`diff_put_e_del_so_do_que_mudou`, `chave_nao_numerica_e_preservada`, `expurgo_apaga_a_chave_na_kvs`, 2 de `plano`) |
| M06 | `apps/worker/src/redirects.rs:63` | checagem do limite de 5 MB desligada | ✅ Killed (`total_acima_de_5_mb_e_erro_nomeado`) |
| M07 | `apps/worker/src/redirects.rs:55` | `ValorGrandeDemais` off-by-one (`>` → `>=`) | ✅ Killed (`valor_acima_de_1024_bytes_e_erro_nomeado`) |
| M08 | `apps/worker/src/geracao.rs:218` | `publicavel` sem checagem de URL | ✅ Killed (`sem_url_de_afiliado_nao_publica_o_card`) |
| M09 | `apps/worker/src/conversao.rs:133` | `para_pagina` sem checagem de URL | ✅ Killed (`url_afiliado_vazia_rejeita_a_pagina`) |
| M10 | `apps/worker/src/redirects.rs:85` | `aplicar` chamado mesmo sem diff | ✅ Killed (`mesma_entrada_duas_vezes_segunda_e_noop`) |
| M11 | `apps/worker/src/redirects.rs:66` | `WARN` com `>=` 40 000 | ✅ Killed (`acima_de_40_mil_entradas_avisa_e_sincroniza`) |
| M12 | `apps/worker/src/geracao.rs:103` | KVS só com cards ativos (sem expirados `x:1`) | ✅ Killed (`kvs_recebe_url_de_todo_card_publicado`, `expurgo_apaga_a_chave_na_kvs`, `relatorio_com_contagens`) |
| M13 | `apps/worker/src/plano.rs:119-120` | `RedirectsPlano` descarta `DeleteKey` | ✅ Killed (`plano_lista_gravacoes_remocoes_e_chaves`) |
| M14 | `apps/worker/src/main.rs:59` | `--sim` aceito sem `--publicar` | ✅ Killed (`sim_sem_publicar_sai_com_erro`) |
| M15 | `apps/worker/src/aws.rs:53` | `kvs_arn` lido de `BESAVE_BUCKET` | ✅ Killed (`publicar_sem_arn_da_kvs_nomeia_a_variavel`) |
| M16 | `apps/worker/src/redirects.rs:61` | limite total conta só o valor (sem a chave) | ✅ Killed (`total_acima_de_5_mb_e_erro_nomeado`) |
| M17 | `apps/worker/src/geracao.rs:155` | `Relatorio.redirects` não preenchido | ✅ Killed (`relatorio_com_contagens`, `expurgo_apaga_a_chave_na_kvs`, `plano_lista_gravacoes_remocoes_e_chaves`) |
| M18 | `apps/worker/src/publicador.rs:70` | `manifest.prev.json` sem headers (`None`) | ✅ Killed (`manifest_prev_tem_headers_do_manifest`, `gerar_grava_com_a_meta_da_tabela`) |

**Sensor depth**: expandido (integridade do redirect de afiliado e proteção contra escrita: ≥ 5 mutações cobrindo todos os ramos novos de domínio, plano e binário)
**Result**: 18/18 killed - PASS ✅. `aws.rs` (adaptadores) fora do sensor além de M15: sem teste por design (revisão acima).

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code | ✅ (`RedirectsMemoria::inserir_bruto`/`chaves`/`aplicados` e `Operacao: Display` existem para testar edge case, KVS-07 e PLN-02) |
| Surgical changes | ✅ (só `apps/worker/` e `.specs/features/BSV-12/`; `gerar` só ganhou o parâmetro `redirects`, o passo KVS e a coleta de URLs) |
| No scope creep | ✅ (sem imagens, HTML, sitemap, invalidação; `--gerar --destino s3` do ticket substituído por `--publicar`, que o próprio ticket lista como alternativa) |
| Matches patterns | ✅ (`thiserror`, fakes em memória, relatório `chave: valor`, testes de binário via `CARGO_BIN_EXE`) |
| Spec-anchored outcome check | ✅ (valores literais: put/del exatos, `bytes: 1025`, `bytes: 6_024_000`, `40001`, headers literais) |
| Per-layer Coverage Expectation | ✅ domínio 1:1 (URL, HDR, KVS, ORD, PLN); binário cobre 4 caminhos de erro; adaptadores AWS só build gate, como no matrix |
| Every test maps to a spec requirement | ✅ (`falha_injetada_vira_erro` e `publicar_e_gerar_juntos_saem_com_erro` = suporte a ORD-03 e ao `ArgGroup`) |
| Documented guidelines followed: `CLAUDE.md`, `apps/worker/CLAUDE.md`, `docs/specs/BSV-12.md` regras 1-8 | ✅ |

---

## Edge Cases

- [x] Fonte sem card válido → KVS vazia (dels de todas as numéricas) - `apps/worker/tests/redirects.rs:110` - `sincronizar_redirects(&[], …)` apaga `"1"`; `:111-114` - só a chave não numérica sobra
- [x] Chave não numérica → ignorada por `listar`, nunca apagada - `apps/worker/tests/redirects.rs:109` - `listar() == {1→a}` com `"config"` presente; `:111-114` - `chaves() == {"config"→"x"}`; no adaptador real: `src/aws.rs:249-254`
- [x] URL com espaços → valor trimado - `apps/worker/tests/redirects.rs:61-63` - KVS `{1→"https://a"}` + ativo `"  https://a \n"` → `(0,0)` e estado inalterado (trim em `src/redirects.rs:52`; `gerar` também trima em `src/geracao.rs:103`)

---

## Gate Check

- **Gate command**: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` (em `apps/worker`)
- **Result**: exit 0; 104 passed, 0 failed, 0 skipped (HEAD `dee0099`; fmt e clippy limpos)
- **Test count before feature** (`1653949`): 77
- **Test count after feature**: 104
- **Delta**: +27 (headers 4, redirects 9, plano 3, geracao +4, ciclo +1, pagina +1, oracle +1, dry_run +4); nenhum `assert`/`#[test]` removido no diff de `tests/`
- **Skipped tests**: nenhum
- **Failures**: nenhuma

---

## Spec-precision gaps

- Nenhum AC com resultado indefinido. Observações (não bloqueiam):
  1. URL-01: o mapeamento da coluna 14 (`DS_URL_AFILIADO`, NULL → `""`) só é verificável por revisão; o teste afirma apenas que o SQL contém a coluna. Coberto quando o dono rodar contra o Oracle.
  2. AWS-01/02/05: cobertos só por revisão (decisão do spec: sem rede e sem mock novo). Risco para BSV-4: `HeadObject`/`GetObject` de chave ausente só devolvem 404/`NoSuchKey` se o usuário IAM tiver `s3:ListBucket`; sem ela o S3 responde 403 e a primeira publicação (sem `manifest.json`) falha com erro. `ListObjectsV2` já exige essa permissão, então a política de BSV-4 deve incluí-la.
  3. Assumptions do spec seguem marcadas `n` (não confirmadas pelo dono); os testes seguem essas decisões.

---

## Summary

**Overall**: ✅ Ready (pendente só a execução real do dono após BSV-4)

**Spec-anchored check**: 27/27 ACs com evidência e valor alinhado ao spec; 0 spec-precision gaps bloqueantes
**Sensor**: 18/18 mutações mortas
**Gate**: 104 passed, 0 failed

**What works**: leitura e rejeição de URL de afiliado; tabela de headers de MANIFEST §4; diff da KVS com limites nomeados e aviso; KVS entre chunks e manifest com falha preservando o manifest antigo; modo plano sem escrita; `--publicar`/`--sim` com erros de config sem panic.

**Next steps**: dono roda `--publicar` (plano) e `--publicar --sim` contra a AWS após BSV-4 e cola as saídas no PR.
