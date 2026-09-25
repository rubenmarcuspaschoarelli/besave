# DECISOES.md — registro de decisões de arquitetura

Formato: `AD-nnn · data · decisão · motivo · alternativas descartadas`. Só o dono/arquiteto escreve aqui, em `main`.
Agentes em worktree relatam propostas no PR; não editam este arquivo.

- AD-001 · 2026-09-19 · Leitura 100% estática (S3 + CloudFront), sem banco e sem Lambda no caminho de leitura · custo e resiliência a pico · Lambda + DynamoDB na leitura (custo e latência sem ganho)
- AD-002 · 2026-09-19 · Página de oferta = HTML estático gerado pelo worker Rust; SvelteKit só para home/áreas/busca · SEO é ≥ 50% do tráfego esperado · SPA pura (invisível ao Google); SSR (custo de servidor)
- AD-003 · 2026-09-19 · Lista/busca usam projeção compacta `OfertaCard` (~150 B) em chunks; registro completo só na página · 30k × 1,2 KB por visita estoura egress e 4G · snapshot único de 10 MB
- AD-004 · 2026-09-24 · Chunks endereçados por conteúdo (`{n}-{hash}`), imutáveis; único mutável é `manifest.json` (TTL 300 s) · hit rate de borda máximo e sem lista de tombstones · `?since=` por cliente (destrói cache); tombstones (estado extra no cliente)
- AD-005 · 2026-09-24 · Chunk por faixa de id (`n = floor(id/1000)`), não por recência · oferta nova só altera o último chunk · chunks por recência (todos mudam a cada inserção)
- AD-006 · 2026-09-24 · Nenhuma URL de afiliado em HTML/chunks; CTA `/ir/{id}` via CloudFront Function + KeyValueStore · log de clique dia 1, SEO limpo, troca de rede sem regerar páginas · URL direta no botão
- AD-007 · 2026-09-24 · Dinheiro em centavos (integer); datas ISO 8601 UTC; enums fechados com `mapeamento.json` · evita float e texto livre · NUMBER/VARCHAR do Oracle repassados
- AD-008 · 2026-09-24 · JSON + Brotli, não Protobuf, na v1 · ganho de 20–30 % não paga o atrito para agentes e debug · Protobuf (revisitar com medição)
- AD-009 · 2026-09-24 · Oferta encerrada: página regerada com `noindex` e CTA desabilitado por 30 dias, depois apagada · preserva tráfego residual; 410 real fica para função de borda futura · apagar imediatamente (404 em massa)
- AD-010 · 2026-09-24 · Oracle recebe `DT_DESATIVACAO`, `DT_ULT_ATUALIZACAO`, `DS_SLUG` · sem elas o worker não sabe o que mudou nem o que morreu · regerar tudo sempre (custo) ; slug recalculado (URL instável)
- AD-011 · 2026-09-23 · Monorepo único; um ticket = uma pasta principal; `CLAUDE.md` por app · contrato compartilhado e worktrees do Orca · repo por projeto (drift de contrato)
- AD-012 · 2026-09-24 · Skill `tlc-spec-driven` como workflow de execução; workers não gravam `STATE.md`/`LESSONS.md` em worktree · evita conflito entre PRs paralelos · cada worker gravando no log
