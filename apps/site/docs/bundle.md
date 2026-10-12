# Carregamento inicial da home (BUD-01)

O que o gate `e2e/saida.spec.ts` › BUD-01 mede: o JS que a home pede ao abrir (`modulepreload` e
imports estáticos, bytes brutos) mais o CSS embutido no `<style>` do HTML. Limite: 150 KiB = 153 600 B
(AD-090). Medido em 11/10/2026 (BSV-39).

| | JS | CSS embutido | total | folga |
|---|---:|---:|---:|---:|
| antes (`develop` em 7256b65) | 131 047 | 22 506 | **153 553** | 47 |
| depois (BSV-39) | 127 218 | 16 043 | **143 261** | **10 339** |

Reproduzir: `pnpm build && pnpm inventario` (tabela por arquivo e por bloco do CSS). Para dividir cada
arquivo por módulo-fonte: `BESAVE_MAPAS=1 pnpm build && pnpm inventario` (sourcemaps só nesse build;
rodar `pnpm build` de novo antes de publicar). Outra página: `pnpm inventario elas/index.html`.

A divisão por módulo vem dos sourcemaps e é aproximada: o trecho entre dois segmentos mapeados conta
para o primeiro, então código sem mapeamento (cola do bundler) cai no módulo anterior. Ex.: depois do
corte do rodapé, o `Busca.svelte` "ganha" ~1 KB que é cola do chunk, não código dele.

## Do que é feito (depois)

| pedaço | arquivo (hash muda a cada build) | bruto | gzip | conteúdo |
|---|---|---:|---:|---|
| runtime do SvelteKit | `chunks/DL7nVcyf.js` | 42 631 | 15 562 | `client.js` (roteador, navegação, hidratação) 31,5 KB + `devalue` 10,7 KB (serialização do estado do histórico) |
| runtime do Svelte | `chunks/DHuMW5uj.js` | 41 349 | 15 879 | reatividade, blocos `each`/`if`/`boundary`, eventos, hidratação; `clsx` |
| componentes da página | `chunks/CdyN-gTE.js` | 14 016 | 5 467 | BarraFiltros, filtros.ts, PaginaOfertas, Grade, BarraCanal, CardMini, FaixaDescontos |
| topo + catálogo | `chunks/CDIFY4Fa.js` | 9 150 | 4 204 | dados/catalogo.ts, Busca, Areas, Topo, destino-busca.ts, config.ts |
| card + vitrine | `chunks/DFqSe291.js` | 5 366 | 2 595 | vitrine.svelte.ts, BotaoFavorito, FotoOferta, Card, dados/navegador.ts |
| camada de dados | `chunks/DGu6V2o0.js` | 4 160 | 2 099 | dados/sincronizador.ts, formato.ts, dados/tipos.ts |
| estado do kit | `chunks/yUpNwsyQ.js` | 3 665 | 1 721 | `$app/state` e parser de rotas do kit |
| entrada do app | `entry/app.*.js` | 1 869 | 888 | tabela de rotas do kit, `params.ts` |
| auxiliar de preload | `chunks/CYtfOYgs.js` | 1 544 | 806 | `__vitePreload` do Vite (só para o CSS das rotas) |
| mensagens do kit | `chunks/q-i9K1th.js` | 1 020 | 378 | erros compartilhados do kit |
| favoritos | `chunks/DGjUKScg.js` | 851 | 478 | favoritos.svelte.ts |
| rotas | `nodes/0.*.js`, `nodes/2.*.js` | 976 | 663 | `+layout.svelte`, `+page.svelte` |
| entrada do kit | `entry/start.*.js`, `entry/payload.*.js`, 2 chunks mínimos | 621 | 539 | `init`/`start`, payload, `__export` do Rolldown |
| CSS embutido | `<style>` | 16 043 | 4 479 | ver abaixo |
| **total** | 17 JS + CSS | **143 261** | 55 758 | |

Fixo (fora do alcance sem trocar de framework): Svelte + SvelteKit somam ~89 KB brutos, 62 % do total.

## Do que era feito (antes, `develop` em 7256b65)

Saída do `pnpm inventario` sobre o build de antes (com sourcemaps temporários).

| arquivo | bruto (B) | gzip (B) | conteúdo |
|---|---:|---:|---|
| `chunks/CoB8Oudm.js` | 42.631 | 15.563 | SvelteKit 31.502, SvelteKit (devalue) 10.727 |
| `chunks/MkdQRX7D.js` | 41.414 | 15.910 | runtime Svelte 41.034, clsx 363 |
| `chunks/BWnVuBX-.js` | 14.673 | 5.681 | BarraFiltros.svelte 3.307, filtros.ts 2.944, PaginaOfertas.svelte 2.719, Grade.svelte 1.727, BarraCanal.svelte 1.086, CardMini.svelte 958 |
| `chunks/CI4vqqd7.js` | 10.949 | 4.881 | dados/catalogo.ts 3.517, Rodape.svelte 2.312, Areas.svelte 1.269, Busca.svelte 963, Topo.svelte 945, destino-busca.ts 826 |
| `chunks/CrpEPjpQ.js` | 5.381 | 2.599 | vitrine.svelte.ts 1.635, BotaoFavorito.svelte 1.061, FotoOferta.svelte 1.028, Card.svelte 914, dados/navegador.ts 418 |
| `chunks/DGu6V2o0.js` | 4.160 | 2.099 | dados/sincronizador.ts 2.006, formato.ts 1.144, dados/tipos.ts 1.005 |
| `chunks/Bg2-zVke.js` | 3.665 | 1.722 | SvelteKit 3.521 |
| `entry/app.y8XgOyPW.js` | 2.973 | 1.128 | SvelteKit 1.794, src/params.ts 129 |
| `chunks/BaNbYf_w.js` | 1.398 | 749 |  |
| `chunks/q-i9K1th.js` | 1.020 | 378 | SvelteKit 1.020 |
| `chunks/DMzAwf5H.js` | 851 | 478 | favoritos.svelte.ts 796 |
| `entry/start.CAWvj3yT.js` | 659 | 349 | SvelteKit 263 |
| `nodes/2.D_T_NKIy.js` | 491 | 343 | src/routes/+page.svelte 173 |
| `nodes/0.Nd3IRwyi.js` | 485 | 326 | src/routes/+layout.svelte 258, src/routes/+layout.ts 11 |
| `chunks/DK3Fl9T5.js` | 158 | 154 |  |
| `chunks/C25We98s.js` | 74 | 84 |  |
| `entry/payload.DSmR2FwN.js` | 65 | 77 | SvelteKit 65 |
| CSS embutido (`<style>`) | 22.506 | 5.553 | Tailwind (tema, preflight, utilitários), tokens, @font-face |
| **total** (17 JS + CSS) | **153.553** | 58.074 | folga 47 B do limite de 153.600 B |

## CSS embutido

| bloco | antes | depois | de onde vem |
|---|---:|---:|---|
| `@layer properties` | 1 198 | 313 | valores iniciais das `--tw-*` para navegadores sem `@property` |
| `@layer theme` | 850 | 695 | tokens do Tailwind usados (`--spacing`, `--text-*`, …) |
| `@layer base` | 3 902 | 1 930 | preflight + `app.css` (`html`, títulos, `:focus-visible`) |
| `@layer utilities` | 13 184 | 11 922 | ~240 classes do Tailwind usadas em `src/` |
| tokens, `@font-face` | 749 | 749 | `lib/estilo/tokens.css`, `fontes.css` |
| `@property` | 2 557 | 368 | uma por variável `--tw-*` usada |

As classes vêm de `src/**/*.svelte` e `src/**/*.ts` (sem `*.test.ts`); o mesmo CSS vai em toda página
(layout). Classes usadas só fora da home (desejos, 404, cabeçalho de área): ~0,4 KB — não compensa
dividir o CSS por rota.

## Cortes da BSV-39

| corte (na ordem em que foi medido) | ganho (B) | por que não muda nada |
|---|---:|---|
| Utilitários `sombra-lg`, `sombra-2xl`, `anel-foco`, `brilho-95`, `foto-grayscale`, `meio-y`, `numeros-tabulares` (`app.css`) no lugar de `shadow-*`, `ring-2`, `brightness-95`, `grayscale`, `-translate-y-1/2`, `tabular-nums` | 3 138 | Mesmo valor computado, sem as sombras transparentes de largura zero que o Tailwind compõe; cada um desses puxava um conjunto de 3 a 15 variáveis `--tw-*` (fallback + `@property`) |
| Tailwind escaneia só `src/` sem testes (`source('./')`, `@source not`) | 1 221 | O `e2e/busca.spec.ts` cita `grayscale` numa regex e gerava a classe e o conjunto de 13 variáveis de filtro |
| Preflight enxuto (`lib/estilo/preflight.css`) | 2 127 | Sem regras de `hr`, `abbr`, `code`, `sub/sup`, `table`, `progress`, `optgroup`, `::file-selector-button`, `textarea`, campos de data/hora, spin buttons, `:-moz-ui-invalid`: o site não tem esses elementos |
| `build.modulePreload: false` | 1 902 | Some a lista de dependências (`__vite__mapDeps`) dos imports dinâmicos; o kit pré-carrega a rota no hover e os pedaços sob demanda (filtros, aviso, setas) são pequenos; o CSS de rota continua pré-carregado |
| Rodapé renderizado no prerender (`hooks.server.ts` → `<!--rodape-->` do `app.html`) | 1 839 | Estático e igual em toda página; fica dentro do contêiner do kit, que continua tratando o clique em "Lista de desejos" sem recarregar |
| `discloseVersion: false` | 65 | Só tira `window.__svelte.v` |
| **total** | **10 292** | |

Medidos e descartados: terser no lugar do minificador do Rolldown (+1,5 KB, pior); campo de busca com
a navegação sob demanda (110 B: o `destino-busca` minificado tem 195 B e o Rolldown redividiu chunks).

## Próximos candidatos (se a folga voltar a apertar)

- Lógica de URL dos filtros (`escreverFiltros`, `destinoArea`) só no clique: ~0,5 KB.
- Getters do catálogo usados só pela `/busca/` (`ofertasTotal`, `ofertasCarregadas`): ~0,3 KB.
- Botões futuros do topo (`config.flags` desligadas): ~0,4 KB, mas exige tirar a configuração do
  runtime (AD-077).
