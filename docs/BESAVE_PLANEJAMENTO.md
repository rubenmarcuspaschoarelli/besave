# Besave — Resumo do planejamento (19/09/2026)

Registro consolidado das decisões tomadas até aqui. Destinado a `docs/PLANEJAMENTO.md` no repositório e a servir de contexto para `CLAUDE.md` e para os agentes.

## 1. O projeto

Site e app de busca de ofertas e cupons. Público inicial: mulheres / beleza; estrutura já preparada para masculino, feminino, unissex, infantil e 9 áreas de interesse (Tech, Players, Meu Lar, Elas, Eles, Cultura, Família & filhos, Pets, Esporte & vida).

Fatos fixados:
- Robôs já capturam e classificam ofertas/cupons em Oracle local. Robô desativa ofertas expiradas (`DT_DESATIVACAO`). Já baixa imagem integral; vai gerar `<id>_small`.
- Catálogo próprio de produtos (dedupe entre lojas) em tabela Oracle.
- ~30.000 ofertas ativas, rotação diária, mínimo 30 dias por oferta. Registro ~1,2 KB; cupom ~210 bytes.
- Lojas/afiliados: Amazon, Mercado Livre, Shopee. Monetização só afiliado; rastreio de conversão depois (mas o log de clique é gratuito e entra desde o início).
- Meta: ≥ 50% de tráfego do Google. Referência de produto: promobit.com.br. Protótipo atual não se aproveita.
- Latência captura → site: pode ser > 1 min.
- Contas de usuário no escopo (login, favoritos, alertas, preferência de área). Admin sim; inclusão de ofertas por usuários depois.
- WhatsApp: só broadcast. Telegram primeiro.
- Teto AWS inicial: US$ 40/mês.
- Capacidade alvo: 10.000 usuários simultâneos.

## 2. Arquitetura decidida

Princípio: **leitura 100% estática (S3 + CloudFront), sem banco e sem Lambda no caminho de leitura.** Dinâmico só onde inevitável (redirect de clique, API de usuário).

### Dados
- Worker Rust local (cron 5–10 min) lê Oracle e publica no S3:
  - `manifest.json` (`max-age=300`): versão, lista de chunks/fatias, tombstones (ids desativados).
  - **Projeção compacta de card** para a home/busca: todos os ~30k registros, mas só os campos do card (id, slug, título, loja, preço de/por, cupom, área, público, data). Estimativa: ~150 B/registro → ~4,5 MB brutos, ~1–1,5 MB em Brotli, dividido em chunks carregados progressivamente. **Nunca o registro completo de 1,2 KB na lista.**
  - Registro completo só na página estática da oferta.
  - Índice de busca client-side derivado da projeção compacta (busca roda no front, sem servidor).
  - Tombstones cobrem desativação; cursor por `updated_at`/versão, não por `id > X` (que só cobre inserção).
- Formato inicial: JSON + Brotli. Protobuf só se medição justificar (ganho ~20–30% vs. atrito para agentes).
- Imagens: `<id>_small.webp` no S3, `Cache-Control` longo, carregadas sob demanda conforme scroll (lazy), nunca em lote.

### Páginas
- **Página de oferta**: HTML estático gerado pelo worker Rust (template minijinja/askama), `schema.org/Offer`, OG tags, sitemap index. Oferta desativada → 410 Gone.
- **Home / categorias / busca**: SvelteKit estático (adapter-static), lista virtualizada por fatia, polling do manifest com toast "N novas ofertas" (sem layout shift), páginas de categoria prerender para SEO.
- CSS compartilhado: o build do SvelteKit gera `besave.css` que o template Rust consome. Trade-off aceito: dois renderers, um CSS.
- Redirect afiliado `/ir/{id}`: CloudFront Function ou Lambda@Edge → 302 + log em S3.

### Usuários (fase posterior)
- Lambda Rust + DynamoDB on-demand. **Não** Aurora (custo mínimo estoura o teto), **não** Iceberg/Parquet (analítico).
- Auth: Cognito (verificar limites gratuitos atuais) ou Supabase Auth.
- Alertas: job no worker cruza deltas × alertas → fila → push.

### App
- Capacitor sobre o SvelteKit + push nativo (FCM/APNs). Compose Multiplatform só se surgir necessidade nativa real. Push também satisfaz a Apple (guideline 4.2).

### Canais
- Telegram: canal + Bot API (grátis). WhatsApp Canais: só após verificar se há API de publicação automatizada.

### Custo estimado
S3 ~US$1 · CloudFront dentro de 1 TB/mês ~US$0–5 · Lambda ~US$0–3 · DynamoDB ~US$1–3 · Route53 US$0,50 · Cognito ~US$0 → **~US$5–15/mês**. O que estoura orçamento: snapshot pesado por visita e imagem sem cache — ambos eliminados pelo desenho acima.

## 3. Críticas ao desenho original que geraram estas decisões
1. Enviar 30k registros completos (~10 MB) por visita: custo de egress e péssimo em 4G → resolvido com projeção compacta + chunks.
2. Delta por `id > X` não cobre expiração/alteração → tombstones + versão.
3. `?since=` por cliente destrói o cache de borda → manifest estático.
4. SPA com dados em binário = sem SEO → HTML estático por oferta e categorias prerender.
5. Redirect/log de clique ausente → `/ir/{id}`.
6. Automação de grupos de WhatsApp = risco de banimento → broadcast oficial / Telegram.
7. Hotlink de imagens → pipeline própria de imagens.
8. `DS_PUBLICO`/`DS_COMUNIDADE` texto livre → enums; faltam `slug`, `status`, `updated_at`, `dt_desativacao`, categoria interna.

## 4. Fases (fatias verticais) — executar F0 → F3 primeiro, testar, depois SEO fino e tráfego pago

**F0 — Contratos (sequencial, antes de qualquer paralelismo)**
- BSV-1 Schema canônico Oferta/Cupom (JSON Schema + enums; validador em CI)
- BSV-2 Layout do bucket, manifest, chunks, tombstones, headers por rota
- BSV-3 Monorepo (`worker/`, `site/`, `api/`, `bots/`) + CI (cargo test, pnpm test, lint)
- BSV-4 Infra base S3 + CloudFront (2 behaviors) + Route53 em IaC

**F1 — Worker Rust (Oracle → S3)**
- BSV-10 Leitura Oracle atrás de trait mockável (testes sem Oracle)
- BSV-11 Geração de projeção compacta em chunks + manifest + tombstones (idempotente)
- BSV-12 Upload S3 idempotente com headers corretos
- BSV-13 Conversão de imagem para WebP small
- BSV-14 Agendamento + alerta de falha no Telegram

**F2 — Páginas de oferta estáticas**
- BSV-20 Template HTML da oferta (Lighthouse SEO ≥ 95)
- BSV-21 Render de todas as páginas + sitemap index (30k em < 2 min)
- BSV-22 Desativação → 410 Gone
- BSV-23 Redirect afiliado `/ir/{id}` + log

**F3 — Home e busca (SvelteKit)**
- BSV-30 Shell estático + `besave.css` compartilhado
- BSV-31 Lista virtualizada com carga progressiva dos chunks (dados) e imagens lazy no scroll
- BSV-32 Polling do manifest + toast de novas ofertas + aplicação de tombstones
- BSV-33 Navegação por área/público + categorias prerender
- BSV-34 Índice compacto + busca client-side sobre até 30k registros

**Depois:** F4 Telegram (BSV-40) · F5 Usuários (BSV-50..53) · F6 App Capacitor + push (BSV-60) · F7 Admin (BSV-70) · WhatsApp Canais (pendente verificação).

Paralelismo: F0 com um agente. F1 e F2 em paralelo após BSV-2. F3 em paralelo com F2 a partir de BSV-30. F4 só depende de F1.

## 5. Fluxo de desenvolvimento com agentes

Stack: **Linear** (verdade do "o quê") → **Orca** (worktree por ticket, roda Claude Code) → **GitHub** (PR + CI obrigatório + aprovação do dono = verdade do "feito") → deploy só de `main` protegida com aprovação manual. **Hermes** em dois bots: *Contexto* (memória do projeto, método, acessível por Telegram) e *Revisor* (lê PR via MCP, checa contrato/teste/custo/SEO). Cursor sai do caminho crítico. Alternativa a avaliar como harness: Agent Orchestrator (Untrivial-ai, Apache-2.0) pelo loop automático CI/review → agente.

Papéis (base das skills): Arquiteto (dono de BSV-1/2, revisa contra contrato) · Backend Rust · Frontend Svelte · DevOps · Revisor.

Template de spec por ticket (uma página; se passar de duas, dividir):
```
# BSV-nn Título
Papel:
Contexto: links para CONTRATO.md, MANIFEST.md, wireframe
Objetivo (1 parágrafo):
Entradas:
Saídas:
Regras: (5–10 bullets)
Fora de escopo:
Critério de aceite (verificável):
Definition of done: PR com testes verdes, screenshot, sem dependência nova sem justificar
```

## 6. Pendências de refinamento antes de abrir tickets no Orca
1. BSV-1: schema com enums, regras de slug e versão (redigir e aprovar).
2. BSV-2: manifest, chunks, tombstones, headers.
3. Regras de negócio não escritas: ordenação padrão da home, definição de "oferta quente", tamanho do chunk, exibição de cupom no card, comportamento de expirada na lista.
4. Wireframes de baixa fidelidade: home, categoria, oferta (referência Promobit).
5. Skills por papel + `CLAUDE.md` do repositório.
6. Verificações externas: limites gratuitos do Cognito; API de Canais do WhatsApp.
