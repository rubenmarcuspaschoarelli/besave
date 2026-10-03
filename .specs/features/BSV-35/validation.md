# BSV-35 Validation (Iteração 2)

**Date**: 2026-10-03
**Spec**: `.specs/features/BSV-35/spec.md` (EARS) + `docs/specs/BSV-35.md` (critério de aceite do dono)
**Diff range**: `c8de133..d9061a0`, commits `786390d..d9061a0` (10 commits). A rodada 1 cobriu `c8de133..3745280`; a rodada 2 acrescenta `d9061a0` (T9: correções)
**Verifier**: sub-agente independente (autor ≠ verificador). Toda a evidência foi recoletada do código e de execuções novas

## Veredito: ✅ PASS (rodada 2), com 1 resíduo para o dono (N4) e 1 risco de ambiente (DES-01/02 sob carga)

**Result**: PASS

Os 3 gaps da rodada 1 foram fechados por `d9061a0`, conferidos por sonda e por mutantes (ver "Rodada 2" no fim).
Resíduo: o mutante N4 (payload de `novas` como delta em vez de total) sobrevive. A spec não define o `n` de
`novas(n)`; o código segue a leitura natural (`n == cat.novas()`). Gap de precisão, não desvio; o dono decide se quer a
asserção. Risco: DES-01/02 flutuam sob carga na máquina compartilhada.

---

## Rodada 1 (histórico, `3745280`): ❌ FAIL

Rodada 1 encerrada com FAIL e 3 fix tasks pequenas: 1 defeito Major e 2 mutantes sobreviventes Minor.

Os 43 ACs têm evidência `file:line`, e o valor de cada asserção bate com o resultado da spec. O gate está verde.
O FAIL vem de fora dos ACs EARS:
1. **Defeito (Major)**: o evento `novas(n)`, listado em "Saídas → Eventos" da spec do ticket, não é reemitido quando,
   depois de `confirmarNovas()`, chega um lote novo com a mesma contagem do anterior. Caso típico: 1 oferta nova por ciclo.
   A UI da BSV-30 não mostraria o toast. Reproduzido por sonda na cópia descartável.
2. **Mutantes vivos (Minor)**: M12 (intervalo de polling 5 → 4 min passa) e M13 (`completo` emitido com catálogo incompleto passa).

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 Esqueleto | ✅ Done | `786390d`/`0bb4994` |
| T2 Tipos | ✅ Done | `8e69e76` |
| T3 Gerador | ✅ Done | `1074d20` |
| T4 Catálogo | ✅ Done | `a36c4ec` |
| T5 Busca | ✅ Done | `e2edfe1` |
| T6 Diff e sincronizador | ⚠️ Partial | `b98a9ca`. O defeito do evento `novas` e os mutantes M12 e M13 ficam aqui |
| T7 Fachada e orçamentos | ✅ Done | `541dd30` |
| T8 `pnpm medir` | ✅ Done | `3745280`; saída real em `apps/site/medicoes/` (gitignored, sem domínio) |

---

## Spec-Anchored Acceptance Criteria

Caminhos relativos a `apps/site/src/lib/dados/`.

### Contrato, gerador, esqueleto

| AC | Spec-defined outcome | `file:line` + asserção | Result |
| -- | -------------------- | ---------------------- | ------ |
| TIP-01 | enums iguais a `enums.schema.json` | `tipos.test.ts:13-15`: `expect([...LOJAS]).toEqual(enums.Loja.enum)` (idem Publico, Area) | ✅ |
| TIP-02 | `chunk-ok.json` e `manifest-ok.json` carregam | `tipos.test.ts:20`: `ehChunk(chunk)` true, `:22` ids `[5412,5413,5420]`, `:33` `ehManifest(m)` true, `:35` `contrato '1.3.3'`, `:36-42` ChunkRef exato | ✅ |
| GER-01 | 30 mil cards e manifest passam no ajv | `gerador.test.ts:26`: `validarChunk(cards)` true; `:28` `validarManifest(pub.manifest)` true; `:30` soma `qtd` = 30 000 | ✅ |
| GER-02 | mesma semente → mesmos bytes | `gerador.test.ts:34`: `JSON.stringify(gerarCards(2000,7))` igual; `:38` manifest igual | ✅ |
| GER-03 | distribuição da regra 13 (±1,5 pp; título 65..75 / p95 140..160 / máx 200; 45 dias; lacunas) | `gerador.test.ts:42-55` (área/público/loja), `:59-61` (cupom/pd/x), `:65-74` (títulos, acento), `:80-86` (ids, dt) | ✅ (tolerância é premissa documentada) |
| ESQ-01 | adapter-static com fallback desligado, `prerender = true`, TS strict, gate verde | `vite.config.ts:13` `adapter({..., fallback: undefined, strict: true})`; `routes/+layout.ts:1` `prerender = true`; `tsconfig.json:4` `strict: true`; gate abaixo com exit 0 | ✅ |

### Catálogo

| AC | Spec-defined outcome | `file:line` + asserção | Result |
| -- | -------------------- | ---------------------- | ------ |
| CAT-01 | `lista` padrão sem `x:1` | `catalogo.test.ts:27-28`: `not.toContain(4)`, `toHaveLength(4)` | ✅ |
| CAT-02 | `mostrarExpiradas` inclui | `catalogo.test.ts:32-33`: `toContain(4)`, `toHaveLength(5)` | ✅ |
| CAT-03 | filtros área/público/loja | `catalogo.test.ts:37-40`: `[1,3,5]`, `[3]`, `[2]`, `[5]` | ✅ |
| CAT-04 | `dt` desc, desempate `id` desc | `catalogo.test.ts:44-45`: `toEqual([5,2,3,1])` (5 e 2 com mesmo `dt`) | ✅ |
| CAT-05 | desconto desc, `pd` nulo por último | `catalogo.test.ts:50`: `toEqual([5,1,3,2])` | ✅ |
| CAT-06 | `pp` asc | `catalogo.test.ts:54`: `toEqual([2,5,1,3])` | ✅ |
| CAT-07 | 4 novos (1 expirado, 1 `dt` antigo) → `novas() == 3` | `catalogo.test.ts:76`: `expect(cat.novas()).toBe(3)` (ids 10 `x:1`, 11 `dt` antigo) | ✅ |
| CAT-08 | `lista` inalterada até `confirmarNovas()`, depois inclui | `catalogo.test.ts:81` `toEqual(antes)`; `:84` `[1,2,3,11,12,13]` | ✅ |
| CAT-09 | preço novo de id exibido aparece sem confirmar | `catalogo.test.ts:91`: `pp` = 1500; `:92` id novo 20 fora | ✅ |
| CAT-10 | `completo` só com todos do alvo; contam chunks | `catalogo.test.ts:120-126`: `[0,2,false]` → `[1,2,false]` → arquivo errado `[1,2,false]` → `[2,2,true]` | ✅ |

### Busca

Caminhos relativos a `busca.test.ts`.

| AC | Spec-defined outcome | `file:line` + asserção | Result |
| -- | -------------------- | ---------------------- | ------ |
| BUS-01 | "protetor solar" acha "Protetor Solar Facial FPS 50" | `:29` `toEqual([1])` | ✅ |
| BUS-02 | "PROTETOR" = "protetor" = "protetór" | `:34-36` `[1,5]` nas três | ✅ |
| BUS-03 | "cafe" acha "Café" | `:40` `toEqual([2])` | ✅ |
| BUS-04 | "olar" não acha "Solar" | `:44` `total` 0; `:45` "sol" → `[1,6]` | ✅ |
| BUS-05 | "besave" acha cupom `BESAVE10` | `:49` `toEqual([3])` | ✅ |
| BUS-06 | "mercado livre" acha a loja | `:53` `toEqual([4])` (título sem "mercado") | ✅ |
| BUS-07 | < 2 caracteres → vazio | `:57-60` `{ itens: [], total: 0, completo: true }` para "a", " é ", "", "!!" | ✅ |
| BUS-08 | inclui expiradas, E, ordem do filtro, limite, total, completo | `:65-66` `[5]` com `x` 1; `:70` E → 0; `:75` filtro; `:77` ordem `[5,1]`; `:79-80` limite 1 com total 2; `:84` `completo` false | ✅ |

### Sincronizador e polling

Caminhos relativos a `sincronizador.test.ts`.

| AC | Spec-defined outcome | `file:line` + asserção | Result |
| -- | -------------------- | ---------------------- | ------ |
| DIF-01 | `baixar` em n desc; `descartar` = n ausentes | `:144` `[2,1,0]`; `:149` igual → `{baixar:[],descartar:[]}`; `:154-155` `[3,1]` / `[2]` | ✅ |
| SIN-01 | manifest → 3 maiores n em paralelo → `pronto` → resto em n desc, um por vez → `completo` no fim | `:169` `log[0]` manifest; `:170` 3 maiores; `:171` `pronto`; `:172` resto em ordem; `:174` posição de `completo`; `:177` 3 em voo; `:178` depois 1 por vez | ✅ (com M13, ver gaps: o caso de falha na 1ª carga não é testado) |
| SIN-02 | manifest com `cache: 'no-cache'` | `:186` `expect(amb.inits).toEqual(['no-cache'])` | ✅ |
| SIN-03 | manifest igual → 0 chunks | `:195-196` 1 manifest, `chunksBaixados()` `[]` | ✅ |
| SIN-04 | 1 chunk alterado → 1 fetch | `:210` `[floor(id/1000)]`; `:211` preço 123 | ✅ |
| SIN-05 | n removido → fora de `lista` e `buscar` | `:226` lista; `:229` buscar; `:232` tamanho | ✅ |
| SIN-06 | `versao` menor → ignorado | `:247` 0 chunks; `:248` lista idêntica | ✅ |
| SIN-07 | `contrato` 2.0.0 → `atualizarApp`, nada aplicado | `:262` eventos `[{tipo:'atualizarApp',contrato:'2.0.0'}]`; `:263-264`; `:269-270` catálogo vazio, `total` 0 | ✅ |
| SIN-08 | 404 → 1 manifest novo + 1 nova tentativa | `:280` 2 manifests; `:281` chunk 2×; `:282` ordem; `:283` sem `erro` | ✅ |
| SIN-09 | 404 persistente → dados antigos, `erro`, nova tentativa no ciclo seguinte | `:301` `[arq,arq]`; `:302` `{tipo:'erro',erro:'chunk',n:3}`; `:303` preço antigo; `:309-310` ciclo seguinte baixa e aplica 77 | ✅ |
| POL-01 | 15 min visível → 3 polls | `:387` `manifests() == 3` | ✅ (M12: intervalo não fixado, ver gaps) |
| POL-02 | 15 min oculta → 0 fetch | `:394` `log` `[]` | ✅ |
| POL-03 | visível após 12 min oculta → 1 poll imediato | `:401` 0; `:403` 1; `:405-407` próximo em `INTERVALO_MS` | ✅ (usa a própria constante; ver M12) |

### Desempenho, pureza, medição

| AC | Spec-defined outcome | `file:line` + asserção | Result |
| -- | -------------------- | ---------------------- | ------ |
| DES-01 | aplicar 30 mil ≤ 400 ms (mediana de 5) | `desempenho.test.ts:84` `mediana(tempos) <= 400` | ✅ no gate; ⚠️ falha sob carga (ver gate) |
| DES-02 | `buscar` p95 de 50 ≤ 20 ms | `desempenho.test.ts:88` 50 consultas; `:93` `p95 <= 20` | ✅ no gate; ⚠️ falha sob carga |
| DES-03 | `lista` área + ordem ≤ 40 ms | `desempenho.test.ts:102` (3 ordens) | ✅ |
| DES-04 | módulo ≤ 10 KB gzip | `desempenho.test.ts:123` `gzipSync(codigo).length <= 10*1024` (build vite lib minificado de `dados.ts`) | ✅ |
| PUR-01 | sem `window`/`document`; sem `dependencies` | `desempenho.test.ts:127` `not.toMatch(/\b(window\|document)\b/)`; `:135` `dependencies ?? {}` = `{}` | ✅ (M35 morto) |
| MED-01 | imprime cards, bytes, pronto, completo, aplicar, busca p95 (20), 2ª passada | `scripts/medir.ts:104-111`; 20 consultas em `:7-28`; saída real `medicoes/medir-1.txt`: 17 326 cards, 690 528 B, pronto 1 805 ms, completo 3 020 ms, aplicar 140 ms, p95 7,1 ms, **2ª passada: 0 chunks** | ✅ (sem teste automatizado, como previsto na matriz; a execução real é do dono) |

**Status**: ✅ 43/43 ACs com evidência e valor conferido. Nenhum gap de precisão bloqueante (ver observações 2 a 4).

---

## Edge Cases

- [x] Consulta normalizada "" ou 1 char → `{itens:[],total:0}`: `busca.test.ts:57-60`
- [x] Manifest com 0 chunks → catálogo vazio e `completo`: `catalogo.test.ts:132-133` (só no nível do `Catalogo`)
- [x] Falha no manifest → `erro('manifest')`, catálogo mantido: `sincronizador.test.ts:323-324`
- [x] `n` que falhou e sumiu do manifest refeito → descartado: `sincronizador.test.ts:353-357` (M16 morto)

---

## Gate Check

- **Gate command**: `corepack pnpm@9.15.9 lint && … check && … test && … build` em `apps/site/`
- **lint**: exit 0 (Prettier OK, ESLint sem achados)
- **check**: exit 0, `398 FILES 0 ERRORS 0 WARNINGS` (inclui `scripts/`, pelo `tsconfig.json`)
- **test**: exit 0, **6 arquivos, 59 passed, 0 failed, 0 skipped**
- **build**: exit 0, `build/index.html` prerenderizado (adapter-static)
- **Test count before feature**: 0 (o app não existia). **After**: 59. **Delta**: +59
- **Flutuação de desempenho** (thresholds intocados): `desempenho.test.ts` rodado isolado 4 vezes depois do sensor, com a
  máquina em ~50% de CPU por outros processos. 3 rodadas falharam (DES-01 mediana 562 ms > 400; DES-02 p95 29 ms > 20) e
  a 4ª passou (6/6). Durante o sensor, DES-01/02 falharam em vários mutantes por carga. Medição real em produção:
  aplicar 17 mil cards levou 130–140 ms e busca p95 ficou em 7 ms, então o código cabe no orçamento com folga; o teste
  é sensível à carga da máquina.

---

## Discrimination Sensor

Scratch: `git worktree add --detach <scratchpad>/wt HEAD` + `pnpm install --frozen-lockfile`. Baseline do scratch: 59/59.
Cada mutante foi aplicado numa linha de produção, com a suíte inteira rodando e o arquivo restaurado em seguida.
Linhas no código de HEAD.

| # | File:line | Mutação | Resultado (teste que matou) |
| - | --------- | ------- | --------------------------- |
| M01 | `sincronizador.ts:9` | lote inicial 3 → 2 | ✅ Killed (SIN-01) |
| M02 | `sincronizador.ts:119` | sem evento `pronto` | ✅ Killed (SIN-01) |
| M03 | `sincronizador.ts:82` | manifest sem `cache:'no-cache'` | ✅ Killed (SIN-02) |
| M04 | `sincronizador.ts:139` | `versao <` → `<=` | ✅ Killed (SIN-09, nova tentativa no ciclo seguinte) |
| M05 | `sincronizador.ts:139` | checagem de versão removida | ✅ Killed (SIN-06) |
| M06 | `sincronizador.ts:133` | checagem do major do contrato removida | ✅ Killed (SIN-07) |
| M07 | `sincronizador.ts:150` | não refaz o manifest na falha | ✅ Killed (SIN-08, SIN-09) |
| M08 | `sincronizador.ts:152` | sem nova tentativa do chunk | ✅ Killed (SIN-08, SIN-09) |
| M09 | `sincronizador.ts:114` | falha descarta os dados antigos do `n` | ✅ Killed (SIN-09) |
| M10 | `sincronizador.ts:193` | aba oculta não cancela o timer | ⚪ Survived, **equivalente**: `tique` (`:186`) checa `visivel()` de novo e não faz fetch |
| M11 | `sincronizador.ts:195` | volta visível não sincroniza na hora | ✅ Killed (POL-03) |
| M12 | `sincronizador.ts:8` | `INTERVALO_MS` 5 → 4 min | ❌ **Survived**: 15 min dá 3 polls com 4 min também (4/8/12); POL-03 usa a própria constante |
| M13 | `sincronizador.ts:157` | `completo` emitido sem `cat.completo` | ❌ **Survived**: no sensor caiu só por DES-02 (flutuação). Rodado de novo sem `desempenho.test.ts`: 53/53 passam |
| M14 | `sincronizador.ts:105` | `n` ausente não é descartado | ✅ Killed (SIN-05) |
| M15 | `sincronizador.ts:52` | `diferenca` sem ordenar por n desc | ✅ Killed (DIF-01, SIN-01) |
| M16 | `sincronizador.ts:151` | nova tentativa ignora o manifest refeito | ✅ Killed (n que falhou e sumiu) |
| M17 | `catalogo.ts:151` | `lista` inclui `x:1` por padrão | ✅ Killed (CAT-01, SIN-01, …) |
| M18 | `catalogo.ts:152` | pendentes aparecem antes de confirmar | ✅ Killed (CAT-08, CAT-09) |
| M19 | `catalogo.ts:110` | nova expirada conta como nova | ✅ Killed (CAT-07) |
| M20 | `catalogo.ts:188` | base fixada antes de `completo` | ✅ Killed (17 testes) |
| M21 | `catalogo.ts:9` | sem remover acentos | ✅ Killed (BUS-02, BUS-03) |
| M22 | `catalogo.ts:30` | cupom fora do texto pesquisável | ✅ Killed (BUS-05) |
| M23 | `catalogo.ts:30` | rótulo da loja fora do texto pesquisável | ✅ Killed (BUS-06) |
| M24 | `catalogo.ts:35` | desconto com `pd` nulo primeiro | ✅ Killed (CAT-05) |
| M25 | `catalogo.ts:55` | preço desc | ✅ Killed (CAT-06) |
| M26 | `catalogo.ts:62` | desempate `id` asc | ✅ Killed (CAT-04) |
| M27 | `catalogo.ts:102` | texto antigo reaproveitado com título novo | ✅ Killed (título alterado) |
| M28 | `catalogo.ts:71` | filtro de público ignorado | ✅ Killed (CAT-03) |
| M29 | `catalogo.ts:174` | `carregados` ignora `arquivo` | ✅ Killed (CAT-10) |
| M30 | `busca.ts:26` | substring em vez de prefixo de palavra | ✅ Killed (BUS-04) |
| M31 | `busca.ts:40` | termos em OU | ✅ Killed (BUS-01, BUS-08) |
| M32 | `busca.ts:23` | mínimo de 1 caractere | ✅ Killed (BUS-07) |
| M33 | `busca.ts:42` | busca ignora o filtro | ✅ Killed (BUS-08) |
| M34 | `busca.ts:47` | busca ignora o limite | ✅ Killed (BUS-08) |
| M35 | `sincronizador.ts:67` | fallback de `ocioso` usa `window.setTimeout` | ✅ Killed (PUR-01) |

**Sensor depth**: expandido (35 mutações em todos os ramos do sincronizador, do catálogo e da busca).
**Result**: 32/35 mortos; 32/34 sem contar o equivalente M10. **M12 e M13 sobreviveram** → fix tasks.
Cada morte foi conferida contra um teste funcional, não contra os de tempo. Só M13 tinha caído exclusivamente por DES-02 e foi reclassificado.

**Sonda extra (defeito, não mutante)**: teste descartável no scratch. Sincroniza, chega 1 id novo (`novas(1)` emitido),
`confirmarNovas()`, chega outro id novo: `cat.novas() == 1`, mas os eventos são só `[{tipo:'atualizado'}]`.
Sem `novas(1)` → **reproduzido** (`AssertionError: expected [ { tipo: 'atualizado' } ] to deep equally contain { tipo: 'novas', n: 1 }`).

**Isolamento**: `git status --porcelain` da árvore real foi igual antes e depois (`diff` vazio). O worktree foi removido
(`git worktree remove --force` + remoção do diretório por caminho longo), e `git worktree list` não mostra mais o scratch.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / sem scope creep | ✅ Nada de UI, Tailwind, `.json.br` no dev nem IndexedDB. Extras (`alvo`, evento `atualizado`) estão documentados nas Assumptions |
| Surgical changes | ✅ Diff só em `apps/site/`, `.specs/features/BSV-35/` e `docs/specs/BSV-35.md` |
| Matches patterns | ✅ Nomes de domínio em português, TS strict, sem dependência de runtime (`package.json` só com `devDependencies`) |
| Spec-anchored outcome check | ✅ Valores exatos da spec (ids, eventos, contagens) |
| Per-layer coverage | ✅ 1:1 para CAT, BUS, SIN, POL, DIF; ⚠️ eventos `novas`/`completo` em cenários de borda sem teste (gaps 1 e 3) |
| Testes sem AC (unclaimed) | ✅ Os testes extras mapeiam edge cases ou Done-when ("título alterado", "antes de completo", "iniciar oculta/parar") |
| Guidelines | `CLAUDE.md`, `apps/site/CLAUDE.md` (Vitest para lógica). Regra 11 (evidência): `medicoes/` é gitignored e a saída não tem domínio |

---

## Fix Plans

### Fix 1 (Major): evento `novas(n)` não reemitido depois de `confirmarNovas()`

- **Root cause**: `sincronizador.ts:162-166` só emite quando `cat.novas() !== ultimasNovas`. Como `confirmarNovas()` mora
  no `Catalogo`, `ultimasNovas` continua com o valor antigo. Um lote novo com a mesma contagem (1 → confirma → 1) não gera
  evento. O mesmo vale para trocas de ids pendentes sem mudança de contagem.
- **Fix task**: emitir `novas` quando esta sincronização acrescentou ids pendentes. Por exemplo, comparar o conjunto ou
  contador de pendentes antes e depois de `aplicar`, ou expor no `Catalogo` um contador monotônico de pendências
  adicionadas. Manter: sem evento quando nada novo chegou.
- **Verify**: teste em `sincronizador.test.ts` com o cenário da sonda: `novas(1)`, `confirmarNovas()`, outro id novo, e o
  evento `{tipo:'novas', n:1}` aparece de novo. Mais o caso negativo: sincronizar sem mudança não emite `novas`.
- **Priority**: Major. É o sinal do toast "N novas ofertas" (MANIFEST §3.1 item 4, regra 8).

### Fix 2 (Minor): fixar o intervalo de 5 min (M12)

- **Fix task**: em POL-01/POL-03 usar o literal `5 * MIN` em vez de `INTERVALO_MS`. Por exemplo, `avancar(5*MIN - 1)`
  → 0 polls e `avancar(1)` → 1, ou `expect(INTERVALO_MS).toBe(300_000)`.
- **Done when**: M12 (`5 → 4 min`) morre.

### Fix 3 (Minor): `completo` só quando o catálogo está completo (M13)

- **Fix task**: teste com 404 persistente num chunk na primeira carga: `pronto` sim, `completo` **não**, `erro` sim. No
  ciclo seguinte, com o chunk servido, `completo` é emitido uma vez.
- **Done when**: M13 morre sem depender de `desempenho.test.ts`.

---

## Observações (não bloqueiam)

1. **M10** é mutante equivalente: o cancelamento do timer ao ocultar é redundante com a checagem em `tique`. Não pede ação.
2. **Premissa "versao igual não é ignorada"** contraria a letra da regra 4 ("`versao` ≤ à atual → ignora"). É justificada
   pela regra 5 (tentar de novo no próximo ciclo o `n` que falhou; M04 prova que o teste depende disso), e o efeito
   observável para manifest idêntico é o mesmo (0 chunks). **Dono confirmar** e, se aceitar, ajustar o texto da regra 4.
3. **POL-03 na fronteira**: o código usa `passou >= INTERVALO_MS` (`sincronizador.ts:195`) e a spec diz "mais de 5 min".
   A diferença é de 1 ms e não há teste da fronteira. Irrelevante na prática.
4. **Desempenho sob carga**: DES-01/DES-02 flutuam em máquina compartilhada (ver Gate). Se o runner de CI for fraco,
   esperar falhas intermitentes. Thresholds não alterados.
5. A medição real mostra `contrato 1.3.1` servido em produção (mesmo major de 1.3.3, aceito pela regra 4). É o worker
   em produção atrás do contrato do repo, não um problema deste ticket.

## Lições propostas (para o dono consolidar; lessons distillation está desligada no repo)

- Eventos derivados de estado ("N novas") não devem ser deduplicados por valor quando o estado pode ser zerado por outro
  objeto (`confirmarNovas`). Comparar o que esta operação acrescentou, não o último valor emitido.
- Teste de intervalo de tempo deve usar o literal da spec, não a constante do código. Senão a constante errada passa.
- No sensor, um mutante morto só por teste de tempo não conta como morto: rodar de novo sem os testes de desempenho.

---

## Summary

**Overall (rodada 1)**: ❌ Not Ready (3 fix tasks pequenas em T6). Ver "Rodada 2" abaixo: PASS

**Spec-anchored check**: 43/43 ACs com evidência e valor conferido; 0 gaps de precisão bloqueantes
**Sensor**: 35 mutações, 32 mortas, 2 vivas (M12, M13) + 1 equivalente (M10)
**Gate**: lint, check e build exit 0; test 59 passed, 0 failed (DES-01/02 flutuam sob carga)

**What works**: primeira carga, diff, versão e contrato, falha com nova tentativa, polling por visibilidade, lista, filtros,
ordens, novas no catálogo, busca por prefixo com acento, cupom e loja, orçamentos, pureza, bundle, `pnpm medir` com
0 chunks na 2ª passada.

**Next steps**: aplicar os Fix 1 a 3 em T6 e despachar o Verifier de novo (iteração 2 de no máximo 3).

---

## Rodada 2 (`d9061a0`)

### O que mudou (conferido no `git show d9061a0`)

- `apps/site/src/lib/dados/sincronizador.ts:147`: `const novasAntes = cat.novas()` é lido antes do diff. Em `:164`,
  `if (novas !== novasAntes) emitir({ tipo: 'novas', n: novas })`. O estado `ultimasNovas`, que ficava obsoleto, foi removido.
- `sincronizador.test.ts:354` (novo): `novas(1)` volta depois de `confirmarNovas()`, e sync sem mudança não emite `novas`
  (`expect(amb.eventos.filter((e) => e.tipo === 'novas')).toEqual([])`).
- `sincronizador.test.ts:372` (novo, SIN-01): 404 persistente na 1ª carga dá `pronto` e `erro` com `n`, sem `completo`
  e com `cat.completo` false. No ciclo seguinte, exatamente 1 `completo`. No terceiro, nenhum.
- `sincronizador.test.ts:421` (POL-01) e `:438` (POL-03): literal `5 * MIN`. POL-01 agora também exige 0 polls em `5*MIN - 1`
  e 1 poll em `5*MIN`. O import de `INTERVALO_MS` saiu do teste.
- Nenhuma asserção antiga foi removida ou afrouxada. O diff de testes só troca a constante pelo literal e acrescenta casos.
  `tasks.md` ganhou a T9.

### Gate (rodada 2)

- lint exit 0 · check exit 0 (`398 FILES 0 ERRORS 0 WARNINGS`) · build exit 0
- test (suíte completa): **59 passed, 2 failed de 61**. As 2 falhas são DES-01 (mediana 526 ms > 400) e DES-02 (p95
  20,9 ms > 20), com a máquina carregada. Todos os testes funcionais passam: 55/55 sem `desempenho.test.ts`.
- `desempenho.test.ts` isolado, 3 reruns seguidos: **6/6, 6/6, 6/6**.
- Julgamento (orientação do coordenador e precedente da rodada 1): os orçamentos passam em runs isolados e a medição real
  em produção dá aplicar 130–140 ms (17 mil cards) e busca p95 de 7 ms. **Não é motivo de FAIL**, mas é **risco para o dono**:
  em runner de CI lento ou compartilhado, DES-01/02 podem falhar de forma intermitente. Thresholds não alterados.
- Test count: 59 → 61 (+2), nenhum removido.

### Sonda e sensor (rodada 2)

Scratch novo: `git worktree add --detach <scratchpad>/w2 d9061a0` + `pnpm install --frozen-lockfile`. Baseline do
scratch: 55/55 sem `desempenho.test.ts`. Mutantes rodados **sem** `desempenho.test.ts`, para que nenhuma morte dependa de tempo.

- **Sonda da rodada 1** (`novas(1)` → `confirmarNovas()` → outro id novo → `novas(1)` de novo): **passa** (1/1). O defeito Major foi corrigido.

| # | File:line | Mutação | Resultado (teste que matou) |
| - | --------- | ------- | --------------------------- |
| M12 | `sincronizador.ts:8` | `INTERVALO_MS` 5 → 4 min | ✅ Killed (POL-01 `:421`, POL-03 `:438`) |
| M13 | `sincronizador.ts:158` | `completo` emitido sem `cat.completo` | ✅ Killed (SIN-01 404 persistente `:372`) |
| N1 | `sincronizador.ts:164` | `novas` nunca emitido | ✅ Killed (`:354` e "novas: chunk com ids novos…") |
| N2 | `sincronizador.ts:147` | compara com valor fixo 0 (emite em todo sync com pendentes) | ✅ Killed (`:354`, "sync sem mudança não emite") |
| N3 | `sincronizador.ts:164` | `novas` emitido sempre | ✅ Killed (`:354`, SIN-01) |
| N4 | `sincronizador.ts:164` | payload `n: novas - novasAntes` (delta) em vez do total | ⚠️ **Survived**: os testes só exercitam transições a partir de 0, onde delta = total |

**Resultado da rodada 2**: 5/6 mortos. Somando as duas rodadas: 38 mutações em código de produção, 36 mortas,
1 equivalente (M10) e 1 resíduo de precisão (N4).

**Isolamento**: `git status --porcelain` da árvore real igual antes e depois (`diff` vazio; só `?? validation.md`).
Worktree `w2` removido (`git worktree remove --force` + remoção por caminho longo), sem entrada em `git worktree list`.

### Resíduo N4: gap de precisão da spec (não bloqueia)

A spec do ticket lista o evento `novas(n)` sem definir `n`. A leitura natural, alinhada ao toast "N novas ofertas"
(MANIFEST §3.1 item 4) e a `Catalogo.novas()`, é `n` = total pendente, que é o que o código faz (`:164`). Nenhum teste
pega a troca por delta: com 1 pendente não confirmada e chegando outra, o evento deveria trazer `n: 2`, e o mutante
traz `n: 1`. **Sugestão ao dono** (opcional, 1 asserção): no teste `:354`, ou num novo, publicar 2 ids em ciclos
seguidos sem confirmar e exigir `{tipo:'novas', n: 2}`. Também sem teste: pendentes que trocam sem mudar a contagem
(1 expurgado + 1 novo no mesmo ciclo) não geram evento. O número exibido continua correto; só não há um novo "ping".

### Rastreabilidade

Gaps 1–3 da rodada 1: **fechados**. ACs: 43/43 com evidência (SIN-01 agora também cobre a falha na 1ª carga; POL-01 e
POL-03 fixam 5 min). Observações 2–5 da rodada 1 continuam valendo para o dono (premissa `versao` igual, fronteira
`>=` do POL-03, desempenho sob carga, produção em `contrato 1.3.1`).

**Overall (rodada 2)**: ✅ PASS. Spec-anchored 43/43; gate funcional verde (DES isolado 3/3); sensor 36/38 com 1
equivalente e 1 resíduo de precisão documentado.
