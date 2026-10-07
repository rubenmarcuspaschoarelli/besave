# BSV-41 Avisos programados no canal e páginas `/avisos/{id}/` Specification

Fonte: `docs/specs/BSV-41.md`. DDL: `apps/worker/sql/bsv-41.sql` (usado como está).

## Problem Statement

O dono quer postar no canal mensagens próprias (aviso de afiliado, campanhas, "ofertas do dia") com
foto, título e link para uma página do site, repetidas numa frequência por canal. O conteúdo é
cadastrado no Oracle (`AVISO`, `AVISO_CANAL`); hoje nada publica nem envia essas linhas.

## Goals

- [ ] `besave-ciclo` publica `avisos/{id}/index.html` (+ imagem) para cada aviso ativo e vigente, só
      sobe o que mudou e remove o que saiu.
- [ ] `besave-envio` posta no máximo 1 aviso por canal e execução, o mais atrasado, na frequência
      própria, dentro da janela do canal, sem consumir a cota de ofertas.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Template definitivo da página, indexação dos avisos | spec: refinado depois; página `noindex` |
| Editar/remover posts antigos de aviso | spec: fora de escopo |
| Link curto `besave.io` para avisos | spec: fora de escopo |
| Agendamento por dia da semana | spec: fora de escopo |
| Formatos de imagem além de `.webp`/`.jpg` | spec: fora de escopo |
| Avisos no `--publicar` (plano sem `--sim`) e no `--dry-run` | a fase roda só no ciclo agendado (`--ciclo`/`besave-ciclo`); o plano continua cobrindo só ofertas |
| Mudança no CloudFront | `/img/*` (política `imutavel`, `min_ttl = 0`) e o behavior padrão (`/avisos/*`) respeitam o `Cache-Control` da origem; nada muda em `infra/` |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Onde a fase de avisos roda no ciclo | Depois do manifest e de `DT_PUBLICACAO_SITE` das ofertas (fora de `gerar`), no S3 e no `BESAVE_DESTINO_LOCAL` | Avisos não dependem do manifest; falha neles não pode atrasar ofertas | n |
| Falha na fase de avisos (Oracle, S3, template) | WARN + `avisos_falhas=1`, ciclo segue com código 0; índice não regravado | Mesmo padrão de `publicacao_site_falhas`: o site de ofertas já foi publicado | n |
| `DT_PUBLICACAO_SITE` do aviso com `BESAVE_DESTINO_LOCAL` | Não gravada nem anulada | Igual às ofertas (BSV-40): o site não foi publicado de verdade | n |
| Fonte do aviso no ciclo | Métodos novos em `FonteOfertas` (`avisos`, `marcar_aviso_site`), implementados no fake e no Oracle | O ciclo já recebe uma única fonte; evita segunda conexão | n |
| Imagem ausente na pasta, ilegível ou `BESAVE_AVISOS_DIR` indefinida (ciclo) | Página sem imagem + WARN | Ausência de imagem não bloqueia publicação (CONTRATO §6, mesmo espírito) | n |
| Extensão da imagem | `.webp` ou `.jpg`, sem diferenciar maiúsculas; nome com `/`, `\` ou `..` = inválido | Regra 2; impede ler fora de `BESAVE_AVISOS_DIR` | n |
| Imagem inválida (formato/nome) no ciclo | Aviso não publicado (fica fora do conjunto: se estava no ar, é removido e a data anulada) | Critério "imagem `.png` → aviso ignorado + WARN" | n |
| Limite de 1 MB | 1 048 576 bytes (inclusive) | "≤ 1 MB" | n |
| Chave da imagem | `img/avisos/{id}.webp` ou `img/avisos/{id}.jpg`, pela extensão do arquivo; troca de extensão remove a chave antiga | MANIFEST §1 pedido pela spec | n |
| Headers | `avisos/*/index.html` = `META_PAGINA`; `img/avisos/*.webp` = `image/webp`, `img/avisos/*.jpg` = `image/jpeg`, ambos `public, max-age=3600` | Spec saída 5 (o `max-age=3600` vale para as duas extensões: o motivo é o mesmo) | n |
| Índice `_estado/avisos.json` | `{"{id}": {"pagina": hash16, "imagem": chave \| null, "hash_imagem": hash16 \| null}}`; ausente/ilegível → reconstruído do bucket (`avisos/`, `img/avisos/`) com hashes vazios | AD-041; sem índice, órfãos ainda são removidos | n |
| Parágrafos | `DS_TEXTO` com quebras normalizadas; linhas em branco separam parágrafos; quebra simples vira `<br>` | DDL: "linhas em branco viram parágrafos" | n |
| Link do canal na página | `BESAVE_CANAL_URL`, padrão `https://t.me/besaveofertas` | Config por env (CLAUDE do worker); canal 1 é `@besaveofertas` | n |
| Link interno válido | `^/[a-z0-9/_-]*$` checado sem regex (só ASCII minúsculo, dígito, `/`, `_`, `-`; começa com `/`); `//…` também é recusado | Regra 3; `//host` é URL externa no navegador; sem dependência nova | n |
| Vigência | `DT_INICIO ≤ agora` e (`DT_FIM` nula ou `agora < DT_FIM`) | `[DT_INICIO, DT_FIM]` com fim exclusivo, igual à janela do canal | n |
| Último envio | `MAX(DT_ENVIO)` de `ENVIO_AVISO` do par (aviso, canal), com ou sem `NR_MESSAGE_ID` | Reserva conta como envio (sem duplicata); falha apaga a linha | n |
| Desempate de atraso | Menor `ID_AVISO` | Determinismo | n |
| Erro do aviso no envio (Oracle ou Telegram ≠ 429) | WARN, linha cancelada se reservada, `aviso_falhou=1` no relatório, lote de ofertas segue | Regra 5 | n |
| Foto do aviso no envio | Arquivo da pasta (`.webp`/`.jpg`) → JPEG 800×800 (`quadrado_jpeg`); `DS_IMAGEM` nula, arquivo ausente/ilegível ou pasta indefinida → `sendMessage` | Regras 1–2 | n |
| Corte da legenda | Título ≤ 120 nunca é cortado; o texto é cortado (fronteira de palavra + `…`) até caber em 1024 | Regra 1 | n |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Página do aviso no site ⭐ MVP

**User Story**: Como dono, quero que cada aviso ativo ganhe uma página `/avisos/{id}/` para o post do canal ter destino.

**Acceptance Criteria**:

1. PAG-01: WHEN o ciclo roda com 2 avisos ativos e vigentes, cada um com imagem válida, THEN o ciclo SHALL gravar `avisos/{id}/index.html` e `img/avisos/{id}.{ext}` de cada um e `_estado/avisos.json` com os 2 ids.
2. PAG-02: WHEN o ciclo roda de novo sem mudança no Oracle nem nas imagens THEN o ciclo SHALL gravar 0 objetos de aviso (nem página, nem imagem, nem índice).
3. PAG-03: The página SHALL ter título, imagem `/img/avisos/{id}.{ext}`, o texto em `<p>` por parágrafo, link para o canal, `/assets/besave.css` e `<meta name="robots" content="noindex">`.
4. PAG-04: IF `DS_TITULO` ou `DS_TEXTO` contém `<script>` THEN a página SHALL conter o texto escapado (`&lt;script&gt;`) e nenhum `<script>` vindo do banco.
5. PAG-05: WHEN `DS_LINK_INTERNO` casa `^/[a-z0-9/_-]*$` THEN a página SHALL ter um botão com `href` igual ao caminho.
6. PAG-06: IF `DS_LINK_INTERNO` não casa (ex.: `https://loja.com`) THEN a página SHALL sair sem botão e o ciclo SHALL logar WARN.
7. PAG-07: IF a imagem tem extensão fora de `.webp`/`.jpg` (ex.: `.png`) THEN o aviso SHALL ficar fora do conjunto publicado e o ciclo SHALL logar WARN.
8. PAG-08: IF a imagem tem mais de 1 MB, não existe ou não pode ser lida THEN a página SHALL sair sem imagem e o ciclo SHALL logar WARN.
9. PAG-09: The objetos SHALL usar os headers: página = `META_PAGINA`; `.jpg` = `image/jpeg`, `.webp` = `image/webp`, ambos `public, max-age=3600`.

**Independent Test**: fakes do ciclo (`FakeFonte` + `PublicadorMemoria` + pasta temporária).

### P1: Remoção e data de publicação ⭐ MVP

**User Story**: Como dono, quero que o aviso saia do ar quando eu desativo ou quando vence, e que o envio saiba o que está no ar.

**Acceptance Criteria**:

1. REM-01: WHEN um aviso publicado passa a `ST_ATIVO = 0` THEN o ciclo SHALL remover a página e a imagem dele e tirá-lo do índice.
2. REM-02: WHEN `DT_FIM` de um aviso publicado fica no passado THEN o ciclo SHALL remover a página e a imagem.
3. REM-03: WHEN um id do índice não existe mais em `AVISO` THEN o ciclo SHALL remover a página e a imagem.
4. REM-04: WHEN `DT_INICIO` está no futuro THEN o ciclo SHALL não publicar o aviso.
5. REM-05: IF `_estado/avisos.json` está ausente ou ilegível THEN o ciclo SHALL reconstruir o conjunto anterior pelo bucket e remover páginas e imagens de avisos fora do conjunto.
6. REM-06: WHEN a imagem muda de extensão ou deixa de existir THEN o ciclo SHALL remover a chave antiga da imagem.
7. DTP-01: WHEN a página de um aviso com `DT_PUBLICACAO_SITE` nula está no ar ao fim da fase THEN o ciclo SHALL gravar `DT_PUBLICACAO_SITE = SYSDATE` nele.
8. DTP-02: WHEN um aviso com `DT_PUBLICACAO_SITE` preenchida sai do conjunto publicado THEN o ciclo SHALL anular a data.
9. DTP-03: WHILE `BESAVE_DESTINO_LOCAL` está definida o ciclo SHALL não gravar nem anular `DT_PUBLICACAO_SITE` de aviso.
10. REL-01: The linha `relatorio` do ciclo SHALL ter `avisos_publicados`, `avisos_removidos`, `avisos_falhas` e `t_avisos`.
11. REL-02: IF a fase de avisos falha (Oracle, S3) THEN o ciclo SHALL logar WARN, contar `avisos_falhas=1` e terminar com código 0.

**Independent Test**: fakes do ciclo; `linha_relatorio`.

### P1: Aviso no canal ⭐ MVP

**User Story**: Como dono, quero que o aviso seja postado no canal a cada N minutos, dentro da janela, sem tirar espaço das ofertas.

**Acceptance Criteria**:

1. ENV-01: WHEN um aviso ligado ao canal com intervalo 120 nunca foi enviado e o envio roda às 08:00 THEN o envio SHALL postá-lo.
2. ENV-02: WHEN o último envio foi às 08:00 e o envio roda às 09:55 THEN o envio SHALL não postar o aviso.
3. ENV-03: WHEN o último envio foi às 08:00 e o envio roda às 10:00 THEN o envio SHALL postar o aviso.
4. ENV-04: WHILE a hora local está fora de `[NR_HORA_INICIO, NR_HORA_FIM)` o envio SHALL não postar aviso.
5. ENV-05: WHEN dois avisos estão vencidos THEN o envio SHALL postar só o de maior atraso (nunca enviado = maior atraso).
6. ENV-06: IF `AVISO.DT_PUBLICACAO_SITE` é nula THEN o envio SHALL não postar o aviso.
7. ENV-07: IF o aviso está inativo, fora da vigência ou a ligação `AVISO_CANAL` está inativa THEN o envio SHALL não postar o aviso.
8. ENV-08: WHEN um aviso é postado THEN o lote de ofertas da mesma execução SHALL ter o mesmo tamanho que teria sem o aviso.
9. ENV-09: The envio SHALL gravar a linha em `ENVIO_AVISO` antes de chamar o Telegram e confirmar `NR_MESSAGE_ID` depois.
10. ENV-10: IF o Telegram recusa o aviso (≠ 429) THEN o envio SHALL apagar a linha reservada e seguir com o lote de ofertas.
11. ENV-11: IF o Telegram responde 429 ao aviso THEN o envio SHALL encerrar a execução com `retry_after` e sem lote de ofertas.
12. ENV-12: IF o aviso não tem imagem THEN o envio SHALL usar `sendMessage` com a mesma legenda e prévia do link ligada.
13. ENV-13: WHEN o aviso tem imagem `.webp`/`.jpg` THEN o envio SHALL usar `sendPhoto` com JPEG 800×800.
14. ENV-14: IF a imagem do aviso tem outro formato THEN o envio SHALL ignorar o aviso com WARN.
15. ENV-15: The silencioso do aviso SHALL seguir o horário de som do canal.
16. ENV-16: WHEN `--sim` roda THEN a simulação SHALL mostrar o aviso que seria enviado, sem gravar nem enviar.
17. LEG-01: The legenda SHALL ser `<b>{titulo}</b>\n{texto}\n<a href="https://besave.com.br/avisos/{id}/?utm_source=telegram">Saiba mais</a>`, com título e texto escapados.
18. LEG-02: The legenda SHALL ter ≤ 1024 unidades UTF-16, cortando só o texto.

**Independent Test**: `FakeEnvio` + `FakeCanal` + `RelogioFake`.

### P2: Documentação

1. DOC-01: The MANIFEST.md SHALL listar `avisos/{id}/index.html`, `img/avisos/{id}.{webp,jpg}`, `_estado/avisos.json` (§1) e os headers deles (§4).
2. DOC-02: The README do worker SHALL explicar cadastrar um aviso (SQL), a pasta de imagens e como pausar.

---

## Edge Cases

- IF `DS_IMAGEM` contém `/`, `\` ou `..` THEN o aviso SHALL ser tratado como imagem inválida (PAG-07, ENV-14).
- WHEN a legenda escapada passa de 1024 THEN o texto SHALL ser cortado com `…` (LEG-02).
- IF `BESAVE_AVISOS_DIR` não está definida THEN ciclo e envio SHALL tratar toda imagem como ausente (PAG-08, ENV-12).

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| PAG-01 | P1: Página | T3 | Pending |
| PAG-02 | P1: Página | T3 | Pending |
| PAG-03 | P1: Página | T2 | Pending |
| PAG-04 | P1: Página | T2 | Pending |
| PAG-05 | P1: Página | T2 | Pending |
| PAG-06 | P1: Página | T2 | Pending |
| PAG-07 | P1: Página | T3 | Pending |
| PAG-08 | P1: Página | T3 | Pending |
| PAG-09 | P1: Página | T1 | Pending |
| REM-01 | P1: Remoção | T3 | Pending |
| REM-02 | P1: Remoção | T3 | Pending |
| REM-03 | P1: Remoção | T3 | Pending |
| REM-04 | P1: Remoção | T3 | Pending |
| REM-05 | P1: Remoção | T3 | Pending |
| REM-06 | P1: Remoção | T3 | Pending |
| DTP-01 | P1: Remoção | T3 | Pending |
| DTP-02 | P1: Remoção | T3 | Pending |
| DTP-03 | P1: Remoção | T4 | Pending |
| REL-01 | P1: Remoção | T4 | Pending |
| REL-02 | P1: Remoção | T4 | Pending |
| ENV-05 | P1: Canal | T5 | Pending |
| ENV-06 | P1: Canal | T5 | Pending |
| ENV-07 | P1: Canal | T5 | Pending |
| ENV-14 | P1: Canal | T5 | Pending |
| LEG-01 | P1: Canal | T5 | Pending |
| LEG-02 | P1: Canal | T5 | Pending |
| ENV-01 | P1: Canal | T6 | Pending |
| ENV-02 | P1: Canal | T6 | Pending |
| ENV-03 | P1: Canal | T6 | Pending |
| ENV-04 | P1: Canal | T6 | Pending |
| ENV-08 | P1: Canal | T6 | Pending |
| ENV-09 | P1: Canal | T6 | Pending |
| ENV-10 | P1: Canal | T6 | Pending |
| ENV-11 | P1: Canal | T6 | Pending |
| ENV-12 | P1: Canal | T6 | Pending |
| ENV-13 | P1: Canal | T6 | Pending |
| ENV-15 | P1: Canal | T6 | Pending |
| ENV-16 | P1: Canal | T6 | Pending |
| DOC-01 | P2: Docs | T7 | Pending |
| DOC-02 | P2: Docs | T7 | Pending |

**Coverage:** 40 total, 40 mapped to tasks, 0 unmapped.

---

## Success Criteria

- [ ] `cargo fmt --check`, `clippy -D warnings`, `cargo test` verdes, sem rede.
- [ ] Execução real do dono: página no ar com imagem; aviso a cada ~2 h entre 8 h e 22 h; desativar tira a página e para o envio.
