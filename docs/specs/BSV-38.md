# BSV-38 · Página da oferta: copiar o cupom e ir para a loja

**Papel:** Backend Rust + Frontend · **Pastas:** `apps/worker/templates/` (+ testes do template),
`apps/site/src/lib/estilo/besave.css` e `infra/deploy-site/` (só o cache do CSS), na mesma PR: o template e o CSS
formam um contrato de classes (apps/site/CLAUDE.md). · **Depende de:** BSV-33 (mergeada).
Roda em paralelo com a BSV-37. CONTRATO.md §4, §7.1; AD-006, AD-014, AD-034, AD-041, AD-087

## Contexto
Na página da oferta (HTML do worker, sem JavaScript), o cupom aparece como texto e o botão "Acesse a oferta"
leva a `/ir/{id}`. Quem quer usar o cupom precisa selecioná-lo e copiar à mão antes de ir à loja.

## Objetivo
Com cupom, um toque copia o código e abre a loja numa aba nova; também é possível só copiar. Sem JavaScript,
a página continua funcionando como hoje.

## Saídas
1. **Template (`oferta.html`), só quando há cupom e a oferta está ativa:**
   - ao lado do código, um botão com ícone de copiar (`aria-label="Copiar cupom"`);
   - o botão principal passa a dizer **"Copiar cupom e ir para a loja"**, com `target="_blank"` e
     `rel="nofollow sponsored noopener"`;
   - um aviso discreto `role="status"` que mostra "Cupom copiado!" por ~2 s.
   Sem cupom: botão "Acesse a oferta" como hoje (pode ganhar `target="_blank"` também, por coerência).
   Oferta encerrada: nada muda (botão desativado, sem cópia).
2. **Script mínimo embutido** no template (sem arquivo externo, sem dependência):
   - clique no ícone: `navigator.clipboard.writeText(código)` e mostra o aviso; se a API faltar ou recusar,
     seleciona o texto do código para cópia manual.
   - clique no botão principal: tenta copiar e mostra o aviso **sem bloquear a navegação** (o link abre a aba
     nova normalmente; a cópia não pode atrasar nem impedir o `/ir/{id}`).
   - Sem JavaScript: o ícone fica oculto (`hidden` removido pelo script) e o botão é um link comum.
3. **CSS (`besave.css` do site):** estilo do ícone de copiar, do estado "copiado" e do aviso, com os tokens do
   modelo A; contraste AA; área de toque ≥ 44 px. Classes novas documentadas no README do template.
4. **Cache do `besave.css` (AD-087):** o deploy do site grava `assets/besave.css` com `public, max-age=300`
   (sem `stale-while-revalidate`); fontes e demais assets mantêm o cache atual. MANIFEST §4 atualizado.

## Regras
1. Nenhuma URL de afiliado no HTML (CTA continua `/ir/{id}`, regra 6).
2. O texto do cupom já é escapado pelo template (AD-034); o script lê o código do DOM, nunca de string montada.
3. Render determinístico (mesma oferta → mesmos bytes); orçamento de 30 KB por página mantido.
4. **Ordem do teste real:** primeiro o deploy do site (CSS novo, cache curto), depois o `besave-ciclo` novo
   (HTML novo), para o botão nunca aparecer sem estilo.
5. O primeiro ciclo com o binário novo reenvia todas as páginas de oferta (~26 mil, ~78 MB; 5–10 min na conexão
   local, AD-040). Esperado; registrar no PR `paginas_publicadas` e `tempo_ms` desse ciclo.

## Fora de escopo
Cupom nos cards da lista (decisão do dono: só na página da oferta), métricas de cópia, cupons da tabela CUPOM.

## Critério de aceite
- Worker (testes do template): com cupom → botão "Copiar cupom e ir para a loja" com `target="_blank"`,
  `rel` com `noopener`, ícone de copiar e região `role="status"`; sem cupom → "Acesse a oferta" sem ícone;
  encerrada → botão desativado, sem ícone; HTML ≤ 30 KB; mesmo input → mesmos bytes; nenhum `http` de afiliado.
- Navegador (Playwright em `apps/site` sobre um HTML de oferta gerado pelo worker como fixture, ou equivalente):
  clicar no ícone grava o código no clipboard e mostra "Cupom copiado!"; clicar no botão grava o código e abre
  uma aba nova em `/ir/{id}`; com o clipboard negado, a aba abre do mesmo jeito; com JavaScript desligado, o
  ícone não aparece e o botão é um link para `/ir/{id}`.
- Deploy: `publicar.mjs` grava `assets/besave.css` com `max-age=300` (teste do script comparando o comando inteiro,
  lição 14).
- Gates: worker `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`; site
  `pnpm … test && pnpm build && pnpm e2e`; `infra/functions` `npm test`.
- **Real (dono):** (1) merge e deploy do site; `curl -I https://besave.com.br/assets/besave.css` → `max-age=300`;
  (2) `besave-ciclo` novo do `main`; primeiro ciclo com `paginas_publicadas` ≈ total; (3) no celular (Android e
  iPhone), numa oferta com cupom: tocar no ícone copia; tocar no botão abre a loja em aba nova e o cupom cola no
  campo da loja.

## Definition of done
PR com prints da página (com cupom, sem cupom, encerrada; celular e computador), o relatório do primeiro ciclo
real, `validation.md` do Verifier independente, testes verdes.
