# Besave — regras do repositório

Site e app de ofertas/cupons. Leitura 100% estática (S3 + CloudFront); dinâmico só onde
inevitável. Custo-alvo AWS: US$ 40/mês. Público inicial: beleza/feminino; 9 áreas de interesse.

## Documentos-fonte (leia o que o ticket apontar, não tudo)
- @docs/CONTRATO.md — schema canônico. JSON Schema em `packages/contract/schema/` vence em conflito.
- @docs/MANIFEST.md — layout do S3, manifest, chunks, headers, behaviors do CloudFront, orçamentos.
- docs/PLANEJAMENTO.md — visão geral e fases (só para contexto amplo; não carregar em tarefa de código).
- docs/DECISOES.md — decisões de arquitetura (AD-nnn). Só o dono/arquiteto escreve aqui.
- docs/specs/BSV-nn.md — spec da tarefa. É o seu escopo; o que não está nela está fora.

## Estrutura
- `packages/contract/` schemas + fixtures + `npm run validate` (gate de CI)
- `apps/worker/` Rust — Oracle → chunks, HTML, imagens, manifest, S3
- `apps/api/` Rust — Lambdas (redirect de clique, API de usuário; fases posteriores)
- `apps/site/` SvelteKit estático — home, áreas, busca
- `apps/mobile/` Capacitor sobre apps/site (não é uma segunda SPA)
- `tools/capture-*` Python — robôs existentes; não alterar sem ticket explícito
- `infra/` IaC

Uma tarefa = uma pasta principal. Não editar fora dela sem que a spec autorize.

## Comandos
- contrato: `cd packages/contract && npm ci && npm run validate`
- worker/api: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`
- site: `pnpm install --frozen-lockfile && pnpm lint && pnpm check && pnpm test && pnpm build`

## Regras não negociáveis
## Regras não negociáveis
1. Testes derivam do critério de aceite da spec; nunca espelham a implementação. O runner decide, não a autoavaliação.
2. Nunca enfraquecer, pular ou apagar teste para passar.
3. Um commit por tarefa, Conventional Commits (`feat(worker): …`, `fix(site): …`).
4. Sem `git push`, deploy, alteração de banco ou operação destrutiva sem ordem explícita.
5. Dinheiro é inteiro em centavos; datas ISO 8601 UTC no dado (exibição em Brasília, offset fixo -03:00); enums fechados (CONTRATO.md §1–2).
6. Nenhuma URL de afiliado em HTML ou chunk. CTA = `/ir/{id}`.
7. Nenhuma dependência nova sem justificar no PR (nome, por quê, alternativa descartada).
8. Não sabe uma API? Verifique (código existente → docs do repo → Context7 → web). Nunca invente. Se ficar em dúvida, diga.
9. Orçamentos do MANIFEST.md §7 são gates: chunk ≤ 60 KB, HTML de oferta ≤ 30 KB, `-small` ≤ 25 KB.
10. Mudança de contrato que adiciona ou renomeia valor de enum, campo ou chave de S3 entra na mesma PR que a adaptação do worker (e do site, quando existir). Nunca em PRs separadas.
11. Arquivos de evidência (relatórios, logs, screenshots, saídas de comando) são inspecionados antes do commit: tokens, IDs de instalação, caminhos com nome de usuário, credenciais e hostnames internos viram `REDACTED`, e o PR avisa o que foi trocado.

## Fluxo de trabalho (skill tlc-spec-driven)
Use a skill `tlc-spec-driven` para toda tarefa: specify → (design) → (tasks) → execute.
Ao final, o Verifier roda sozinho e escreve `.specs/features/<ticket>/validation.md`.
Em worktree de ticket, **não** grave em `.specs/STATE.md` nem em `LESSONS.md`; relate decisões
e lições no resumo final do PR — o dono as move para `docs/DECISOES.md` em `main`.
Detalhes: @docs/WORKFLOW-AGENTES.md

## Estilo
- Rust: `thiserror` em libs, `anyhow` em binários; sem `unwrap`/`expect` fora de testes; `tracing` para log.
- Svelte 5 com runes (`$state`, `$derived`, `$props`); sem stores legados; Tailwind, sem CSS ad hoc.
- Nomes de domínio em português (`oferta`, `cupom`, `loja`); código e comentários curtos.
- Resposta final de cada tarefa: o que foi feito, como testar, o que ficou de fora. Sem narrar o processo.
