# BSV-39 · Site: dieta do carregamento inicial da home

**Papel:** Frontend Svelte · **Pasta:** `apps/site/` · **Depende de:** BSV-34 (no ar).
AD-075, AD-086, AD-090, AD-095; WORKFLOW lições 17, 19, 25, 26

## Contexto
O gate do CI (`e2e/saida.spec.ts`, BUD-01) mede o carregamento inicial da home: JavaScript em
`modulepreload` e imports estáticos (bruto) **mais** o CSS embutido no HTML. Está em **153.553 B**, a **47 B**
do limite de 153.600 B (150 KiB, AD-090). Os tickets recentes cabiam usando truques locais (painel do celular e
aviso de novas carregados depois da montagem, a `/busca/` reaproveitando a casca da home). A próxima melhoria na
home vai travar no CI. PageSpeed celular da home hoje: 98.

## Objetivo
Voltar a ter **pelo menos 10 KiB de folga** (carregamento inicial ≤ 143.360 B) **sem nenhuma mudança visível nem de
comportamento**, e deixar documentado do que o carregamento inicial é feito.

## Saídas
1. **Inventário** (`apps/site/docs/bundle.md` ou seção no README do site): para o estado atual e para o final,
   tabela por pedaço inicial (arquivo, bytes brutos e gzip, o que contém: runtime do Svelte/SvelteKit, camada de
   dados, componentes, rotas) e o CSS embutido (bytes, de onde vêm as classes). Ferramenta de medição: preferir o
   que o build já dá (manifest do Vite, sourcemaps temporários); uma devDependency de análise só com justificativa
   (regra 7) e sem ir para o build de produção.
2. **Cortes**, escolhidos pelo inventário, em ordem de ganho por risco. Candidatos a investigar (não obrigatórios):
   - código que a home importa mas só a `/busca/`, as áreas ou `/desejos/` usam (busca, normalização, textos de
     área, favoritos completos) → import dinâmico ou rota própria;
   - lógica de filtros e faixas de opções que só roda depois de um clique → carregada sob demanda;
   - sincronizador e polling, que podem iniciar depois da primeira pintura (sem atrasar os 3 primeiros chunks);
   - CSS embutido: classes do Tailwind sem uso na home, regras duplicadas entre componentes, tokens repetidos;
   - divisão de chunks do Vite/SvelteKit que puxa para a home código compartilhado só por outras rotas.
3. **Gate:** o limite do BUD-01 **continua 150 KiB**; acrescentar ao relatório do teste (anotação do Playwright)
   a folga em bytes. Registrar no PR antes/depois por pedaço.

## Regras
1. Nada visível muda; nenhum fluxo muda. Todos os e2e existentes passam **sem alteração de asserção**; teste novo só
   para garantir que algo passou a carregar sob demanda (e que carrega quando precisa).
2. A primeira pintura da home não pode piorar: os 3 primeiros chunks de dados continuam sendo pedidos na mesma
   ordem e sem atraso artificial; a faixa e a grade aparecem como hoje.
3. Sem dependência de runtime nova. Sem mudar `adapter-static`, o prerender nem o CSS embutido como estratégia
   (AD-086), a não ser que o inventário mostre que embutir custa mais do que rende — nesse caso, propor no PR e
   não mudar sem aprovação.
4. Se 10 KiB não forem alcançáveis sem mexer em comportamento, parar no máximo seguro e explicar no PR o que
   impede, com o inventário.
5. Testes de tempo por último e sem carga (lição 17); servidor de testes próprio (AD-097).

## Fora de escopo
Mudanças de design, novas funções, trocar Svelte/SvelteKit/Tailwind, mexer no CSS da página de oferta
(`besave.css`), imagens.

## Critério de aceite
- BUD-01: carregamento inicial da home ≤ 143.360 B (folga ≥ 10 KiB), com a folga anotada no relatório do teste.
- Inventário antes/depois no repositório e no PR.
- `pnpm install --frozen-lockfile && pnpm lint && pnpm check && pnpm test && pnpm build && pnpm e2e` verdes, com os
  e2e existentes intactos; testes novos para cada carregamento sob demanda introduzido (carrega no gatilho certo;
  não carrega antes).
- Ordem dos pedidos de rede na primeira carga da home igual à de hoje para `manifest.json` e os 3 primeiros chunks.
- Prints da home, de uma área, da `/busca/` e de `/desejos/` (390 e 1280 px) iguais aos de antes (comparação
  visual lado a lado no PR).
- **Real (dono):** depois do deploy, PageSpeed celular **e** computador da home ≥ 90 (esperado: ≥ 98 no celular) e
  navegação normal no celular: filtros, busca, favoritos, aviso de novas.

## Definition of done
PR com o inventário antes/depois, tabela de bytes, prints comparados, `validation.md` do Verifier independente,
testes verdes.
