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
- AD-013 · 2026-09-25 · Estado da oferta vem de `ST_ATIVO` (1/0) + `DT_DESATIVACAO`; expiradas ficam nos chunks (`x:1`) e nas páginas até expurgo em 7 dias · decisão do dono: usuário vê "expirada" em vez de sumiço; Promobit faz igual · sumir imediatamente (perde contexto e tráfego residual)
- AD-014 · 2026-09-25 · Página expirada é renderizada pelo worker (CSS grayscale + faixa + noindex), não por JavaScript · worker sabe o status na geração; Google vê o HTML final · JS no cliente (não indexável, estado duplicado)
- AD-015 · 2026-09-25 · Preço permanece inteiro em centavos; string rejeitada · string obriga parse em cada consumidor, impede ordenação/desconto e é maior · string formatada
- AD-016 · 2026-09-25 · Infra nova em IaC (Terraform) ao lado da atual: bucket privado `besave-site` + OAC + distribuição nova + KVS; virada por DNS no Route53 · não quebrar o protótipo no ar; bucket website público não suporta OAC/funções como precisamos · reconfigurar `E28G93A17WHHD` no lugar (sem rollback)
- AD-017 · 2026-09-25 · Segredos nunca no repositório; robôs leem credenciais de `.env`/variáveis; `conf/config.json` sai do git · repo é público · manter config com senha versionada
- AD-018 · 2026-09-25 · URL da oferta é `/oferta/{id}/`, sem slug; link curto `besave.io/{id}` via 301 em CloudFront Function · dono precisa de links numéricos para canais; título na URL é sinal de SEO menor que title/h1/schema.org; elimina `DS_SLUG` e o problema de retítulo · slug com id na frente (AD anterior, revogado)
- AD-019 · 2026-09-25 · Expurgo não apaga do Oracle: worker publica `ST_ATIVO = 1 OR DT_DESATIVACAO >= hoje-7` e remove do S3 o que saiu do resultado · histórico preservado no banco; worker continua sem estado além do último manifest · apagar do banco
- AD-020 · 2026-09-25 · Sem fallback SPA; 403/404 do S3 viram 404 com `/404.html` (TTL 60 s) · não há rotas client-side: tudo é prerender ou HTML do worker; fallback esconderia chunk ausente como 200 · custom error 200 global
- AD-021 · 2026-09-25 · Aliases da distribuição nova só na virada (`ativar_dominios`); certificado ACM nasce validado · CloudFront recusa CNAME em duas distribuições · reconfigurar a antiga
- AD-022 · 2026-09-25 · Certificado e registros de validação com `prevent_destroy`; validação com `allow_overwrite` · o CNAME de validação é compartilhado com o certificado do protótipo · destroy livre
- AD-023 · 2026-09-25 · `PriceClass_All` · única classe com PoPs na América do Sul; egress dentro do free tier no início · PriceClass_100 (mais barata, latência EUA)
- AD-024 · 2026-09-25 · Logs padrão legacy do CloudFront em S3 (`besave-logs`, ACL `awslogsdelivery`) · v2 cobra por GB entregue · standard logging v2
- AD-025 · 2026-09-25 · Oferta sem `id_produto` não entra no chunk · card levaria a página inexistente · publicar card sem página
- AD-026 · 2026-09-25 · `total_ofertas` conta publicadas (inclui `x:1`); `areas` conta só ativas; manifest anterior ilegível aborta sem gravar · contagens coerentes com o menu; segurança do cache de clientes · tratar ilegível como ausente
- AD-027 · 2026-09-26 · KVS de redirects espelha o conjunto publicado (não `ST_ATIVO`); atualizada por `UpdateKeys` em lotes de 50 · link compartilhado vale enquanto a página existe; 30k chaves em ~600 chamadas · PutKey unitário; remover na desativação
- AD-028 · 2026-09-26 · `manifest.json` e `manifest.prev.json` são regravados em toda execução (batimento para BSV-14); idempotência = nenhum outro objeto · alerta de "worker parado" depende disso · pular manifest sem mudança
- AD-029 · 2026-09-26 · Área `OUTROS` (10ª); slug de URL por área no contrato; `Bebes/Menina/Menino` → INFANTIL · robô grava "Outros" quando não classifica; vazio continua rejeitado; 253 ofertas recuperadas · área-lixo silenciosa no worker
- AD-030 · 2026-09-26 · CloudFront Functions: `await` nunca como argumento; `aws cloudfront test-function` obrigatório após mudança em Function · runtime 2.0 é subconjunto do JS e Node não o emula · confiar nos testes Node
