# BSV-34 · Site: página de busca `/busca/`

**Papel:** Frontend Svelte (+ template do worker) · **Pastas:** `apps/site/` e, só o formulário de busca no
topo da página da oferta, `apps/worker/templates/` + `apps/site/src/lib/estilo/besave.css` (contrato de
classes, mesma PR) · **Depende de:** BSV-37 e BSV-38 (no ar).
CONTRATO.md §3; AD-020, AD-061, AD-067, AD-088, AD-090, AD-093, AD-095

## Contexto
Hoje a busca filtra a grade da página em que a pessoa está (home ou área) e não tem endereço próprio: não dá
para compartilhar "ofertas de protetor solar", e a página da oferta (HTML do worker) não tem campo de busca.

## Objetivo
`https://besave.com.br/busca/?q=protetor` mostra os resultados com contagem, filtros e ordem, a partir de qualquer
página do site, inclusive da página da oferta.

## Saídas
1. **Rota `/busca/`** (prerenderizada; resultados no cliente sobre o catálogo, AD-061):
   - lê `?q=` e, opcional, `?area=slug`; mostra "N ofertas para "protetor"" (com "em Elas" quando há área, e um
     botão para tirar a área); grade com os mesmos cards, "Ver mais" de 40 em 40;
   - filtros e ordem da BSV-31/37 aplicados aos resultados, com o mesmo formato de URL (`?q=…&loja=…`);
   - expiradas entram **depois** das ativas, em cinza, com o selo "Encerrada" (CONTRATO §3);
   - catálogo ainda carregando → "Buscando em X de Y ofertas…" e resultado parcial (BSV-35);
   - `q` vazio ou com menos de 2 caracteres → sugestões: botões das áreas e a faixa "Maiores descontos de hoje";
   - nenhum resultado → "Nenhuma oferta para "xyz"", dicas curtas (verificar a grafia, usar menos palavras) e as
     áreas;
   - `<meta name="robots" content="noindex">`, fora do sitemap; `<title>` "Busca: protetor · Besave".
2. **Campo de busca do topo (site):** em qualquer página, digitar 2+ caracteres leva a `/busca/?q=` (navegação no
   cliente, mantendo o foco e o que foi digitado); na `/busca/`, digitar atualiza resultados e URL
   (`replaceState`, com espera curta entre teclas). Em página de área, a busca leva `&area={slug}`. Enter também
   envia. A home e as áreas deixam de filtrar a grade pela busca (um comportamento só).
3. **Página da oferta (template do worker):** formulário `GET /busca/` com campo `q` no topo, sem JavaScript;
   estilo no `besave.css` (classes novas documentadas). No celular, um ícone de lupa que abre o campo é aceitável
   se for só CSS.
4. Sem dependência nova; nenhum fetch além de manifest e chunks.

## Regras
1. Gate do bundle inicial da home ≤ 150 KiB (AD-090): a página de busca é rota própria; o que a home ganha (a
   navegação do campo) entra no limite. Registrar antes/depois.
2. **Ordem do teste real (como na BSV-38):** primeiro o deploy do site (rota `/busca/` e CSS novo), depois o
   `besave-ciclo` novo (o HTML das ~23 mil páginas muda uma vez; ~5 min).
3. Acessibilidade: o formulário tem `role="search"` e rótulo; o resultado anuncia a contagem (`aria-live`).

## Fora de escopo
Relevância por pontuação (a ordem é a dos filtros, padrão "Recentes"), correção ortográfica, sugestões enquanto
digita (autocomplete), busca no servidor, histórico de buscas.

## Critério de aceite
- Vitest: leitura e escrita de `q` e `area` na URL junto com os filtros; expiradas depois das ativas.
- Playwright (390 px e 1280 px): `/busca/?q=protetor` mostra a contagem e só cards com a palavra; `&loja=shopee`
  filtra; recarregar mantém; digitar na home leva a `/busca/?q=…` com o foco no campo; em `/elas/` a busca leva
  `&area=elas` e o botão tira a área; `q` de 1 caractere mostra sugestões; termo inexistente mostra o estado vazio;
  expiradas aparecem por último com "Encerrada"; `noindex` presente; voltar do navegador funciona.
- Worker (testes do template): formulário `GET /busca/` com `name="q"` no topo; HTML ≤ 30 KB; mesmo input → mesmos
  bytes. Navegador: na página da oferta, digitar e enviar abre `/busca/?q=…`.
- Gates: site `pnpm install --frozen-lockfile && pnpm lint && pnpm check && pnpm test && pnpm build && pnpm e2e`;
  worker `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`.
- **Real (dono):** (1) deploy do site: buscar na home e numa área no celular e no computador; compartilhar um link de
  busca; (2) `besave-ciclo` novo: buscar a partir de uma página de oferta; PageSpeed celular da home ≥ 90.

## Definition of done
PR com prints (busca com resultados, vazia, sem resultado; celular e computador), bundle antes/depois,
`validation.md` do Verifier independente, testes verdes.
