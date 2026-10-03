# apps/api — Rust: Lambdas (ARM64, cargo-lambda)

Fase posterior. Hoje só o redirect `/ir/{id}` existe, e ele é CloudFront Function + KeyValueStore (MANIFEST.md §5), não Lambda. Este app só entra em F5 (API de usuário: auth, favoritos, alertas) com DynamoDB.

## Regras
- Axum + `lambda_http`; uma Lambda por domínio, não por rota.
- Sem estado em memória entre invocações; sem Aurora; DynamoDB on-demand.
- Mesmos padrões de Rust do worker (`tracing`, `thiserror`/`anyhow`, sem `unwrap`).
