# BSV-10 · Worker: leitura do Oracle atrás de trait, com fake em memória

**Papel:** Backend Rust · **Pasta:** `apps/worker/` · **Depende de:** BSV-1 (CONTRATO.md §2, §3, §4, §5, §7, §9)

## Contexto
Primeiro ticket do worker. O objetivo é a **fronteira**: tudo que o worker sabe do Oracle passa
por um trait, com uma implementação real e uma fake, para que todo o resto do worker seja
testável sem banco. Nada de S3 nem geração de arquivos aqui.

## Objetivo
Crate `apps/worker` (binário + lib) que consulta OFERTA/PRODUTO, converte cada linha em
`OfertaCard` e `OfertaPagina` conforme o contrato, rejeita inválidas com motivo, e expõe isso
por um trait. `cargo run -- --dry-run` imprime contagens (lidas / válidas / rejeitadas por motivo).

## Entradas
- Colunas de OFERTA e PRODUTO listadas em CONTRATO.md §3, §4, §7 (`ST_ATIVO`, `DT_DESATIVACAO`;
  `DS_SLUG`/`DT_ULT_ATUALIZACAO` **opcionais** — o código funciona se não existirem).
- `packages/contract/mapeamento.json` (carregado em tempo de execução, caminho configurável).
- Fixtures de `packages/contract/fixtures/` como casos de teste.

## Saídas (lib)
```rust
pub trait FonteOfertas {
    fn ofertas(&self) -> Result<Vec<LinhaOferta>>;   // linhas cruas (ativas + inativas)
    fn produto(&self, id_produto: i64) -> Result<Option<LinhaProduto>>;
}
pub struct OracleFonte { /* python-oracledb não; usar crate `oracle` (OCI) — Oracle XE 11.2 */ }
pub struct FakeFonte { /* Vec em memória, construível em teste */ }

pub fn para_card(l: &LinhaOferta, m: &Mapeamento) -> Result<OfertaCard, Rejeicao>;
pub fn para_pagina(l: &LinhaOferta, p: Option<&LinhaProduto>, m: &Mapeamento) -> Result<OfertaPagina, Rejeicao>;
pub fn slug(id: i64, titulo: &str) -> String;       // CONTRATO §5
pub fn centavos(n: f64) -> i64;                       // round half up
```
`OfertaCard`/`OfertaPagina`/`Manifest` com `serde`, nomes de campo idênticos ao JSON Schema
(`#[serde(rename = "pp")]` etc.). `Rejeicao` é enum com os motivos de CONTRATO §9.

## Regras
1. Conexão Oracle só em `OracleFonte`; config por env `BESAVE_ORACLE_DSN`, `BESAVE_ORACLE_USER`,
   `BESAVE_ORACLE_PASS`; nunca em arquivo versionado. Oracle XE **11.2**: usar crate `oracle`
   (OCI, precisa de Instant Client ≥ 19 no host); documentar no README da crate.
2. Normalização para o mapeamento: maiúsculas, sem acento (NFKD), trim, espaços simples.
3. `pd ≤ pp` → `pd = None` (não rejeita). `pp ≤ 0` → rejeita.
4. `t` truncado em 200 com `…` na fronteira de palavra; `titulo` da página integral (≤ 400).
5. `x: Some(1)` quando `ST_ATIVO = 0`; `status: ENCERRADA` na página.
6. Sem `unwrap`/`expect` fora de teste; `tracing` com nível por env; `thiserror` na lib.
7. Testes de conversão usam as fixtures do contrato como esperado (round-trip serde → JSON
   idêntico byte a byte às fixtures `*-ok.json`, chaves na mesma ordem).

## Fora de escopo
Geração de chunks/manifest/HTML (BSV-11), imagens (BSV-13), upload S3 (BSV-12), agendamento (BSV-14).

## Critério de aceite
- `cargo test` passa sem Oracle disponível (FakeFonte) e cobre: cada motivo de rejeição, `pd ≤ pp`,
  truncamento de título, slug (acentos, símbolos, 60 chars), centavos (19.995 → 2000), enum via
  sinônimo (`MERCADOLIVRE` → `MERCADO_LIVRE`), `ST_ATIVO = 0` → `x`/`ENCERRADA`.
- Serialização de `OfertaCard` de uma fixture ≤ 220 bytes; média das 3 ≤ 160.
- `cargo clippy --all-targets -- -D warnings` limpo.
- `cargo run -- --dry-run` com `BESAVE_FONTE=fake` imprime o relatório de contagens.
- Contra o Oracle real (dono roda): `--dry-run` lê todas as ofertas e reporta rejeições sem panic.

## Definition of done
PR com README da crate (como rodar com fake e com Oracle), testes verdes, sem dependência além de
`oracle`, `serde`, `serde_json`, `thiserror`, `anyhow`, `tracing`, `tracing-subscriber`, `unicode-normalization`,
`clap` sem justificar.
