# BSV-12 — Worker: `PublicadorS3` + KeyValueStore de redirects

Fonte: `docs/specs/BSV-12.md`. Contrato: `docs/MANIFEST.md` §4, §5, §6; `docs/CONTRATO.md` §1.2, §7, §10.1.

## Problem Statement

BSV-11 gera chunks e manifest numa pasta local atrás do trait `Publicador`. Falta publicar no
bucket com os headers de MANIFEST §4 e manter a KVS `id → DS_URL_AFILIADO` que a Function
`/ir/{id}` consulta (BSV-23). Tudo precisa ser testável sem AWS e protegido contra rodar no
bucket errado.

## Goals

- [ ] `besave-worker --publicar` imprime o plano (gravações, remoções, putKey, deleteKey) sem escrever nada.
- [ ] `besave-worker --publicar --sim` publica no bucket e sincroniza a KVS na ordem de MANIFEST §6.
- [ ] `cargo test` passa sem credenciais e sem rede.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Criar bucket, KVS, usuário IAM | BSV-4 |
| Imagens | BSV-13 |
| Páginas HTML, sitemap, apagar `oferta/{id}/` no expurgo | BSV-21 |
| Invalidação de CloudFront | Manifest tem TTL 300 s; o resto é imutável |
| Agendamento | BSV-14 |
| Teste contra AWS real | Dono roda após BSV-4 |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| `url_afiliado` na `LinhaOferta` | `String`; `DS_URL_AFILIADO` NULL vira `""`. URL vazia (após trim) é rejeitada com `Rejeicao::UrlAfiliadoAusente` já em `para_card` (e, por consequência, em `para_pagina` e na geração). `sincronizar_redirects` recusa valor vazio (`ErroRedirects::ValorVazio`) como defesa extra | CONTRATO §10.1: oferta sem URL não é gerada. Revisão do dono: nenhum valor vazio pode chegar à KVS | y |
| Quem entra na KVS | A KVS espelha o conjunto publicado (`ST_ATIVO = 1 OR DT_DESATIVACAO >= hoje - 7`), não `ST_ATIVO`: expirada continua até o expurgo e some junto com a página | Decisão do dono na revisão (proposta AD); link `/ir/{id}` já compartilhado continua levando à loja | y |
| `meta_para` | `meta_para(chave) -> Option<Meta>`; `None` para chave fora da tabela de MANIFEST §4. `manifest.prev.json` recebe os headers do manifest. `Content-Type` "conforme" = por extensão | Uma chave desconhecida não deve ganhar header inventado | n |
| Idempotência na AWS ("zero escritas") | Segunda execução sem mudança: 0 chunks gravados, 0 removidos, 0 putKey, 0 deleteKey. `manifest.json` e `manifest.prev.json` são sempre regravados (`versao` nova) | Decisão do dono: é o batimento que BSV-14 monitora; `apps/worker/CLAUDE.md` ajustado | y |
| Posição do passo KVS em `gerar` | Chunks → KVS → `manifest.prev.json` → `manifest.json` → órfãos | MANIFEST §6 e regra 3 da spec do ticket; HTML/sitemap ainda não existem | n |
| Falha em `sincronizar_redirects` | `gerar` retorna `ErroGeracao::Redirects` sem gravar `manifest.json` nem `manifest.prev.json` | Regra 3: o manifest antigo continua válido | n |
| Limites da KVS | Chave ≤ 512 B; valor ≤ 1 024 B (`ErroRedirects::ValorGrandeDemais`); soma de bytes de chave + valor do estado final ≤ 5 242 880 (`ErroRedirects::KvsAcimaDoLimite`). Checados antes de qualquer escrita | Quotas da AWS (docs CloudFront, "Quotas on key value stores") | n |
| Aviso de volume | Mais de 40 000 entradas → `WARN` com o total; sincroniza mesmo assim | MANIFEST §5 | n |
| Chaves não numéricas na KVS | Ignoradas por `listar` (com `WARN`), nunca apagadas | A KVS pode ser compartilhada; o worker só mexe no que é dele | n |
| Escrita na KVS real | `UpdateKeys` com lotes de até 50 chaves montados por `lotes_kvs` (puts e deletes no mesmo lote), encadeando o `ETag` a partir de `DescribeKeyValueStore` | `PutKey`/`DeleteKey` um a um fariam 30 000 chamadas sequenciais no primeiro ciclo. Quota da AWS: 50 chaves ou 3 MB por chamada. Aceito pelo dono | y |
| Plano (sem `--sim`) | `gerar` roda com `PublicadorPlano`/`RedirectsPlano`: leituras vão ao destino real, escritas só são registradas e impressas | Mesmo caminho de código do `--sim`; o plano mostra exatamente o que seria feito | n |
| Runtime assíncrono | `ContextoAws` guarda um `tokio` `current_thread` compartilhado (`Arc`) por `PublicadorS3` e `RedirectsKvs`; cada método faz `block_on`. `gerar()` continua síncrono | Regra 8: async só na borda; um runtime por processo, sem threads extras | y |
| Config | `BESAVE_BUCKET`, `BESAVE_KVS_ARN` obrigatórias no `--publicar`; região pela cadeia do SDK (`AWS_REGION`/perfil), erro se ausente. Credenciais só pela cadeia padrão do SDK | Regra 6 | n |
| Dependências | `aws-config` (`behavior-version-latest`), `aws-sdk-s3` e `aws-sdk-cloudfrontkeyvaluestore` sem features padrão (`default-https-client`, `rt-tokio`; `sigv4a` na KVS, que exige SigV4A), `tokio` só com `rt` | Regra 8; sem features padrão evita o hyper 0.14 / rustls 0.21 legados | y |
| Teste do `PublicadorS3`/`RedirectsKvs` | Sem teste automatizado de chamada AWS; só as funções puras (`meta_para`, diff, limites) e o build. Validação real fica com o dono | Regra: `cargo test` sem rede e sem dependência de mock nova | n |

**Open questions:** none - all resolved or logged above (required before the spec is confirmed).

---

## User Stories

### P1: URL de afiliado na leitura ⭐ MVP

**User Story**: Como worker, quero ler `DS_URL_AFILIADO` para alimentar a KVS de redirects.

**Why P1**: Sem ela a KVS não tem valor.

**Acceptance Criteria**:

1. The `SQL_OFERTAS` SHALL selecionar `DS_URL_AFILIADO` e `LinhaOferta` SHALL expor `url_afiliado: String`.  <!-- URL-01 -->
2. IF `url_afiliado` é vazia após trim THEN `para_pagina` SHALL retornar `Rejeicao::UrlAfiliadoAusente`.  <!-- URL-02 -->
3. IF `url_afiliado` é vazia após trim THEN `gerar` SHALL não publicar o card e SHALL contar a rejeição `UrlAfiliadoAusente` no relatório.  <!-- URL-03 -->
4. IF `url_afiliado` é `""` ou só espaços THEN `para_card` SHALL retornar `Rejeicao::UrlAfiliadoAusente`.  <!-- URL-04 -->

**Independent Test**: `cargo test --test pagina --test geracao --test oracle`.

---

### P1: Headers por prefixo ⭐ MVP

**User Story**: Como CloudFront, quero cada objeto com os headers de MANIFEST §4 para cachear certo.

**Why P1**: Headers errados quebram o cache imutável e o Brotli pré-comprimido.

**Acceptance Criteria**:

1. WHEN `meta_para` recebe uma chave de cada linha de MANIFEST §4 (`manifest.json`, `data/chunks/*`, `data/busca/*`, `oferta/*/index.html`, `{area}/**/index.html`, `img/**`, `_app/**`, `index.html`, `sitemap*.xml`, `robots.txt`) THEN a função SHALL devolver exatamente o `Content-Type`, `Content-Encoding` e `Cache-Control` da tabela.  <!-- HDR-01 -->
2. WHEN `meta_para` recebe `manifest.prev.json` THEN a função SHALL devolver os headers do `manifest.json`.  <!-- HDR-02 -->
3. IF a chave não casa com nenhuma linha da tabela THEN `meta_para` SHALL devolver `None`.  <!-- HDR-03 -->
4. The `gerar` SHALL gravar chunks e manifest com a mesma `Meta` que `meta_para` devolve para as suas chaves.  <!-- HDR-04 -->

**Independent Test**: `cargo test --test headers`.

---

### P1: Sincronização da KVS ⭐ MVP

**User Story**: Como Function `/ir/{id}`, quero a KVS com `id → URL` de toda oferta publicada, atualizada só no que mudou.

**Why P1**: É o redirect de afiliado.

**Acceptance Criteria**:

1. WHEN a KVS tem {1→a, 2→b} e os ativos são {1→a, 2→c, 3→d} THEN `sincronizar_redirects` SHALL aplicar put {2→c, 3→d} e del {} e a KVS SHALL ficar {1→a, 2→c, 3→d}.  <!-- KVS-01 -->
2. WHEN a KVS tem {1→a, 2→c, 3→d} e os ativos são {1→a} THEN `sincronizar_redirects` SHALL aplicar del {2, 3} e put {}.  <!-- KVS-02 -->
3. WHEN `sincronizar_redirects` roda duas vezes com os mesmos ativos THEN a segunda SHALL reportar 0 puts e 0 dels e SHALL não chamar `aplicar`.  <!-- KVS-03 -->
4. IF uma URL tem mais de 1 024 bytes THEN `sincronizar_redirects` SHALL retornar `ErroRedirects::ValorGrandeDemais` com o id, sem chamar `aplicar`.  <!-- KVS-04 -->
5. IF a soma de bytes de chave + valor dos ativos passa de 5 242 880 THEN `sincronizar_redirects` SHALL retornar `ErroRedirects::KvsAcimaDoLimite`, sem chamar `aplicar`.  <!-- KVS-05 -->
6. WHEN os ativos passam de 40 000 entradas THEN `sincronizar_redirects` SHALL emitir um `WARN` com o total e sincronizar mesmo assim.  <!-- KVS-06 -->
7. The chave na KVS SHALL ser o `id` em decimal e o valor a URL.  <!-- KVS-07 -->
8. IF um valor dos ativos é vazio após trim THEN `sincronizar_redirects` SHALL retornar `ErroRedirects::ValorVazio` com o id, sem chamar `aplicar`.  <!-- KVS-08 -->
9. WHEN um diff tem 120 chaves THEN `lotes_kvs` SHALL devolver 3 lotes (50, 50, 20) na ordem do diff, com puts e deletes compartilhando o lote da fronteira, e `RedirectsKvs::aplicar` SHALL fazer uma chamada `UpdateKeys` por lote.  <!-- KVS-09 -->

**Independent Test**: `cargo test --test redirects`.

---

### P1: Ordem de publicação com KVS ⭐ MVP

**User Story**: Como dono, quero que a KVS seja atualizada antes do manifest, e que falha nela mantenha o manifest antigo.

**Why P1**: Manifest novo apontando para ofertas sem redirect quebraria o CTA.

**Acceptance Criteria**:

1. WHEN `gerar` roda THEN a KVS SHALL receber `(id, url)` de todo card publicado (ativo ou expirado) e nenhum de card rejeitado.  <!-- ORD-01 -->
2. WHEN `gerar` roda THEN a sincronização da KVS SHALL acontecer depois da gravação dos chunks e antes da gravação de `manifest.prev.json` e `manifest.json`.  <!-- ORD-02 -->
3. IF a KVS falha THEN `gerar` SHALL retornar `ErroGeracao::Redirects` e `manifest.json` SHALL não ter sido gravado no `PublicadorMemoria`.  <!-- ORD-03 -->
4. WHEN `gerar` termina THEN o `Relatorio` SHALL trazer puts e dels da KVS.  <!-- ORD-04 -->
5. WHEN uma oferta sai da fonte (expurgo) THEN a execução seguinte SHALL apagar a chave dela da KVS.  <!-- ORD-05 -->

**Independent Test**: `cargo test --test geracao --test ciclo`.

---

### P1: Plano e execução ⭐ MVP

**User Story**: Como dono, quero ver o que `--publicar` faria antes de autorizar com `--sim`.

**Why P1**: Proteção contra rodar no bucket errado (regra 5).

**Acceptance Criteria**:

1. WHEN `publicar` roda em modo plano THEN nenhum `gravar`, `remover` ou `aplicar` SHALL chegar ao `Publicador`/`Redirects` de destino.  <!-- PLN-01 -->
2. WHEN `publicar` roda em modo plano THEN o plano SHALL listar cada chave que seria gravada (com bytes e `Cache-Control`), cada chave que seria removida e cada putKey/deleteKey.  <!-- PLN-02 -->
3. WHEN `publicar` roda em modo `--sim` THEN as escritas SHALL chegar ao destino e o plano SHALL vir vazio.  <!-- PLN-03 -->
4. WHEN `publicar` roda em modo plano contra `PublicadorMemoria` e `RedirectsMemoria` THEN o histórico de gravações e remoções do publicador e o de `aplicar` da KVS SHALL ficar inalterados, e `Plano::linhas()` (o texto que o binário imprime) SHALL listar `gravar`, `remover`, `putKey` e `deleteKey` previstos.  <!-- PLN-04 -->

**Independent Test**: `cargo test --test plano`.

---

### P1: Binário `--publicar` e AWS ⭐ MVP

**User Story**: Como dono, quero `besave-worker --publicar [--sim]` usando as credenciais padrão do SDK.

**Why P1**: É a entrega do ticket.

**Acceptance Criteria**:

1. The `PublicadorS3` SHALL implementar `Publicador` com `HeadObject` (404 → `false`) em `existe`, `GetObject` em `ler` (ausente → `None`), `PutObject` com `ContentType`/`ContentEncoding`/`CacheControl` da `Meta` em `gravar`, `DeleteObject` em `remover` e `ListObjectsV2` paginado em `listar`.  <!-- AWS-01 -->
2. The `RedirectsKvs` SHALL implementar `Redirects` com `ListKeys` paginado e `UpdateKeys` nos lotes de `lotes_kvs` com `IfMatch` do `ETag` corrente.  <!-- AWS-02 -->
3. IF `BESAVE_BUCKET` ou `BESAVE_KVS_ARN` está ausente THEN `--publicar` SHALL sair com erro nomeando a variável, sem panic e sem acessar a rede.  <!-- AWS-03 -->
4. IF `--sim` é passado sem `--publicar` THEN o binário SHALL sair com erro, sem panic.  <!-- AWS-04 -->
5. The código SHALL não ter campo de credencial em config, CLI ou log.  <!-- AWS-05 -->

**Independent Test**: `cargo test --test dry_run`; revisão de `src/aws.rs`.

---

## Edge Cases

- WHEN a fonte não tem nenhum card válido THEN a KVS SHALL ficar vazia (dels de todas as chaves numéricas).
- WHEN a KVS tem uma chave não numérica THEN `listar` SHALL ignorá-la e `sincronizar_redirects` SHALL não apagá-la.
- WHEN a URL tem espaços nas pontas THEN o valor na KVS SHALL ser a URL trimada.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| URL-01 | P1: URL de afiliado | T1 | Implemented |
| URL-02 | P1: URL de afiliado | T1 | Implemented |
| URL-03 | P1: URL de afiliado | T1 | Implemented |
| URL-04 | P1: URL de afiliado | T8 | Implemented |
| HDR-01 | P1: Headers | T2 | Implemented |
| HDR-02 | P1: Headers | T2 | Implemented |
| HDR-03 | P1: Headers | T2 | Implemented |
| HDR-04 | P1: Headers | T2 | Implemented |
| KVS-01 | P1: KVS | T3 | Implemented |
| KVS-02 | P1: KVS | T3 | Implemented |
| KVS-03 | P1: KVS | T3 | Implemented |
| KVS-04 | P1: KVS | T3 | Implemented |
| KVS-05 | P1: KVS | T3 | Implemented |
| KVS-06 | P1: KVS | T3 | Implemented |
| KVS-07 | P1: KVS | T3 | Implemented |
| KVS-08 | P1: KVS | T8 | Implemented |
| KVS-09 | P1: KVS | T9 | Pending |
| ORD-01 | P1: Ordem | T4 | Implemented |
| ORD-02 | P1: Ordem | T4 | Implemented |
| ORD-03 | P1: Ordem | T4 | Implemented |
| ORD-04 | P1: Ordem | T4 | Implemented |
| ORD-05 | P1: Ordem | T4 | Implemented |
| PLN-01 | P1: Plano | T5 | Implemented |
| PLN-02 | P1: Plano | T5 | Implemented |
| PLN-03 | P1: Plano | T5 | Implemented |
| PLN-04 | P1: Plano | T10 | Pending |
| AWS-01 | P1: Binário e AWS | T6 | Implemented |
| AWS-02 | P1: Binário e AWS | T6 | Implemented |
| AWS-03 | P1: Binário e AWS | T7 | Implemented |
| AWS-04 | P1: Binário e AWS | T7 | Implemented |
| AWS-05 | P1: Binário e AWS | T6 | Implemented |

**Coverage:** 31 total, 31 mapped to tasks, 0 unmapped

---

## Success Criteria

- [ ] `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` verde em `apps/worker`, sem credenciais nem rede.
- [ ] Contra a AWS (dono, após BSV-4): `--publicar --sim` publica; `curl -I` do manifest mostra `max-age=300`; chunk mostra `Content-Encoding: br` e `immutable`; `/ir/<id>` dá 302; segunda execução reporta 0 chunks e 0 put/del na KVS.
