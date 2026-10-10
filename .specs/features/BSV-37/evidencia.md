# BSV-37 — evidência

## Bundle inicial da home (teste `e2e/saida.spec.ts`, BUD-01)

| | JS | CSS embutido | total |
|---|---|---|---|
| antes (`develop` 2acdad0) | 130 992 B (18 arquivos) | 22 278 B | **153 270 B (149,7 KiB)** |
| depois | 130 739 B (18 arquivos) | 22 506 B | **153 245 B (149,7 KiB)** |

Gate: ≤ 153 600 B (150 KiB). Ficou 25 B abaixo do valor de antes.

O que saiu do carregamento inicial para caber a linha compacta e as setas:
- grupos de opções, faixa e painel (`filtros-sob-demanda.ts`): um import no primeiro clique
  (computador) ou ao montar no celular/tablet, onde os grupos ficam ocultos no DOM como na BSV-31;
- setas da faixa (`SetasFaixa.svelte`): só com `(hover: hover) and (pointer: fine)`;
- aviso "N novas ofertas" (`AvisoNovas.svelte`): importado ao montar a página (invisível até haver novas);
- rótulos de público e loja reaproveitam `ROTULO_PUBLICO`/`ROTULO_LOJA`, que já estavam no bundle;
- contorno de foco das pílulas vem do `:focus-visible` base (`app.css`), não de utilitários repetidos.

## Prints (`prints/`)

| arquivo | o que mostra |
|---|---|
| `1280-linha-fechada.png` | título + `Ordem: Recentes ▾`, `Público ▾`, `Loja ▾`, `Preço ▾`, interruptor numa linha; seta › na faixa |
| `1280-faixa-aberta.png` | `Público ▾` aberto: faixa com Todos…Infantil logo abaixo da linha |
| `1280-valor-escolhido.png` | `Público: Unissex`, `Preço: Até R$ 50`, cupom ligado, "Limpar filtros" na linha |
| `1280-faixa-descontos-setas.png` | faixa rolada até o fim: ‹ visível, › oculta, sem barra de rolagem |
| `390-home.png` | celular: "Filtros" + ordem, igual à BSV-31 |
| `390-painel.png` | celular: painel "Filtros" igual à BSV-31 |

Prints gerados com o catálogo de fixtura do e2e (sem imagens). Sem dado sensível.

## Execução dos gates (Windows, 09/10/2026)

- `pnpm lint`, `pnpm check`: verdes.
- `pnpm test`: 148/148. Numa primeira rodada, DES-01 e DES-02 (tempo) falharam com a máquina
  carregada por outros worktrees (lição 17); sem carga, passaram. `src/lib/dados/` não mudou.
- `pnpm build`, `pnpm e2e`: 228/228 (desktop e celular). A porta 4173 estava ocupada pelo preview
  de outro worktree (o `reuseExistingServer` do config usaria o servidor errado); o e2e rodou com um
  config temporário igual ao do site na porta 4187.
