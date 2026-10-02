# BSV-35 · Site: camada de dados (manifest, chunks, sincronização, busca), sem UI

**Papel:** Frontend TS · **Pasta:** `apps/site/` · **Depende de:** contrato 1.3.3. Não depende do design (a BSV-30 pinta por cima).
CONTRATO.md §2, §3; MANIFEST.md §2, §3, §3.1, §4, §7; AD-004, AD-005, AD-013, AD-020, AD-061..064

## Contexto
`apps/site` ainda não existe. Produção (02/10/2026): 17.326 cards em 22 chunks, 690 KB em Brotli no
total (~40 B/card, maior chunk 36 KB), meta de 30 mil. A lista e a busca precisam de todos os cards no
cliente, então baixar todos os chunks já é o desenho (MANIFEST §3.1).

## Objetivo
Um módulo TypeScript puro (`src/lib/dados/`, exposto só por `src/lib/dados.ts`) que mantém no navegador
o catálogo de cards em sincronia com o `manifest.json`, baixando só o que mudou, e responde lista
filtrada, contagem de novas e busca. É testável em Node sem DOM nem rede. Inclui o esqueleto mínimo do
SvelteKit para o CI do site rodar.

## Decisão
Busca construída no cliente sobre os títulos dos chunks; `manifest.busca` continua `null`. Comparação de
custo e tempo com o índice gerado pelo worker: AD-061.

## Saídas
```ts
// tipos.ts — espelham packages/contract/schema (OfertaCard, ChunkRef, Manifest, Loja, Area, Publico)
export function diferenca(atual: Manifest | null, novo: Manifest): { baixar: ChunkRef[]; descartar: number[] }; // baixar em n decrescente
export class Catalogo { aplicarChunk(ref, cards); descartar(n); lista(f: Filtro): OfertaCard[];
  novas(): number; confirmarNovas(): void; readonly completo: boolean; readonly carregados: number; readonly total: number }
export function buscar(cat: Catalogo, consulta: string, f?: Filtro, limite = 200): { itens: OfertaCard[]; total: number; completo: boolean };
export function criarSincronizador(cat: Catalogo, deps: Deps): { iniciar(): Promise<void>; parar(): void; sincronizarAgora(): Promise<void> };
// Deps injetadas: fetch, relógio, agendar/cancelar, ocioso (requestIdleCallback com fallback), visivel(), aoMudarVisibilidade(cb)
// Eventos: pronto (3 primeiros chunks), completo, novas(n), erro(tipo), atualizarApp
export function gerarCards(qtd: number, semente: number): OfertaCard[]; export function gerarManifest(cards): { manifest; chunks }; // só testes
```
`Filtro`: `area?`, `publico?`, `loja?`, `mostrarExpiradas` (padrão false), `ordem`: `recentes` (padrão; `dt` desc, desempate `id` desc) | `desconto` (desc, `pd` nulo por último) | `preco` (asc).

## Regras
1. **Primeira carga:** `manifest.json` → os 3 chunks de maior `n` em paralelo → evento `pronto` → demais em `n` decrescente, um por vez, via `ocioso` → `completo`.
2. **Manifest sempre com `cache: 'no-cache'`** (AD-062): sem isso o cliente pode ficar 2 ciclos atrás e pedir chunk já apagado como órfão.
3. **Diff por `arquivo` de cada `n`:** baixa só `n` novos ou alterados; `n` ausente no novo manifest é descartado. Manifest igual → zero fetch de chunk.
4. `versao` ≤ à atual → ignora (borda servindo o anterior). `contrato` com major diferente do de `packages/contract` (lido no build) → não aplica nada e emite `atualizarApp`.
5. **Falha:** chunk com 404 ou erro → refaz o manifest uma vez e tenta de novo; se persistir, mantém os dados antigos daquele `n`, emite `erro` e tenta no próximo ciclo. Falha parcial nunca esvazia o catálogo.
6. **Polling** a cada 5 min só com a aba visível; aba oculta → nenhum fetch; ao voltar a ficar visível com o último sync há mais de 5 min → sincroniza na hora.
7. **Expiradas (`x:1`):** `lista` exclui por padrão; `buscar` inclui (a UI pinta de cinza). Ids que somem do manifest (expurgo) saem do catálogo na hora.
8. **Novas:** após `completo`, o conjunto de ids exibidos é a base. Nova = id fora da base e sem `x` (**não** `dt` maior — AD-063). Ids novos ficam pendentes, fora de `lista`, até `confirmarNovas()`. Mudanças em ids já exibidos (preço, cupom, `x`) aplicam na hora.
9. **Busca:** normaliza (minúsculas, NFD sem diacríticos, não alfanumérico → espaço). O texto pesquisável é título + cupom + rótulo da loja, pré-computado ao aplicar o chunk, nunca por consulta. Todos os termos precisam casar (E), cada um como **prefixo de palavra** (`sol` casa "Solar", `olar` não). Consulta normalizada com menos de 2 caracteres → vazio. Resultado na ordem do filtro. Título nunca é cortado no cliente (AD-064).
10. **Sem dependência de runtime** (nem biblioteca de busca). devDependencies justificadas no PR.
11. **Módulo puro:** sem Svelte, sem `window`/`document` globais; tudo que é do navegador entra por `Deps`. Componentes nunca fazem fetch.
12. **Esqueleto:** SvelteKit + `adapter-static` com fallback desligado (AD-020), `prerender = true`, TS strict, Vitest, ESLint + Prettier; `+page.svelte` placeholder. Sem Tailwind e sem design (BSV-30). `pnpm lint/check/test/build` verdes.
13. **Gerador sintético** com semente fixa (PRNG próprio, determinístico) e distribuição medida em produção: área ELAS 72%, MEU_LAR 18%, ESPORTE_VIDA 5%, TECH 3%, demais 2% (OUTROS incluso); público FEMININO 68%, UNISSEX 29%, MASCULINO 2%, INFANTIL 1%; loja MERCADO_LIVRE 55%, AMAZON 37%, SHOPEE 8%; cupom 32%; `pd` nulo 17%; expiradas 5%; títulos pt-BR com acento, média ~70 caracteres (p95 ~150, máx 200); ids crescentes com lacunas; `dt` em 45 dias. Saída validada pelo JSON Schema do contrato (ajv).

## Fora de escopo
UI, componentes, toast visual, virtualização (BSV-30..34); servir `.json.br` no `vite dev`; índice do worker; busca com erro de digitação (fuzzy); Web Worker; persistência offline (IndexedDB).

## Critério de aceite
- Tipos conferem com o contrato: `chunk-ok.json` e `manifest-ok.json` carregam; 30 mil cards do gerador passam no schema (ajv); mesma semente → mesmos bytes.
- Primeira carga (fetch falso com log): manifest, depois os 3 maiores `n` antes de `pronto`, depois o resto em `n` decrescente; `completo` só no fim.
- Diff: manifest igual → 0 chunks; 1 chunk alterado → 1 fetch; `n` removido → cards dele fora de `lista` e `buscar`.
- Manifest pedido com `no-cache`. `versao` menor → ignorado. `contrato` 2.0.0 → `atualizarApp` e nada aplicado.
- Chunk 404 → 1 novo manifest + 1 nova tentativa; persistindo → dados antigos mantidos e `erro`.
- Relógio falso: 15 min visível → 3 polls; 15 min oculta → 0; volta a ficar visível após 12 min oculta → 1 poll imediato.
- `lista` padrão sem `x:1`; `mostrarExpiradas` inclui; `buscar` inclui com o flag.
- Chunk novo com 4 ids novos (1 expirado, 1 com `dt` antigo) → `novas() == 3`; `lista` inalterada até `confirmarNovas()`; mudança de preço num id exibido aparece sem confirmar.
- Busca: "protetor solar" acha "Protetor Solar Facial FPS 50"; "PROTETOR", "protetor" e "protetór" dão o mesmo resultado; "cafe" acha "Café"; "olar" não acha "Solar"; "besave" acha o cupom `BESAVE10`; "mercado livre" acha a loja; "a" → vazio.
- Desempenho (Node, 30 mil cards do gerador, mediana de 5): aplicar todos os chunks ≤ 400 ms; `buscar` p95 de 50 consultas ≤ 20 ms; `lista` com área + ordem ≤ 40 ms.
- `pnpm lint && pnpm check && pnpm test && pnpm build` limpos; bundle do módulo ≤ 10 KB gzip.
- **Real (dono):** `pnpm medir` (script Node, `BESAVE_BASE_URL` = domínio do CloudFront) baixa o manifest e os chunks reais pelo próprio módulo e imprime: cards, bytes, tempo até `pronto` e até `completo`, tempo para aplicar e busca p95 sobre 20 consultas reais. Rodar duas vezes: a segunda com o mesmo manifest → 0 chunks baixados.

## Definition of done
PR com a justificativa de cada dependência, a saída do `pnpm medir` colada (domínio trocado por `REDACTED`), o veredito do Verifier e a proposta da AD-061 no corpo.
