# Validation: BSV-17 - FAIL ❌

## Veredito do ciclo 4: reprovado por 1 mutante sobrevivente (HEAD `f4a4e83`, delta `ca64835..f4a4e83`)

Os gaps 1, 3, 4 e 5 do ciclo 3 estão fechados. C21, C22, C23 e C25 agora morrem, e também C23b e todos os
mutantes que o dono pediu. R1 e R3 estão cumpridos. R2 está implementado, e o teste de R2 com o S3 simulado
pega o `--size-only` de volta, incondicional (N1) ou só quando a chave já existe (N2). Gates verdes. Nenhum
teste foi enfraquecido.

O ciclo reprova pela regra da skill porque 1 de 37 mutantes do delta sobreviveu, o **N3**: um sync com
`--no-overwrite`. Esse flag existe no `aws s3 sync` v2 e só envia "files not present at the destination", ou
seja, traz de volta exatamente o defeito que R2 elimina: a carência voltaria a contar do 1º upload. O S3
simulado só sabe o que é `--size-only` (`deploy-site.test.mjs:374`), e o PUB-04 só afirma
`!s.includes('--size-only')` (`:135`). A correção é de uma linha: afirmar o comando `sync` inteiro com
`deepEqual`. Esse `deepEqual` também mata o N3b (abaixo, fora do delta).

Este é o ciclo 4, o último que o dono autorizou. A decisão sobe para ele: aplicar a correção de uma linha, ou
aceitar o risco e cobrir pela leitura do código e pela execução real.

- **Data**: 2026-10-07
- **Verifier**: sub-agente Verifier independente, Claude Opus 5.5 (autor ≠ verificador; não escreveu código nem testes)
- **Spec do dono**: `docs/specs/BSV-17.md` + requisitos R1–R3 do dono (limpeza de `_app/` com carência, sem `--size-only`, nota AD-079) · **EARS**: `.specs/features/BSV-17/spec.md` (PUB-04, PUB-08 e PUB-09 ajustados)
- **Faixa total do diff**: `31a86f4..f4a4e83`
- **Delta deste ciclo**: `ca64835..f4a4e83` (033c53d relatório do ciclo 3; 6c7d94e testes com aws falso, `--remotos` só no ensaio; 9a6f402 sem `--size-only`; f4a4e83 nota na spec do dono)

---

## Histórico de ciclos

| ciclo | HEAD | veredito | sensor | gaps |
|---|---|---|---|---|
| 1 | `6c2d4a3` | FAIL ❌ | 39/40 (W7 sobreviveu) | 5 (ver relatório do ciclo 2) |
| 2 | `2fd9fd7` | PASS ✅ | 47/47 | 2 não bloqueantes |
| 3 | `ca64835` | FAIL ❌ | 24/28 no delta | C21, C22, C23 e C25 sobreviveram; carência contava do 1º upload; PUB-08 e spec do dono desatualizados; `--remotos` aceito fora do ensaio |
| 4 | `f4a4e83` | FAIL ❌ | 36/37 no delta (+1 informativo fora do delta) | N3 (`--no-overwrite`) sobreviveu; os 5 gaps do ciclo 3 estão fechados |

---

## Gates (em `f4a4e83`, árvore real)

| gate | comando | resultado |
|---|---|---|
| fmt | `cd infra && terraform fmt -check -recursive` | limpo (exit 0) |
| validate | `terraform validate` | `Success! The configuration is valid.` |
| test | `terraform test` | **17 passed, 0 failed** |
| node | `cd infra/functions && npm test` (com o `aws` fora do PATH, `AWS_ENDPOINT_URL=http://127.0.0.1:9`, credencial falsa) | **67 passed, 0 failed, 0 skipped** (ciclo 3: 59 → +8) |
| workflow | `actionlint -shellcheck shellcheck.exe .github/workflows/site-deploy.yml` | exit 0, sem achados (workflow sem mudança no delta) |

### Integridade dos testes (asserts removidos × adicionados)

`git diff ca64835..HEAD -- infra/functions/test/` só remove 4 linhas:
- 3 linhas de `import` (`readdirSync`, `relative`, `listagem`, `principal` passaram a ser importados);
- o título do teste PUB-04 (`:126`), que ficou com "reenviado a cada deploy (sem --size-only)".

Nenhum `assert` foi removido ou afrouxado. Entraram 1 assert no PUB-04 (`:135`) e 8 testes novos (`:284-420`).

---

## Gaps do ciclo 3 × delta

| gap (ciclo 3) | correção | evidência | resultado |
|---|---|---|---|
| 1. caminho real sem teste (C21, C22, C23, C25) | `principal(argv, aws, agora)` exportado com executor injetável (`publicar.mjs:110-114`); `listagem` exportada (`:88`); `JSON.parse` com `try` (`:154-159`) | `deploy-site.test.mjs:284-288` (argumentos exatos da listagem), `:321-333` (modo real: só `rm` de `velho.js`, depois da listagem e da invalidação), `:341-346` (status 255 ou saída ilegível → 1, sem `rm`) | ✅ C21, C22, C23, C23b e C25 morrem |
| 2. carência contava do 1º upload | `--size-only` saiu do sync (`publicar.mjs:51`), conforme R2 | `deploy-site.test.mjs:135`, `:405-412`, `:414-421` | ✅ para N1 e N2; ❌ N3 sobrevive (gap 1 abaixo) |
| 3. PUB-08 desatualizado | EARS reescrito (`spec.md:75`) | `deploy-site.test.mjs:348-352`: `deepEqual(chamadas, [listagem('besave-site')])` | ✅ |
| 4. spec do dono desatualizada | nota de R3 (`docs/specs/BSV-17.md:25-26`) | `git diff ca64835..HEAD -- docs/specs/BSV-17.md` | ✅ |
| 5. `--remotos` fora do ensaio | recusado (`publicar.mjs:120-123`) | `deploy-site.test.mjs:354-359`: exit 1, `deepEqual(chamadas, [])` | ✅ N5 morre |

---

## Requisitos do dono × evidência

| req. | o que pede | código | teste (`file:line` + asserção) | resultado |
|---|---|---|---|---|
| R1 (a)+(b) | apaga só o que está fora do build **e** tem `LastModified` há mais de 7 dias | `publicar.mjs:76-83` | `deploy-site.test.mjs:92-99`: `deepEqual(expurgar(...), ['_app/immutable/chunks/velho.js'])` (8 d sai; 1 d fica; do build com 30 d fica); `:101-107` fronteira estrita | ✅ |
| R1 | arquivo do build nunca sai | `publicar.mjs:80` | `:109-119` (`version.json` com 90 d), `:121-124` (caminho Windows), `:420` (todo `_app/` do build continua no S3 simulado) | ✅ |
| R1 | `--ensaio` mostra a lista e não apaga | `publicar.mjs:136,162-163` | `:348-352`: só a listagem chega ao aws; CLI `:235-247` (ciclo 3): `aws s3 rm …velho.js` impresso, `apagaria 1 arquivo` | ✅ |
| R1 | modo real apaga de fato | `publicar.mjs:137,163` | `:330`: `deepEqual(rms, [['s3','rm','s3://besave-site/_app/immutable/chunks/velho.js']])` | ✅ (C22 morre) |
| R2 | sem `--size-only` no sync de `_app/` | `publicar.mjs:51` | `:135`: `!s.includes('--size-only')` | ✅ |
| R2 | saiu agora, 1º upload há 30 d, estava no deploy anterior (1 d) → **não** sai | `publicar.mjs:51,161` | `:405-412`: `s3.objetos.has(SAIU)` e `get(SAIU) === AGORA - 1*DIA` | ✅ para `--size-only`; ❌ não pega `--no-overwrite` (N3) |
| R2 | saiu há mais de 7 dias → sai no deploy seguinte | idem | `:414-421`: `!s3.objetos.has(SAIU)` | ✅ |
| R2 | PUB-04 ajustado | `spec.md:71` | — (leitura) | ✅ |
| R3 | só a nota, no início do item 3 | `docs/specs/BSV-17.md:25-26` | `git diff ca64835..HEAD -- docs/specs/BSV-17.md`: 1 linha trocada por 2; o texto antigo do item 3 segue igual depois da nota | ✅ |

Sobre R3: o texto da nota é idêntico ao pedido. Ele quebra a linha depois de "7 dias,", e no Markdown essa
quebra é só um espaço. A nota tem a data 2026-10-08, como o dono pediu. As linhas antigas do item 3
(`aws s3 sync --delete`, "`--delete` só dentro de `_app/`") continuam no arquivo, e isso é o esperado por R3
("e mais nada").

---

## O S3 simulado é fiel ao `aws s3 sync`?

Documentação da AWS CLI (`aws s3 sync help`, CLI 2.37.3 local, sem chamar a AWS):

- Sem flags: "A local file will require uploading if the size of the local file is different than the size of
  the S3 object, the last modified time of the local file is newer than the last modified time of the S3
  object, or the local file does not exist under the specified bucket and prefix."
- `--size-only`: "Makes the size of each key the only criteria used to decide whether to sync from source to
  destination."
- `--no-overwrite`: "only files not present at the destination will be transferred."

O modelo em `deploy-site.test.mjs:363-401` reenvia todo arquivo do build quando não há `--size-only`
(`:374`). No CI isso vale, porque o checkout e o `pnpm build` são novos a cada execução: o mtime local é
sempre mais novo que o `LastModified` do deploy anterior. Com `--size-only` e a chave já existente, o arquivo
não é reenviado. Para nomes com hash (mesmo nome, mesmo conteúdo, mesmo tamanho) isso também confere com a
documentação. Os arquivos do teste têm todos o mesmo tamanho (`'x'`), então o caso modelado é o certo.

**O teste prova o requisito ou espelha a implementação?** Ele não espelha: o modelo reage aos argumentos
reais que o script passa ao executor (`args.includes('--size-only')`), e não a uma constante do script. Por
isso mata N1 e N2 (o `--size-only` condicional, que um teste por leitura de argumentos não pegaria tão bem).
Mas o modelo é parcial. Ele conhece um único mecanismo de "não reenviar" e trata qualquer outro flag como
sync completo. Não modela `--no-overwrite` (N3 sobrevive) nem um 2º `--exclude` (N3b sobrevive). Resumindo:
o teste prova R2 contra a volta do `--size-only`, não contra qualquer forma de pular o reenvio. A garantia de
que o sync real reenvia tudo só vem da execução real (abaixo).

---

## Sensor de discriminação (delta)

Worktree temporário (`git worktree add --detach <scratchpad>/m4 HEAD`). Um script Node aplica cada
mutação por substituição de texto e confere que o padrão ocorre exatamente 1 vez (o checkout tem CRLF). Depois
roda `npm test` em `infra/functions` e restaura o arquivo original. Para nenhum mutante chegar à AWS, o `aws`
ficou fora do `PATH`, com `AWS_ENDPOINT_URL=http://127.0.0.1:9` e credencial falsa. Baseline sem mutação:
67/67. Worktree removido com `git worktree remove --force`. O `git status --porcelain` da árvore real ficou
vazio antes e depois. Nunca foi usado `git stash`. Profundidade: P0, porque o código apaga objetos num bucket
compartilhado.

Linhas em `infra/deploy-site/publicar.mjs` no HEAD `f4a4e83`.

### Mutantes do ciclo 3, refeitos

| # | linha | mutação | resultado | quem mata (`deploy-site.test.mjs`) |
|---|---|---|---|---|
| C1 | `:27` | carência 6 dias | ✅ morto | fronteira `:101` |
| C2 | `:27` | carência 8 dias | ✅ morto | `:92`, `:101`, `:321`, `:414` |
| C3 | `:80` | `<` → `<=` | ✅ morto | `:101` |
| C4 | `:80` | sem condição (a) | ✅ morto | `:92`, `:109`, `:121`, CLI |
| C5 | `:80` | sem condição (b) | ✅ morto | `:92`, `:101`, CLI |
| C6 | `:80` | sem filtro `_app/` | ✅ morto | `:109` |
| C7 | `:80` | `_app` sem barra | ✅ morto | `:109` |
| C8 | `:78` | carência em horas | ✅ morto | `:92`, `:101`, CLI |
| C9 | `:77` | build sem normalizar `\` | ✅ morto | `:121`, CLI, `:321` |
| C10 | `:65` | `sync --delete` de volta no fim | ✅ morto | PUB-03, PUB-08 |
| C11 | `:51` | `--delete` no sync | ✅ morto | PUB-03, PUB-08 |
| C12 | `:141,164` | limpeza antes do HTML e da invalidação | ✅ morto | CLI `:235`, `:321` |
| C13 | `:163` | `rm` chama o aws direto, também no ensaio | ✅ morto | CLI `:235`, `:348` |
| C14 | `:163` | ensaio não mostra a lista | ✅ morto | CLI `:235` |
| C15 | `:162` | contagem errada | ✅ morto | CLI `:235`, `:249` |
| C16 | `:79,86` | sem `?? []` nos dois lugares | ✅ morto | `:109`, `:256`, `:335` |
| C17 | `:86` | `lerListagem` sem `?? []` | ✅ morto | `:256` |
| C18 | `:79` | `expurgar` sem `?? []` | ✅ morto | `:109` |
| C19 | `:145` | ignora `--remotos` e lista de verdade | ✅ morto | PUB-08, CLI |
| C20 | `:163` | `rm` em `_app/_app/…` | ✅ morto | CLI `:235`, `:321`, `:414` |
| C21 | `:89` | listagem com `--prefix ''` | ✅ **morto** (sobrevivia no ciclo 3) | `:284` |
| C22 | `:163` | modo real não apaga (`if (!a.ensaio) return 0`) | ✅ **morto** (sobrevivia) | `:321`, `:414` |
| C23 | `:150` | listagem com status ≠ 0 ignorada (`if (false)`) | ✅ **morto** (sobrevivia) | `:341` |
| C23b | `:157-158` | listagem ilegível vira `[]` em vez de exit 1 | ✅ morto | `:341` |
| C24 | `:161` | expurgo sem a lista do build | ✅ morto | CLI `:235`, `:321` |
| C25 | `:90` | `--query` com `LastModified: Owner` | ✅ **morto** (sobrevivia) | `:284` |

### Mutantes novos do ciclo 4

| # | linha | mutação | resultado | quem mata |
|---|---|---|---|---|
| N1 | `:51` | `--size-only` de volta | ✅ morto | `:135`, `:405` |
| N2 | `:141` | `--size-only` só quando `_app/` já existe no bucket (`s3 ls` antes, só fora do ensaio) | ✅ morto | `:405` (só o teste de R2 pega) |
| N3 | `:51` | carência do 1º upload por outro caminho: `--no-overwrite` no sync | ❌ **sobreviveu** | — |
| N4a | `:137` | executor ignorado: `spawnSync('aws', …)` direto em `executar` | ✅ morto | `:321`, `:335`, `:405`, `:414` |
| N4b | `:149` | executor ignorado na listagem | ✅ morto | `:321`, `:335`, `:348`, `:405` |
| N5 | `:120` | `--remotos` aceito sem `--ensaio` | ✅ morto | `:354` |
| N6 | `:150` | listagem só falha com status nulo (status 255 ignorado) | ✅ morto | `:341` |
| N7 | `:141,164` | invalidação só depois do `rm` | ✅ morto | CLI `:235`, `:321` |
| N8a | `:136` | ensaio executa os `cp` | ✅ morto | PUB-08, CLI, `:348` |
| N8b | `:136` | ensaio executa os `rm` | ✅ morto | CLI `:235`, `:348` |
| N9 | `:167` | CLI passa `agora = 0` | ✅ morto | CLI `:235` |

### Informativo, fora do delta

| # | linha | mutação | resultado | observação |
|---|---|---|---|---|
| N3b | `:51` | 2º `--exclude 'immutable/*'` no sync (o `_app/immutable/` nunca sobe) | ❌ sobreviveu | Fraqueza que já existia: o PUB-04 (`:133`) só lê o 1º `--exclude`, e o S3 simulado (`:372`) também. Em produção o site quebraria, e o 1º deploy manual mostraria isso. A mesma correção do N3 mata este. |

**Resultado**: 36/37 mortos no delta (N3 sobreviveu). N3b fica registrado à parte, porque a fraqueza já existia
desde o ciclo 1 e o requisito dela não mudou no delta.

---

## Code quality (delta)

| verificação | status |
|---|---|
| Só o pedido: executor injetável, `listagem` exportada, `try` no parse, recusa de `--remotos`, `--size-only` removido | ✅ |
| Mudanças cirúrgicas: `publicar.mjs`, teste, README, spec.md e nota na spec do dono; workflow e `site_deploy.tf` sem mudança | ✅ |
| Sem dependência nova (regra 7) | ✅ |
| `principal` só roda sozinho quando é o script de entrada (`publicar.mjs:167`), então importar no teste não dispara nada | ✅ |
| Workflow não usa `--remotos` (`site-deploy.yml:85,88`) | ✅ |
| README coerente (`infra/README.md:317,324-325`): sem `--delete`, sem `--size-only`, carência a partir da saída do build | ✅ |
| `awsReal` sem `encoding` no modo não capturado: `r.status` vale do mesmo jeito | ✅ |

---

## Gaps ranqueados

1. **[Teste, motivo do FAIL] N3: o teste de R2 não pega `--no-overwrite`.** `deploy-site.test.mjs:126-136`
   (PUB-04) só proíbe `--size-only`, e o S3 simulado (`:374`) só modela esse flag. Correção sugerida, de uma
   linha, no PUB-04: `assert.deepEqual(s, ['s3','sync','build/_app','s3://besave-site/_app/','--exclude','version.json','--cache-control', IMUTAVEL])`.
   Isso mata N3, N3b e qualquer flag extra no sync. Uma alternativa é o S3 simulado recusar flag desconhecido.
2. **[Informativo, fora do delta] N3b: 2º `--exclude` no sync passa.** Resolvido pela mesma correção do gap 1.
3. **[Execução real] R2 depende do CI reenviar todo o `_app/`.** O teste assume que o mtime local é sempre mais
   novo. Isso vale para checkout e build novos, e só a execução real confirma (abaixo).

---

## O que só a execução real do dono prova (bloqueia o merge)

Tudo o que já estava nas listas dos ciclos 2 e 3: `plan` só com adições, `apply`, provedor OIDC inexistente,
simulação do papel (incluindo `s3:ListBucket` com `s3:prefix=_app/` e `s3:DeleteObject` em `_app/x.js` →
allowed), `sub` do token, variáveis, 1º deploy manual depois da BSV-30, evidência `REDACTED` e CI rodado. Mais:

- **R2 de verdade**: em dois deploys seguidos do mesmo commit (`workflow_dispatch`), o log do 2º mostra o `sync`
  com `upload:` de **todos** os arquivos de `_app/immutable/`, não só os novos. Em seguida,
  `aws s3api list-objects-v2 --bucket besave-site --prefix _app/` mostra o `LastModified` desses arquivos igual
  à hora do 2º deploy.
- **Carência**: num deploy em que um chunk saiu do build, mas estava no deploy anterior feito há menos de 7 dias,
  o passo Publicar diz `apagando 0 arquivo(s)` para ele, e `curl -I https://besave.com.br/_app/immutable/…`
  desse chunk continua 200.
- **Ensaio**: o passo Ensaio lista `_app/` e mostra `apagaria N arquivo(s)` sem nenhum `upload:` nem `delete:` no
  log.

---

## Resumo

**Overall**: ❌ não pronto pelo critério da skill. Há 1 mutante sobrevivente no delta (N3), que se corrige com
1 linha de teste. R1, R2 e R3 estão implementados, e os 5 gaps do ciclo 3 estão fechados. Ciclo 4 de 4
autorizados: a decisão é do dono.
**Spec-anchored**: R1 e R3 afirmados com o valor exato; R2 afirmado contra `--size-only`, mas não contra `--no-overwrite`
**Sensor (delta)**: 36/37 mortos (N3 sobreviveu); N3b informativo, fora do delta
**Gates**: terraform test 17/17, npm test 67/67, actionlint limpo, fmt/validate limpos

---

## Histórico: relatório do ciclo 3 (HEAD `ca64835`)

### Veredito do ciclo 3: reprovado (HEAD `ca64835`, delta `2fd9fd7..ca64835`)

O requisito do dono para a limpeza de `_app/` com carência está implementado e os três casos que ele pediu
(fora do build com 8 dias → apagado; com 1 dia → mantido; do build com 30 dias → mantido) são afirmados por
teste com o valor exato. Os gates estão verdes. A troca da ordem no workflow é legítima.

Mesmo assim o ciclo reprova por regra da skill: 4 de 28 mutantes do delta sobreviveram (C21, C22, C23, C25).
Os quatro estão no caminho que só roda com a AWS de verdade: a listagem real e o `s3 rm` fora do ensaio.
Nenhum deles faz apagar mais do que deveria. Todos falham para o lado seguro (não apagam nada, ou o
deploy fica vermelho depois de publicar). É o 3º ciclo, então a decisão sobe para o dono: corrigir os testes
(correção pequena, abaixo) ou aceitar a cobertura pela execução real.

- **Data**: 2026-10-07
- **Verifier**: sub-agente Verifier independente, Claude Opus 5.5 (autor ≠ verificador; não escreveu código nem testes)
- **Spec do dono**: `docs/specs/BSV-17.md` + revisão do dono de 07/10 (limpeza com carência) · **EARS**: `.specs/features/BSV-17/spec.md` (PUB-03 reescrito, PUB-09 novo)
- **Faixa do diff**: `31a86f4..ca64835`; delta verificado neste ciclo: `2fd9fd7..ca64835` (commit `ca64835`; `39e7e5b` só trouxe o validation.md)
- **Escopo do ciclo 3**: só o delta, a pedido do dono; o resto teve PASS no ciclo 2 (histórico abaixo)

---

### Histórico de ciclos

| ciclo | HEAD | veredito | sensor | gaps |
|---|---|---|---|---|
| 1 | `6c2d4a3` | FAIL ❌ | 39/40 (W7 sobreviveu) | 5 (ver relatório do ciclo 2) |
| 2 | `2fd9fd7` | PASS ✅ | 47/47 | 2 não bloqueantes (ex-gap 3 `--delete` cedo; D6) |
| 3 | `ca64835` | FAIL ❌ | 24/28 no delta | 4 mutantes sobreviventes no caminho real; carência medida a partir do 1º upload; PUB-08 e spec do dono desatualizados |

O ex-gap 3 do ciclo 2 (`sync --delete` logo depois da invalidação) foi fechado pela revisão do dono: o
`--delete` saiu e entrou a limpeza com carência.

---

### Gates (em `ca64835`, árvore real)

| gate | comando | resultado |
|---|---|---|
| fmt | `cd infra && terraform fmt -check -recursive` | limpo (exit 0) |
| validate | `terraform validate` | `Success! The configuration is valid.` (Terraform 1.16.2, aws 6.66.0) |
| test | `terraform test` | **17 passed, 0 failed** |
| node | `cd infra/functions && npm test` (com o `aws` fora do PATH) | **59 passed, 0 failed, 0 skipped** (ciclo 2: 52 → +7) |
| workflow | `actionlint -shellcheck shellcheck.exe .github/workflows/site-deploy.yml` | exit 0, sem achados |

Integridade dos testes: nenhum teste apagado. Dois foram reescritos por causa da mudança de requisito:
- `deploy-site.test.mjs:76-86` (PUB-03): antes exigia exatamente um `--delete` no fim; agora exige nenhum
  `--delete`, nenhum `rm`/`delete-object(s)` no plano, um só sync e o sync antes do 1º HTML. Segue o PUB-03 novo.
- `site-deploy-workflow.test.mjs:52-59`: antes "ensaio antes da credencial"; agora "credencial → ensaio →
  publicar". Análise abaixo.

---

### Requisito do dono × evidência

| requisito (dono, 07/10) | código | teste (`file:line` + asserção) | resultado |
|---|---|---|---|
| sem `sync --delete` em `_app/` | `infra/deploy-site/publicar.mjs:60-66` (o plano não tem mais o 2º sync) | `deploy-site.test.mjs:78-80`: `!comandos.some(c => c.includes('--delete'))`, sem `rm`; `:224-231`: `doesNotMatch(stdout, /--delete/)` | ✅ |
| apaga só o que (a) não está no build atual | `publicar.mjs:76,79` (`!build.has(o.Key)`) | `deploy-site.test.mjs:92-99`: `deepEqual(expurgar(...), ['_app/immutable/chunks/velho.js'])`; o do build com 30 dias fica | ✅ |
| e (b) tem `LastModified` há mais de 7 dias | `publicar.mjs:27,77,79` (`Date.parse(o.LastModified) < agora - 7*86_400_000`) | `deploy-site.test.mjs:101-107`: exatamente 7 dias fica, 7 dias + 1 s sai | ✅ |
| arquivo do build nunca sai, mesmo antigo | `publicar.mjs:76,79` | `deploy-site.test.mjs:92-99` (30 dias), `:109-119` (`version.json` com 90 dias), `:121-124` (caminho Windows) | ✅ |
| só dentro de `_app/` | `publicar.mjs:79` (`startsWith('_app/')`), `:88` (`--prefix _app/`) | `deploy-site.test.mjs:109-119`: `index.html`, `data/chunks/…`, `_appx/x.js` com 90 dias → `[]` | ✅ |
| limpeza por último (depois do HTML e da invalidação) | `publicar.mjs:132-149` | `deploy-site.test.mjs:233-245`: `indexOf('create-invalidation') < indexOf('aws s3 rm ')` | ✅ |
| `--ensaio` mostra a lista e não apaga | `publicar.mjs:125-131,148-149` | `deploy-site.test.mjs:233-245`: `deepEqual(rms, ['aws s3 rm s3://besave-site/_app/immutable/chunks/velho.js'])`, `apagaria 1 arquivo`, exit 0; `:247-252`: `apagaria 0 arquivo` | ✅ |
| listagem vazia (`null`) não quebra | `publicar.mjs:78,85` | `deploy-site.test.mjs:254-260`: `lerListagem('null\n')` → `[]`; `:117`: `expurgar(null, …)` → `[]` | ✅ |
| no modo real, o `s3 rm` roda de fato | `publicar.mjs:128,149` | **nenhum teste** (C22 sobrevive) | ⚠️ só a execução real prova |
| o comando de listagem real é o certo | `publicar.mjs:87-90,139-145` | **nenhum teste** (C21, C25 sobrevivem); conferido à mão com S3 falso local (abaixo) | ⚠️ |

### IDs EARS do delta

| ID | evidência | resultado |
|---|---|---|
| PUB-03 (novo) | `deploy-site.test.mjs:76-86` | ✅ |
| PUB-08 | `deploy-site.test.mjs:224-231` | ✅ (texto do EARS desatualizado, gap 3) |
| PUB-09 | `deploy-site.test.mjs:92-124`, `:233-260` | ✅ no ensaio e na função; ⚠️ no modo real (C22) |

### Ordem do workflow: legítima, não é enfraquecimento

`.github/workflows/site-deploy.yml:76-88`: credencial (`:76`) → Ensaio (`:84-85`) → Publicar (`:87-88`).
Teste `site-deploy-workflow.test.mjs:56`: `iCred > 0 && iCred < iEnsaio && iEnsaio < iPub`.

- O requisito novo exige que o `--ensaio` mostre a lista que seria apagada. Para isso ele precisa listar `_app/`
  no bucket, e isso exige credencial. Ensaio antes da credencial e requisito novo não cabem juntos no workflow.
- A garantia que o teste antigo protegia continua: com build fora dos prefixos ou sem `404.html`, o script sai
  em `publicar.mjs:121-124` antes de qualquer `spawnSync`, também no ensaio (`deploy-site.test.mjs:262-267`:
  exit 1, sem comando impresso). A única diferença é que o STS emite uma credencial de 1 h para um run que vai
  falhar sem usá-la. O papel é o mesmo do Publicar, que já recebia essa credencial.
- O teste novo continua discriminando: W13 (ensaio de volta antes da credencial), W14 (ensaio removido) e W15
  (ensaio sem `--ensaio`) morrem.
- Nenhum WF-xx da spec exigia ensaio antes da credencial; isso era uma suposição do autor no ciclo 1.

### Policy do papel (`infra/site_deploy.tf`, sem mudança) × o que a limpeza usa

| chamada | permissão | policy | resultado |
|---|---|---|---|
| `s3api list-objects-v2 --bucket besave-site --prefix _app/` | `s3:ListBucket` no bucket com `s3:prefix = "_app/"` | `site_deploy.tf:45-51`: `StringLike s3:prefix` ∈ `prefixos.json`, que tem `_app/*`; o `*` casa vazio, então `_app/` casa | ✅ |
| `s3 rm s3://besave-site/_app/…` | `s3:DeleteObject` em `arn:…:besave-site/_app/…` | `site_deploy.tf:39-44`: Put/Delete em `${bucket}/_app/*` | ✅ |
| paginação da listagem (> 1000 objetos) | mesma `ListBucket` com `continuation-token`; o prefixo não muda | idem | ✅ |

O `sync` de `_app/` já listava com o mesmo prefixo, então a limpeza não pede nenhuma permissão nova. A
simulação do papel pelo dono deve incluir `s3:ListBucket` com `s3:prefix=_app/` → allowed (veja a execução real).

### Formato da listagem (AWS CLI), conferido sem tocar a AWS real

- Documentação (`cli-usage-filter`): com `--output json` "the output is completely processed as a single, native
  structure before the `--query` filter is applied" → a paginação automática junta todas as páginas antes do
  `--query`. Com `--output text` seria por página; o script usa `json` (`publicar.mjs:89`). ✅
- Documentação (`cli-configure-files`): `cli_timestamp_format` padrão do CLI v2 é `iso8601`. A página do
  `list-objects-v2` mostra `"2019-11-05T23:11:50.000Z"` (formato do v1/wire).
- Execução local do `aws-cli/2.37.3` contra um S3 **falso em 127.0.0.1** (`--endpoint-url`, credencial falsa,
  nenhuma chamada à AWS): com 1 objeto a saída foi
  `[{"Key": "_app/immutable/chunks/a b(1).js", "LastModified": "2026-09-28T10:11:12+00:00"}]`; com prefixo
  vazio, `null`. O CLI pede `encoding-type=url` e decodifica a chave sozinho (espaço e parênteses voltaram
  certos). `Date.parse` aceita `+00:00`, `.000Z` e `Z`; `lerListagem('null')` → `[]`. ✅
- Se o `LastModified` vier ilegível, `Date.parse` dá `NaN`, `NaN < limite` é falso e o arquivo fica. Falha segura.

---

### Sensor de discriminação (só o delta)

Worktree temporário (`git worktree add --detach <scratchpad>/m3 HEAD`), mutação textual, arquivo original
restaurado a cada mutante, `npm test` em `infra/functions`. Para nenhum mutante chegar à AWS, os testes rodaram
com o diretório do `aws` fora do `PATH`, `AWS_ENDPOINT_URL=http://127.0.0.1:9` e credencial falsa. Mutantes de
workflow também passaram pelo actionlint. Worktree removido com `git worktree remove --force`; `git status
--porcelain` da árvore real vazio antes e depois.

| # | arquivo | mutação | resultado | quem mata |
|---|---|---|---|---|
| C1 | `publicar.mjs:27` | carência 6 dias | ✅ morto | fronteira de 7 dias (`:101`) |
| C2 | `publicar.mjs:27` | carência 8 dias | ✅ morto | caso de 8 dias (`:92`), fronteira |
| C3 | `publicar.mjs:79` | `<` → `<=` | ✅ morto | fronteira (`:101`) |
| C4 | `publicar.mjs:79` | sem condição (a): apaga arquivo do build antigo | ✅ morto | `:92`, `:109`, `:121` |
| C5 | `publicar.mjs:79` | sem condição (b): ignora a idade | ✅ morto | `:92`, `:101`, CLI |
| C6 | `publicar.mjs:79` | sem filtro de prefixo `_app/` | ✅ morto | `:109` |
| C7 | `publicar.mjs:79` | `_app` sem barra | ✅ morto | `:109` (`_appx/x.js`) |
| C8 | `publicar.mjs:77` | carência em horas em vez de dias | ✅ morto | `:92`, `:101`, CLI |
| C9 | `publicar.mjs:76` | sem normalizar `\` do build | ✅ morto | `:121`, CLI |
| C10 | `publicar.mjs:65` | volta o `sync --delete` no fim | ✅ morto | PUB-03 (`:76`), PUB-08 (`:224`) |
| C11 | `publicar.mjs:61` | `--delete` no sync de `_app/` | ✅ morto | PUB-03, PUB-08 |
| C12 | `publicar.mjs:132,149` | limpeza antes do HTML e da invalidação | ✅ morto | CLI (`:233`) |
| C13 | `publicar.mjs:149` | ensaio executa o `s3 rm` de verdade | ✅ morto | CLI (`:233`): exit ≠ 0 |
| C14 | `publicar.mjs:149` | ensaio não mostra a lista | ✅ morto | CLI (`:233`) |
| C15 | `publicar.mjs:148` | contagem errada na mensagem | ✅ morto | CLI (`:233`) |
| C16 | `publicar.mjs:78,85` | listagem `null` quebra (sem `?? []` nos dois lugares) | ✅ morto | `:109`, `:254` |
| C17 | `publicar.mjs:85` | só `lerListagem` sem `?? []` | ✅ morto | `:254` |
| C18 | `publicar.mjs:78` | só `expurgar` sem `?? []` | ✅ morto | `:109` |
| C19 | `publicar.mjs:136` | ignora `--remotos` e lista de verdade | ✅ morto | PUB-08, CLI |
| C20 | `publicar.mjs:149` | `rm` em `s3://bucket/_app/_app/…` | ✅ morto | CLI (`:233`) |
| C24 | `publicar.mjs:147` | expurgo sem a lista do build | ✅ morto | CLI (`:233`) |
| C21 | `publicar.mjs:88` | listagem com `--prefix ''` | ❌ **sobreviveu** | — |
| C22 | `publicar.mjs:147` | modo real não apaga nada (`if (!a.ensaio) return 0`) | ❌ **sobreviveu** | — |
| C23 | `publicar.mjs:141` | falha da listagem ignorada | ❌ **sobreviveu** | — |
| C25 | `publicar.mjs:89` | `--query` com `LastModified: Owner` (campo errado) | ❌ **sobreviveu** | — |
| W13 | `site-deploy.yml:84-85` | ensaio de volta antes da credencial | ✅ morto | `site-deploy-workflow.test.mjs:56` (actionlint 0) |
| W14 | `site-deploy.yml:84-85` | ensaio removido | ✅ morto | `:56` (actionlint 0) |
| W15 | `site-deploy.yml:85` | ensaio sem `--ensaio` | ✅ morto | `:56` (actionlint 0) |

**Resultado**: 24/28 mortos. Os sobreviventes e o efeito de cada um em produção:
- **C22**: o deploy real nunca apaga; `_app/` só cresce. Silencioso, seguro (custo de armazenamento).
- **C25**: `LastModified` vira `undefined` → `NaN` → nada sai. Silencioso, seguro.
- **C21**: `ListBucket` com `s3:prefix=""` é negado pela policy → deploy vermelho depois de publicar. Barulhento, seguro.
- **C23**: com o `aws` falhando, `stdout` vazio → `JSON.parse('')` lança → exit 1 com stack trace; com o
  `aws` ausente, `stdout` nulo → `[]` → exit 0 sem limpar. Seguro, mas pode esconder a falha.

---

### Code quality (delta)

| verificação | status |
|---|---|
| Só o pedido: função pura `expurgar`, `lerListagem`, a listagem e o `rm` | ✅ |
| Mudanças cirúrgicas, só em `infra/`, workflow e spec; `site_deploy.tf` sem mudança | ✅ |
| Sem dependência nova (regra 7) | ✅ |
| Testes com os valores do dono (8 d, 1 d, 30 d, fronteira estrita) | ✅ |
| `--remotos` também vale fora do ensaio (apaga com base num arquivo local) | ⚠️ não usado pelo workflow; ver gap 5 |
| README coerente com o código (`infra/README.md:317-326,399-400`) | ✅, salvo a frase da carência (gap 2) |

---

### Gaps ranqueados

1. **[Teste, motivo do FAIL] Caminho real sem teste: C22, C25, C21, C23.** Correção sugerida:
   (a) exportar `listagem` e afirmar os argumentos exatos (`--prefix _app/`, `--query 'Contents[].{Key: Key,
   LastModified: LastModified}'`, `--output json`). Mata C21 e C25.
   (b) teste de CLI no modo real com um `aws` falso, por exemplo uma variável `AWS_CLI` (padrão `aws`) que o
   teste aponta para um shim Node que grava os argumentos e devolve a listagem. O teste afirma que houve
   `s3 rm` só da chave velha e que listagem com exit ≠ 0 dá exit 1 com `falhou … listagem de _app/`. Mata C22 e C23.
   Também trocar `JSON.parse(r.stdout)` por uma checagem de `r.error`/`stdout` nulo.
2. **[Risco de desenho, decisão do dono] A carência conta do 1º upload, não da saída do build.** Com
   `--size-only` (`publicar.mjs:51`), um chunk que ficou igual por mais de 7 dias mantém o `LastModified`
   antigo. No deploy em que ele sai do build, é apagado **no mesmo deploy**, sem carência nenhuma. Isso segue a
   letra do requisito ("LastModified há mais de 7 dias"), mas contradiz o motivo dado no spec.md
   ("página antiga em cache acha seus chunks durante a carência") e no `infra/README.md:324`. A borda
   (`immutable`, 1 ano) reduz o risco, mas não zera: aba aberta há horas pedindo chunk que a borda não tem.
   Correção sugerida: tirar o `--size-only` do sync de `_app/`. No CI o build é novo, então o mtime local é
   sempre mais novo e o sync reenvia tudo. Assim `LastModified` = último deploy que tinha o arquivo, e
   "mais de 7 dias" passa a ser "fora de todos os builds dos últimos 7 dias". Custa algumas centenas de PUT por
   deploy, sem invalidação nova. Outra saída: `s3 cp --metadata-directive REPLACE` só nos arquivos do build.
3. **[Spec-precision] PUB-08 desatualizado.** `.specs/features/BSV-17/spec.md` PUB-08 diz "imprimir os comandos
   sem executá-los", mas o ensaio agora executa `list-objects-v2` (só leitura). Corrigir para "sem executar
   nenhum comando que escreva; a listagem de `_app/` roda".
4. **[Doc do dono] `docs/specs/BSV-17.md` ainda diz `_app/` → `aws s3 sync --delete` e "`--delete` só dentro
   de `_app/`".** A revisão de 07/10 está só no spec.md e no README. O dono atualiza a spec ou registra a decisão
   (AD) no PR.
5. **[Menor] `--remotos` aceito fora do ensaio.** `publicar.mjs:136-137`: no modo real, apaga com base num
   arquivo local, sem olhar o bucket. O workflow não usa. Sugestão: recusar `--remotos` sem `--ensaio`.

---

### O que só a execução real do dono prova (bloqueia o merge)

Tudo o que estava na lista do ciclo 2 (plan só com adições, apply, provedor OIDC inexistente, simulação, `sub`
do token, variáveis, primeiro deploy manual depois da BSV-30, evidência `REDACTED`, CI rodou), mais:

- `aws iam simulate-principal-policy`: `s3:ListBucket` com `s3:prefix=_app/` → allowed; `s3:DeleteObject` em
  `_app/x.js` → allowed.
- No 1º deploy manual, o passo Ensaio mostra a linha `list-objects-v2` e `apagaria 0 arquivo(s)` (bucket sem
  `_app/` antigo), e o Publicar termina com `apagando 0 arquivo(s)` e exit 0.
- Num deploy com mais de 7 dias de distância de outro que mudou chunks, o log mostra `aws s3 rm` só de
  `_app/…` fora do build atual, e `curl -I` de uma chave do build atual continua 200. É o que prova C22 e C25
  enquanto o gap 1 não for corrigido.

---

### Resumo

**Overall**: ❌ não pronto pelo critério da skill (mutantes sobreviventes); o requisito do dono está cumprido.
Ciclo 3 de 3: decisão escalada ao dono (corrigir o gap 1 ou aceitar a cobertura pela execução real).
**Spec-anchored**: os 8 itens do requisito do dono afirmados com o valor exato; o modo real ficou sem teste
**Sensor (delta)**: 24/28 mortos (C21, C22, C23, C25 sobreviveram; todos falham para o lado seguro)
**Gates**: terraform test 17/17, npm test 59/59, actionlint limpo, fmt/validate limpos


---

## Histórico: relatório do ciclo 2 (HEAD `2fd9fd7`)


### Veredito do ciclo 2: aprovado (HEAD 2fd9fd7)

Todos os critérios de aceite da spec do dono (`docs/specs/BSV-17.md`) que dá para verificar offline estão
atendidos no código e afirmados por teste com o valor da spec. Gates verdes. Sensor: 47/47 mutantes mortos;
o sobrevivente do ciclo 1 (W7) agora morre, assim como 2 variantes dele. O que falta é a execução real do dono
(abaixo), que bloqueia o merge por regra do repositório, não por este relatório.

- **Data**: 2026-10-07
- **Verifier**: Verifier sub-agente independente, Claude Opus 5.5 (autor ≠ verificador; não escreveu código nem testes)
- **Spec do dono**: `docs/specs/BSV-17.md` · **EARS**: `.specs/features/BSV-17/spec.md`
- **Diff range**: `31a86f4..2fd9fd7` (5 commits: 5359044, d2549ca, 4180d48, 6c2d4a3, 2fd9fd7)

---

### Histórico de ciclos

| ciclo | HEAD | veredito | sensor | gaps |
|---|---|---|---|---|
| 1 | `6c2d4a3` | FAIL ❌ | 39/40 (W7 sobreviveu) | 1 teste anti-injeção não discriminava; 2 cache de fonte/favicon não afirmado; 3 `--delete` logo após a invalidação (risco); 4 stack trace com build ausente; 5 frase errada no README |
| 2 | `2fd9fd7` | PASS ✅ | 47/47 | 1, 2, 4, 5 fechados (ver abaixo); 3 vai ao PR como proposta para o dono |

Correções do ciclo 2 (commit `2fd9fd7`, só 4 arquivos: README, `publicar.mjs`, 2 testes; `site_deploy.tf`,
`tests/`, mocks e workflow sem mudança):

- **Gap 1** — `infra/functions/test/site-deploy-workflow.test.mjs:48`: `deepEqual` das linhas com `${{ inputs.` fora de comentário = `['COMMIT: ${{ inputs.commit }}']`. Mata W7, W7b, W7c.
- **Gap 2** — `infra/functions/test/deploy-site.test.mjs:129-137`: `--cache-control` de fonte e favicon = `public, max-age=3600, stale-while-revalidate=86400`. Mata F1, F2, F3.
- **Gap 4** — `infra/deploy-site/publicar.mjs:94-97` (`existsSync`) + teste `deploy-site.test.mjs:192-197` (exit 1, `build não encontrado`, sem `at …publicar.mjs` no stderr). Mata B1, B2.
- **Gap 5** — `infra/README.md:311`: "O job só roda em `main` (o `if` pula outros branches)". Correto (`site-deploy.yml:27`).

---

### Gate Check (em `2fd9fd7`)

| gate | comando | resultado |
|---|---|---|
| fmt | `cd infra && terraform fmt -check -recursive` | limpo |
| validate | `terraform init -backend=false && terraform validate` | `Success! The configuration is valid.` (Terraform 1.16.2, aws 6.66.0) |
| test | `terraform test` | **17 passed, 0 failed** (`site_deploy`: 1 run, 7 asserts) |
| node | `cd infra/functions && npm test` | **52 passed, 0 failed, 0 skipped** (ciclo 1: 51; antes da feature: 28 → +24) |
| workflow | `actionlint -shellcheck shellcheck.exe .github/workflows/site-deploy.yml` | exit 0, sem achados |

Nenhum teste removido ou enfraquecido: o único assert trocado (`site-deploy-workflow.test.mjs:48`) ficou mais
forte (de "não casa nesta linha" para "conjunto exato de ocorrências").

---

### Spec-Anchored Acceptance Criteria

### Critérios da spec do dono

| critério | valor da spec | código (`file:line`) | teste (`file:line` + asserção) | resultado |
|---|---|---|---|---|
| provedor OIDC com `client_id_list` certo | url `https://token.actions.githubusercontent.com`, `["sts.amazonaws.com"]` | `infra/site_deploy.tf:9-12` | `infra/tests/site_deploy.tftest.hcl:19-20` — `client_id_list == toset(["sts.amazonaws.com"])` | ✅ |
| confiança só em `main` deste repo, `aud = sts.amazonaws.com` | `repo:rubenmarcuspaschoarelli/besave:ref:refs/heads/main`, `StringEquals` | `infra/site_deploy.tf:17-30` | `infra/tests/site_deploy.tftest.hcl:30-44` — `jsondecode(assume_role_policy) == {…}` literal | ✅ |
| sessão ≤ 1 h | `max_session_duration = 3600` | `infra/site_deploy.tf:16` | `infra/tests/site_deploy.tftest.hcl:26` | ✅ |
| Put/Delete exatamente nos 17 prefixos | `_app/*`, `index.html`, `404.html`, `favicon.*`, `desejos/*`, `assets/besave.css`, `assets/fontes/*` + 10 slugs do CONTRATO §2.3 | `infra/site_deploy.tf:39-44`, `infra/deploy-site/prefixos.json:1-19` | `infra/tests/site_deploy.tftest.hcl:7-11` (lista literal da spec, independente do JSON) e `:55-80` — igualdade da policy inteira; `infra/functions/test/deploy-site.test.mjs:35-42` | ✅ |
| `ListBucket` com `s3:prefix` nos mesmos | `StringLike s3:prefix` = os 17 | `infra/site_deploy.tf:45-51` | `infra/tests/site_deploy.tftest.hcl:64-70` | ✅ |
| `CreateInvalidation` só na distribuição do site | ARN de `aws_cloudfront_distribution.site` | `infra/site_deploy.tf:52-57` | `infra/tests/site_deploy.tftest.hcl:71-76` — ARN literal `…distribution/EEXEMPLO000000`; `curto` tem ARN distinto no mock (`ECURTO00000000`, `infra/tests/mocks/aws.tfmock.hcl:85-87`) → lição 11 respeitada (T7b) | ✅ |
| nada em prefixos do worker | sem `data/`, `oferta/`, `img/`, `manifest*`, `sitemap*`, `robots.txt`, `_estado/`, nem `*` | `infra/deploy-site/prefixos.json` | `infra/tests/site_deploy.tftest.hcl:87-95` | ✅ |
| `pnpm install --frozen-lockfile && pnpm build` em `apps/site` | literal | `.github/workflows/site-deploy.yml:70-74` | `site-deploy-workflow.test.mjs:27-29` | ✅ |
| `_app/` → `sync --delete`, `public, max-age=31536000, immutable` | literal | `publicar.mjs:10,50,66` | `deploy-site.test.mjs:75-105` | ✅ (desvio D1) |
| HTML → `public, max-age=300`, `text/html; charset=utf-8` | literal | `publicar.mjs:11,14,63` | `deploy-site.test.mjs:107-118` | ✅ |
| `assets/besave.css` → `public, max-age=3600, stale-while-revalidate=86400`, `text/css; charset=utf-8` | literal | `publicar.mjs:12,15,62` | `deploy-site.test.mjs:120-126` | ✅ |
| invalidação só HTML e `/assets/*`, nunca `/*` | literal | `publicar.mjs:55-56,64` | `deploy-site.test.mjs:139-156` — conjunto exato; `!includes('/*')` | ✅ |
| `--delete` só dentro de `_app/` | regra | `publicar.mjs:66` | `deploy-site.test.mjs:75-90` | ✅ |
| gatilho `workflow_dispatch` sempre; `push` em `main` + `paths: apps/site/**` só com `SITE_DEPLOY_ATIVO == 'true'` | literal | `site-deploy.yml:5-14,27` | `site-deploy-workflow.test.mjs:9-20` | ✅ |
| `AWS_ROLE_SITE` em variável; `us-east-1` | literal | `site-deploy.yml:36,82,85` | `site-deploy-workflow.test.mjs:22-25,31-34` | ✅ |
| ações `@v4` | 4 ações | `site-deploy.yml:43,65,67,80` | `site-deploy-workflow.test.mjs:36-41` | ✅ |
| nenhuma chave no GitHub; `id-token: write` | — | `site-deploy.yml:16-18` | `site-deploy-workflow.test.mjs:22-25` | ✅ |
| `actionlint` limpo | — | — | execução acima | ✅ |
| README: variável, ligar, rodar à mão, reverter | — | `infra/README.md` (seção "Deploy do site (BSV-17)") | leitura | ✅ |
| `plan` só com adições; `apply`; simulação; 1º deploy manual | — | — | **só a execução real do dono prova** | ⏳ |

### IDs EARS (`.specs/features/BSV-17/spec.md`)

| ID | evidência de teste | resultado |
|---|---|---|
| OIDC-01..03 | `site_deploy.tftest.hcl:18-51` | ✅ |
| POL-01..04 | `site_deploy.tftest.hcl:54-95` | ✅ |
| PUB-01 | `deploy-site.test.mjs:44-54` (12 intrusos), `:185-190` (CLI) | ✅ |
| PUB-02 | `deploy-site.test.mjs:56-62` | ✅ |
| PUB-03 | `deploy-site.test.mjs:75-90` | ✅ |
| PUB-04 | `deploy-site.test.mjs:92-105` | ✅ |
| PUB-05 | `deploy-site.test.mjs:107-118` | ✅ |
| PUB-06 | `deploy-site.test.mjs:120-126` | ✅ |
| PUB-07 | `deploy-site.test.mjs:139-156` | ✅ |
| PUB-08 | `deploy-site.test.mjs:177-183` | ✅ |
| WF-01..04, WF-06 | `site-deploy-workflow.test.mjs:9-41` + actionlint | ✅ |
| WF-05 | `site-deploy-workflow.test.mjs:43-49` (SHA, ancestral, só `apps/site`, input só via `env`) | ✅ |
| OPS-01 | `infra/README.md` | ✅ (leitura) |

### Fidelidade EARS × spec do dono (desvios registrados pelo autor como suposição; dono confirma no PR)

- **D1** `_app/version.json` com `public, max-age=300` em vez de imutável (nome fixo do SvelteKit).
- **D2** `--size-only` no sync de `_app/`; só seria problema com arquivo de nome fixo em `_app/` além de `version.json` (o build atual não tem).
- **D3** Ordem sync sem `--delete` → HTML → invalidação → sync com `--delete`.
- **D4** Variável `CF_DISTRIBUICAO_SITE` e output `id_distribuicao`.
- **D5** Reverter por input `commit` (só ancestral de `main`), porque a confiança é só `ref:refs/heads/main`.
- **D6** Cache de `favicon.*`/`assets/fontes/*` = o do CSS: a spec não define; agora fixado pela suposição do spec.md e afirmado (`deploy-site.test.mjs:129-137`). Fica como ⚠️ spec-precision para o dono confirmar o valor.

---

### Discrimination Sensor

Worktree temporário (`git worktree add --detach <scratchpad>/m2 2fd9fd7`), mutação textual, `git checkout -- .`
entre mutantes, worktree removido no fim. `git status --porcelain` da árvore real igual antes e depois (só o
próprio `validation.md`, não rastreado). Profundidade P0 (credencial e permissão em bucket compartilhado).
No ciclo 2 rodou o conjunto inteiro do ciclo 1 mais 7 mutantes novos.

| # | arquivo | mutação | testes | ciclo 1 | ciclo 2 |
|---|---|---|---|---|---|
| T1 | `prefixos.json` | + `"data/*"` | tf, npm | ✅ | ✅ |
| T2 | `prefixos.json` | + `"*"` | tf, npm | ✅ | ✅ |
| T3 | `prefixos.json` | − `"pets/*"` | tf, npm | ✅ | ✅ |
| T4 | `site_deploy.tf:26` | `refs/heads/main` → `refs/heads/*` | tf | ✅ | ✅ |
| T5 | `site_deploy.tf:26` | sub → `repo:…:*` | tf | ✅ | ✅ |
| T6 | `site_deploy.tf:16` | `max_session_duration = 7200` | tf | ✅ | ✅ |
| T7 | `site_deploy.tf:56` | Invalidar → `one(aws_cloudfront_distribution.curto[*].arn)` | tf | ✅ | ✅ |
| T7b | `site_deploy.tf:56` | Invalidar → `curto[0].arn` com `-var=ativar_curto=true` (ARNs distintos; lição 11) | tf | ✅ | — (arquivo sem mudança) |
| T8 | `site_deploy.tf:56` | Invalidar em `"*"` | tf | ✅ | ✅ |
| T9 | `site_deploy.tf:11` | `client_id_list = ["sigstore"]` | tf | ✅ | ✅ |
| T10 | `site_deploy.tf:50` | sem condição `s3:prefix` | tf | ✅ | ✅ |
| T11 | `site_deploy.tf:25` | sem condição `aud` | tf | ✅ | ✅ |
| T12 | `site_deploy.tf:43` | Put/Delete no bucket `logs` | tf | ✅ | ✅ |
| T13 | `site_deploy.tf:42` | + `s3:GetObject` | tf | ✅ | ✅ |
| J1 | `publicar.mjs:60` | `--delete` no primeiro sync | npm | ✅ | ✅ |
| J2 | `publicar.mjs:42` | sem checagem de prefixos | npm | ✅ | ✅ |
| J3 | `publicar.mjs:26` | `404.html` não obrigatório | npm | ✅ | ✅ |
| J4 | `publicar.mjs:63` | HTML com cache de 1 h | npm | ✅ | ✅ |
| J5 | `publicar.mjs:62` | CSS com cache de 300 s | npm | ✅ | ✅ |
| J6 | `publicar.mjs:10` | `_app` sem `immutable` | npm | ✅ | ✅ |
| J7 | `publicar.mjs:56` | invalidação inclui `/*` | npm | ✅ | ✅ |
| J8 | `publicar.mjs:60,66` | sync `--delete` antes do HTML | npm | ✅ | ✅ |
| J9 | `publicar.mjs:14` | HTML sem `charset=utf-8` | npm | ✅ | ✅ |
| J10 | `publicar.mjs:50` | sync com destino na raiz do bucket | npm | ✅ | ✅ |
| J11 | `publicar.mjs:30` | `*` não cruza `/` | npm | ✅ | ✅ |
| J12 | `publicar.mjs:56` | invalida também `/_app/*` | npm | ✅ | ✅ |
| J13 | `publicar.mjs:105` | `--ensaio` executa comandos | npm | ✅ | ✅ |
| W1 | `site-deploy.yml:27` | sem `vars.SITE_DEPLOY_ATIVO` | npm | ✅ | ✅ |
| W2 | `site-deploy.yml:82` | `vars.AWS_ROLE_SITE` → `secrets.` | npm | ✅ | ✅ |
| W3 | `site-deploy.yml:18` | sem `id-token: write` | npm | ✅ | ✅ |
| W4 | `site-deploy.yml:85` | `sa-east-1` | npm | ✅ | ✅ |
| W5 | `site-deploy.yml:27` | sem guarda `refs/heads/main` | npm | ✅ | ✅ |
| W6 | `site-deploy.yml:14` | push sem `paths` | npm | ✅ | ✅ |
| W7 | `site-deploy.yml:63` | `${{ inputs.commit }}` numa linha interna de `run: \|` | npm, actionlint | ❌ sobreviveu | ✅ morto |
| W7b | `site-deploy.yml:61` | `${{inputs.commit}}` (sem espaços) dentro do bloco `run` | npm, actionlint | — | ✅ morto |
| W7c | `site-deploy.yml:43` | `run: echo "${{ inputs.commit }}"` em linha única | npm, actionlint | — | ✅ morto |
| W8 | `site-deploy.yml:57-60` | sem checagem de ancestral | npm | ✅ | ✅ |
| W9 | `site-deploy.yml:43` | `checkout@v5` | npm | ✅ | ✅ |
| W10 | `site-deploy.yml:13` | push também em `develop` | npm | ✅ | ✅ |
| W11 | `site-deploy.yml:78` | ensaio sem `--ensaio` | npm | ✅ | ✅ |
| W12 | `site-deploy.yml:73` | `pnpm install` sem `--frozen-lockfile` | npm | ✅ | ✅ |
| F1 | `publicar.mjs:62` | fontes com cache de 300 s | npm | — | ✅ morto |
| F2 | `publicar.mjs:62` | favicon com cache de 300 s | npm | — | ✅ morto |
| F3 | `publicar.mjs:62` | fontes/favicon imutáveis por 1 ano | npm | — | ✅ morto |
| B1 | `publicar.mjs:94-97` | sem checagem do build (volta o stack trace) | npm | — | ✅ morto |
| B2 | `publicar.mjs:94` | checagem do build desligada (`if (false)`) | npm | — | ✅ morto |

**Resultado ciclo 2**: 47/47 mortos (T7b não reexecutado: `site_deploy.tf` e mocks iguais aos do ciclo 1) — PASS ✅.
O actionlint não mata nenhum mutante W (não trata `inputs.*` como não confiável); quem pega são os testes de leitura.

### Ensaio contra o build real (ciclo 1, `vite build` de `apps/site`)

O build atual traz `index.html`, `_app/version.json` e `_app/immutable/**`, sem `404.html`. O `publicar.mjs --ensaio`
responde `faltando no build: 404.html`, exit 1, sem comando — correto (MANIFEST §5) e documentado no README.
Com um `404.html` sintético a ordem sai como esperada (sync → `version.json` → `404.html` → `index.html` →
invalidação `/index.html /404.html /assets/*` → sync `--delete`).

---

### Code Quality

| princípio | status |
|---|---|
| Mínimo de código / sem escopo extra | ✅ (D2/D4/D5 justificados) |
| Mudanças cirúrgicas, só nas pastas da spec | ✅ |
| Nada muda na distribuição, bucket, worker, vigia | ✅ |
| Testes afirmam valor da spec (lista literal independente do JSON) | ✅ |
| Lição 11 (mocks distintos) | ✅ (`curto` ≠ `site`; `logs` ≠ `site`) |
| Line endings | ✅ índice em LF (`git ls-files --eol`) |
| Regra 7 (dependência nova) | ✅ nenhuma |
| Diretrizes: `CLAUDE.md`, `docs/WORKFLOW-AGENTES.md` §6 | ✅ |

---

### Gaps restantes (não bloqueiam este veredito)

1. **[Risco, decisão do dono — ex-gap 3]** `publicar.mjs:64-66`: `sync --delete` de `_app/` logo após uma invalidação
   assíncrona. Página antiga (até 300 s no navegador) pode pedir chunk já apagado numa falta de cache na borda → 404.
   Probabilidade baixa (borda guarda `_app/` por 1 ano, `immutable`). Proposta: apagar só o `_app/` de dois builds atrás,
   como os manifests do worker. Vai ao PR como proposta.
2. **[Spec-precision, D6]** valor de cache de fonte/favicon não está na spec; dono confirma.

---

### O que só a execução real do dono prova (bloqueia o merge)

- `terraform plan` real: só 3 adições (provedor OIDC, papel, policy), 0 change/destroy; `apply`.
- Que a conta não tem `token.actions.githubusercontent.com` (senão `EntityAlreadyExists` → `import`).
- `aws iam simulate-principal-policy`: `PutObject _app/x.js` → allowed; `DeleteObject manifest.json`,
  `oferta/1/index.html`, `data/chunks/x` → implicitDeny; `ListBucket` com `s3:prefix=data/` → implicitDeny.
- Que o `sub` do token num `workflow_dispatch` em `main` é `repo:rubenmarcuspaschoarelli/besave:ref:refs/heads/main`
  (muda com template de `sub` customizado ou com `environment:`).
- Criar `AWS_ROLE_SITE` e `CF_DISTRIBUICAO_SITE`; primeiro deploy manual (`workflow_dispatch`) só depois da BSV-30
  (o build precisa trazer `404.html`); até lá `curl -s https://besave.com.br/` mostra a home provisória.
- `plan` e log do workflow manual colados no PR com ARNs `REDACTED` (regra 11).
- CI do GitHub rodou de fato no PR (lição 12).

---

### Requirement Traceability Update

| Requirement | Ciclo 1 | Ciclo 2 |
|---|---|---|
| OIDC-01..03, POL-01..04, PUB-01..08, WF-01..04, WF-06, OPS-01 | ✅ Verified | ✅ Verified |
| WF-05 | ❌ Needs Fix | ✅ Verified |

### Summary

**Overall**: ✅ Ready para o PR (merge bloqueado só pela execução real do dono)
**Spec-anchored check**: 21/21 ACs verificáveis offline com valor da spec; 1 spec-precision (D6, agora afirmado); plan/apply/simulação/deploy só na execução real
**Sensor**: 47/47 mortos (ciclo 1: 39/40)
**Gate**: terraform test 17/17, npm test 52/52, actionlint limpo, fmt/validate limpos
