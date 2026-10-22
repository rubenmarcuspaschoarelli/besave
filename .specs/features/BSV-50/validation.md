# BSV-50 — validation.md

**Verificador:** sub-agente independente (autor ≠ verificador), lançado a pedido do dono. Não escreveu nem alterou código de produção ou testes; só este arquivo.
**Range do diff:** `299d35c..1c9ab9e` (1 commit, `feat(worker): cupom com vários códigos e faixa "Encerrada" (BSV-50)`; 36 arquivos, +923/-85). `origin/develop` andou durante a verificação; o range acima é o do commit.

## Validation

**Result**: PASS (com ressalvas de força de teste, nenhuma de comportamento do produto)

Implementação confere com `docs/specs/BSV-50.md` e `.specs/features/BSV-50/spec.md`. Dois mutantes de comportamento do canal e três de schema sobreviveram (achados 1 a 3 abaixo); nenhum indica defeito no código entregue.

## Critério de aceite x evidência

| AC / requisito | Teste (valor esperado vem da spec) | Código |
|---|---|---|
| SEP-01 dois/três códigos reais, espaços, minúsculas, 30 car. | `apps/worker/tests/cupons.rs:40` (3 do log), `:48` (2 do log), `:61` (trim/maiúsculas), `:69` (30 ok, 31 não) | `apps/worker/src/conversao.rs:266` |
| SEP-02 repetido, ordem mantida | `apps/worker/tests/cupons.rs:77`, `:98` (duplicado não conta no limite) | `apps/worker/src/conversao.rs:266` |
| SEP-03 mais de 5 + WARN com id | `apps/worker/tests/cupons.rs:83`, `:91` (exatamente 5 sem WARN) | `apps/worker/src/conversao.rs:80` |
| SEP-04 parte inválida + WARN id e parte | `apps/worker/tests/cupons.rs:104`, `:113` (parte vazia não é inválida) | `apps/worker/src/conversao.rs:266` |
| SEP-05 só inválidos / vazio / ausente | `apps/worker/tests/cupons.rs:121` | `apps/worker/src/conversao.rs:266` |
| CARD-01 `c` = primeiro válido, sem campo novo | `apps/worker/tests/card.rs:439` | `apps/worker/src/conversao.rs:168` |
| PAG-01 `cupons` completo, `cupom` = primeiro, `[]` sem cupom | `apps/worker/tests/pagina.rs:179`, `:209` | `apps/worker/src/conversao.rs:212` |
| TPL-01 lista, botão por código, abaixo do preço | `apps/worker/tests/template_oferta.rs:158` (golden 3 cupons), `:796` | `apps/worker/templates/oferta.html` (loop de `o.cupons`) |
| TPL-02 botão principal com o primeiro; sem JS link `/ir/{id}` "Ir para a loja" | `apps/worker/tests/template_oferta.rs:829`; e2e `apps/site/e2e/cupons-varios.spec.ts:52` e `:65` | `apps/worker/templates/oferta.html` (script, `botoes[0]`) |
| TPL-03 faixa "Encerrada", sem "Oferta expirada" | `apps/worker/tests/template_oferta.rs:883`; e2e `apps/site/e2e/cupons-varios.spec.ts:75` | `apps/worker/templates/oferta.html:43` |
| TPL-04 HTML ≤ 30 KB e mesmos bytes | `apps/worker/tests/template_oferta.rs:891` (3 cupons: 7.016 B no golden) | idem |
| CAN-01 legenda com todos (`Cupons: A · B · C`) | `apps/worker/tests/envio_legenda.rs:182` (html e encerrada), `apps/worker/tests/envio_modelo.rs:119` | `apps/worker/src/envio/legenda.rs:115` |
| CAN-02 corte do fim, fica 1, antes do título | `apps/worker/tests/envio_legenda.rs:208` | `apps/worker/src/envio/legenda.rs:150` |
| CON-01 contrato 1.6.0, schema, fixtures, mesma PR | `packages/contract/validate.mjs` (2 fixtures novas), `apps/worker/tests/envio_modelo.rs:38` (assert 1.6.0) | `packages/contract/schema/oferta-pagina.schema.json:18`, `docs/CONTRATO.md:7` |
| Regra 6 (sem URL de afiliado) | golden `oferta-pagina-cupons.html`: só `besave.com.br` e `schema.org`; CTA `/ir/5412` | — |
| Idempotência | `apps/worker/tests/template_oferta.rs:891` (render duas vezes, mesmos bytes); suíte `ciclo`/`geracao` verde | — |
| Fora de escopo (sem dependência nova, robô intocado) | diff sem `Cargo.toml`/`tools/` | — |

Itens "Real (dono)" da spec (deploy, VPS, celular, post do canal, contagem de `cupom fora do padrão`) não são verificáveis aqui e seguem como bloqueio de merge do dono.

## Gates

| Gate | Comando | Resultado |
|---|---|---|
| Contrato | `cd packages/contract && npm ci && npm run validate` | 6/6 casos PASS, "contrato OK" (fixtures `oferta-pagina-cupons` válida, `-invalido` rejeitada com 1 erro) |
| Worker fmt | `cargo fmt --check` | limpo |
| Worker clippy | `cargo clippy --all-targets -- -D warnings` | limpo |
| Worker test | `cargo test` (CARGO_TARGET_DIR compartilhado, JOBS=1) | 538 passed, 0 failed (61 binários; 2 ignorados pré-existentes) |
| Site lint/check/build | `pnpm lint`, `pnpm check`, `pnpm build` | verdes (check: 484 arquivos, 0 erros) |
| Site test | `pnpm test` | 166/166 em 4 execuções; **1 execução inicial teve 2 falhas** (arquivo não identificado, máquina com cargo rodando); não reproduziu em 4 reexecuções |
| E2E | `E2E_PORTA=4192 pnpm exec playwright test e2e/cupom.spec.ts e2e/cupons-varios.spec.ts` | 22 passed (celular e desktop) |

## Sensor de discriminação (cópia isolada em worktree temporário fora do repo, removido ao final)

Lotes rodando `cargo test --test cupons --test card --test pagina --test envio_legenda --test envio_modelo --test template_oferta --test envio_selecao`.

Worker/template: 29 mutantes aplicados (M01 a M30, sem M23), **26 mortos, 2 sobreviventes reais (M10, M26), 1 sobrevivente equivalente (M27)**.

Mortos: M01 limite 6, M02 limite 4, M03 sem dedup, M04 sem trim, M05 sem maiúsculas, M06 aceita 31, M07 card usa o último, M08 `cupom` da página = último, M09 corta título mantendo todos os cupons, M11 corta todos os cupons, M12 separador trocado, M13 rótulo Cupom/Cupons invertido, M14 botão principal copia o último, M15 aria-label sem o código, M16 faixa volta a "Oferta expirada", M17 `cupons` fora do JSON, M18 `selecao.rs` com `is_empty` invertido, M19 template lista só o primeiro, M20 sem WARN de parte inválida, M21 sem WARN de excesso, M22 hífen inválido, M24 canal só com o primeiro, M25 parte vazia vira inválida, M28 cópia ligada em oferta encerrada, M29 sem limpar `copiado` dos outros, M30 aceita 6º código.

Sobreviventes:
- M10 (legenda tenta só "todos os cupons" e já cai para 1 antes de cortar o título): **real**. Ver achado 1.
- M26 (`legenda_encerrada` ignora `n` e passa todos os cupons ao corpo): **real**. Ver achado 2.
- M27 (`escapar(c)` removido do código na legenda HTML): **equivalente** hoje, porque os códigos já casam `^[A-Z0-9_-]+$` e `escapar` é identidade neles; só defesa em profundidade.

Schema (`npm run validate`): sem `maxItems` e `maxItems` 6 mortos; **sem `uniqueItems`, sem `pattern` e `maxLength` 31 sobreviveram** (achado 3). CSS: o teste `besave-css.test.ts` exige a regra `.cupons`.

`git status` do worktree real antes e depois do sensor: idêntico (`?? docs/specs/BSV-50.md`). O worktree temporário foi criado e removido por mim; nada mais foi apagado.

## Achados (ranqueados)

1. **Lacuna de teste CAN-02 (média-baixa).** Nenhum teste cobre "cabem 2 a 4 códigos mas não 5". `apps/worker/tests/envio_legenda.rs:208` comenta que a folga é para 2 códigos, mas só afirma `1..5` presentes (`:240-243`), então a mutação que pula direto para 1 código sobrevive. A spec diz "cortar códigos do fim (mantendo 1) antes de cortar o título": o código atual (`legenda.rs:150`) faz o certo, o teste é que não o prende. Sugestão: afirmar o número exato esperado de códigos presentes para uma folga calculada.
2. **Lacuna de teste CAN-02 na legenda encerrada (baixa-média).** `legenda_encerrada` usa `ajustar` (`legenda.rs:181`), mas nenhum teste exercita o corte de cupons por 1.024 nesse caminho; M26 sobrevive.
3. **Fixture inválida do contrato só cobre `maxItems` (baixa).** `packages/contract/fixtures/oferta-pagina-cupons-invalido.json` (6 códigos distintos e válidos) não prova `uniqueItems`, `pattern` nem `maxLength` do schema (`oferta-pagina.schema.json:18`). O worker nunca emite esses casos, então é risco de contrato futuro, não defeito.
4. **Estilo (baixa).** `legenda.rs:169` e `:183` têm `.join("` seguido de quebra de linha literal e `format!` com quebra literal no meio (`⛔ <b>Oferta encerrada</b>` + newline + `<s>`): funciona e passa em `fmt`, mas troca `"\n"` por newline cru no fonte, o que dificulta a leitura e parece efeito colateral de edição. Sem impacto de comportamento.
5. **Nome de teste defasado (cosmético).** `apps/worker/tests/envio_modelo.rs:38` `contrato_na_versao_1_5_0` agora afirma 1.6.0.
6. **Observação pré-existente (informativa).** `to_uppercase()` sobre Unicode pode expandir (`ß` vira `SS`) e passar na validação ASCII; comportamento já existia antes da BSV-50 (era o mesmo `to_uppercase` + filtro). Fora do escopo.
7. **Intermitência não reproduzida.** 2 falhas em uma execução do `pnpm test` do site, com máquina sob carga; 4 reexecuções verdes. Regra 15/17 do WORKFLOW (teste de tempo sob carga) é a hipótese, sem prova.
8. **Escopo.** Fora das pastas da spec, o diff toca `apps/site/src/lib/dados/tipos.test.ts` (versão 1.6.0), `packages/contract/fixtures/manifest-ok.json` e `docs/MANIFEST.md` (versão do contrato) e `.specs/features/BSV-50/prints/`: consequências diretas do bump 1.6.0, aceitáveis; recomenda-se citá-las na PR. `docs/specs/BSV-50.md` segue untracked (não é do commit).

## Lacunas de precisão da spec

- Spec não diz o texto do botão por código nem o `aria-label`; o autor escolheu `Copiar cupom {código}` com 2+ códigos e `Copiar cupom` com 1. Coberto por teste, mas decisão do autor.
- A spec fixa `Cupons: A · B · C` mas não o rótulo no singular após corte para 1 (o código usa `Cupom:`). Coberto por teste (`envio_legenda.rs:208`, trecho final).
- "No máximo 5 (o resto sai com WARN)": a spec não diz se duplicados contam; o código não conta (testado em `cupons.rs:98`).

## Pós-verificação (autor)

Achados 1–5 tratados depois do relatório, no mesmo commit: CAN-02 agora asserta exatamente 2 códigos (legenda e
legenda encerrada, mata M10 e M26); 3 fixtures inválidas novas (`uniqueItems`, `pattern`, `maxLength`) em
`validate.mjs`; `"\n"` literal restaurado em `legenda.rs`; teste renomeado para `contrato_na_versao_1_6_0`.
Gates reexecutados pelo autor: `npm run validate`, `cargo fmt --check`, `clippy -D warnings`, `cargo test` verdes.
