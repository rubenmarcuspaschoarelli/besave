# BSV-30 · Site: shell, design system (modelo A) e home básica

**Papel:** Frontend Svelte · **Pasta:** `apps/site/` (+ `apps/worker/` só para deixar de publicar o CSS,
regra 3) · **Depende de:** BSV-35, BSV-36 (`dp`), BSV-17 (deploy).
CONTRATO.md §2.3, §3; MANIFEST.md §1, §3.1, §4; AD-001, AD-020, AD-061..067, AD-075..077
Referência visual aprovada: `docs/design/vitrine.html`, **modelo A** (abrir no navegador; o card, o topo e o rodapé do mock são o alvo).

## Contexto
`besave.com.br` mostra uma home provisória. A camada de dados (BSV-35) já baixa, sincroniza e busca os
cards. Falta a tela. O dono escolheu o modelo A: fundo branco, verde da marca em títulos, rodapé e na
barra do Telegram, laranja queimado nos botões e no selo de desconto (60-30-10).

## Objetivo
Site no ar com cabeçalho fixo, áreas, faixa "Maiores descontos de hoje", grade "Mais recentes" com busca
simples, Lista de desejos local, 404 e o CSS que a página de oferta do worker também usa.

## Saídas
1. **Tokens** (variáveis CSS + tema do Tailwind; nomes em português): fundo `#ffffff`, superfície
   `#f4f6f5`, borda `#e1e6e3`, texto `#17201c`, suave `#56615b`, marca `#0b6e4f`, marca-escura `#084c37`,
   destaque `#c2410c` (texto branco), rodapé `#084c37`/`#e3efe9`, raio 10px. Corpo na fonte do sistema;
   **Lato 900/700 auto-hospedada** (woff2, só latin, `font-display: swap`) no logo e nos títulos. Logo =
   texto "Besave" em Lato 900, cor marca. Modo escuro fora (tokens prontos para depois).
2. **Componentes:** Topo (fixo ao rolar, com áreas), BarraCanal (verde, fechável, lembra no
   `localStorage`), Busca, Areas (botões; "Outros" só no menu "Mais"), FaixaDescontos, Card, CardMini,
   Grade, Rodape, BotaoFavorito.
3. **Home `/`:** barra do canal → topo → áreas → "Maiores descontos de hoje" (8, de
   `maioresDescontos`) → "Mais recentes" (`recentes`, 40 por vez, botão "Ver mais ofertas") → rodapé.
   Busca e áreas filtram a grade na própria home (sem navegação; páginas de área são da BSV-33).
4. **Card:** foto quadrada (`-small`, `loading="lazy"`, `width/height` fixos; sem imagem → placeholder da
   área), selo `-xx%` quando há `pd`, título em 2 linhas, preço "por" em destaque, "de" riscado, loja,
   "há X h" a partir de `dp` (Brasília, AD-032), ♡ à direita. **Sem cupom.** O card inteiro leva a
   `/oferta/{id}/`; nenhum link `/ir/` na home.
5. **Lista de desejos `/desejos/`:** ♡ grava o id no `localStorage` (`lib/favoritos.ts`); contador no
   ícone do topo; a página lista os favoritos a partir do catálogo; id que saiu do ar → "Esta oferta saiu
   do ar" com opção de remover.
6. **Configuração `lib/config.ts`:** link do canal; redes (X, Facebook, Instagram, YouTube, Discord) e
   apps (Android, iOS) com valor `null`; flags `postar`, `notificacoes`, `entrar`, `social` = `false`.
   Ícone/botão só aparece com link ou flag ligada; a área reservada no layout existe desde já (AD-077).
7. **404** (`/404.html`, prerender, `noindex`): "Oferta encerrada ou não encontrada", início e canal.
8. **`besave.css`** gerado no build a partir dos mesmos tokens, com as classes que o template do worker
   usa hoje (`topo`, `logo`, `menu`, `oferta`, `foto`, `preco`, `por`, `de`, `desconto`, `cupom`,
   `codigo`, `cta`, `faixa`, `barra`, `marcador`, `ficha`, `detalhes`, `encerrada`, `expirada`, …: lista
   completa extraída de `apps/worker/templates/oferta.html`). Publicado em `assets/besave.css` pelo
   deploy (BSV-17). O worker **deixa de publicar** o CSS (remover a fase e a entrada `_css` do índice).

## Regras
1. Fetch só via `lib/dados.ts`; componentes não fazem fetch (apps/site/CLAUDE.md).
2. Prerender de tudo; sem rota client-side (AD-020).
3. Nenhum link de afiliado; nenhuma chamada a servidor além de manifest e chunks.
4. Orçamentos: bundle inicial ≤ 150 KB; Lighthouse mobile ≥ 90 (Performance, Acessibilidade, SEO,
   Boas práticas); sem layout shift nas imagens; contraste AA em todo texto.
5. Dependências: Tailwind (já previsto no CLAUDE.md do site); qualquer outra, justificar.
6. Mudar classes usadas pelo template do worker é mudança de contrato: só restilizar, não renomear.

## Fora de escopo
Filtros, ordens, faixa de preço e virtualização (BSV-31); toast de novas (BSV-32); páginas de área
(BSV-33); página de busca (BSV-34); login, likes, comentários, notificações; modo escuro; analytics.

## Critério de aceite
- Vitest: favoritos (adicionar, remover, persistir, id inexistente); config esconde ícones sem link;
  "há X h" em Brasília; card sem `pd` sem selo e sem "de".
- Playwright (celular 390 px e desktop 1280 px): topo fixo ao rolar; barra fecha e não volta ao recarregar;
  área filtra a grade; busca "protetor" mostra só cards com a palavra; ♡ atualiza o contador e
  `/desejos/` lista a oferta; "Ver mais" acrescenta 40; card abre `/oferta/{id}/`; 2 colunas no celular,
  5 no desktop largo.
- `/404.html` gerada com `noindex`; build sem fallback.
- Worker: `cargo test` verde sem a fase de CSS.
- Gates: `pnpm lint/check/test/build`; `cargo fmt/clippy/test`.
- **Real (dono):** ligar `SITE_DEPLOY_ATIVO` e rodar o deploy; `https://besave.com.br/` mostra a home
  nova com ofertas reais; Lighthouse mobile ≥ 90 nas quatro categorias (print); página de oferta com o
  visual novo; `curl -I https://besave.com.br/assets/besave.css` → 200 `text/css`.

## Definition of done
PR com prints celular/desktop comparados ao modelo A, Lighthouse, tamanho do bundle, `validation.md` do
Verifier independente, testes verdes.
