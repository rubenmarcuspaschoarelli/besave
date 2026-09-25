# BSV-10 — Worker: leitura do Oracle atrás de trait, com fake em memória

Fonte: `docs/specs/BSV-10.md`. Contrato: `docs/CONTRATO.md` §2, §3, §4, §7, §9 e `packages/contract/schema/`.

## Problem Statement

O worker ainda não existe. Todo o resto dele (chunks, HTML, S3) precisa de ofertas já convertidas
para o contrato e precisa ser testável sem banco. Este ticket cria a fronteira: um trait de leitura
com implementação Oracle e fake, e a conversão linha → `OfertaCard`/`OfertaPagina` com rejeição motivada.

## Goals

- [ ] `cargo test` verde sem Oracle, cobrindo cada regra de conversão e rejeição do contrato.
- [ ] Serialização idêntica byte a byte às fixtures `*-ok.json` (compactadas), mesma ordem de chaves.
- [ ] `BESAVE_FONTE=fake cargo run -- --dry-run` imprime lidas / válidas / rejeitadas por motivo.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Chunks, manifest, HTML | BSV-11 |
| Upload S3 | BSV-12 |
| Imagens | BSV-13 |
| Agendamento | BSV-14 |
| Tabela CUPOM | F3/F4 (CONTRATO §8) |
| Uso de `DT_ULT_ATUALIZACAO` | coluna opcional; o worker não a lê nesta fase |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Fuso das colunas DATE do Oracle | Hora local fixa `-03:00`, convertida para UTC no SQL; configurável por `BESAVE_ORACLE_TZ` | Robôs gravam `datetime.now()` local (tools/capture-chat-groups). Offset fixo porque o arquivo de fuso do XE 11.2 é anterior ao fim do horário de verão (2019). | n |
| Datas na `LinhaOferta` | Segundos Unix UTC (`i64`); ISO 8601 formatado em Rust | Sem `chrono` (lista de deps fechada); a fake precisa comparar datas para o expurgo. | n |
| `centavos` e ponto flutuante | Arredonda sobre a representação decimal mais curta do `f64` (half up, meia para longe de zero) | `19.995 * 100` em f64 = 1999.4999…; a spec exige 2000. | n |
| Truncamento do título do card | > 200 caracteres Unicode → primeiros 197, corta no último espaço, `trim`, + `…` | CONTRATO §3; `maxLength` do schema conta caracteres. Sem espaço: corta seco em 197. | n |
| `titulo` da página > 400 | Mesma regra com limite 400 (397 + `…`) e log `warn` | Schema exige ≤ 400; rejeitar perderia a oferta. | n |
| Cupom fora do padrão `^[A-Z0-9_-]{1,30}$` após trim+maiúsculas | `c` ausente e `cupom: null`, log `warn`; não rejeita | §9 não lista cupom como motivo de rejeição. | n |
| `ID_PRODUTO` nulo | `para_pagina` rejeita com `Rejeicao::IdProdutoAusente`; o card não depende dele | Schema da página exige `id_produto ≥ 1`. Motivo extra fora do §9 (proposta de decisão). | n |
| `desconto_pct` | `round((1 - pp/pd) * 100)` half up em inteiros, limitado a 0..99 | Schema: 0..99; `pd=10000, pp=1` daria 100. | n |
| `nota` | 1 casa decimal; fora de 0..5 → `null` | Schema 0..5. | n |
| `qt_avaliacoes` negativo | `null` | Schema ≥ 0. | n |
| `produto.descricao` | Primeiro parágrafo não vazio de `DS_DESCRICAO_PRODUTO`, truncado em 600 com `…`; vazio → `produto: null` | "Primeiro bloco de Detalhes" (CONTRATO §4.2) sem formato definido; schema exige descrição ≥ 1. | n |
| Demais strings do produto | `trim`; vazio → `null`; acima do `maxLength` do schema, corta no limite | Schema limita marca 40, fabricante 80, modelo 200, país 40, gênero 20, faixa 20. | n |
| `preco_min`/`preco_max` ≤ 0 | `null` | Centavos ≥ 0; zero no Oracle significa ausente. | n |
| Colunas `NR_NOTA_AVALIACAO`, `QT_AVALIACAO` | Lidas de `OFERTA` | CONTRATO §4.1 as lista na oferta. | n |
| Tabelas sem schema qualificado | `OFERTA`, `PRODUTO` do usuário conectado | Não há schema documentado. | n |
| Mapeamento | Caminho por `--mapeamento` / `BESAVE_MAPEAMENTO`, padrão `../../packages/contract/mapeamento.json` | `cargo run` roda em `apps/worker`. | n |
| Sem `--dry-run` | Binário sai com erro explicando que só `--dry-run` existe | Geração é BSV-11. | n |

**Open questions:** none - all resolved or logged above (required before the spec is confirmed).

---

## User Stories

### P1: Conversão linha → contrato ⭐ MVP

**User Story**: Como worker, quero converter cada linha do Oracle em `OfertaCard` e `OfertaPagina` conforme o contrato, para publicar só dados válidos.

**Why P1**: Toda saída do worker depende disso.

**Acceptance Criteria**:

1. WHEN `DS_LOJA`, `DS_COMUNIDADE` ou `DS_PUBLICO` chegam como sinônimo (ex.: `MercadoLivre`, `Família & filhos`) THEN o worker SHALL mapear para o enum após normalizar (maiúsculas, sem acento NFKD, trim, espaços simples); `MERCADOLIVRE` → `MERCADO_LIVRE`.  <!-- CONV-01 -->
2. IF `l`, `a` ou `p` não mapeiam THEN o worker SHALL rejeitar com o motivo `LojaSemMapeamento`, `AreaSemMapeamento` ou `PublicoSemMapeamento`.  <!-- CONV-02 -->
3. IF `VL_PRECO_POR` é nulo ou ≤ 0 em centavos THEN o worker SHALL rejeitar com `PrecoPorInvalido`.  <!-- CONV-03 -->
4. IF `DS_TITULO` é vazio após trim THEN o worker SHALL rejeitar com `TituloVazio`.  <!-- CONV-04 -->
5. IF `DT_OFERTA` é nula THEN o worker SHALL rejeitar com `DataNula`.  <!-- CONV-05 -->
6. WHEN `pd ≤ pp` THEN o worker SHALL emitir `pd: null` sem rejeitar.  <!-- CONV-06 -->
7. WHEN o título tem mais de 200 caracteres THEN o card SHALL ter `t` com os primeiros 197 cortados na última fronteira de palavra + `…`, e a página SHALL manter o título integral.  <!-- CONV-07 -->
8. The `centavos` function SHALL arredondar half up (`19.995` → `2000`).  <!-- CONV-08 -->
9. WHEN `ST_ATIVO = 0` THEN o card SHALL ter `x: 1` e a página `status: "ENCERRADA"`; WHEN `ST_ATIVO = 1` THEN `x` SHALL estar ausente e `status: "ATIVA"`.  <!-- CONV-09 -->
10. WHEN uma linha equivalente a cada registro de `chunk-ok.json` / `oferta-pagina-ok.json` é convertida THEN a serialização compacta SHALL ser idêntica byte a byte à fixture compactada, na mesma ordem de chaves.  <!-- CONV-10 -->
11. The `OfertaCard` serializado de cada fixture SHALL ter ≤ 220 bytes, e a média das 3 SHALL ser ≤ 160.  <!-- CONV-11 -->
12. WHEN `chunk-ok.json`, `oferta-pagina-ok.json` e `manifest-ok.json` são desserializadas e reserializadas THEN o resultado SHALL ser idêntico byte a byte à fixture compactada.  <!-- CONV-12 -->

**Independent Test**: `cargo test` em `apps/worker` sem Oracle.

---

### P1: Fonte de ofertas atrás de trait ⭐ MVP

**User Story**: Como resto do worker, quero ler ofertas por um trait `FonteOfertas` para testar sem banco.

**Why P1**: Fronteira pedida pelo ticket; tudo depois dele usa a fake.

**Acceptance Criteria**:

1. WHEN `FakeFonte::ofertas()` é chamada THEN a fonte SHALL devolver só linhas com `ST_ATIVO = 1` ou `DT_DESATIVACAO ≥ agora − 7 dias`; inativa há 8 dias SHALL ficar de fora e inativa há 6 dias SHALL sair.  <!-- FONTE-01 -->
2. WHEN `FakeFonte::produto(id)` é chamada THEN a fonte SHALL devolver o produto com aquele id ou `None`.  <!-- FONTE-02 -->
3. The `OracleFonte` SHALL ler credenciais só de `BESAVE_ORACLE_DSN`, `BESAVE_ORACLE_USER`, `BESAVE_ORACLE_PASS` e aplicar o mesmo filtro de expurgo no SQL (`ST_ATIVO = 1 OR DT_DESATIVACAO >= SYSDATE - 7`).  <!-- FONTE-03 -->
4. IF uma variável de conexão falta THEN `OracleFonte` SHALL retornar erro nomeando a variável, sem panic.  <!-- FONTE-04 -->

**Independent Test**: testes da fake; `OracleFonte` só compila no CI e roda com o dono.

---

### P1: Dry-run ⭐ MVP

**User Story**: Como dono, quero `cargo run -- --dry-run` para ver quantas ofertas passariam antes de publicar.

**Why P1**: Critério de aceite do ticket e verificação contra o Oracle real.

**Acceptance Criteria**:

1. WHEN `--dry-run` roda com `BESAVE_FONTE=fake` THEN o binário SHALL imprimir `lidas`, `validas` e uma linha por motivo de rejeição com a contagem, e sair com código 0.  <!-- DRY-01 -->
2. IF uma linha é rejeitada THEN o binário SHALL logar `id` e motivo via `tracing` e seguir para a próxima, sem panic.  <!-- DRY-02 -->

**Independent Test**: `BESAVE_FONTE=fake cargo run -- --dry-run`.

---

## Edge Cases

- IF o título tem > 200 caracteres sem nenhum espaço THEN o card SHALL cortar seco em 197 + `…`.
- IF `pd` é nulo THEN o card SHALL emitir `pd: null` e a página `desconto_pct: null`.
- IF o cupom é só espaços THEN `c` SHALL estar ausente e `cupom: null`.
- WHEN `ST_ATIVO = 0` e `DT_DESATIVACAO` é nula THEN a fake SHALL excluir a linha (mesma semântica do SQL com `NULL`).

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| CONV-01 | P1: Conversão | T2 | Implemented |
| CONV-02 | P1: Conversão | T3 | Implemented |
| CONV-03 | P1: Conversão | T3 | Implemented |
| CONV-04 | P1: Conversão | T3 | Implemented |
| CONV-05 | P1: Conversão | T3 | Implemented |
| CONV-06 | P1: Conversão | T3 | Implemented |
| CONV-07 | P1: Conversão | T4 | Implemented |
| CONV-08 | P1: Conversão | T3 | Implemented |
| CONV-09 | P1: Conversão | T4 | Implemented |
| CONV-10 | P1: Conversão | T4 | Implemented |
| CONV-11 | P1: Conversão | T3 | Implemented |
| CONV-12 | P1: Conversão | T1 | Implemented |
| FONTE-01 | P1: Fonte | T5 | Implemented |
| FONTE-02 | P1: Fonte | T5 | Implemented |
| FONTE-03 | P1: Fonte | T6 | Implemented |
| FONTE-04 | P1: Fonte | T6 | Implemented |
| DRY-01 | P1: Dry-run | T7 | Implemented |
| DRY-02 | P1: Dry-run | T7 | Implemented |

**Coverage:** 18 total, 18 mapped to tasks, 0 unmapped

---

## Success Criteria

- [ ] `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` verde em `apps/worker` sem Oracle.
- [ ] Contra o Oracle real (dono roda), `--dry-run` lê todas as ofertas e reporta rejeições sem panic.
