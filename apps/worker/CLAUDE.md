# apps/worker — Rust: Oracle → chunks, HTML, imagens, manifest → S3

Roda local (cron 5–10 min). Lê OFERTA/PRODUTO/CUPOM, gera os artefatos de MANIFEST.md e publica no S3 na ordem da §6 (manifest por último).

## Regras
- Todo acesso ao Oracle passa por um trait (`FonteOfertas`) com implementação real (`oracle` crate) e fake em memória. Testes nunca tocam Oracle.
- Todo acesso ao S3 passa por trait (`Publicador`) com fake em memória. Testes nunca tocam AWS.
- Serialização de `OfertaCard`/`OfertaPagina`/`Manifest` com `serde`; structs derivam dos JSON Schema de `packages/contract` e as fixtures de lá são casos de teste (round-trip + validação).
- Idempotência é requisito: rodar duas vezes sem mudança no banco não sobe nenhum objeto (hash antes do upload).
- Registros inválidos (CONTRATO.md §9) são rejeitados e logados com motivo; nunca derrubam o ciclo.
- Falha em imagem não bloqueia a oferta (placeholder por área).
- `tracing` para log; `anyhow` no binário, `thiserror` na lib; sem `unwrap` fora de teste.
- Config por env (`BESAVE_ORACLE_URL`, `BESAVE_BUCKET`, …), nunca hardcode; `.env` no `.gitignore`.

## Comandos
cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test

## Orçamentos (gates de teste)
chunk comprimido ≤ 60 KB · HTML de oferta ≤ 30 KB · `_small` ≤ 25 KB · geração completa ≤ 2 min (medir com fixture de 30k).
