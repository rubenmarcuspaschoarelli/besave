# BSV-63 — Validação

## Validation: BSV-63 - PASS

**Result**: PASS

Reteste do ciclo 6, faixa `f1b0f5e..431df65` (`9a075c1` fix + `431df65` test). `431df65` muda em produção só a leitura
da legenda (`LEITURA_MS = 2_000`, `cw:42`, usado em `cw:185`, `cw:346`, `cw:360`); o resto é teste e simulador. As duas
lacunas bloqueantes da 1ª rodada estão fechadas: o re-render agora é disparado do lado Python, fora do mundo JS da
página, e **A1 e A6 morrem pelo comportamento** (a espera de 30 s do `nth(i)`), sem marca interna. **Toda a lista
mínima do dono morre.** Sobrevivem só A14 (sem efeito observável) e os 3 mutantes do `LEITURA_MS` (sem teste; baixa).
Execução real na inst2 continua bloqueando o merge (§C6R.5).

- **Quem verificou:** Verifier independente (sub-agente), autor ≠ verificador. Data 2026-11-18.
- **Árvore real:** no início do reteste `git status --porcelain` = ` M .specs/features/BSV-63/validation.md` (este
  arquivo, da 1ª rodada) e `?? docs/canal_real.html`. Cópia `git archive 431df65 tools` no scratchpad, removida no fim;
  nenhum `git stash`; `docs/canal_real.html` intocado; único arquivo editado: este. `T` = `tools/tests/test_pub_canal_web.py`,
  `SIM` = `tools/tests/fixtures/whatsapp_simulador.js`, `cw` = `.../pub/canal_web.py` (linhas de `431df65`).

### C6R.1 O novo modelo de re-render é honesto? Sim, com um limite

`T:568-606`: `_ListaVirtualizada` embrulha a `page` e devolve `_LocatorQueRerenderiza` só para `locator(SEL_BALAO)`;
logo **depois** de cada `count()` ou `evaluate_all` (`T:598-606`), `_re_render` (`T:580-584`) tira 3 balões FAKE do DOM
por `page.evaluate`, no máximo 2 vezes. O balão novo nasce " Pendente " por 1,5 s (`SIM:162-169`, `pendenteMs`), então a
1ª varredura da confirmação percorre a lista até o fim — como na inst2, onde os índices sumidos foram `nth(6)`/`nth(7)`.
O teste (`T:609-625`) passa por `enviar()` (1º re-render, no `_ids_baloes`) e pela confirmação (2º) e exige `True` em
< 5 s, `remocoes == 2`, 3 FAKE restantes e nenhum WARN. É o mesmo modelo que o Verifier usou na 1ª rodada (§C6.3), agora
no repositório: independe do mundo JS em que o Playwright lê, e quem lê em dois passos acha índice sumido e espera 30 s.
Medido (3 execuções isoladas): 2,19 / 2,16 / 2,18 s contra o limite de 5 s.

Limite: o gatilho casa pela string exata `SEL_BALAO` em `page.locator`. Uma leitura por outro seletor ou por
`get_by_test_id` escaparia do re-render. Aceitável: o seletor é a constante do módulo.

### C6R.2 Sensor de discriminação (cópia `431df65`; `timeout 300` em cada; `T -k "confirmacao or balao_confirmado"`, os `B` em `T` inteiro)

| id | mutante | resultado | morto por |
|---|---|---|---|
| A1 | `_balao_confirmado` volta ao `count()` + `nth(i)` | **morto (comportamento)** | `T:618`: `False` depois de 32 s (o `get_attribute` de índice sumido esperou 30 s) |
| A2 | re-levanta na 1ª exceção | morto | `T:639`, `T:660` |
| A3 | loga a cada sondagem | morto | `T:660` |
| A4 | engole navegador morto | morto | `T:679` |
| A5 | `False` na 1ª exceção | morto | `T:639`, `T:660` |
| A6 | `_ids_baloes` com `count()` + `nth(i)` | **morto (comportamento)** | `T:617`: `TimeoutError: Locator.get_attribute: Timeout 30000ms` em `enviar()` |
| A7 | status ignorado | morto | `T:628` |
| A8 | `tid` antigo aceito | morto | `T:628` |
| A9 | sem o log do aviso | morto | `T:639`, `T:660` |
| A10 | desiste na 2ª exceção | morto | `T:660` |
| A12 | legenda sempre `null` | morto | `T:609`, `T:639` |
| A14 | híbrido: tids do `evaluate_all`, legenda/status por `nth(i)` com índice velho e guarda `count()==0` | sobrevive — **sem efeito observável** | índice sumido → `count()==0` sem espera e a sondagem seguinte acha; confirmação falsa é impossível, porque só o balão novo tem a chave. No máximo atrasa uma sondagem |
| A14b | o mesmo híbrido sem a guarda (`inner_text` com auto-wait) | morto | `T:618` (`False` em 32 s) |
| B1 | `LEITURA_MS = 30_000` | sobrevive | nenhum teste da leitura com 2 s |
| B2 | `texto_do_editor` sem `timeout` | sobrevive | idem |
| B3 | colar sem `timeout` | sobrevive | idem |

**12 de 16 mortos**: A1–A10, A12 e A14b. Sobrevivem A14 (sem efeito observável) e B1–B3 (sem teste). A11 da 1ª rodada
(equivalente) não foi reaplicado. Toda a lista mínima do dono morre (A1, A2, A3, A4, A5, A6, A7, A8).

### C6R.3 Gates (lição 21) — cópia de `431df65`, sem carga minha em paralelo

| gate | resultado |
|---|---|
| `cd tools && python -m pytest -q` (Windows) | **821 passed, 7 skipped** (os 7 POSIX antigos), 312 s |
| `ruff check vps/ tests/ publish-whatsapp-channel/` | All checks passed! |
| `shellcheck vps/*.sh` | sem saída (ok) |
| WSL (os mesmos 8 arquivos da 1ª rodada, `--basetemp=/tmp/bsv63c6r`, apagado) | **182 passed, 0 skipped** |

### C6R.4 Lacunas restantes (nenhuma bloqueia)

1. Baixa: B1–B3 sobrevivem. O `timeout=LEITURA_MS` da legenda (`cw:346`, `cw:360`) e do título (`cw:185`) não tem
   teste. Efeito: caixa que some entre `_visivel` e `evaluate` espera 30 s, antes do clique (fica P, sem D). Correção
   por leitura confere o item 4.
2. Baixa: A14 sobrevive sem efeito observável (§C6R.2).
3. Baixa: o gatilho do re-render casa pela string `SEL_BALAO` (§C6R.1).
4. Por desenho (o dono aceitou): D é gravado antes de `enviar()`, então erro no `_ids_baloes` vira D.

### C6R.5 Pendência do dono (bloqueia o merge)

Novo teste real na inst2 com 20 posts ou mais. No log, nenhum D deve vir de "erro depois do clique", e
"[confirmar] WARN sondagem falhou" deve aparecer no máximo uma vez por post.

---

## Histórico: ciclo 6, 1ª rodada (resultado: reprovado; corrigido no reteste acima)

Ciclo 6 (3º achado do teste real, 17/11, `f1b0f5e`: 2 de 27 posts D por `TimeoutError` em `nth(i).get_attribute`
durante a confirmação). Faixa `f1b0f5e..9a075c1` (um commit, `9a075c1`). **O código de produção atende aos itens 1–4**
(por leitura e por um teste honesto do Verifier, §C6.3). **Reprova pelos testes**: o teste do re-render não reproduz o
achado — o gatilho do simulador só dispara quando a leitura passa pelo `Element.prototype.getAttribute` do mundo
principal, o que só o `evaluate_all` novo faz; com o código antigo (`count()` + `nth(i)`) a lista nunca re-renderiza e a
confirmação dá `True` em 2,5 s. O mutante "volta ao nth(i)" morre **só pela sentinela** `__reRenderizou` (espelha a
implementação, regra 1), e o mutante "`_ids_baloes` com nth(i)", da lista mínima do dono, **sobrevive**. Correção só de
teste (§C6.5). Execução real na inst2 continua bloqueando o merge (§C6.7).

- **Quem verificou:** Verifier independente (sub-agente), autor ≠ verificador. Data 2026-11-18.
- **Árvore real:** no início `git status --porcelain` = `?? docs/canal_real.html`; no fim, mais este arquivo. Mutantes,
  gates e WSL numa cópia `git archive 9a075c1 tools` no scratchpad (sem `docs/`), removida no fim. Nenhum `git stash`;
  `docs/canal_real.html` intocado; único arquivo editado: este.

`cw` = `tools/publish-whatsapp-channel/pub/canal_web.py`, `pb` = `.../pub/publicador.py`,
`T` = `tools/tests/test_pub_canal_web.py`, `SIM` = `tools/tests/fixtures/whatsapp_simulador.js` (linhas de `9a075c1`).

### C6.1 Itens do pedido

| item | evidência | ok |
|---|---|---|
| 1. Leitura atômica: um `evaluate_all` sobre `[data-testid^="conv-msg-"]` → `{tid, legenda (innerText de image-caption), status (aria-label de msg-meta)}`; sem `nth(i)` na confirmação | `cw:67-72` (`_JS_BALOES`), `cw:186-187` (`_ler_baloes`), `cw:402-403` (`_balao_confirmado` = função pura `balao_confirmado`, `cw:136-139`). No caminho de `confirmar` só resta `_visivel(SEL_LEGENDA)` (`count`/`is_visible`, sem auto-wait). JS é monothread: a lista não muda no meio de um `evaluate_all`; elemento removido depois da captura continua legível (array estático) | sim |
| 2. `confirmar` não aborta por erro transitório; registra UMA vez; só o prazo dá D; navegador morto sobe | `cw:384-400`: `try` por sondagem, `except BrowserMorto: raise`, `_FECHADO` → `raise` (o `@_morto`, `cw:378` e `cw:90-101`, converte em `BrowserMorto`), senão log único (`avisou`) e segue; `return False` só com `time.monotonic() >= fim`. `pb:188-198`: `BrowserMorto` → aviso "navegador caiu" + `raise` → `rodar` devolve 1 (`pb:271-278`); `False` → D + aviso | sim |
| 3. `_ids_baloes` com `evaluate_all` mantido; nenhuma outra leitura de balão por `nth` | `cw:189-190` reaproveita `_ler_baloes`; `SEL_LEGENDA_BALAO`/`SEL_STATUS_BALAO` (`cw:35-36`) ficaram sem uso em Python (o JS repete os seletores) | sim (código); **teste não discrimina** (A6) |
| 4. Timeout explícito ≤ 2 s em toda leitura de DOM fora do evaluate | §C6.2 | sim, com 1 observação |
| Teste: re-render na confirmação → E, sem exceção; o mutante nth(i) morre | `T:568-575` + `SIM:163-180`. **Não é modelo honesto** (§C6.3): A1 morre só por `T:573` (`__reRenderizou is True`) | **não** |
| Teste: exceção transitória numa sondagem, confirma na seguinte → E | `T:589-607` (log "sondagem falhou" exatamente 1) | sim |
| Teste: exceção em todas as sondagens → D com aviso | `T:610-626` (≥ 3 s = sondou até o prazo; `("D","enviando")`; 1 aviso "conferir no canal"; 1 log; sem "erro depois do clique") | sim |
| Teste: navegador morto na confirmação → D + código 1 | `T:629-646` (`rodar` == 1, nenhuma volta extra, aviso "navegador caiu") | sim |

### C6.2 Leituras de DOM fora de `evaluate` em `cw` (item 4)

| leitura | linha | espera |
|---|---|---|
| `loc.count()`, `loc.nth(i).is_visible()` em `_visivel` | `cw:171-172` | sem auto-wait (nth sumido → `False`) |
| `count()` em `_existe` | `cw:179` | sem auto-wait |
| `titulo.inner_text(timeout=2_000)` em `_canal_aberto` | `cw:184` | 2 s |
| `item.count()`, `item.nth(i).is_visible()` em `_item_fotos` | `cw:288-289` | sem auto-wait |
| `menu.count()` em `limpar` | `cw:410` | sem auto-wait |
| `_ler_baloes` (`Locator.evaluate_all`) | `cw:187` | não espera elemento |
| `page.content()` na evidência | `cw:336` | não espera elemento |

Observação (não bloqueia; antes do clique → P): `caixa.evaluate(_JS_TEXTO)` (`cw:345`) e `caixa.evaluate(_JS_COLAR)`
(`cw:359`) são `Locator.evaluate`, que espera o elemento com o timeout padrão (30 s). Pela letra do item 4 estão "dentro
do evaluate", mas têm auto-wait. Ações com 30 s padrão (`fill`/`press_sequentially` `cw:222-223`, `set_files` `cw:259`,
`reload`) não são leituras.

### C6.3 O simulador `reRender` é modelo honesto do achado? Não

`SIM:165-180` troca `Element.prototype.getAttribute` no **mundo principal** da página. O Playwright conta e lê atributos
(`count`, `nth(i).get_attribute`) pelo script injetado no seu mundo **utilitário** (isolado), que não vê o protótipo
trocado. Medido na cópia, com o mutante A1 (o `_balao_confirmado` de `f1b0f5e`) e `abrir(reRender=True)`: `confirmar` =
`True` em 2,5 s, `window.__reRenderizou` = `None`, **9** balões FAKE no DOM (nenhum removido). Com o código novo: `True`,
`__reRenderizou` = `True`, 6 balões. O re-render só acontece quando o código usa `evaluate_all`; a "corrida entre count()
e nth(i)" nunca é exercitada. A1 morre só porque `T:573` exige que a leitura passe pelo `getAttribute` do mundo
principal — sentinela de implementação, não de comportamento.

Modelo honesto (rodado só na cópia, `tests/test_zz_verifier_rerender.py`, apagado): `abrir(status=" Pendente ")`;
depois do `enviar()`, um embrulho de `Locator.count`/`Locator.evaluate_all` (lado Python, independe do mundo JS)
dispara, na 1ª leitura de `SEL_BALAO`, a remoção dos 3 FAKE mais altos e agenda o status " Enviada " para +1,5 s;
asserções: `confirmar(CHAVE, 5) is True` em < 5 s e sem "sondagem falhou". Resultado: **HEAD passa (4,4 s); A1 falha**
com `False` em 32 s — o `nth(i).get_attribute` de índice sumido esperou 30 s, o sintoma da inst2 (o balão novo ainda
pendente na 1ª varredura leva o laço aos índices sumidos). Confirma que o código de produção corrige o achado; falta o
teste do repositório provar isso.

### C6.4 Sensor de discriminação

Cópia `9a075c1`; `T -k "confirmacao or balao_confirmado"`; sobreviventes também em `T` + `test_pub_publicador.py`
inteiros; `timeout 300` em cada execução.

| id | mutante | resultado | morto por |
|---|---|---|---|
| A1 | `_balao_confirmado` volta ao `count()` + `nth(i)` (código de `f1b0f5e`) | morto **só pela sentinela** | `T:573`; os outros 3 testes caem porque o mutante não chama o `_ler_baloes` que eles trocam. Comportamento não discriminado (§C6.3) |
| A2 | `confirmar` re-levanta na 1ª exceção | morto | `T:589`, `T:610` |
| A3 | loga a cada sondagem | morto | `T:610` (1 log) |
| A4 | engole navegador morto (sem `_FECHADO` nem `BrowserMorto` no `except`) | morto | `T:629` |
| A5 | `return False` na 1ª exceção | morto | `T:589`, `T:610` |
| A6 | `_ids_baloes` com `count()` + `nth(i).get_attribute` | **sobrevive** | 102 passed em `T` + `test_pub_publicador.py`. Não equivalente: `_ids_baloes` roda em `enviar()` (`cw:372`), depois do D gravado; com re-render, `nth(i)` volta a esperar 30 s |
| A7 | `balao_confirmado` ignora o status | morto | `T:578` |
| A8 | aceita `tid` antigo | morto | `T:578` |
| A9 | sem o log do aviso | morto | `T:589`, `T:610` |
| A10 | desiste (False) na 2ª exceção | morto | `T:610` (≥ 3 s) |
| A11 | sem o `except BrowserMorto: raise` | sobrevive — **equivalente** | dentro do `try` nada levanta `BrowserMorto` (`_visivel`/`_ler_baloes` não têm `@_morto`); o erro cru com "closed" cai no `_FECHADO` (`cw:393`) |
| A12 | legenda sempre `null` no JS | morto | `T:568`, `T:589` |
| A13 | qualquer status não nulo confirma | morto | `T:233` (`Pendente`, `Enviando`; ciclo anterior) |
| A14 | híbrido: tids pelo `evaluate_all`, legenda/status por `nth(i)` com índice velho | sobrevive | passa também no teste honesto do Verifier (índice sumido → `count()==0`, sem espera; a sondagem seguinte acha). Risco baixo, mas é `nth(i)` na confirmação, que o item 1 proíbe |

**10 de 14 mortos por comportamento** (A1 só pela sentinela; A6 e A14 sobrevivem; A11 equivalente).

### C6.5 Correção pedida (só teste)

1. Trocar o gatilho do `reRender` (ou o teste `T:568`) por um que independa do mundo JS da leitura, como o do §C6.3:
   remoção na 1ª leitura de `SEL_BALAO` pelo lado Python (embrulho de `Locator.count`/`evaluate_all`), balão novo
   **pendente** na 1ª varredura e confirmado depois; asserção de comportamento (`True` em < 5 s, sem "sondagem falhou"),
   sem `__reRenderizou` como critério. A1 tem de morrer por `False`/tempo.
2. Teste de `_ids_baloes` sob re-render (A6): o mesmo gatilho armado antes do `enviar()`; `enviar()` termina em ≤ 2 s,
   sem exceção.
3. Opcional (A14): no teste honesto, uma ordem de balões em que o índice velho leia o balão errado.

### C6.6 Gates (lição 21) — cópia de `9a075c1`, sem carga minha em paralelo

| gate | resultado |
|---|---|
| `cd tools && python -m pytest -q` (Windows) | **821 passed, 7 skipped** (os 7 POSIX antigos), 319 s |
| `ruff check vps/ tests/ publish-whatsapp-channel/` | All checks passed! |
| `shellcheck vps/*.sh` | sem saída (ok) |
| WSL: `test_pub_canal_web`, `test_pub_publicador`, `test_pub_fila`, `test_pub_foto`, `test_pub_isolamento`, `test_pub_regras`, `test_vigia_publicador`, `test_unidades` (`--basetemp=/tmp/bsv63c6`, apagado) | **182 passed, 0 skipped** |

### C6.7 Lacunas (ranqueadas) e pendências do dono

1. **Bloqueia (teste):** `T:568` não reproduz o achado; A1 morre só pela sentinela (§C6.3, §C6.5.1).
2. **Bloqueia (teste):** A6 sobrevive — item 3, na lista mínima do dono (§C6.5.2).
3. Média: A14 sobrevive (`nth(i)` com índice velho na confirmação).
4. Baixa: `Locator.evaluate` da legenda (`cw:345`, `cw:359`) com auto-wait de 30 s (antes do clique; fica P).
5. Baixa: D é gravado antes de `enviar()`; erro no `_ids_baloes` (antes do clique de fato) vira D (`pb:178-198`). Por
   desenho (D conservador), mas reforça a lacuna 2.
6. **Pendência do dono (bloqueia o merge):** novo teste real na inst2 com ≥ 20 posts; conferir no log que nenhum D sai de
   "erro depois do clique" e que "[confirmar] WARN sondagem falhou" aparece no máximo 1 vez por post.

---

## Histórico: ciclo 5, reteste (resultado do ciclo: PASS)

Reteste do ciclo 5, faixa `3fccc36..42aadeb`. `42aadeb` (`test(tools)`) só mexe em testes, simulador e `tasks.md`:
`git diff a5b172d..42aadeb -- tools/publish-whatsapp-channel` = **vazio** (0 linhas), então a checagem do código de
produção da 1ª rodada (§C5.1) continua valendo. As 5 lacunas da 1ª rodada (M9, M12, M13, M14, M17) e a asserção vazia da
linha 392 foram fechadas; o pedido novo do dono (Enviar que não passa fica D) está coberto. **24 de 24 mutantes mortos**
(14 da 1ª rodada + 10 do reteste). Execução real na inst2 continua bloqueando o merge (§C5.6).

- **Quem verificou:** Verifier independente (sub-agente), autor ≠ verificador. Data 2026-11-17.
- **Árvore real:** no início do reteste `git status --porcelain` = ` M .specs/features/BSV-63/validation.md` (este
  arquivo, da 1ª rodada) e `?? docs/canal_real.html`; as modificações alheias vistas na 1ª rodada são as de `42aadeb`.
  Mutantes, gates e WSL numa cópia `git archive 42aadeb tools` no scratchpad (conferida igual ao commit, ignorando CR),
  removida no fim. `docs/canal_real.html` intocado; nenhum `git stash`; único arquivo editado: este.

### C5R.1 Pedido novo do dono: clique no Enviar que não passa fica D

`T` = `tools/tests/test_pub_canal_web.py`, `TP` = `tools/tests/test_pub_publicador.py`, `pb` = `.../pub/publicador.py`,
`cw` = `.../pub/canal_web.py` (linhas de `42aadeb`).

| pedido | evidência | ok |
|---|---|---|
| Enviar com timeout de 5 s ou interceptado → a linha (já D) fica D, sai o aviso de D, não volta a P | código: `cw:358` (`_clicar` → `ErroPagina`, que é `FalhaPasso`) e `pb:188-198` (qualquer exceção depois do D só loga; sem confirmação → `_avisar_duvidoso` e `DUVIDOSO`). `TP:409-419` (`FalhaPasso` no Enviar → `("D", "enviando")`, 1 aviso com a linha e "conferir no canal", 15 min depois continua D e `enviar` chamado 1 vez = sem reenvio); `T:519-533` (`CanalWeb` real + publicador real, camada `enviarCoberto` sobre o botão: D, aviso, nada enviado, log com "Enviar da previa nao passou" + `intercepts pointer events`, < 30 s) | sim |
| "nenhum caso grava D" vale só antes do clique | inalterado: `pb:166-176` (anexo/legenda → `FALHA_ANTES` sem D); testes do anexo com o publicador real seguem `("P", None)` | sim |

### C5R.2 Mutantes do reteste (só `T` + `TP`, sem o de 20 s; M19 também isolado em cada teste)

| id | mutante | resultado | teste que matou |
|---|---|---|---|
| M19 | `pb`: `except FalhaPasso` no bloco do clique → marca D→P e `return FALHA_ANTES` | morto | `TP:409` e, isolado, `T:519`. **Com só o antigo `TP:160` (`test_est03_erro_no_clique_tambem_fica_d`) sobrevive** (1 passed) — confirma a necessidade dos testes novos |
| M20 | Enviar com `botao.click()` (30 s padrão) em vez de `_clicar` | morto | `T:519` (< 30 s) |
| M9 | recarrega ANTES da evidência | morto | `T:441` (`ordem == ["evidencia", "recarga"]`, `T:452`) |
| M12 | até 6 Escapes | morto | `T:549` (`__escapes == 3` com `dialogoTeimoso`) |
| M12b | só 2 Escapes | morto | `T:549` |
| M13 | sem `_depois_da_falha` | morto | `T:538` (camada aberta pelo Anexar some depois da falha) |
| M14 | exceção inesperada vira `ErroPagina` | morto | `T:473` (`type(erro.value) is RuntimeError`, `T:484`) |
| M17 | `ESPERA_MENU_S = 0` | morto | `T:558` (item em 2 s passa) — morre pelo comportamento, não só pela constante |
| M17b | item sem a espera (falha na 1ª sonda) | morto | `T:558` |
| L392 | asserção vazia removida | conferido | `git diff a5b172d..42aadeb` remove a linha `assert m.pagina.recargas == 0 if hasattr(...) else True` |

Os 14 mutantes mortos da 1ª rodada não foram reaplicados: `42aadeb` só acrescenta asserções e cenários (nenhum teste
removido ou afrouxado além da linha vazia), então eles continuam mortos. **Total do ciclo: 24 de 24.**

### C5R.3 Gates (lição 21) — cópia de `42aadeb`, sem carga minha em paralelo

| gate | resultado |
|---|---|
| `cd tools && python -m pytest -q` (Windows) | **816 passed, 7 skipped** (os 7 POSIX antigos), 309 s |
| `ruff check vps/ tests/ publish-whatsapp-channel/` | All checks passed! |
| `shellcheck vps/*.sh` | sem saída (ok) |
| WSL (mesmos 8 arquivos da 1ª rodada, `--basetemp=/tmp/...`, apagado no fim) | **153 passed, 0 skipped** |
| tempo, por último, 3 repetições isoladas | ≤ 6 s: 5,48 / 5,53 / 5,50 s (folga ~0,5 s, sensível a carga); Enviar interceptado (< 30 s): 6,47 / 6,43 / 6,36 s; item em 2 s: 3,24 / 3,22 / 3,15 s; prévia de 20 s: 20,87 / 20,85 / 20,82 s; passou nas 3 |

### C5R.4 Lacunas restantes (nenhuma bloqueia)

1. O teste de ≤ 6 s tem folga de ~0,5 s (inclui `abrir_canal`): pode falhar com a máquina carregada (lições 15/17).
2. Leituras da 1ª rodada sem mutante (§C5.1 a–c): `expect_file_chooser` que não dispara é falha inesperada (P,
   recarrega); `_depois_da_falha` pode mascarar a exceção original; o menu do Anexar não é `role=dialog`, quem fecha
   é o `limpar()`.
3. Risco residual do desvio `SEL_DIALOGO` (modal dentro do nó do aviso) só se confere no teste real.

---

## Histórico: ciclo 5, 1ª rodada (resultado: reprovado; corrigido no reteste acima)

Ciclo 5 (2º achado do teste real, 17/11: anexo pelo menu, clique curto, camadas, evidência em toda falha, janela),
faixa `3fccc36..a5b172d`. **O código de produção atende aos itens 1–5 por leitura e pelos testes** (nenhuma falha
do anexo grava D; o input oculto saiu). **Reprova pelos testes**: 5 de 19 mutantes sobrevivem, e 2 deles estão na
lista mínima do dono (recarregar ANTES da evidência; mais de 3 Escapes); outros 2 tocam pedidos explícitos (Escape
depois da falha; exceção inesperada re-lançada como está). A correção é **só de teste** (§C5.4); nenhum mutante
sobrevivente é equivalente. Execução real na inst2 continua bloqueando o merge (§C5.6).

- **Quem verificou:** Verifier independente (sub-agente), autor ≠ verificador. Data 2026-11-17.
- **Faixa:** `3fccc36..a5b172d` — `573fa10` fix (menu, `_clicar` 5 s, camadas, `FooterPerdido`, evidência em toda
  falha, `motivo_playwright`, janela), `a5b172d` README. `cddeb1a`/`3fccc36` são do ciclo 4.
  `git merge-base --is-ancestor origin/develop HEAD` = 0.
- **Árvore real:** no início `git status --porcelain` = `?? docs/canal_real.html`. **Durante a verificação** apareceram
  modificações não commitadas que não são minhas (`tools/tests/fixtures/whatsapp_simulador.js`,
  `tools/tests/test_pub_canal_web.py`, `tools/tests/test_pub_publicador.py`: cenário `enviarCoberto` e testes de
  "Enviar interceptado fica D") — provavelmente o autor em paralelo. Não as toquei e **não fazem parte deste veredito**:
  mutantes, gates e WSL abaixo rodaram numa cópia `git archive HEAD tools` (conferida igual ao HEAD, ignorando CR).
  `docs/canal_real.html` não foi lido, copiado nem citado. Nenhum `git stash`. Único arquivo editado: este.

### C5.1 Checagem ancorada no pedido do dono

`cw` = `tools/publish-whatsapp-channel/pub/canal_web.py`, `mn` = `.../main.py`, `pb` = `.../pub/publicador.py`,
`R` = `.../README.md`, `T` = `tools/tests/test_pub_canal_web.py` (linhas do HEAD).

| item | pedido | evidência | ok |
|---|---|---|---|
| 1 | caminho = Anexar → "Fotos e vídeos" em `expect_file_chooser` → `set_files`; input oculto não é usado | `cw:236-241`; `SEL_INPUT_FOTO`, `_por_input`, `_input_disponivel`, `set_input_files` saíram (grep em `publish-whatsapp-channel/` = 0); `T:362-371` (input presente no DOM, `__arquivosPorCaminho == {input: 0, menu: 1}`, 1 clique no Anexar, log `caminho=menu previa_s=x.x`, sem evidência no sucesso); `T:190` `not hasattr(canal_web, "SEL_INPUT_FOTO")` | sim |
| 1 | item ausente em 5 s → falha prevista | `cw:41` `ESPERA_MENU_S = 5`, `cw:266-275` (`ErroPagina`, que é `FalhaPasso`); `T:385-394` com o `Publicador` real: `("P", None)`, `falhas_seguidas == 1`, nada enviado, log, 2 arquivos de evidência. O prazo de 5 s não é testado (o simulador mostra o item na hora — mutante M17) | sim (lacuna M17) |
| 2 | antes de anexar: Escape até sumir `[role="dialog"]` e a prévia (máx. 3) e caixa do canal visível | `cw:236` → `_garantir_footer` `cw:285-289` → `_fechar_camadas` `cw:277-283` (`range(3)`, sai quando não há `SEL_DIALOGO` nem `SEL_LEGENDA` visível); `T:422-429` (camada `role=dialog` fechada por Escape antes do anexo e post sai) | sim (lacuna M12: teto de 3 sem teste) |
| 2 | depois de qualquer falha do anexo: o mesmo, e footer que não volta → falha prevista + recarrega | `cw:254-257` (`FooterPerdido` → `_recarregar_pagina`; senão `_depois_da_falha` `cw:291-296`, que recarrega se o footer não volta); `cw:298-304` (`page.reload`; navegador fechado vira `BrowserMorto`); `T:442-450` (sem caixa: `ErroPagina`, 1 recarga, evidência, Anexar nunca clicado). O Escape **depois** da falha não é testado (mutante M13); `pb` também roda `limpar()` no `finally` (`pb:160-161`) | sim (lacuna M13) |
| 2 | desvio: `SEL_DIALOGO` exclui o aviso fixo do canal | `cw:28-30`; `T:432-439` (fixture real: 1 `role=dialog`, 0 em `SEL_DIALOGO`, post sem nenhum Escape, sem evidência); `T:429` o aviso continua lá. **Aceito**: aplicar o item 2 ao pé da letra apertaria Escape em toda volta, e o autor documenta que Escape sem modal fecha a conversa; a exclusão é estreita (`:has(conversation-subheader)`), a prévia é conferida à parte por `SEL_LEGENDA`. Mutante M6 morto. Risco residual: se um modal real vier dentro do mesmo nó do aviso, ele não leva Escape — o dono confirma no teste real | sim (desvio aceito) |
| 3 | clique com 5 s; erro de clique = falha prevista com a causa | `cw:42` `CLIQUE_MS = 5_000`; `cw:218-225` (`click(timeout=CLIQUE_MS)`, `ErroPagina` com `motivo_playwright`; navegador fechado repassa); usado em Canais/busca/célula (`cw:199,203,209`), Anexar (`cw:237`), item (`cw:240`), legenda (`cw:337`), Enviar (`cw:358`); `T:397-411` (camada que intercepta: `ErroPagina` em ≤ 6 s, `intercepts pointer events` no erro e no log, 2 arquivos, nenhum arquivo enviado); `T:414-419` com o `Publicador`: P sem D | sim |
| 3 | `_clicar` no Enviar (depois do D) não volta a P | lido: `pb:188-198` — qualquer exceção depois do D fica D com aviso; nada regride a P | sim |
| 4 | evidência (png + html redigido) em TODA falha do anexo, inclusive inesperada | `cw:247-258`: toda exceção que não é navegador fechado → log `[anexo] falha: <resumo>` + `_evidencia()` (`cw:253`) **antes** de recarregar (`cw:254-255`) e re-lança como está (`cw:258`); `T:453-467` (prévia não abre: P, png pela assinatura, html redigido), `T:385`, `T:397`, `T:442`, `T:470-482` (exceção inesperada: 2 arquivos, `RuntimeError` + mensagem no log). "Antes de recarregar" e "re-lançada como está" não são provados (M9, M14) | sim (lacunas M9, M14) |
| 4 | motivo = última linha do call log com o porquê | `cw:402-417` (`motivo_playwright`: última linha que casa `intercepts pointer events\|outside of the viewport\|…`; senão a última linha útil; sem call log, a 1ª linha); `cw:420-423` `_resumo`; `T:485-499`, `T:409` | sim |
| 4 | nenhuma falha do anexo grava D | `ErroPagina`/`FooterPerdido` são `FalhaPasso` (`cw:73-78`) → `pb:170-172` `FALHA_ANTES`; inesperada → `pb:173-176` recarrega uma vez e `FALHA_ANTES`; o `marcar(... "D" ...)` (`pb:179`) só vem depois do `anexar` sem exceção. `T:385`, `T:414`, `T:453` com o publicador real: `("P", None)` | sim |
| 5 | janela `--window-size=1600,880 --window-position=0,0` (ou do ambiente) e `no_viewport` | `mn:32-48` (`BESAVE_JANELA=LxA`, mínimo 400, inválido → 1600×880), `mn:54` `launch_persistent_context(..., **opcoes_navegador())` (o `viewport` 1280×900 saiu); `T:502-511` | sim |
| 5 | documentar no README | `R:73-76` (janela, `no_viewport`, `BESAVE_JANELA`), `R:21-29` (fluxo do anexo), `R:88-91` (log e evidência), `R:129-130` (tabela de seletores) | sim |

Leituras sem mutante: (a) `expect_file_chooser` que não dispara depois do clique no item (`cw:239`) sai como
`TimeoutError` do Playwright, isto é, falha **inesperada**: evidência, re-lança, o publicador recarrega e a linha fica P —
seguro, mas não é "falha prevista"; (b) `_depois_da_falha` pode lançar outra exceção do Playwright e mascarar a
original (o publicador ainda trata como inesperada → P); (c) o menu do Anexar aberto (`aria-expanded`) não é
`role=dialog`: `_fechar_camadas` não o fecha, mas `limpar()` (`cw:387-395`) fecha no `finally` de cada post;
(d) `T:392` `assert m.pagina.recargas == 0 if hasattr(...) else True` é vazio na prática (não prova nada).

### C5.2 Gates (lição 21) — cópia do HEAD, sem carga minha em paralelo

| gate | resultado |
|---|---|
| `cd tools && python -m pytest -q` (Windows) | **811 passed, 7 skipped** (os 7 POSIX antigos), 298 s |
| `ruff check vps/ tests/ publish-whatsapp-channel/` | All checks passed! |
| `shellcheck vps/*.sh` | sem saída (ok) |
| WSL (`test_pub_canal_web`, `test_pub_publicador`, `test_pub_fila`, `test_pub_foto`, `test_pub_isolamento`, `test_pub_regras`, `test_vigia_publicador`, `test_config_permissao`; `--basetemp=/tmp/...`, apagado no fim) | **148 passed, 0 skipped** |
| tempo, por último, 5 repetições isoladas (`-k "6s or 20s"`) | ≤ 6 s: 5,48 / 5,47 / 5,50 / 5,47 / 5,46 s (inclui `abrir_canal`; folga ~0,5 s — sensível a carga, lições 15/17); prévia de 20 s: 20,64 / 20,76 / 20,89 / 20,76 / 20,79 s; passou nas 5 |

### C5.3 Sensor de discriminação (lotes de 6, 7, 6; só os testes relevantes; sobreviventes reconfirmados com `T` inteiro + `test_pub_publicador.py`)

Seleção: `T -k "anexo and not 20s or motivo or janela"` com `-x`; sobreviventes de novo com `T` + `test_pub_publicador.py`
(91 testes, menos o de 20 s).

| id | mutante | resultado | teste que matou |
|---|---|---|---|
| M1 | input oculto primeiro (prévia por ele, menu só se não abrir) | morto | `T:362` (`input: 0`) |
| M2 | `alvo.click()` sem timeout curto | morto | `T:397` (≤ 6 s) |
| M3 | sem evidência na exceção inesperada | morto | `T:470` |
| M4 | sem evidência na falha prevista | morto | `T:385` |
| M5 | sem `_garantir_footer` antes do anexo | morto | `T:422` |
| M5b | `_fechar_camadas` não faz nada | morto | `T:422` |
| M6 | `SEL_DIALOGO = '[role="dialog"]'` (sem a exclusão) | morto | `T:397` (e `T:432`) |
| M7 | motivo = 1ª linha da mensagem | morto | `T:397` |
| M8 | `FooterPerdido` sem recarregar | morto | `T:442` |
| **M9** | **recarrega ANTES da evidência** | **sobreviveu — lacuna** | `T:442` troca `_recarregar_pagina` por um lambda que só conta; ordem não verificada. Efeito real: a evidência mostraria a página recarregada, não a falha |
| M10 | item ausente sem falhar (devolve o locator vazio) | morto | `T:385` (texto do log) |
| M11 | `viewport` 1280×900 em vez de `no_viewport` | morto | `T:502` |
| **M12** | **até 6 Escapes em vez de 3** | **sobreviveu — lacuna** | nenhum cenário tem camada `role=dialog` que o Escape não fecha. Efeito real: Escapes a mais fecham a conversa |
| **M13** | **sem `_depois_da_falha`** (sem Escape nem recarga depois de falha comum) | **sobreviveu — lacuna** | nenhum teste abre camada/prévia ou perde o footer **depois** da falha. Atenuado pelo `limpar()` do publicador e pelo `_garantir_footer` da próxima volta, mas o item 2 pede o Escape e a recarga depois da falha |
| **M14** | exceção inesperada vira `ErroPagina` (não re-lança como está) | **sobreviveu — lacuna** | `T:470` usa `pytest.raises(RuntimeError)`, e `ErroPagina` é `FalhaPasso(RuntimeError)`. Efeito real: o publicador deixa de recarregar a página na falha inesperada (`pb:173-176` vira `pb:170-172`) |
| M15 | `_fechar_camadas` olha só a prévia (ignora `SEL_DIALOGO`) | morto | `T:422` |
| M16 | `_garantir_footer` não confere a caixa do canal | morto | `T:442` |
| **M17** | `ESPERA_MENU_S = 0` | **sobreviveu — lacuna** (não equivalente) | o simulador cria o item no mesmo clique; no WhatsApp real o item aparece depois. Efeito real: falha prevista em toda volta em que o menu demora |
| M18 | `_clicar` sem o motivo na mensagem | morto | `T:397` |

**14 de 19 mortos.** Da lista mínima do dono (12: M1, M2, M3, M4, M5, M6, M7, M8, M9, M10, M11, M12) morrem 10;
**M9 e M12 sobrevivem**. Nenhum sobrevivente é equivalente.

### C5.4 Lacunas (ranqueadas) — correção só de teste

1. **M14** — `T:470`: trocar `pytest.raises(RuntimeError)` por uma exceção que não seja ancestral de `ErroPagina`
   (ex.: `class Quebra(Exception)`) e conferir `type(erro.value) is Quebra`; idealmente também no publicador real:
   inesperada → recarrega uma vez (`T`/`test_pub_publicador`).
2. **M9** — `T:442`: o lambda de recarga registra se `falha_*.png`/`.html` já existem naquele instante (ou uma lista
   de ordem com `_evidencia` embrulhado) e exige evidência antes da recarga.
3. **M13** — cenário em que a falha deixa camada/prévia aberta ou some com a caixa (ex.: `menuNaoAbre` + camada
   `role=dialog` que aparece no clique do item, ou `semCaixa` ligado só depois do Anexar) e exigir Escape e/ou
   recarga **depois** da falha, chamando `CanalWeb.anexar` direto (sem o `limpar()` do publicador).
4. **M12** — cenário `camadaDialogo` que o Escape não fecha: exigir `__escapes == 3` (não mais), `FooterPerdido` não,
   mas falha prevista / recarga conforme o desenho, e conversa não fechada.
5. **M17** — opção do simulador com atraso do item (ex.: 2 s) que precisa passar, e item ausente medindo ~5 s.
6. `T:392` — remover ou tornar real o `assert ... if hasattr(...) else True`.

### C5.5 Mudanças fora do pedido

`_clicar` com 5 s também em Canais/busca/célula/legenda/Enviar (declarado; coerente com o item 3; no Enviar, depois do
D, continua D — `pb:188-198`); `screenshot(timeout=10_000)` na evidência (`cw:317`). Nada fora de `tools/` e `.specs/`.

### C5.6 Pendências do dono (bloqueiam o merge)

- Teste real na inst2 com o commit que fechar este ciclo: log `[anexo] caminho=menu previa_s=<x>`; em falha,
  `[anexo] falha: <motivo>` com a linha do porquê e `log/falha_*.png/.html` gravados; conferir que a janela 1600×880
  cabe na tela `:1` (footer inteiro visível no VNC) e que o aviso fixo do canal não leva Escape (conversa não fecha).
- Revisar um `log/falha_*.html` real antes de qualquer uso fora da máquina (regra 11).
- Demais pendências dos ciclos 3 e 4 (§C3.7, §C4.6) seguem valendo.

---

## Histórico: ciclo 4 (resultado do ciclo: PASS)

Ciclo 4 (prévia da foto lenta ou que não abre — achado do teste real na inst2, 17/11), faixa `6b5f96b..18fdca0`.
Os 4 itens do pedido do dono e os 5 testes pedidos conferidos com evidência; **16 de 18 mutantes mortos**
(1 equivalente, 1 lacuna de cobertura sem efeito no envio: evidência gravada também no sucesso, §C4.3).
Execução real na inst2 com este código continua bloqueando o merge (§C4.6).

- **Quem verificou:** Verifier independente (sub-agente), autor ≠ verificador. Data 2026-11-17.
- **Faixa:** `6b5f96b..18fdca0` — `2f1d2c1` test (lacunas M-n, M-s, M-t do ciclo 3), `5000ff1` fix (anexo: 30 s,
  segundo caminho, log, evidência), `18fdca0` README. `git merge-base --is-ancestor origin/develop HEAD` = 0.
- **Árvore real:** `git status --porcelain` no início e no fim = `?? docs/canal_real.html` (mais este arquivo,
  editado). `docs/canal_real.html` não foi lido, copiado nem citado neste ciclo. Mutantes numa cópia
  `git archive HEAD tools` no scratchpad da sessão, fora do repo, removida no fim; nenhum `git stash`.

### C4.1 Checagem ancorada no pedido do dono

`cw` = `tools/publish-whatsapp-channel/pub/canal_web.py`, `pb` = `.../pub/publicador.py`,
`T` = `tools/tests/test_pub_canal_web.py`, `sim` = `tools/tests/fixtures/whatsapp_simulador.js`.

| item | pedido | evidência | ok |
|---|---|---|---|
| seletor | legenda `[data-testid="media-caption-input-container"][contenteditable="true"][role="textbox"]` sem mudança | `cw:30` igual; `git diff 6b5f96b..HEAD -- cw` não toca `SEL_LEGENDA =` (0 linhas) | sim |
| 1 | espera da prévia 15 → 30 s, constante própria | `cw:40` `ESPERA_PREVIA_S = 30`; usada em `cw:266` (`ESPERA_PASSO_S` não é mais usada na prévia); `T:326-335` (prévia em 20 s passa, `previa_s` em [20, 30)), `T:338` | sim |
| 2 | input sem prévia → Escape → uma vez Anexar → "Fotos e vídeos" em `expect_file_chooser` → espera de novo → só então falha | `cw:212-227` (Escape `cw:222`, `_por_menu` uma vez, `_esperar_previa` de novo); `_por_menu` `cw:248-261` com `expect_file_chooser` `cw:259`; `T:342-352` (input 1, menu 1, Escape antes do menu via `sim` `__escapesAntesDoMenu`) | sim |
| 2 | falha sem D, linha volta a P | `cw:70` `ErroPagina(FalhaPasso)`; `_morto` repassa `FalhaPasso` (`cw:80`); `pb:170-172` `except FalhaPasso` → `FALHA_ANTES` ("P") antes do `marcar(... "D" ...)` de `pb:179`; `T:355-376` com o `Publicador` real (`pub_falso.Mundo`): `st == ("P", None)`, `falhas_seguidas == 1`, nada enviado, sem aviso | sim |
| 3 | log `[anexo] caminho=input\|menu previa_s=<x.x>` / `previa=nao` | `cw:268`, `cw:270` (e `cw:256` com sufixo explicativo quando o menu nem mostra o item); `T:333` e `T:350` com `re.fullmatch`, `T:349`, `T:371` | sim |
| 4 | `log/falha_<DDMM_HHMMSS>.png` + `.html` redigido, 20 mais recentes | `cw:273-291` (nome `cw:279`, screenshot `cw:284`, `redigir_dom` `cw:285`; colisão no mesmo segundo ganha `_2`); `rodar_evidencias` `cw:369-377`; `main.py:90` `pasta_log=RAIZ / "log"`; `T:372-376` (PNG pela assinatura, DOM da página, sem `\d{10,}`, com `REDACTED`), `T:379-389` (21º apaga o mais antigo, `run_publicador_*.log` intocado), `T:392-405` (rotação chamada pela evidência) | sim |
| 4 | `log/` fora do git | `tools/publish-whatsapp-channel/.gitignore:15` `log/`; `git check-ignore` confirma `log/falha_x.png` | sim |
| testes | simulador + fixture real | `T` parte 2 roda sobre `whatsapp_canal_real.html` + `sim` (cenários novos `atrasoPrevia`, `inputNaoAbre`, `menu`, `menuNaoAbre`, `sim:12-16`) | sim |
| ciclo 3 | lacunas M-n, M-s, M-t | `T:288` (colar rejeitado → digita e envia), `T:294` (célula pelo aria-label com isca antes), `T:310` (sem caixa → `ErroPagina`, nada enviado) | sim |

Leitura (sem mutante): a falha da evidência só vai ao log, salvo navegador fechado, que sobe e vira `BrowserMorto`
(`cw:286-290` + `_morto`); "20 mais recentes" conta **arquivos** (`.png` e `.html` separados = 10 falhas) — leitura
literal do pedido ("o 21º arquivo apaga o mais antigo"); o dono confirma se queria 20 falhas.

### C4.2 Gates (lição 21)

| gate | resultado |
|---|---|
| `cd tools && python -m pytest -q` (Windows) | **803 passed, 7 skipped** com o teste de 20 s à parte + o de 20 s rodado 3 vezes sem carga (22,1 / 22,1 / 21,9 s, passou nas 3) = 804 passed; os 7 skipped são os POSIX antigos |
| `ruff check vps/ tests/ publish-whatsapp-channel/` | All checks passed! |
| `shellcheck vps/*.sh` | sem saída (ok) |
| WSL (`test_pub_canal_web`, `test_pub_publicador`, `test_pub_fila`, `test_pub_foto`, `test_pub_isolamento`, `test_pub_regras`, `test_vigia_publicador`, `test_config_permissao`; `--basetemp=/tmp/...`, apagado no fim) | **141 passed, 0 skipped** (inclui o de 20 s e os 7 de permissão) |

### C4.3 Sensor de discriminação (lotes de 7, 7, 2, 2; só os testes relevantes; os de tempo por último, sem carga)

Seleção: `T -k "anexo and not em_20s"`; M1/M13 com `-k em_20s`; M11b com `T` + `test_pub_publicador.py`.

| id | mutante | resultado | teste que matou |
|---|---|---|---|
| M1 | `ESPERA_PREVIA_S = 15` | morto | `T:326` (prévia em 20 s) |
| M13 | prévia volta a usar `ESPERA_PASSO_S` (15) | morto | `T:326` |
| M2 | sem segundo caminho (só Escape) | morto | `T:342` |
| M3 | segundo caminho repetido (2 vezes) | morto | `T:355` (`menu: 1`) |
| M4 | sem Escape antes do menu | morto | `T:342` (`__escapesAntesDoMenu`) |
| M5 | sem evidência na falha | morto | `T:355` |
| M12 | evidência sem o `.png` (sem screenshot) | morto | `T:355` |
| M6 | sem rotação | morto | `T:392` |
| M7a | `MAX_EVIDENCIAS = 21` | morto | `T:392` |
| M7b | rotação mantém `manter + 1` | morto | `T:379` |
| M8a | log sem `caminho=` | morto | `T:342` |
| M8b | `previa_s` com 0 casas | morto | `T:342` |
| M8c | sem o log `previa=nao` | morto | `T:342` |
| M9a | `.html` sem `redigir_dom` | morto | `T:355` |
| M11a | `ErroPagina(RuntimeError)` (deixa de ser `FalhaPasso`) | morto | `T:355` |
| M11b | `pb`: `except FalhaPasso` sem `return FALHA_ANTES` (segue para D) | morto | `T:355` |
| M9b | sem `_RE_NUMERO_LONGO` | **sobreviveu — equivalente**: `_RE_TELEFONE` (`\+?\d[\d\s().-]{7,}\d`) já casa qualquer sequência de 10+ dígitos, aplicado logo depois; o resultado continua sem `\d{10,}` | — |
| M10 | `_evidencia()` também quando a prévia abre | **sobreviveu — lacuna**: os testes de sucesso (`T:326`, `T:342`) usam `pasta_log=None`, então a evidência é no-op neles. Pela leitura o código está certo (`cw:219`/`cw:224` retornam antes de `cw:226`) | — |

**16 de 18 mortos** (17 de 17 não equivalentes, menos a lacuna M10).

### C4.4 Lacunas (ranqueadas)

1. **M10** — nenhum teste prova que o sucesso não grava evidência. Efeito se regredir: um print + DOM por post
   (custo de tempo na inst2 e a lista de conversas no disco), sem efeito em envio/estado. Correção: em `T:342`
   (ou `T:326`) passar `pasta=tmp_path / "log"` e exigir `list(pasta.glob("falha_*")) == []` (em `T:342` isso
   também cobre "primeiro caminho falhou mas o segundo abriu → sem evidência").
2. O html redigido mantém nomes de conversa (só números e URLs saem): o README avisa (regra 11); o dono não anexa
   `log/falha_*` em PR sem revisar.
3. Interpretação "20 arquivos" (= 10 falhas), §C4.1.

### C4.5 Mudanças fora do pedido

Só testes e simulador (T10), `main.py:90` (passa `pasta_log`), README (T12) e `tasks.md`. Nada fora de `tools/` e `.specs/`.

### C4.6 Pendências do dono (bloqueiam o merge)

- Teste real na inst2 com `18fdca0`: voltas com prévia lenta devem logar `[anexo] caminho=input previa_s=<15..30>`;
  se cair no menu, `caminho=menu`; falha dupla deixa `log/falha_*.png/.html` e a linha em P. Conferir o tempo real
  da prévia contra 30 s.
- Revisar um `log/falha_*.html` real antes de qualquer uso fora da máquina (regra 11).
- Demais pendências do ciclo 3 (§C3.7) seguem valendo.

---

## Histórico: ciclo 3 (resultado do ciclo: PASS)

Ciclo 3 (seletores reais), faixa `062acc5..1ec1a1b`. Todos os itens do pedido do dono conferidos com evidência;
**19 de 24 mutantes mortos** (5 sobreviventes, nenhum que leve a envio errado nem a E sem confirmação: 2 equivalentes
no ambiente de teste e 3 lacunas de cobertura, §C3.5). Execução real na inst2 continua bloqueando o merge (§C3.7).

- **Quem verificou:** Verifier independente (sub-agente), autor ≠ verificador. Data 2026-11-16.
- **Faixa:** `062acc5..1ec1a1b` — `20411f5` feat (seletores reais, fixture real redigida, simulador, `FalhaPasso`,
  `chave_oferta`), `75de7ac` README "Seletores", `1ec1a1b` spec. `git merge-base --is-ancestor origin/develop HEAD` = 0.
- **Fonte:** pedido do dono deste ciclo (itens 1–5 abaixo); `docs/specs/BSV-63.md`; T8–T9 de `tasks.md`.
- **Árvore real:** `git status --porcelain` no início e no fim = `?? docs/canal_real.html` (mais este arquivo,
  editado). Mutantes numa cópia `git archive HEAD tools` no scratchpad da sessão, fora do repo, removida no fim;
  `docs/canal_real.html` não foi copiado para o scratch.

### C3.1 Dado pessoal

- `git log --all --oneline -- docs/canal_real.html` → **vazio** (nunca entrou em commit); segue `??`.
- Grep do dono sobre a fixture:
  `grep -nE '[0-9]{10,}|pps\.whatsapp|cdn\.whatsapp|blob:|data-pre-plain-text="\[' tools/tests/fixtures/whatsapp_canal_real.html`
  → **0 linhas**. O mesmo grep é teste: `tools/tests/test_pub_canal_web.py:101-109`.
- Nós de texto da fixture lidos um a um: só nome do canal, "Você:", horários, textos dos posts de teste ("teste",
  "222", "TESTE X"…), rótulos de UI e `REDACTED`. Nenhum nome de pessoa. `<title>REDACTED</title>`,
  `data-pre-plain-text="REDACTED"`, `data-id="REDACTED"`, ids `conv-msg-FAKE1..9`.

### C3.2 Checagem ancorada no pedido do dono

Caminhos relativos a `tools/`; `cw` = `publish-whatsapp-channel/pub/canal_web.py`, `pb` = `.../pub/publicador.py`,
`T` = `tests/test_pub_canal_web.py`, `TP` = `tests/test_pub_publicador.py`.

| item | o que foi pedido | evidência | ok |
|---|---|---|---|
| 1 | fixture = recorte (Canais, célula, `#main`), sem lista de conversas, sem script/style/link, sem classes `x…` | `tests/fixtures/whatsapp_canal_real.html` (30 linhas, 32 KB; cabeçalho em comentário :2-10); `T:101-109` (sem `<script/<style/<link`, sem `class="x…"`, sem "(N) WhatsApp", ids só `FAKEn`) | sim |
| 1 | recorte fiel | conferido contra `docs/canal_real.html` (Chromium local, JS desligado, rede bloqueada): os testids `newsletter-tab-drawer`, `newsletter-tab-newsletter-cell`, `conversation-info-header-chat-title`, `conversation-compose-box-input`, 9 `conv-msg-`, 5 `msg-meta` (todos `" Enviada "`), 3 `image-caption`, `Anexar`, `input accept=image/*`, `Canais` aparecem nas mesmas quantidades no real e na fixture | sim |
| 1 | prévia de mídia acrescentada à mão com comentário | `whatsapp_canal_real.html:24-29` ("Transcrito do mapeamento do dono (16/11/2026)"), só `data-testid`/`contenteditable`/`role` e `role`/`aria-label` do Enviar; `T:108` exige o comentário | sim |
| 1 | sintética apagada, testes só com a real | `whatsapp_canal.html` removido em `20411f5`; `T:29` `FIXTURE = whatsapp_canal_real.html`; `T:109` falha se a sintética voltar | sim |
| 1 | desvio `<button>` dentro de `<button>` → externo vira `div role=button` | **aceitável.** Provado: no `canal_real.html` cru o `<footer>` vem depois de `id="main"` sem `</main>` entre eles e com 10 `<button>`/10 `</button>`, mas parseado pelo Chromium `#main footer` = 0 (o parser fecha o botão externo e expulsa o footer). Na página viva o DOM é montado por JS e o aninhamento existe; a tabela do dono usa `#main footer`. A troca só muda a tag de um ancestral sem seletor nosso (`div[role=button] button` = 2 na fixture) | sim |
| 2 | nome do canal de `CANAL_ENVIO.DS_CHAT_ID` (ID_CANAL 2), não no config | `pub/fila.py:21` `SELECT DS_CHAT_ID FROM CANAL_ENVIO WHERE ID_CANAL = :1`; `pb:147` `nome_canal(cfg.id_canal)`; `pb:151-153` sem nome → P; `conf/config.example.json` sem nome de canal (só `id_canal`, `pub/config.py:29`) | sim |
| 3 | só data-testid/aria-label/role/title (+ `#side`/`#pane-side`); sem `x…`, XPath, `_r_`, `data-icon` | `cw:18-33`; `T:91-98` varre todos os `SEL_*` (sem `data-icon`, `_r_`, `//`, nenhuma classe) | sim |
| 3 | tabela linha a linha | logado `cw:18`; aba `cw:21`; busca `cw:22` (`[data-testid="newsletter-tab-drawer"] input[type="text"]`, primeiro visível via `_visivel` `cw:139-149`); célula `cw:23`; título `cw:24`+`cw:154-157` (`==` normalizado); caixa `cw:25`; anexar `cw:26`; input `cw:27`; legenda `cw:29`; enviar `cw:30`; balão `cw:31`; legenda do balão `cw:32`; status `cw:33-34`, `cw:113-114`. Igual ao README `publish-whatsapp-channel/README.md:104-118` (data 16/11/2026, :100). `T:176-189` conta cada seletor na fixture real (1 cada; 9 balões; 3 legendas; status todos confirmados; 1 input de arquivo). Contra o `canal_real.html` parseado: todos 1 (exceto os do footer, pelo desvio acima, e os da prévia, que não estavam gravados) | sim |
| 4a | canal aberto + caixa → pula; senão Canais → busca → célula → cabeçalho; divergiu = falha | `cw:182-183` pula; `cw:184-197` navega; `cw:198-202` cabeçalho igual ou `ErroPagina` (`FalhaPasso`); `T:193-197` (`__cliquesCanais == 0`), `T:200-205`, `T:208-213` | sim |
| 4b | `set_input_files` no oculto; senão Anexar + 5 s; senão `expect_file_chooser` em volta de "Fotos e vídeos" | `cw:211-227`; `T:253-257`, `T:260-263`, `T:266-273` | sim |
| 4c | cola (fallback Shift+Enter), confere cru com cru (quebras, espaços NBSP, NFC), divergiu: limpa e tenta 1 vez; de novo: Escape, falha, sem D | `cw:97-105`, `cw:234-255`; `T:56-75`, `T:216-223`; sem D: `pb:165-172` antes de `pb:179`; `TP:401-406` | sim (nova tentativa sem teste, §C3.5) |
| 4d | grava D → clica Enviar | `pb:179` antes de `pb:189`; `TP:124`, `TP:141` | sim |
| 4e | confirmação positiva ≤ 60 s: prévia fechada, balão novo, legenda com `besave.io/{id}` (com fronteira), msg-meta ∈ {enviada, entregue, lida}; senão fica D; só então E | `cw:265-289`; `pb:39-41` `chave_oferta`; `pb:190` passa a chave, não a legenda; `pb:196-198` D; `pb:201` E; `T:78-88`, `T:226-250`; `TP:394-397` | sim |
| 5 | testes de página sobre a fixture real, sem WhatsApp real | `T:122-148` (`set_content` da fixture + `whatsapp_simulador.js` via `add_script_tag`); cabeçalho divergente `T:208`; legenda divergente `T:216` (+ `TP:401` sem D); balão sem chave `T:226`; msg-meta desconhecido/ausente `T:231-234`; "Enviada" → confirmado `T:192-197` e → E `TP:383-391`; balão antigo com a mesma chave `T:237-240`; input ausente → Anexar `T:253-257`. Nenhuma URL do WhatsApp é aberta (só `set_content`) | sim |
| 5 | README "Seletores" com a tabela e a data | `publish-whatsapp-channel/README.md:98-126` | sim |

Observação de forma (não bloqueia): `tasks.md` repete as linhas de dependência `T8 → T9` na fase 5.

### C3.3 Gates

| gate | resultado |
|---|---|
| `cd tools && python -m pytest -q` (Windows, venv com Playwright/Chromium) | **795 passed, 7 skipped** em 3 min 52 s (os 7 são os POSIX antigos) |
| `ruff check vps/ tests/ publish-whatsapp-channel/` | All checks passed |
| `shellcheck vps/*.sh` | sem saída, código 0 |
| WSL Ubuntu (Playwright, Chromium): `pytest -rs tests/test_pub_canal_web.py tests/test_pub_publicador.py` | **76 passed, 0 skipped** em 42,8 s |

### C3.4 Sensor de discriminação (ciclo 3)

Cópia `git archive HEAD tools` no scratchpad; Windows, Chromium do venv; lotes de 8/8/8; cada mutante roda só o
arquivo de teste relevante com `-x`; o arquivo é restaurado depois de cada um (conferido com
`diff -rq --strip-trailing-cr` contra a árvore real: idênticos).

| id | mutação | resultado | morto por |
|---|---|---|---|
| M-a | status aceito = qualquer aria-label | morto | `T::test_status_do_balao[Pendente-False]` |
| M-b1 | publicador passa a legenda inteira a `confirmar` | morto | `TP::test_est01_confirmacao_pede_o_link_curto_da_oferta` |
| M-b2 | balão confere a legenda inteira (igualdade) em vez da chave | morto | `T::test_dom_enviada_vira_confirmado_num_envio_so[colar]` |
| M-c1 | não filtra os balões de antes do clique | morto | `T::test_dom_balao_antigo_com_a_mesma_chave_nao_confirma_o_novo` |
| M-c2 | contagem de balões tirada depois do clique | morto | `T::test_dom_enviada_vira_confirmado_num_envio_so[colar]` |
| M-d | pula a checagem do cabeçalho | morto | `T::test_dom_cabecalho_divergente_nao_envia` |
| M-e | primeiro input de arquivo da página (fora do footer) | morto | `T::test_dom_input_de_arquivo_fora_do_footer_nao_e_usado` |
| M-f | não exige a prévia fechada | morto | `T::test_dom_previa_aberta_nao_confirma` |
| M-g | `in` em vez de `==` no título | morto | `T::test_dom_cabecalho_divergente_nao_envia` |
| M-h | chave sem fronteira (54120 casa 5412) | morto | `T::test_chave_besave_io_com_fronteira` |
| M-i | sem Escape na legenda divergente | morto | `T::test_dom_legenda_divergente_na_previa_fecha_e_nao_envia` |
| M-j | sem escrever a legenda | morto | `TP::test_esc01_tres_p_posta_a_mais_recente` |
| M-j2 | legenda escrita depois de gravar D (D antes da legenda) | morto | `TP::test_est02_falha_antes_do_clique_volta_a_p_e_conta[escrever_legenda]` |
| M-k | sem `expect_file_chooser` em volta de "Fotos e vídeos" | morto | `T::test_dom_sem_input_nenhum_usa_fotos_e_videos_com_expect_file_chooser` |
| M-l | não pula a navegação com o canal aberto | morto | `T::test_dom_enviada_vira_confirmado_num_envio_so[colar]` |
| M-m | `FalhaPasso` cai no `except Exception` (recarrega) | morto | `TP::test_est02_falha_prevista_da_pagina_e_p_sem_recarregar[abrir_canal]` |
| M-o | status sem `strip` | morto | `T::test_status_do_balao[ Enviada -True]` |
| M-r | ignora o msg-meta | morto | `T::test_dom_status_desconhecido_ou_ausente_nao_confirma[ Pendente ]` |
| M-n | legenda divergente sem a nova tentativa (1 modo só) | **sobreviveu** | lacuna L1 |
| M-s | célula sem `[aria-label="Canal {nome}"]` (qualquer célula) | **sobreviveu** | lacuna L2 |
| M-t | sem a checagem da caixa depois de abrir o canal | **sobreviveu** | lacuna L3 |
| M-q | sem a espera de 5 s pelo input depois de Anexar | sobreviveu — **equivalente no ambiente**: o simulador cria o input no mesmo clique; só o WhatsApp real tem a demora | — |
| M-u | Enviar afrouxado para `[role=button][aria-label^="Enviar"]` | sobreviveu — **equivalente na fixture**: só há um "Enviar…" no recorte; o seletor exato é conferido por leitura (`cw:30`) e pelo teste de seletores `T:176-184` | — |

**Mortos: 19 de 24** (19 de 22 não equivalentes).

### C3.5 Lacunas (ranqueadas)

1. **L1 — nova tentativa da legenda sem teste (M-n).** O pedido diz "divergiu: limpa, tenta 1 vez". O cenário
   `rejeitaTexto` recusa colar **e** digitar, então tirar a segunda tentativa não muda nada no teste. Efeito do
   defeito seria conservador (falha antes, sem D, sem envio errado). Sugestão: cenário do simulador que recusa só
   o `paste` e um teste que espera sucesso pelo modo digitar.
2. **L2 — célula escolhida pelo `aria-label` sem teste discriminante (M-s).** A fixture tem uma célula só. A
   checagem do cabeçalho (`cw:198-202`, M-d/M-g mortos) segura o envio no canal errado, então é defesa em
   profundidade. Sugestão: injetar uma segunda célula "Canal {nome} 2" antes da certa.
3. **L3 — "canal aberto sem caixa" sem teste (M-t).** Fora da lista explícita do dono; sem caixa a prévia não
   abriria e o passo seguinte falha antes do D.

### C3.6 Itens conferidos por leitura

- `FalhaPasso` não recarrega e não conta como exceção inesperada (`pb:34-36`, `pb:170-172`); `ErroPagina` herda
  dela (`cw:67-68`); `_morto` deixa `FalhaPasso` passar (`cw:77-78`).
- QR fora do mapeamento de 16/11 (`cw:19-20`), declarado no README `:121-122`.

### C3.7 Pendências do dono (bloqueiam o merge)

1. **Teste real na inst2** com o binário/código desta branch: um post de oferta no canal (ID_CANAL 2), conferindo
   E com o balão "Enviada", e um caso de D (cortar a rede depois do clique).
2. **QR não capturado:** os seletores `SEL_QR` (`cw:20`) e o aria-label do relógio de pendente são palpites; conferir
   no primeiro QR/sessão deslogada e no primeiro post pendente.
3. `docs/canal_real.html` continua fora do git; decidir apagá-lo ou guardá-lo fora do worktree (o Verifier não mexeu).

---

## Histórico: ciclo 2

Resultado do ciclo 2: aprovado (faixa `3d61c84..0eaf0a6`). No ciclo 1 (`3d61c84..1f0711d`) o veredito foi reprovado
com 4 de 54 mutantes não equivalentes vivos (M21, M47, M54, M55). O commit `0eaf0a6` (só testes:
`tests/test_pub_publicador.py`, `tests/test_pub_canal_web.py`, `tests/pub_falso.py`) fechou as lacunas 1–4 e os
quatro agora morrem: **54 de 54 mortos** (mais 2 equivalentes, 56 no total). Conferido que nenhum código de
produção mudou: `git diff 1f0711d..0eaf0a6 -- tools/publish-whatsapp-channel tools/vps` sai vazio. Lacunas 5–6
seguem (não bloqueantes para o veredito). **Continua bloqueando o merge** a execução real do dono na inst2
(§6), que inclui trocar a fixture sintética pela gravada.

- **Quem verificou:** Verifier independente (sub-agente), autor ≠ verificador.
- **Diff:** ciclo 1 `3d61c84..1f0711d`, 6 commits: `b6d7cd3` config/ritmo/descarte, `3e32484` foto, `6bc2ddd`
  fila/avisos/batimento, `b20d6d8` laço P/D/E, `bf9fe7b` página/fixture/main, `1f0711d` vigia/unidade/README;
  ciclo 2 `3d61c84..0eaf0a6` (+ `0eaf0a6` só testes e `tasks.md`).
- **Referência:** `docs/specs/BSV-63.md` (spec do dono, fonte dos critérios); `.specs/features/BSV-63/spec.md`
  (EARS do autor).
- **Data:** 2026-11-16.
- **Tarefas:** T1–T6 marcadas ✅ em `.specs/features/BSV-63/tasks.md`.
- **Árvore real:** o único arquivo criado/editado é este (`?? .specs/features/BSV-63/validation.md` no início e
  no fim do ciclo 2). Mutantes rodados numa cópia `git archive <commit> tools` no scratchpad da sessão
  (ciclo 1: `HEAD` = `1f0711d`; ciclo 2: `0eaf0a6`), removida no fim de cada ciclo.

---

## 1. Checagem ancorada na spec

Caminhos relativos a `tools/`. `pub/` = `publish-whatsapp-channel/pub/`.

### 1.1 Critérios de aceite da spec do dono

| Critério (spec do dono) | Valor definido pela spec | Código | Teste (`file:line` + asserção) | Resultado |
|---|---|---|---|---|
| Ritmo: teto 40, janela 8–22, dia de voltas de 15 min | ≤ 40 posts, nenhum fora da janela | `pub/regras.py:38-53` | `tests/test_pub_publicador.py:18-31` (96 voltas, `38 <= len <= 40`, `8 <= h < 22`) | ✅ PASS |
| Ritmo: 07:59 → 0 | 0 tentativas | `pub/regras.py:44` | `tests/test_pub_publicador.py:34-38` (`envios == []`, sem `abrir_canal`); `tests/test_pub_regras.py:25-29` (07:59 e 22:00 → `None`) | ✅ PASS |
| Ritmo: mutante sem teto falha | morre | — | M01 (só janela) e M02 (posta toda volta) mortos (§3) | ✅ PASS |
| Escolha: 3 `P` → a mais recente | maior `DT_FILA` | `pub/regras.py:91-93` | `tests/test_pub_publicador.py:80-86` (só a legenda de `b`, −5 min); `tests/test_pub_regras.py:92-97` | ✅ PASS |
| Oferta inativa → `X expirou` | `("X","expirou")`, sem post | `pub/regras.py:70-71`; `pub/fila.py:24-27` (LEFT JOIN, `ST_ATIVO = 1`) | `tests/test_pub_publicador.py:89-92`; `tests/test_pub_fila.py:57-66` | ✅ PASS |
| Fila de 4 h → `X velha` | `max_horas_fila` 3 | `pub/regras.py:74-75` | `tests/test_pub_publicador.py:95-98`; `tests/test_pub_regras.py:71-76` (3 h exatas ainda vale) | ✅ PASS |
| Pendente de ontem → `X outro_dia` | dia de Brasília | `pub/regras.py:72-73`, `:24-26` | `tests/test_pub_publicador.py:101-104`, `:107-121` (teto não descarta; virada sim); `tests/test_pub_regras.py:79-89` | ✅ PASS |
| Estados: confirmado → `E` | `E` com `DT_ENVIO`, passando por `D` antes do clique | `pub/publicador.py:166`, `:188` | `tests/test_pub_publicador.py:124-137` (`estado_no_clique == [("D","enviando")]`, `dt_envio == local(T0)`) | ✅ PASS |
| Falha antes do clique → `P` e falha contada | `P`, `falhas_seguidas == 1` | `pub/publicador.py:154-163`, `:221-231` | `tests/test_pub_publicador.py:141-148` (abrir/anexar/legenda) | ✅ PASS |
| Sem confirmação → `D` e aviso | `D 'enviando'`, aviso com o id | `pub/publicador.py:183-185`, `:196-199` | `tests/test_pub_publicador.py:151-157`, `:160-164` | ✅ PASS |
| `D` não é tentada na volta seguinte; mutante que reenvia `D` falha | 0 envios daquele id | `pub/fila.py:27` (`ST_ENVIO = 'P'`) | `tests/test_pub_publicador.py:167-176`, `:179-182`; `tests/test_pub_fila.py:57-62`; M05 e M06 mortos | ✅ PASS |
| Legenda idêntica, com linhas em branco, num envio só; mutante `\n`→`Enter` falha | igual a `DS_LEGENDA`; 0 `Enter` | `pub/canal_web.py:124-131`, `:244-262` | `tests/test_pub_canal_web.py:52-58` (teclado em que `Enter` envia: `enviadas == []`, `buffer == LEGENDA`); `:142-148` (Chromium, colar e digitar: `__envios == [LEGENDA]`, `__enters == 0`); M07, M08, M09 mortos | ✅ PASS (fixture sintética — §6) |
| Pausa: 3 falhas → pausa + 1 aviso; 0 tentativas dentro; volta → "voltou" | 60 min, 1 aviso | `pub/publicador.py:20-22`, `:86-93`, `:221-239` | `tests/test_pub_publicador.py:226-235`, `:238-245`, `:248-253` (lembrete 6 h) | ✅ PASS |
| Desligar: `habilitado: false` → 0 tentativas, sem reiniciar | 0 chamadas na página e na fila | `pub/publicador.py:83-85`; `pub/config.py:49-52` | `tests/test_pub_publicador.py:286-293` (`chamadas == []`, `leituras_de_estado == []`, religa sem novo objeto) | ✅ PASS |
| Foto: 800×800 JPEG branco, proporção preservada | idem | `pub/foto.py:38-52` | `tests/test_pub_foto.py:38-48` (formato, tamanho, faixas brancas, 400 px de altura), `:51-54` | ✅ PASS |
| Foto: 404 → placeholder da área **da linha** | URL `placeholder/{DS_AREA_SLUG}.webp` | `pub/foto.py:58`; `pub/publicador.py:144` | `tests/test_pub_foto.py:57-65` (URLs exatas, WARN); fiação no laço: `tests/test_pub_publicador.py:377-381` (`fotos_pedidas == [(oferta, "meu-lar")]`) | ✅ PASS (ciclo 2; ciclo 1 parcial, M54 vivo) |
| Foto: 404 também no placeholder → `P`, sem post, sem `D`; mutante sem foto falha | `None` → `P` | `pub/foto.py:71`; `pub/publicador.py:145-147` | `tests/test_pub_foto.py:73-76`; `tests/test_pub_publicador.py:200-205`; M10, M11 mortos | ✅ PASS |
| Vigia: `BESAVE_VIGIA_ROBOS=publicador` → só ele; ausente → `lojas,whatsapp` | idem; testes BSV-57 verdes | `vps/vigia_robos.py:61-62`, `:120-130`, `:660` | `tests/test_vigia_publicador.py:20-45`, `:103-140`; `tests/test_vigia_robos.py` inteiro verde | ✅ PASS |
| Gates | verdes | — | §2 | ✅ PASS |
| DOM com fixture **gravada do WhatsApp real** e redigida; seletores capturados pelo VNC | fixture real | `pub/canal_web.py:1-12` (origem declarada) | `tests/fixtures/whatsapp_canal.html` é **sintética** (declarado no spec.md e no README §Seletores) | ❌ não atendido aqui — **pendente do dono, bloqueia o merge** (§6) |
| Real (dono) | 5 passos na inst2 | — | não executável aqui | **pendente — bloqueia o merge** (§6) |

### 1.2 Requisitos EARS do autor

| ID | Código | Teste (`file:line`) | Resultado |
|---|---|---|---|
| RIT-01 | `pub/regras.py:38-53` | `tests/test_pub_publicador.py:18-31` | ✅ PASS |
| RIT-02 | `pub/regras.py:44` | `tests/test_pub_regras.py:25-35`; `tests/test_pub_publicador.py:34-38` | ✅ PASS |
| RIT-03 | `pub/regras.py:50-53`; `pub/fila.py:22-23` | `tests/test_pub_regras.py:38-55`; `tests/test_pub_publicador.py:41-58`; `tests/test_pub_fila.py:69-74`; `D` do próprio laço no teto: `tests/test_pub_publicador.py:364-374` | ✅ PASS (ciclo 2; ciclo 1 parcial, M21 vivo) |
| RIT-04 | `pub/regras.py:96-101`; `pub/publicador.py:115` | `tests/test_pub_regras.py:58-61`; `tests/test_pub_publicador.py:61-75` | ✅ PASS |
| ESC-01..04 | `pub/regras.py:68-93` | §1.1; M16–M19, M35 mortos | ✅ PASS |
| EST-01 | `pub/publicador.py:166-195` | `tests/test_pub_publicador.py:124-137`; M22 morto | ✅ PASS |
| EST-02 | `pub/publicador.py:154-163` | `tests/test_pub_publicador.py:141-148`; M32, M42 mortos | ✅ PASS |
| EST-03 | `pub/publicador.py:174-185` | `tests/test_pub_publicador.py:151-164`, `:317-321`; M31, M36 mortos | ✅ PASS |
| EST-04 | `pub/fila.py:27`; `pub/fila.py:29` (guarda `AND ST_ENVIO = :de`) | `tests/test_pub_publicador.py:167-197`; `tests/test_pub_fila.py:77-85` | ✅ PASS |
| FOT-01..03 | `pub/foto.py`; `pub/publicador.py:144` | §1.1; M10–M15, M54 mortos | ✅ PASS (ciclo 2) |
| LEG-01 | `pub/canal_web.py:124-131` | `tests/test_pub_canal_web.py:52-64`, `:142-148` | ✅ PASS |
| LEG-02 | `pub/canal_web.py:115-121`, `:244-262` | `tests/test_pub_canal_web.py:67-71`, `:158-177`; M41, M51 mortos | ✅ PASS |
| PAU-01/02 | `pub/publicador.py:221-239` | §1.1; M23, M24, M33, M43, M48, M49 mortos | ✅ PASS |
| QR-01 | `pub/publicador.py:95-101`, `:247-254`; `pub/canal_web.py` (`sessao`) | `tests/test_pub_publicador.py:271-283`; `tests/test_pub_canal_web.py:134-139`; M34, M50 mortos | ✅ PASS |
| CFG-01 | `pub/publicador.py:62-72`, `:83-85` | `tests/test_pub_publicador.py:286-293`, `:345-354`; `tests/test_pub_regras.py:123-125` | ✅ PASS |
| CFG-02 | `pub/config.py:12-15`; `conf/config.example.json` | `tests/test_pub_regras.py:110-134`; M45, M52, M53 mortos | ✅ PASS |
| BAT-01 | `pub/publicador.py:79`; `pub/batimento.py` | `tests/test_pub_publicador.py:296-301`; `tests/test_pub_fila.py:152-157` (JSON inteiro); M38 morto | ✅ PASS |
| LIM-01 | `pub/publicador.py:201-208`, `:258-271` | `tests/test_pub_publicador.py:311-342`; M37, M42 mortos | ✅ PASS |
| Limpeza (spec item 6, sem ID EARS) | `pub/publicador.py:149-151` (`finally: self._limpar()`) | falha: `tests/test_pub_publicador.py:148`; `E` e `D`: `:383-388` (`chamadas[-2:] == ["confirmar", "limpar"]`) | ✅ PASS (ciclo 2; ciclo 1 parcial, M55 vivo) |
| Confirmação "balão com o começo da legenda" (spec 4.3) | `pub/canal_web.py:273-291` | `tests/test_pub_canal_web.py:74-77` (chave), `:151-155` (relógio), `:185-192` (balão novo de outro texto, sem relógio → `False`) | ✅ PASS (ciclo 2; ciclo 1 parcial, M47 vivo) |
| VIG-01 | `vps/vigia_robos.py:61-62`, `:120-130`, `:499`, `:660` | `tests/test_vigia_publicador.py`; M28, M29 mortos | ✅ PASS |
| UNI-01 | `vps/systemd/besave-publicador-whatsapp.service:26-27`; `vps/systemd/inst2/.../robos.conf` | `tests/test_unidades.py:223-246` (seção `[Service]` comparada inteira — lição 14); M30, M46 mortos | ✅ PASS |
| ISO-01 | `publish-whatsapp-channel/` | `tests/test_pub_isolamento.py:11-26` | ✅ PASS |

---

## 2. Gates (lição 21)

Python 3.14.7 (venv local com pytest, ruff, Pillow, Playwright + Chromium, shellcheck).

**Ciclo 2 (`0eaf0a6`):**

| Gate | Comando | Resultado |
|---|---|---|
| pytest (suíte inteira) | `cd tools && python -m pytest -q` | **773 passed, 7 skipped** em 220 s (+5 testes novos do `0eaf0a6`) |
| pytest BSV-63 + vigia/unidades | mesmo subconjunto do ciclo 1 | **134 passed, 0 skipped** (DOM em Chromium real, incluindo o novo `test_dom_balao_novo_de_outra_mensagem_nao_confirma`) |
| ruff | `ruff check vps/ tests/ publish-whatsapp-channel/` | `All checks passed!` |
| shellcheck | `shellcheck vps/*.sh` | exit 0, sem saída |

**Ciclo 1 (`1f0711d`):**

| Gate | Comando | Resultado |
|---|---|---|
| pytest (suíte inteira) | `cd tools && python -m pytest -q` | **768 passed, 7 skipped** em 226 s, exit 0. Os 7 skips são de testes POSIX antigos: o subconjunto do BSV-63 (abaixo) tem 0 skip |
| pytest BSV-63 + vigia/unidades | `python -m pytest -q -rs tests/test_pub_*.py tests/test_vigia_publicador.py tests/test_unidades.py` | **129 passed, 0 skipped**; os 7 testes `test_dom_*` de `test_pub_canal_web.py` **rodaram em Chromium real** (13/13 do arquivo passaram) |
| ruff | `ruff check vps/ tests/ publish-whatsapp-channel/` | `All checks passed!` |
| shellcheck | `shellcheck vps/*.sh` | exit 0, sem saída |

No CI os `test_dom_*` pulam (Playwright fora de `requirements-dev.txt`, proposta do autor no spec.md); os
mutantes de DOM (M27, M47, M51) só são vistos localmente.

---

## 3. Sensor de discriminação

56 mutantes, aplicados um a um numa cópia isolada (`git archive <commit> tools` no scratchpad), cada um com
só os testes relevantes (lição 23), em lotes de 3 a 12 (lição 13).

- **Ciclo 1 (`1f0711d`):** 50 mortos, 2 equivalentes, 4 vivos (M21, M47, M54, M55).
- **Ciclo 2 (`0eaf0a6`):** os 4 vivos reaplicados sobre os testes novos: **4 de 4 mortos**. Os outros 50
  não precisaram ser repetidos: o `0eaf0a6` só **acrescenta** testes (nenhum teste existente mudou nem saiu, e
  nenhum código de produção mudou), então quem os matava continua lá. **Total: 54 de 54 não equivalentes
  mortos.**

| ID (ciclo 2) | Mutante | Resultado | Morto por |
|---|---|---|---|
| M21 | `D` gravado com `DT_ENVIO = None` | MORTO | `test_pub_publicador.py::test_rit03_d_gravado_pelo_proprio_laco_conta_no_teto` (`:364`) |
| M47 | confirmação aceita qualquer balão novo | MORTO | `test_pub_canal_web.py::test_dom_balao_novo_de_outra_mensagem_nao_confirma` (`:185`, Chromium) |
| M54 | laço passa área fixa para a foto | MORTO | `test_pub_publicador.py::test_fot02_laco_pede_o_placeholder_da_area_da_linha` (`:377`) |
| M55 | sem limpeza depois de post confirmado | MORTO | `test_pub_publicador.py::test_limpeza_depois_de_toda_tentativa_com_clique[E]` (`:383`) |

Tabela completa do ciclo 1 (histórico):

| ID | Mutante | Resultado | Morto por |
|---|---|---|---|
| M01 | `devido` só olha a janela (sem teto nem ritmo) — *spec* | MORTO | `test_pub_regras.py::test_rit03_ritmo_l1_igual_ao_do_telegram` |
| M02 | `devido` sempre `True` (posta toda volta) — *spec* | MORTO | `test_pub_regras.py::test_rit02_fora_da_janela_nao_e_devido` |
| M03 | `esperado` sem `min(MAX, …)` | EQUIVALENTE | `ritmo = MAX·(m−ini)//(fim−ini) ≤ MAX−1` com `m < fim`, então `1 + ritmo ≤ MAX` sempre |
| M04 | janela inclui o FIM (`m > fim`) | MORTO | `test_rit02_fora_da_janela_nao_e_devido` |
| M05 | SQL lê `P` e `D` como pendentes — *spec (reenvia D)* | MORTO | `test_pub_fila.py::test_pendentes_so_p_do_canal_com_st_ativo_da_oferta` |
| M06 | `D` sem confirmação volta a `P` — *spec (reenvia D)* | MORTO | `test_est03_sem_confirmacao_fica_d_e_avisa_com_o_id` |
| M07 | `digitar` quebra com `Enter` — *spec* | MORTO | `test_leg01_digitar_nao_envia_nada_e_o_editor_fica_identico` |
| M08 | `digitar` usa `type(texto)` inteiro (`\n` vira `Enter`) — *spec* | MORTO | idem |
| M09 | `digitar` perde as linhas em branco | MORTO | idem |
| M10 | laço ignora `None` da foto (posta sem foto) — *spec* | MORTO | `test_fot03_sem_foto_volta_a_p_sem_post_e_sem_d` |
| M11 | `preparar` devolve caminho sem imagem | MORTO | `test_fot03_sem_oferta_e_sem_placeholder_none_e_nada_gravado` |
| M12 | placeholder de área fixa em `foto.py` | MORTO | `test_fot02_404_da_oferta_usa_placeholder_da_area_da_linha` |
| M13 | foto esticada (sem proporção) | MORTO | `test_fot01_retrato_vira_quadrado_branco_com_proporcao` |
| M14 | fundo preto | MORTO | idem |
| M15 | salva PNG | MORTO | idem |
| M16 | ordem: `velha` antes de `outro_dia` | MORTO | `test_esc04_ontem_e_velha_vira_outro_dia_e_inativa_vira_expirou` |
| M17 | ordem: `expirou` depois de `outro_dia` | MORTO | idem |
| M18 | `velha` com `>=` | MORTO | `test_esc03_fila_de_4h_velha_e_3h_ainda_vale` |
| M19 | `outro_dia` ignorado | MORTO | `test_esc04_pendente_de_ontem_outro_dia_mesmo_recente` |
| M20 | SQL do dia conta só `E` | MORTO | `test_enviados_do_dia_contam_e_e_d` |
| **M21** | `D` gravado com `DT_ENVIO = None` (o `D` do próprio programa não conta no teto) | **VIVO** | — lacuna 1 |
| M22 | não grava `D` antes do clique | MORTO | `test_rit01_dia_simulado_teto_40_janela_8_22` (e `test_est01_…`) |
| M23 | pausa com 2 falhas | MORTO | `test_pau01_tres_falhas_pausa_com_um_aviso_e_zero_tentativas` |
| M24 | pausa não bloqueia tentativas | MORTO | idem |
| M25 | `habilitado` ignorado no laço | MORTO | `test_cfg01_habilitado_false_zero_tentativas_na_volta_seguinte` |
| M26 | `habilitado` ignorado no config | MORTO | idem |
| M27 | confirmação ignora o relógio `msg-time` | MORTO | `test_dom_rede_caida_balao_com_relogio_nao_confirma` (Chromium) |
| M28 | `BESAVE_VIGIA_ROBOS` ignorado | MORTO | `test_vig01_ambiente_real_le_a_variavel` |
| M29 | `pede_qr` não aplicado ao publicador | MORTO | `test_vig01_publicador_com_qr_avisa_sem_reiniciar` |
| M30 | unidade sem `SuccessExitStatus=130` | MORTO | `test_uni01_publicador_unit_inteira` |
| M31 | sem confirmação vira `E` | MORTO | `test_est03_sem_confirmacao_fica_d_e_avisa_com_o_id` |
| M32 | falha antes do clique não conta | MORTO | `test_est02_falha_antes_do_clique_volta_a_p_e_conta` |
| M33 | sem aviso "voltou" | MORTO | `test_pau02_volta_avisa_voltou` |
| M34 | QR não impede tentar | MORTO | `test_qr01_deslogado_avisa_sem_tentar` |
| M35 | escolhe a mais antiga | MORTO | `test_esc01_escolhe_a_mais_recente` |
| M36 | `D` sem aviso | MORTO | `test_est03_sem_confirmacao_fica_d_e_avisa_com_o_id` |
| M37 | navegador morto sai com 0 | MORTO | `test_lim01_navegador_morto_sai_com_codigo_1` |
| M38 | batimento só em volta com post | MORTO | `test_bat01_bate_a_cada_volta_mesmo_sem_post` |
| M39 | sono sem variação | MORTO | `test_rit04_sono_com_variacao_de_30_porcento` |
| M40 | início do dia em UTC | MORTO | `test_rit01_dia_simulado_teto_40_janela_8_22` |
| M41 | comparação do editor sempre igual | MORTO | `test_leg02_comparacao_do_editor_so_tolera_o_invisivel` |
| M42 | exceção na página não recarrega | MORTO | `test_est02_falha_antes_do_clique_volta_a_p_e_conta` |
| M43 | lembrete da pausa nunca | MORTO | `test_pau01_nova_pausa_na_mesma_ocorrencia_nao_avisa_e_lembra_em_6h` |
| M44 | `PARAMETROS_ENVIO` lido uma vez só | MORTO | `test_rit04_parametros_lidos_a_cada_volta` |
| M45 | `max_horas_fila` padrão 4 | MORTO | `test_cfg02_padroes` |
| M46 | drop-in da inst2 com `lojas,whatsapp` | MORTO | `test_uni01_dropin_da_inst2_vigia_so_o_publicador` |
| **M47** | confirmação aceita qualquer balão novo (sem a chave da legenda) | **VIVO** | — lacuna 2 |
| M48 | pausa de 30 min | MORTO | `test_pau01_tres_falhas_pausa_com_um_aviso_e_zero_tentativas` |
| M49 | lembrete a cada 3 h | MORTO | `test_pau01_nova_pausa_na_mesma_ocorrencia_nao_avisa_e_lembra_em_6h` |
| M50 | aviso de QR a cada volta | MORTO | `test_qr01_deslogado_avisa_sem_tentar` |
| M51 | sem fallback colar → digitar | MORTO | `test_dom_leg02_colar_que_perde_linhas_cai_para_digitar` (Chromium) |
| M52 | `timeout_post_segundos` padrão 120 | MORTO | `test_cfg02_padroes` |
| M53 | `id_canal` padrão 1 | MORTO | `test_cfg02_padroes` |
| **M54** | laço passa área fixa (`"outros"`) para a foto em vez de `linha.area_slug` | **VIVO** | — lacuna 3 |
| **M55** | sem limpeza (`Escape`) depois de post confirmado | **VIVO** | — lacuna 4 |
| M56 | fim da pausa não zera `falhas_seguidas` | EQUIVALENTE | `_contabilizar` já zera o contador ao entrar na pausa (`pub/publicador.py`, `self.pausa_ate, self.falhas_seguidas = agora + PAUSA, 0`) |

Mutantes que a spec do dono cita (sem teto, reenvia `D`, `\n` como `Enter`, posta sem foto) e os pedidos no
prompt (ordem de descarte, `>=` no `velha`, `outro_dia`, `D` no teto via SQL, `D` antes do clique, pausa com 2
falhas, pausa sem bloquear, `habilitado`, `msg-time`, `BESAVE_VIGIA_ROBOS`, `pede_qr`, `SuccessExitStatus`):
**todos mortos**. "`D` não contado no teto" morre na forma SQL (M20), mas sobrevive na forma do laço (M21).

---

## 4. Itens conferidos por leitura (sem mutante dedicado)

- Isolamento: `main.py` e `pub/` não importam `capture-*` nem mexem em `sys.path`
  (`tests/test_pub_isolamento.py:11-17`); o perfil é `publish-whatsapp-channel/.chrome_perfil`, próprio.
- Regra 3 da spec (não lê nem responde mensagens): `pub/canal_web.py` só abre o canal, anexa, escreve,
  envia e lê os últimos balões do próprio canal para confirmar. OK.
- Regra 5 / regra 11: sem telefone, IP, token ou convite no programa (`tests/test_pub_isolamento.py:20-26`);
  `redigir_dom` tira telefones e URLs; avisos redigem token e URL (`tests/test_pub_fila.py:127-137`).
- Dependências: `requirements.txt` com Playwright, Pillow e oracledb (já usados pelos robôs); Pillow entra em
  `requirements-dev.txt` para o CI (justificado no spec.md).

---

## 5. Lacunas (ranqueadas)

**Ciclo 2:** 1–4 **resolvidas** pelo `0eaf0a6` (testes em `tests/test_pub_publicador.py:364-388`,
`tests/test_pub_canal_web.py:185-192`, `tests/pub_falso.py:131`, `:139`). Seguem abertas 5 (fixture
sintética, pendente do dono e bloqueante para o merge) e 6 (DOM fora do CI, decisão do dono). Texto do
ciclo 1 preservado abaixo.

1. **(resolvida no ciclo 2) M21 — o `D` gravado pelo programa contar no teto do dia não é provado (regra 1 da spec, RIT-03).**
   `test_rit03_d_de_hoje_conta_no_teto` monta o `D` à mão com `dt_envio`; nenhum teste usa o `D` que o próprio
   laço grava. Com `DT_ENVIO = None` no `marcar(P→D)` (`pub/publicador.py:166`), o `COUNT` do dia ignora o `D` e
   o teto pode ser passado — exatamente o cenário de rede ruim. O README promete isso (`README.md:89`).
   *Teste que falta:* `QT_MAX_DIA = 1`, uma `P` com `confirma = False` (vira `D`), outra `P` na volta seguinte
   dentro da janela → 0 envios; e/ou afirmar `dt_envio == local(T0)` da linha `D` em `test_est03_…`.
2. **(resolvida no ciclo 2) M47 — a confirmação não exige que o balão novo tenha o começo da legenda (spec 4.3).** Nenhum teste põe um
   balão novo de outro texto (outro admin do canal, por exemplo). *Teste que falta (DOM):* depois de `enviar`,
   injetar um balão novo sem relógio com outro texto e travar o envio real (ou rede caída) → `confirmar` dá
   `False`.
3. **(resolvida no ciclo 2) M54 — o laço passar `linha.area_slug` para o placeholder não é provado (FOT-02, "área da linha";
   lição 23).** `test_pub_foto.py` prova `preparar`; o `Mundo` falso ignora o slug. *Teste que falta:* o
   `_foto` falso registra `slug` e o teste afirma `DS_AREA_SLUG` da linha (ex.: `meu-lar`).
4. **(resolvida no ciclo 2) M55 — limpeza depois de post confirmado (spec item 6: "depois de cada tentativa").** Só o caminho de falha
   afirma `chamadas[-1] == "limpar"` (`tests/test_pub_publicador.py:148`). *Teste que falta:* depois de um `E`,
   `m.pagina.chamadas[-1] == "limpar"` (e o mesmo para `D`).
5. **Fixture sintética (não bloqueante para este ciclo, bloqueante para o merge).** A spec pede fixture gravada
   do WhatsApp Web real e redigida, com seletores capturados pelo VNC. O autor declarou a fixture sintética
   (`.specs/features/BSV-63/spec.md`, tabela de suposições; `README.md:91-104`; cabeçalho da fixture). Vai para
   o dono (§6).
6. **DOM fora do CI (não bloqueante).** Os `test_dom_*` pulam no CI; M27, M47 e M51 só são vistos localmente.
   Proposta do autor; decisão do dono.

Correção sugerida no ciclo 1 (feita no `0eaf0a6`): um commit só de testes fechando 1–4; o ciclo 2 repetiu
M21, M47, M54, M55.

---

## 6. Pendências do dono (bloqueiam o merge)

1. Teste real na inst2 com a branch, os 5 passos da spec: (1) QR lido e um dia com `QT_MAX_DIA 40` — posts
   iguais à legenda (negrito, riscado, cupom monoespaçado, `utm_source=whatsapp`, linhas em branco), foto
   quadrada sem virar figurinha, nenhum repetido; (2) derrubar a rede durante um envio — linha `D`, aviso, nada
   reenviado (lição 29); (3) `habilitado: false` para na volta seguinte; (4) `free -m` e RSS do Chromium após
   24 h (fecha `MemoryHigh`/`MemoryMax` provisórios da unidade); (5) prints do canal redigidos, olhados antes
   da PR (lição 19).
2. Seletores reais: `python main.py --gravar-dom` na inst2, conferir cada âncora de `pub/canal_web.py`
   (aba de canais, anexo, legenda, enviar, `msg-time`, QR ainda **não conferidos**), trocar a fixture
   sintética pela gravada e redigida (revisar nomes de contatos — regra 11) e rodar de novo os `test_dom_*`.
3. Pré-condições da spec: número de publicação admin do canal; VNC, Python 3.12 e Chromium ARM64 na inst2.
