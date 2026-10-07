# BSV-36 · Contrato, worker e camada de dados: data de publicação no card (`dp`)

**Papel:** Backend Rust + TS · **Pasta:** `apps/worker/` + `packages/contract/` + `apps/site/src/lib/dados/`
(regra 10: contrato, worker e site na mesma PR) · **Depende de:** BSV-35, BSV-40 (mergeados).
CONTRATO.md §3, §10.6; MANIFEST.md §3.1, §7; AD-007, AD-063, AD-064, AD-066

## Contexto
A home ordena "Mais recentes" pela data em que a oferta entrou no site, não por `DT_OFERTA` (decisão do
dono, CONTRATO §10.6): uma oferta antiga que só ganhou URL de afiliado depois não pode aparecer no meio
da lista. A data já existe no Oracle (`OFERTA.DT_PUBLICACAO_SITE`, BSV-40), mas não está no card.

## Objetivo
Todo `OfertaCard` traz `dp` (data de publicação no site, ISO 8601 UTC); a camada de dados do site ordena
"recentes" por `dp` e oferece a faixa "Maiores descontos de hoje".

## Saídas
1. **Contrato 1.5.0:** `OfertaCard.dp` (string date-time, obrigatório) no JSON Schema, nas fixtures
   (`chunk-ok.json`, `manifest-ok.json`) e no CONTRATO §3; §10.6 respondida ("ordenação por `dp`").
   Orçamento do card: média ≤ 230 B (AD-074, revisa a AD-064); o gate continua o chunk ≤ 60 KB.
2. **Worker (`besave-ciclo`):** `dp` = `DT_PUBLICACAO_SITE` quando preenchida; quando nula (oferta indo
   ao ar neste ciclo), o **instante do ciclo** truncado ao minuto. O `UPDATE` pós-manifest da BSV-40 passa
   a gravar **esse mesmo instante** (não mais `SYSDATE`), para o card publicado e o banco terem o mesmo
   valor. Conversão local ↔ UTC pelo `BESAVE_ORACLE_TZ`, como `dt`.
3. **Site (`apps/site/src/lib/dados/`):** tipo com `dp`; ordem `recentes` = `dp` desc, desempate `id`
   desc; card sem `dp` (chunk antigo em cache durante a troca) usa `dt`; função
   `maioresDescontos(cat, agora, n)`: ativas com `dp` nas últimas 24 h, por desconto desc, desempate
   `dp` desc; gerador sintético com `dp ≥ dt`.

## Regras
1. `dp` nunca é anterior a 2026-10-06 (primeira gravação) nem posterior ao instante do ciclo; valor fora
   disso no Oracle → usa o instante do ciclo e WARN (não rejeita a oferta).
2. Idempotência (AD-028): segundo ciclo sem mudança → `dp` igual, chunks iguais, 0 uploads.
3. Primeiro ciclo depois do deploy: todos os chunks mudam uma vez (campo novo). Esperado; registrar no PR
   o tempo e os bytes dessa execução.
4. Sem dependência nova.

## Fora de escopo
UI (BSV-30/31), mudar o envio ao canal (continua usando `DT_OFERTA` nas 24 h), expor `dp` na página da oferta.

## Critério de aceite
- Schema: card sem `dp` → inválido; com `dp` → válido; `npm run validate` verde.
- Worker (fakes): oferta com `DT_PUBLICACAO_SITE` → `dp` igual (UTC); oferta sem → `dp` = instante do
  ciclo, e o `UPDATE` grava esse valor (fonte fake confere); segundo ciclo → mesmo `dp`, 0 uploads;
  `DT_PUBLICACAO_SITE` no futuro → instante do ciclo + WARN.
- Orçamento: fixture de 1.000 cards realistas → média ≤ 230 B; chunk comprimido ≤ 60 KB.
- Site: `recentes` com `dp` fora da ordem de `dt` segue `dp`; card sem `dp` usa `dt`;
  `maioresDescontos` ignora `dp` de 25 h e expiradas, e desempata por `dp`.
- Gates: `cargo fmt/clippy/test`, `npm run validate`, `pnpm lint/check/test/build`.
- **Real (dono):** instalar o `besave-ciclo` da branch; primeiro ciclo regrava os chunks (anotar tempo e
  `bytes_totais` antes/depois); `pnpm medir` em produção mostra `dp` nos cards e a ordem nova; segundo
  ciclo → 0 chunks escritos.

## Definition of done
PR com contrato 1.5.0, `bytes_totais` antes/depois, saída do `pnpm medir`, `validation.md` do Verifier
independente, testes verdes.
