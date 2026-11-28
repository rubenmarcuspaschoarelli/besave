# BSV-66 Validation

## Validation: PASS (ciclo 2)

**Date**: 2026-11-25
**Spec**: `docs/specs/BSV-66.md` (fonte da verdade) e `.specs/features/BSV-66/spec.md` (EARS do autor)
**Diff range**: `af6cd54..1a7c1ac` (ciclo 1: `af6cd54..972e27f`; ciclo 2: `972e27f..1a7c1ac`, só testes)
**Verifier**: Verifier sub-agente independente (autor ≠ verificador)

**Ciclo 2 (veredito final, PASS):** o commit `1a7c1ac` só acrescenta testes (nenhuma linha de
`tools/capture-web-apoio/` mudou) e mata os 4 sobreviventes do ciclo 1. Os 7 mutantes novos morreram
ou são equivalentes. Gates verdes. A execução real do dono continua bloqueando o merge.

Ciclo 1 (histórico), por que deu FAIL: todos os itens do "Critério de aceite" têm teste com o valor da spec e os gates estão verdes,
mas 4 mutantes não equivalentes sobreviveram (35 injetados, 31 mortos). Três deles quebram regras escritas
nas Saídas 2, 6 e 7, e um quebra uma interpretação do autor. Nenhum defeito de código foi encontrado: as
lacunas são de teste e se fecham com 4 testes pequenos (Fix 1–4). Execução real do dono: ver "Bloqueia o
merge".

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 Extratores | ✅ Done | - |
| T2 URL limpa e cupons | ✅ Done | - |
| T3 HTTP, banco e estado | ✅ Done | - |
| T4 Rodada | ✅ Done | lacunas do ciclo 1 (Fix 2–4) fechadas em `1a7c1ac` |
| T5 CLI, config e log | ✅ Done | - |
| T6 Operação e CI | ✅ Done | - |

---

## Spec-Anchored Acceptance Criteria (docs/specs/BSV-66.md, "Critério de aceite")

| Critério | Resultado definido pela spec | Evidência (teste `file:line`, código `file:line`) | Resultado |
| -------- | ---------------------------- | ------------------------------------------------- | --------- |
| Extração Pelando: Astro decodificado, quantidade e campos por igualdade | 4 válidas com `id`, `title`, `price`, `NULL` de "de", `sourceUrl` (nunca `redirectUrl`), `createdAt` UTC | `tools/tests/test_web_extrair.py:178` (`validas == [...]` inteiro); `:208` (`redirectUrl` ignorada, `hideInFeed`); código `tools/capture-web-apoio/webapoio/extrair.py:54-98` | ✅ PASS |
| Pelando `kind: coupon` e `status: expired` descartados | descartados | `tools/tests/test_web_extrair.py:198` (`{...: 'status', ...: 'tipo'}`); `extrair.py:82-87` | ✅ PASS |
| Promobit: válidas por igualdade, `COUPON`/`STARTING_AT` descartados | preço só em `NORMAL`; "de" `NULL` se ≤ 0,01 | `tools/tests/test_web_extrair.py:215`, `:232`, `:243` (`preco_de is None` com 0,01), `:235-242` status; `extrair.py:123-149` | ✅ PASS (ver Fix 1: "de" igual a "por" sem teste) |
| Pechinchou: válidas por igualdade, `CLOSED` descartada, id+slug | `CLOSED` descarta; `is_any_text_price` descarta | `tools/tests/test_web_extrair.py:248`, `:273`, `:282`, `:290`; `extrair.py:152-171` | ✅ PASS |
| Sem a ilha / sem `__NEXT_DATA__` → erro de estrutura, sem exceção | `erro` preenchido, sem exceção | `tools/tests/test_web_extrair.py:304-307` (9 casos), `:310-316` (todo item incompleto), `:319-324` (parte incompleta não é erro); `extrair.py:32-45`, `:106-120` | ✅ PASS |
| Redirect do Promobit: URL lida de `promobit_redirect.html`; sem URL → descarte | URL de `l = '...'` ou `<a href>` do `<p>`; sem URL = descarte | `tools/tests/test_web_extrair.py:333`, `:338`, `:343`; `tools/tests/test_web_filtros.py:103` (`sem_url`); código `extrair.py:176-188`, `rodada.py:215-225` | ✅ PASS |
| URL limpa: tabela (Amazon `tag=`, `/gp/product/`, ML `#`/query, Shopee 3 formatos, domínio fora, > 350) com saída inteira | tripla `(loja, url, motivo)` inteira | `tools/tests/test_web_url.py:9-50` (20 casos, `limpar(url) == esperado`), `:53-56` (350 entra); código `url.py:44-66` | ✅ PASS |
| Encurtador: `Location` simulado 1 e 3 saltos; sem `Location` → descarte | uma requisição sem seguir por salto, até 3 | `tools/tests/test_web_url.py:79`, `:87`, `:95` (4 saltos não), `:102`; `tools/tests/test_web_filtros.py:106-114` (`encurtador_nao_resolvido`, `seguir=False`); `tools/tests/test_web_http.py:221-247`; código `url.py:74-92`, `http.py:322-337`, `:389-394` | ✅ PASS |
| Idade com relógio fixo: 23h59 entra, 24h01 sai, futuro > 10 min sai | entra / `antiga` / `futura` | `tools/tests/test_web_filtros.py:60-69` (23h59, 24h01, +9, +11 min); código `rodada.py:209-212` | ✅ PASS |
| Já vista: cada um dos 4 casos pula | estado local / mesma rodada / chave no banco / mesmo título | `tools/tests/test_web_filtros.py:119` (local), `:125` (rodada), `:136-141` (fila e `OFERTA`), `:144` (título), `:192-206` (mesma loja, ±1%); SQL inteiro `tools/tests/test_web_banco.py:114-132`; código `rodada.py:236-249`, `banco.py:29-42`, `:144-171` | ✅ PASS |
| Preço menor que a ativa entra | 12,00 ativa → entra; 10,50 e 9,00 → `vista_oferta` | `tools/tests/test_web_filtros.py:180-189`; `banco.py:34` (`VL_PRECO_POR <= :preco`) | ✅ PASS |
| Estado local de 8 dias é esquecido | 8 dias sai, 6 dias fica | `tools/tests/test_web_filtros.py:209-217`; `estado.py:13`, `:26-35` | ✅ PASS |
| Cota `por_menu` e `teto_rodada` com rodízio, ordem inteira; teto = sem requisição a mais | ordem das gravações inteira; nenhuma URL depois do teto | `tools/tests/test_web_rodada.py:276-289` (7 gravações e lista de URLs inteiras), `:292-298`, `:301-306` (30 → 10/10/10), `:309-313`; código `rodada.py:116-163` | ✅ PASS |
| `INSERT` comparado inteiro (SQL e binds) | SQL e binds iguais aos da Saída 6 | `tools/tests/test_web_banco.py:101-111` (`sql == INSERT_ESPERADO`, `binds == LINHA`, 1 commit); código `banco.py:20-27`, `:173-188` | ✅ PASS (ver Fix 2: corte do título em 350 sem teste) |
| Cupons §4.3: `'25 Full'` cai, repetido sai, 6 → 5 | `[]`, sem repetido, 5 | `tools/tests/test_web_url.py:132-140`; fim a fim `tools/tests/test_web_rodada.py:385-401` (3255106 com `'25 Full'` → `None, None`); código `cupons.py:8-36`, `rodada.py:254-263` | ✅ PASS |
| 403 → site para, outros seguem, uma mensagem | `Captura web: Promobit bloqueado (HTTP 403). Gravadas 4 oferta(s).` | `tools/tests/test_web_rodada.py:318-324`, `:327-332` (429 no redirect), `:484-491` (uma chamada ao avisador, texto inteiro); `tools/tests/test_web_http.py:205-211`; código `http.py:366-367`, `rodada.py:157-162` | ✅ PASS |
| Estrutura mudou → mensagem; tudo ok → nenhuma; textos inteiros | `... estrutura mudou em /mais-quentes; Pechinchou sem resposta. Gravadas 4 oferta(s).`; `None` | `tools/tests/test_web_rodada.py:335-341`, `:344-350`, `:353-363` (banco fora); código `rodada.py:80-90` | ✅ PASS |
| `--simular` não grava nem chama `INSERT`; segunda instância → 2 | sem `gravar`, sem `vistas.json`; código 2 | `tools/tests/test_web_rodada.py:445-452`, `:455-460`, `:494-501`; código `cli.py:56-61`, `:91-103`, `rodada.py:265-269`, `estado.py:50-75` | ✅ PASS |
| `pytest` + `ruff` do job `tools` verdes com `capture-web-apoio/` no `ruff` e no `conftest.py` | verde | `.github/workflows/ci.yml:179` (`ruff check vps/ tests/ capture-web-apoio/`); `tools/tests/conftest.py:11-13`; execução abaixo | ✅ PASS |

**Status**: ✅ todos os critérios de aceite cobertos com o valor da spec. Lacunas de discriminação em
regras das Saídas que o critério não lista uma a uma (Fix 1–4).

### Regras da spec

| Regra | Evidência | Resultado |
| ----- | --------- | --------- |
| 1. Sem navegador, sem dependência nova | `tools/capture-web-apoio/requirements.txt:2` (`oracledb==4.0.2`, igual a `capture-store-pages/requirements.txt:3`); só stdlib nos imports; `tools/tests/test_web_config.py:108-113` | ✅ |
| 2. Sem `/api/*`, só páginas das tabelas | `config.py:70-77` (menu fora do host ou em `/api/` é ignorado); `tools/tests/test_web_config.py:62`; `tools/tests/test_web_rodada.py:413-419` | ✅ |
| 3. Não importa `capture-store-pages` / `capture-chat-groups` | `url.py:95-115` reimplementa `chave_loja` (regexes iguais a `capture-store-pages/core/duplicidade.py:31-33`); `tools/tests/test_web_config.py:108` | ✅ |
| 4. Sem URL de afiliado de terceiro no banco ou no log | `oferta.py:21` (`url` com `repr=False`), logs só com `limpa` ou `host` (`rodada.py:233`, `:266`, `:275`); `tools/tests/test_web_rodada.py:407-410`, `:422-426` | ✅ |
| 5. Testes sem rede nem banco reais | `tools/tests/web_falso.py:89-139` (urllib e banco simulados); `banco.py:70` (import tardio de `oracledb`) | ✅ |
| 6. Mensagem e SQL comparados inteiros | `tools/tests/test_web_banco.py:107`, `:120`, `:131`; `tools/tests/test_web_rodada.py:324`, `:340`, `:490`; `tools/tests/test_web_config.py:96-105` | ✅ |

### Interpretações do autor (tabela "Assumptions")

| Interpretação | Parecer |
| ------------- | ------- |
| `COUPON`/`STARTING_AT` e `is_any_text_price` descartados já na extração | Razoável: a tabela da Saída 2 os põe como regra do site e o critério os põe no teste de extração. |
| Rodízio = um turno por site, menu seguinte ao da última gravação, lista baixada só quando o turno chega | Razoável e coerente com "teto sem requisição a mais" e "cerca de 10 por site" (`tools/tests/test_web_rodada.py:301`). |
| Promobit: estado local antes do redirect | Razoável: muda só a ordem e poupa requisição. Coberto em `tools/tests/test_web_rodada.py:473`. |
| O que entra em `vistas.json` (gravadas + descartes permanentes; transitórios fora) | Razoável ("visto" na spec é amplo), mas **sem teste** da parte "transitórios fora" (Fix 4). Efeito colateral aceitável: `vista_oferta`/`mesmo_titulo` também ficam 7 dias no estado local. |
| Chave de produto = trecho do `LIKE` de `chave_loja` (item da Shopee, dígitos do MLB, ASIN) | Razoável: a spec manda usar a mesma regra; `{shop}.{item}` literal não casaria `/product/{shop}/{item}`. |
| Já vista no banco numa consulta só (`UNION ALL`) | Razoável ("uma por candidata"). O SQL contra o Oracle real é verificado em Real 1–4. |
| `sem resposta` = timeout/5xx após repetição ou outro código; menu falha, site segue | Razoável: a spec só manda parar o site em 403/429. |
| Banco fora + problema de site → só a mensagem do banco | Razoável: "uma mensagem por rodada" e a spec dá um formato próprio para o banco. |
| `--simular` sem banco → WARN e segue sem as consultas | Razoável: a spec não define; não grava nada. |
| Trava com lock do SO (`msvcrt`/`fcntl`) | Razoável; melhor que um arquivo-sentinela. |
| Menu fora do host ou em `/api/` ignorado com WARN | Razoável (regra 2). |
| `agendar.ps1` aceita `--remover` e `-Remover` | Razoável. |

Nenhuma interpretação foi classificada como SPEC_DEVIATION.

---

## Ciclo 2: reverificação de `1a7c1ac`

Testes novos, cada um ligado a uma lacuna do ciclo 1:
- Fix 1: `tools/tests/test_web_extrair.py:200-209` (`test_preco_de_igual_ao_por_vira_none`). Pechinchou e Promobit com "de" == "por" → `None`; 10,01 > 10 → `Decimal('10.01')`.
- Fix 2: `tools/tests/test_web_filtros.py:226-229` (`test_titulo_com_trim_e_corte_em_350_no_insert`). `'  ' + 'x'*400` → `'x'*350`.
- Fix 3: `tools/tests/test_web_rodada.py:296-301` (`test_resumo_lidas_validas_gravadas_e_descartes_da_fixture`). Linha inteira de `linhas_resumo` com `lidas=6 validas=4 gravadas=3`.
- Fix 4: `tools/tests/test_web_filtros.py:232-241` (futura e encurtador fora; antiga, loja_fora e gravada dentro) e `:243-247` (Promobit `sem_url` fora).

Sensor do ciclo 2: worktree descartável em `1a7c1ac`, só `tests/test_web_*.py`, removido depois.

| # | File:line | Mutação | Morto? |
| - | --------- | ------- | ------ |
| M9 | `webapoio/extrair.py:124` | "de" `<= por` → `< por` | ✅ Morto (`test_preco_de_igual_ao_por_vira_none`) |
| M12 | `webapoio/rodada.py:32-34` | os 3 transitórios em `PERMANENTES` | ✅ Morto |
| M12a | `webapoio/rodada.py:34` | só `futura` em `PERMANENTES` | ✅ Morto |
| M12b | `webapoio/rodada.py:34` | só `encurtador_nao_resolvido` | ✅ Morto |
| M12c | `webapoio/rodada.py:34` | só `sem_url` | ✅ Morto (`test_promobit_sem_url_nao_entra_no_estado_local`) |
| M20 | `webapoio/rodada.py:257` | sem corte em 350 | ✅ Morto |
| M21 | `webapoio/rodada.py:186` | inválidas contadas como `validas` | ✅ Morto |
| N1 | `webapoio/rodada.py:257` | sem `strip()` antes do corte | ➖ Equivalente: o extrator já faz o trim (`webapoio/extrair.py:24-25`) |
| N2 | `webapoio/rodada.py:32` | `antiga` sai de `PERMANENTES` | ✅ Morto |
| N3 | `webapoio/rodada.py:35` | `tipo` sai de `INVALIDAS` | ✅ Morto (resumo) |
| N4 | `webapoio/extrair.py:124` | `de <= 0,01` → `de < 0,01` | ➖ Equivalente: com "por" ≥ 0,01, "de" = 0,01 já cai em `de <= por`; "por" ausente só ocorre em oferta já inválida |

**Placar do ciclo 2**: 9/9 mortos entre os não equivalentes; 2 equivalentes. Total dos dois ciclos: 40 não
equivalentes, todos mortos.

Gates do ciclo 2 (árvore real em `1a7c1ac`):
- `cd tools && python -m pytest -q tests/test_web_*.py` → **169 passed** (164 + 5 novos).
- `cd tools && python -m ruff check vps/ tests/ capture-web-apoio/` → **All checks passed!**
- Suíte inteira não foi rodada de novo: `1a7c1ac` só acrescenta testes `test_web_*`. No ciclo 1 a suíte deu 948 passed e 44 skipped.
- `git status --porcelain` da árvore real: só `?? .specs/features/BSV-66/validation.md`.

---

## Discrimination Sensor (ciclo 1)

Feito num worktree descartável (`git worktree add --detach <scratchpad>/mut66 972e27f`), um mutante por vez,
rodando só `tests/test_web_*.py`. Worktree removido depois; `git status --porcelain` da árvore real vazio
antes e depois.

| # | File:line | Mutação | Morto? |
| - | --------- | ------- | ------ |
| M1 | `webapoio/rodada.py:209` | limite de idade vira 23 h | ✅ Morto (`test_idade[-1439]`) |
| M2 | `webapoio/rodada.py:211` | futuro tolerado 20 min | ✅ Morto (`test_idade[11]`) |
| M3 | `webapoio/rodada.py:145` | `por_menu` `>=` → `>` | ✅ Morto |
| M4 | `webapoio/rodada.py:154` | ponteiro do rodízio não avança | ✅ Morto |
| M5 | `webapoio/rodada.py:161` | 403 não para o site | ✅ Morto |
| M6 | `webapoio/http.py:366` | 429 deixa de ser bloqueio | ✅ Morto |
| M7 | `webapoio/http.py:360` | 2 repetições em vez de 1 | ✅ Morto |
| M8 | `webapoio/extrair.py:14` | `FINISHED` aceito no Promobit | ✅ Morto |
| M9 | `webapoio/extrair.py:124` | preço "de" `<= por` → `< por` (igual passa a valer) | ❌ Sobreviveu → Fix 1 |
| M10 | `webapoio/url.py:16` | formato Shopee `-i.{shop}.{item}` quebrado | ✅ Morto |
| M11 | `webapoio/url.py:12` | 4 saltos de encurtador | ✅ Morto |
| M12 | `webapoio/rodada.py:32-34` | `futura`, `sem_url`, `encurtador_nao_resolvido` entram no estado local | ❌ Sobreviveu → Fix 4 |
| M13 | `webapoio/cupons.py:9` | até 6 cupons | ✅ Morto |
| M14 | `webapoio/banco.py:23` | `'CAPTURA WEB'` → `'CAPTURA_WEB'` | ✅ Morto |
| M15 | `webapoio/rodada.py:90` | `oferta(s)` → `ofertas` | ✅ Morto |
| M16 | `webapoio/cli.py:89` | simular grava o estado local | ✅ Morto |
| M17 | `webapoio/cli.py:59` | trava ocupada sai com 0 | ✅ Morto |
| M18 | `webapoio/rodada.py:265` | simular chama `gravar` | ✅ Morto |
| M19 | `webapoio/rodada.py:263` | `DS_CUPOM_LOJA` sempre preenchido | ✅ Morto |
| M20 | `webapoio/rodada.py:257` | título sem corte em 350 | ❌ Sobreviveu → Fix 2 |
| M21 | `webapoio/rodada.py:186` | resumo conta inválidas como `validas` | ❌ Sobreviveu → Fix 3 |
| M22 | `webapoio/url.py:56` | ML mantém a query | ✅ Morto |
| M23 | `webapoio/rodada.py:218` | Promobit sem o estado local antes do redirect | ✅ Morto |
| M24 | `webapoio/banco.py:16` | título com tolerância de 2% | ✅ Morto |
| M25 | `webapoio/estado.py:13` | estado local de 9 dias | ✅ Morto |
| M26 | `webapoio/rodada.py:122` | sem o teto dentro do turno | ✅ Morto |
| M27 | `webapoio/url.py:14` | Amazon sem `/gp/aw/d/` | ✅ Morto |
| M28 | `webapoio/extrair.py:84` | Pelando aceita `kind != promotion` | ✅ Morto |
| M29 | `webapoio/extrair.py:43` | um item incompleto já é erro de estrutura | ✅ Morto |
| M30 | `webapoio/rodada.py:216` | Promobit sem filtro por `storeDomain` | ✅ Morto |
| M31 | `webapoio/banco.py:130` | sem reconexão | ✅ Morto |
| M32 | `webapoio/http.py:352` | pausa só antes da 2ª requisição | ✅ Morto |
| M33 | `webapoio/rodada.py:251` | preço 0 aceito | ✅ Morto |
| M34 | `webapoio/extrair.py:182` | redirect só pelo `l = '...'` | ✅ Morto |
| M35 | `webapoio/rodada.py:240` | sem "mesma rodada" | ✅ Morto |

**Sensor depth**: reforçado (35 mutantes manuais; não há mutmut no projeto)
**Placar**: 31/35 mortos; 4 sobreviventes não equivalentes.

---

## Code Quality

| Princípio | Status |
| --------- | ------ |
| Código mínimo / sem escopo extra | ✅ (só `tools/capture-web-apoio/`, `tools/tests/`, `conftest.py` e uma linha do `ci.yml`, como a spec autoriza) |
| Mudanças cirúrgicas | ✅ |
| Segue os padrões dos robôs (lista de erros de conexão, formato do alerta, `oracledb` 4.0.2) | ✅ |
| Valores testados batem com a spec | ✅ nos critérios de aceite; ⚠️ Fix 1–3 em regras das Saídas |
| Todo teste mapeia uma Saída ou critério | ✅ |
| Diretrizes seguidas: `CLAUDE.md` (regras 6, 7, 11), `docs/WORKFLOW-AGENTES.md` lição 14 | ✅ |

---

## Gate Check

- `cd tools && python -m pytest -q tests/test_web_*.py` → **164 passed**, 0 failed (3,7 s).
- `cd tools && python -m ruff check vps/ tests/ capture-web-apoio/` → **All checks passed!**
- `cd tools && python -m pytest -q` (suite inteira do job `tools`): **948 passed, 44 skipped**, 0 failed (4 min 43 s).
- Pulado no CI Linux: `tools/tests/test_web_config.py:116` (`test_agendar_mostra_a_tarefa`, só Windows com PowerShell); rodou e passou aqui (Windows). A montagem do `Register-ScheduledTask` também é conferida por texto em `tools/tests/test_web_config.py:141`.
- Contagem de testes: +164 novos (`test_web_*.py`); nenhum teste existente removido ou enfraquecido (diff só acrescenta `WEB` ao `conftest.py`).

---

## Fix Plans (ciclo 1; todos fechados em `1a7c1ac`)

### Fix 1: preço "de" igual ao preço "por" (Saída 2, "≤ preço por") — Minor
- **Causa**: nenhum teste usa `old_price == price` nem `offerOldPrice == offerPrice`.
- **Tarefa**: em `tools/tests/test_web_extrair.py`, caso Pechinchou `price='10.00', old_price='10.00'` e Promobit `offerPrice=10, offerOldPrice=10` → `preco_de is None`.

### Fix 2: título ≤ 350 no `INSERT` (Saída 6) — Minor
- **Causa**: nenhuma oferta de teste tem título > 350; `rodada.py:257` pode perder o corte sem teste falhar (no banco real viraria `ORA-12899` → `erro_insert`).
- **Tarefa**: em `tools/tests/test_web_filtros.py`, deal Pelando com `title='  ' + 'x' * 400` → `banco.gravadas[0]['titulo'] == 'x' * 350`.

### Fix 3: contagem `validas` do resumo (Saída 7) — Minor
- **Causa**: nenhum teste lê `ResumoMenu.validas` nem `linhas_resumo`.
- **Tarefa**: em `tools/tests/test_web_rodada.py`, sobre a fixture real do Pelando, conferir `res.resumo[('Pelando', '/recentes')]` com `lidas=6`, `validas=4` e a linha de `linhas_resumo(res)` inteira.

### Fix 4: descartes transitórios fora do estado local (interpretação do autor) — Minor
- **Causa**: o teste da segunda rodada só cobre gravadas; `sem_url`, `encurtador_nao_resolvido` e `futura` poderiam entrar em `vistas.json` (e bloquear a oferta por 7 dias) sem teste falhar.
- **Tarefa**: em `tools/tests/test_web_rodada.py`, rodada com uma oferta `futura`, um redirect Promobit sem URL e um encurtador sem `Location` → nenhuma das três chaves em `rodada.novas_vistas`; e uma `antiga`/`loja_fora` → presente.

---

## Bloqueia o merge (execução real do dono; não são falhas desta verificação)

Spec, "Real" 1–6, no PC do dono, com o código da branch da PR:
1. `sql/bsv-66-usuario.sql` aplicado; `python main.py --simular` → resumo dos três sites com ofertas válidas e nenhuma gravação (confere também o `UNION ALL` da consulta de já vista no Oracle real).
2. `python main.py` → até 30 linhas com `DS_TIPO_ORIGEM='CAPTURA WEB'`; nenhuma `DS_URL_ORIGEM` com `tag=`, `utm_`, `matt_` ou encurtador.
3. O robô das lojas processa essas linhas como as outras.
4. Segunda rodada logo depois → as mesmas puladas como já vistas.
5. `agendar.ps1` cria a tarefa com 08:00, 12:00 e 17:00; uma execução pela tarefa grava o log.
6. Evidência redigida (regra 11).

---

## Requirement Traceability Update

| Requirement | Status |
| ----------- | ------ |
| LER-01, LER-02, LER-03, LER-04, LER-05 | ✅ Verified (LER-03: Fix 1) |
| URL-01, URL-02, URL-03 | ✅ Verified |
| FIL-01, FIL-02 | ✅ Verified |
| GRV-01 | ✅ Verified (ciclo 2) |
| COT-01, GRV-02, AVI-01, ROD-01 | ✅ Verified (AVI-01/resumo: Fix 3) |
| OPS-01, OPS-02, CFG-01 | ✅ Verified (OPS-01 completo só em Real 5) |

---

## Summary

**Overall**: ✅ Pronto do lado do código e dos testes; o merge espera a execução real do dono (Real 1–6).

**Spec-anchored check**: 19/19 critérios de aceite com o valor da spec; 6/6 regras.
**Sensor**: ciclo 1 com 31/35 mortos; ciclo 2 com os 4 sobreviventes mortos, mais 5 novos (3 mortos, 2 equivalentes).
**Gate**: 169 passed (`test_web_*.py`); ruff limpo.

**Próximo passo**: execução real do dono (Real 1–6) com a branch da PR, antes do merge.
