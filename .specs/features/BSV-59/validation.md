# BSV-59 Validation

## Validation: BSV-59 - PASS

**Result**: PASS ✅ (veredito final, iteração 2, `6b3ece7..77aab68`).
- O commit `77aab68` (T5) fecha as cinco lacunas da iteração 1.
- Todos os mutantes relevantes morrem, somadas as duas rodadas (45 mutantes distintos).
- O único sobrevivente é o M38, equivalente.
- A suíte de `tools` ficou verde duas vezes, uma delas com a máquina carregada.
- Continua **bloqueando o merge**: a execução real do dono na inst1 (os 5 passos da spec).

**Iteração 1** (`6b3ece7..4ee10b7`): FAIL. O M11 (`float(price)`, regra 4) sobreviveu, e a suíte teve uma execução
vermelha intermitente sob carga (lacuna 2). Detalhes abaixo, mantidos como histórico.

**Date**: 2026-11-11
**Spec**: `docs/specs/BSV-59.md` (fonte; o Critério de aceite vence) e `.specs/features/BSV-59/spec.md` (EARS)
**Diff range**: `6b3ece7..77aab68` (base = `origin/develop`; commits `24ba32a`, `9db40a6`, `6461665`, `4ee10b7`,
`77aab68`). A iteração 1 cobriu `6b3ece7..4ee10b7`.
**Verifier**: Verifier sub-agente independente (autor ≠ verificador). Não escreveu o código nem os testes, e não
alterou nenhum dos dois.

---

## Iteração 2 (`77aab68`, T5: correções do Verifier)

### O que mudou (`git show --stat 77aab68`)

| arquivo | mudança |
| ------- | ------- |
| `tools/capture-store-pages/core/shopee_api.py:131` | `_chamar` captura também `http.client.HTTPException` (resposta cortada → `api_indisponivel`) |
| `tools/capture-store-pages/core/shopee_api.py:261` | `resolver` captura também `http.client.HTTPException` → `api_indisponivel` |
| `tools/tests/test_shopee_api.py:140` | caso `"12345678901234567.89"` no parametrize do preço (lacuna 1, M11) |
| `tools/tests/test_shopee_api.py:62,71-72` | servidor falso: escrita protegida contra socket fechado, `daemon_threads = False` e `handle_error` silencioso (lacuna 2) |
| `tools/tests/test_shopee_api.py:232` | `test_err01_resposta_cortada_indisponivel` (`Content-Length` maior que o corpo → `IncompleteRead`) |
| `tools/tests/test_shopee_api.py:354` | `test_res_protocolo_quebrado_e_passageiro` (`HTTPException` no resolver) |
| `tools/tests/test_shopee_lote.py:198` | `assert gravado["url_final"] == f"https://shopee.com.br/product/{SHOP}/{item(1)}"` (lacuna 3, M33) |
| `tools/tests/test_shopee_lote.py:114,167` | `img_root = tmp_path` (lacuna 5) |

O diff não toca `tools/capture-chat-groups/`, `stores/` nem nenhum teste existente fora dos dois arquivos do ticket.

### Gates (iteração 2)

| gate | resultado |
| ---- | --------- |
| `cd tools && python -m pytest -q -p no:cacheprovider`, execução 1 (máquina quase livre) | ✅ **509 passed**, 0 failed, 0 errors (215 s) |
| execução 2, **sob carga**: em paralelo, o sensor de mutantes num worktree temporário e 5 repetições seguidas de `test_shopee_api.py` + `test_shopee_lote.py` | ✅ **509 passed**, 0 failed, 0 errors (222 s) |
| as 5 repetições dos testes do ticket (rodaram em paralelo com o item acima) | ✅ 5 × **82 passed** |
| `grep "Exception occurred\|UnicodeDecodeError"` nas 7 saídas acima | 0 ocorrências |
| `python -m ruff check vps/ tests/` | All checks passed |
| `ruff` em `core/shopee_api.py` e `core/bloqueio.py` | All checks passed |
| `cd tools/capture-chat-groups && python -m unittest discover -s tests` | 15 OK |
| `shellcheck vps/*.sh` | não executado (não está no PATH); nenhum `.sh` no diff |
| `tools/img` depois das execuções | não existe (lacuna 5 resolvida) |

Delta: 506 → 509 testes. Os 3 novos são o caso de preço grande, a resposta cortada e a `HTTPException` no resolver.

### Sensor de discriminação (iteração 2)

- Worktree temporário com `git worktree add --detach … 77aab68` no scratch; removido ao fim.
- Testes rodados em cada mutante: `test_shopee_api.py`, `test_shopee_lote.py` e `test_pausa_lojas.py`. A linha de
  base, sem mutante, deu 99 passed.
- Isolamento: o `git status --porcelain` da árvore real ficou igual antes e depois (só o `validation.md`, sem
  commit).

| # | Mutante | Resultado | Teste que matou |
| - | ------- | --------- | --------------- |
| M11 | (h) `Decimal(float(price))` | **morto** (era sobrevivente) | `test_pro01_preco_em_decimal_duas_casas[12345678901234567.89-…]` |
| M33 | `url_final` = URL do grupo | **morto** (era sobrevivente) | `test_pro01_linha_da_shopee_vira_ok_com_as_chaves_da_api` |
| M38 | `status != 200` → `status >= 500` | sobreviveu: **equivalente** (`urlopen` já levanta `HTTPError` para ≥ 400) | - |
| N1 | `HTTPException` fora do `except` de `_chamar` | morto | `test_err01_resposta_cortada_indisponivel` |
| N2 | `HTTPException` fora do `except` de `resolver` | morto | `test_res_protocolo_quebrado_e_passageiro` |
| N3 | `HTTPException` no resolver → `url_nao_reconhecida` (`'9'` em vez de retida) | morto | `test_res_protocolo_quebrado_e_passageiro` |
| N4 | `url_final` limpo mais `?utm_source=an_x` | morto | `test_pro01_linha_da_shopee_…` |
| N5 | imagem em `img/<captura>`, ignorando `img_root` | morto | `test_pro01_linha_da_shopee_…` |
| N6 | `HTTPException` em `_chamar` → `fora_do_programa` | morto | `test_err01_resposta_cortada_indisponivel` |

**Iteração 2**: 9 mutantes, 8 mortos e 1 equivalente. **Total das duas rodadas**: 45 mutantes distintos; 44 mortos
e 1 equivalente (M38); nenhum sobrevivente relevante.

### Situação das lacunas da iteração 1

| # | lacuna | situação |
| - | ------ | -------- |
| 1 | M11, `float(price)` | ✅ fechada (`tools/tests/test_shopee_api.py:140`; M11 morto) |
| 2 | gate intermitente sob carga | ✅ fechada (`tools/tests/test_shopee_api.py:62,71-72`; 509 passed sob carga, 0 traceback) |
| 3 | M33, `url_final` não asserido | ✅ fechada (`tools/tests/test_shopee_lote.py:198`; M33 e N4 mortos) |
| 4 | `HTTPException` fora do `try` | ✅ fechada (`tools/capture-store-pages/core/shopee_api.py:131,261`; N1, N2, N3 e N6 mortos) |
| 5 | pastas `tools/img` no checkout | ✅ fechada (`tools/tests/test_shopee_lote.py:167`; nenhuma pasta criada) |

Nenhuma lacuna aberta. Continua **bloqueando o merge** a execução real do dono na inst1 (5 passos do critério "Real").

---

# Iteração 1 (histórico)

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 assinatura e cliente GraphQL | ✅ Done | ver lacuna 1 (M11) |
| T2 resolução da URL | ✅ Done | - |
| T3 integração no lote e pausa | ✅ Done | ver lacunas 2, 3 e 4 |
| T4 README e SQL | ✅ Done | - |

---

## Gate Check (job `tools` do CI, lição 21)

| gate | comando | resultado |
| ---- | ------- | --------- |
| unittest (chat-groups) | `cd tools/capture-chat-groups && python -m unittest discover -s tests` | 15 OK |
| pytest, 1ª execução | `cd tools && python -m pytest -q -p no:cacheprovider` | ❌ **1 failed, 447 passed, 117 errors** (254 s). Rodou em paralelo com o 1º lote de mutantes, com a máquina carregada. Causa na lacuna 2. |
| pytest, 2ª execução | mesmo comando, sem carga | ✅ **506 passed**, 0 failed, 0 skipped (210 s) |
| repetição dos testes do ticket | `pytest tests/test_shopee_api.py tests/test_shopee_lote.py`, 6× com saída redirecionada | 6 × 79 passed; nenhum traceback de thread |
| ruff do CI | `cd tools && python -m ruff check vps/ tests/` | All checks passed |
| ruff nos módulos novos/alterados | `ruff check capture-store-pages/core/shopee_api.py capture-store-pages/core/bloqueio.py` | All checks passed |
| ruff `main.py` contra a base | `main.py` de `HEAD` contra `git show 6b3ece7:…/main.py` | 16 = 16 violações (BLE001×9, S110×5, I001×1, F401×1); nenhuma nova |
| shellcheck | `shellcheck vps/*.sh` | **não executado**: `shellcheck` não está no PATH. Nenhum `.sh` mudou no diff. |

- Testes novos: `tools/tests/test_shopee_api.py` e `tools/tests/test_shopee_lote.py`. Os testes existentes não
  foram alterados nem apagados: `git diff --stat` só cita arquivos novos de teste.
- Escopo: o diff não toca `tools/capture-chat-groups/`, `stores/amazon.py` nem `stores/mercadolivre.py` (regra 6).

---

## Spec-anchored check: Critério de aceite de `docs/specs/BSV-59.md`

| Critério | Outcome da spec | Evidência (`file:line` - asserção) | Result |
| -------- | --------------- | ---------------------------------- | ------ |
| Assinatura: vetor fixo → hex calculado à mão | hex = SHA-256(app_id+ts+payload+secret) | `tools/tests/test_shopee_api.py:99` - `api.assinar(APP_ID, TS, '{"query":"{ ping }"}', SECRET) == "83c486ec…8f67c28"`. O Verifier recalculou o hex à parte e ele confere. | ✅ PASS |
| Assinatura: corpo é byte a byte o payload assinado; cabeçalho inteiro (lição 14) | `Authorization: SHA256 Credential=<id>, Timestamp=<ts>, Signature=<hex>` sobre os bytes enviados | `tools/tests/test_shopee_api.py:108` - `p["headers"]["Authorization"] == esperado(p["corpo"])`, com `esperado` montando o cabeçalho inteiro a partir dos bytes recebidos pelo servidor (`:91-93`) | ✅ PASS (M01, M28, M39 mortos) |
| Resolução: `s.shopee` → 301 `/opaanlp/<shop>/<item>` | ids | `tools/tests/test_shopee_api.py:280-281` - `resolver(CURTO) == ((SHOP, ITEM), None)` e `abrir.pedidos == [CURTO]` | ✅ PASS |
| Resolução: `-i.`, `/universal-link/…-i.`, `/product/` | ids, sem pedido | `tools/tests/test_shopee_api.py:293-294` (5 formatos parametrizados em `:284-290`) | ✅ PASS |
| Resolução: 4 saltos → `url_nao_reconhecida` | `(None, 'url_nao_reconhecida')`, 3 pedidos | `tools/tests/test_shopee_api.py:311-312` | ✅ PASS (M15 morto) |
| Resolução: página sem ids → `url_nao_reconhecida` | idem | `tools/tests/test_shopee_api.py:318` e, no lote, `tools/tests/test_shopee_lote.py:264` - `db.erros == [(1, "url_nao_reconhecida")]` | ✅ PASS |
| Resolução: o pedido do link curto não segue redirect | um pedido só | `tools/tests/test_shopee_api.py:363,367` - `abrir_sem_seguir(url, 2) == (301, "/destino-REDACTED")` e `vistos == [("HEAD", "/REDACTED1")]` (servidor real) | ✅ PASS (M08 morto) |
| Produto: 1 nó → chaves da tabela do item 4 | título com trim, preço, nota, vendas, comissão em %, `<shop>.<item>`, url_afiliado, `img_1.jpg` | `tools/tests/test_shopee_api.py:117-125` (dict inteiro); `tools/tests/test_shopee_lote.py:188-196` (gravado + `download_image` para `img/1/img_1.jpg`) | ✅ PASS (M22, M23, M24, M34 mortos) |
| Produto: `"89.99"` → 89.99; `"19.9"` → 19.90 | `VR_PRECO_1` com 2 casas | `tools/tests/test_shopee_api.py:131-136`; `tools/tests/test_shopee_lote.py:206-210` | ✅ PASS (ver lacuna 1: regra 4, `float`) |
| Produto: price vazio/não numérico → `'9' item_divergente` | `'9'` | `tools/tests/test_shopee_api.py:167-170` (`""`, `"abc"`, `None`, `"NaN"`, `"0"`, `"-5"`); `tools/tests/test_shopee_lote.py:251,256` | ✅ PASS (M40 morto) |
| Produto: 0 nó → `'9' fora_do_programa` | `'9'` | `tools/tests/test_shopee_api.py:154`; `tools/tests/test_shopee_lote.py:248,256` - `db.erros == [(1, motivo)] and 1 not in db.capturas` | ✅ PASS (M12 morto) |
| Produto: nó de outro `itemId` → `'9' item_divergente` | `'9'` | `tools/tests/test_shopee_api.py:159`; `tools/tests/test_shopee_lote.py:249` | ✅ PASS (M09 morto) |
| Produto: 20 nós (o caso do `matchId`) → `'9' item_divergente` | `'9'` | `tools/tests/test_shopee_api.py:163-164`, com o 1º nó sendo o item certo | ✅ PASS (M10 morto) |
| Link: `originUrl` exato mesmo com `utm_source=an_<terceiro>`; `DS_URL_AFILIADO` = `shortLink` | `https://shopee.com.br/product/<shop>/<item>` | `tools/tests/test_shopee_lote.py:218-221`; `tools/tests/test_shopee_api.py:179-180` | ✅ PASS (M07 morto) |
| Sem navegador com `habilitado: true` | nenhuma navegação à Shopee, nem `_shopee`/`_aba_shopee` | `tools/tests/test_shopee_lote.py:226-228` - `amb.navegou == [amz(2)]`, gerador sem `shopee`/`_shopee`/`_aba_shopee` | ✅ PASS (M06 morto) |
| Desligado: `false` ou bloco ausente → navegador; o mutante falha nos dois sentidos | navegador chamado, API não chamada | `tools/tests/test_shopee_lote.py:232-243` (bloco ausente, `false` e sem a chave `habilitado`) mata o "sempre ligado"; `:183-198` e `:224-228` matam o "sempre desligado" | ✅ PASS (M04, M05, M06 mortos) |
| Erros com HTTP 200: `10020` (`Invalid Signature`, `Request Expired`) → `api_credencial` com a mensagem | motivo + mensagem | `tools/tests/test_shopee_api.py:189-195`, nas duas chamadas | ✅ PASS (M02, M30 mortos) |
| Erros com HTTP 200: `nodes: []` → `fora_do_programa`; outro código → `api_indisponivel`; decide por `errors` | idem | `tools/tests/test_shopee_api.py:207-209` (11001, código no log, corpo fora dele); `:212-214` (`errors` ganha de `data`) | ✅ PASS (M02, M03 mortos) |
| Erros: `10030` → `api_limite` (decisão da pré-condição) | `api_limite` | `tools/tests/test_shopee_api.py:201` | ✅ PASS (M19 morto) |
| Falhas: timeout → `retida(0)`, nada em `OFERTA`, ponteiro travado | `'0'`, sem gravação | `tools/tests/test_shopee_lote.py:274-278` - `oracle=retida(0)`, `1 not in db.capturas`, `db.erros == []`, `lojas.ponteiro == []`, `db.trava_ponteiro == 1` | ✅ PASS (M20 morto) |
| Falhas: 3 seguidas → pausa `shopee` + 1 aviso; volta → "voltou" e retida processada; Amazon/ML ok | idem | `tools/tests/test_shopee_lote.py:303-316` | ✅ PASS (M16, M25 mortos) |
| Falhas: erro de assinatura → aviso com "conferir app_id/app_secret" | texto no aviso | `tools/tests/test_shopee_lote.py:309-310`; sem credencial no aviso de indisponível: `:323` | ✅ PASS (M16 morto) |
| Falhas: passageiro nunca vira `'9'` (10020, 10030, 500, código desconhecido) | retida | `tools/tests/test_shopee_lote.py:281-288`; falha no link: `:291-294` | ✅ PASS (M13, M14, M32 mortos) |
| Segredo: nenhuma saída (stdout, log, exceção, CSV, Telegram) com `app_id`/`app_secret`/assinatura | ausência | `tools/tests/test_shopee_api.py:240-256` (cliente, `repr`, `detalhe`); `tools/tests/test_shopee_lote.py:335-350` (stdout, saídas, CSV, Telegram, lembrete) | ✅ PASS (M17, M18, M21 mortos) |
| Gates | pytest + ruff verdes | ver Gate Check | ⚠️ verde na 2ª execução; intermitente sob carga (lacuna 2) |
| Real (dono) | 5 passos na inst1 | - | ⏳ **bloqueia o merge**; fora do alcance do Verifier |

### Requisitos EARS (`.specs/features/BSV-59/spec.md`)

| Req | Coberto por | Result |
| --- | ----------- | ------ |
| CFG-01 | `tools/tests/test_shopee_lote.py:232-243` | ✅ |
| ASS-01 | `tools/tests/test_shopee_api.py:99,108` | ✅ |
| RES-01 | `tools/tests/test_shopee_api.py:280,293,297-304,363-367` | ✅ |
| RES-02 | `tools/tests/test_shopee_api.py:311,318,325,330`; `tools/tests/test_shopee_lote.py:264` | ✅ |
| PRO-01 | `tools/tests/test_shopee_api.py:117,135,143`; `tools/tests/test_shopee_lote.py:188-198` | ✅ (lacuna 1) |
| PRO-02 | `tools/tests/test_shopee_api.py:154,159,164,170`; `tools/tests/test_shopee_lote.py:256` | ✅ |
| LNK-01 | `tools/tests/test_shopee_lote.py:218-221` | ✅ |
| NAV-01 | `tools/tests/test_shopee_lote.py:226-228` | ✅ |
| ERR-01 | `tools/tests/test_shopee_api.py:194-236` | ✅ |
| FAL-01 | `tools/tests/test_shopee_lote.py:274-278,287-288` | ✅ |
| PAU-01 | `tools/tests/test_shopee_lote.py:303-331` | ✅ |
| SEG-01 | `tools/tests/test_shopee_api.py:255-256`; `tools/tests/test_shopee_lote.py:349-350` | ✅ |
| DOC-01 | `tools/tests/test_shopee_lote.py:357-368` (README, exemplo e SQL) | ✅ |

### Regras 1–6 da spec do dono (leitura do código)

| Regra | Evidência | Result |
| ----- | --------- | ------ |
| 1. Sem dependência nova | `tools/capture-store-pages/core/shopee_api.py:8-15`: só `hashlib`, `json`, `re`, `time`, `urllib`, `decimal`. Nenhum requirements alterado. | ✅ |
| 2. Segredo fora de log/exceção/CSV/Telegram | `shopee_api.py:44-45,105-106`: `__repr__` sem credencial. `:108-111` e `:128-132`: `_falha` imprime motivo e detalhe; exceção vira só o nome do tipo. `:148`: a mensagem do servidor é cortada em 120 caracteres. `main.py:497-499`: no `detalhe`, só o motivo. | ✅ |
| 3. `originUrl` limpa | `shopee_api.py:190`: monta a URL só com os ids inteiros. `main.py:507` grava `url_final` limpa (ver lacuna 3). | ✅ |
| 4. `Decimal`, nunca `float` | `shopee_api.py:61-68`: `Decimal(str(texto).strip())` e `quantize(Decimal('0.01'))`, sem `float`. O teste não discrimina (M11, lacuna 1). | ✅ código / ❌ teste |
| 5. `habilitado: false` = caminho de hoje | `shopee_api.py:50-52`: `is not True` → `None`. `main.py:636`: o ramo novo só entra com config, e o `else` é o bloco original intacto (diff só acrescenta o `elif`). | ✅ |
| 6. Amazon/ML/robô do WhatsApp intocados | `git diff --stat 6b3ece7..HEAD -- tools/capture-chat-groups tools/capture-store-pages/stores` vazio | ✅ |

---

## Discrimination Sensor

- Ambiente isolado: `git worktree add --detach` num diretório scratch, fora do repositório.
- Cada mutante: aplicado por substituição exata de texto e revertido com `git checkout -- .` dentro do
  worktree temporário.
- Testes rodados em cada mutante: `pytest -x tests/test_shopee_api.py tests/test_shopee_lote.py tests/test_pausa_lojas.py`.
  A linha de base, sem mutante, deu 96 passed.
- Execução: lotes de 10 (lição 13). O worktree temporário foi removido ao fim.
- Isolamento: o `git status --porcelain` da árvore real ficou vazio antes e depois.

| # | Mutante (pedido do dono entre parênteses) | Resultado | Teste que matou |
| - | ------------------------------------------ | --------- | --------------- |
| M01 | (a) corpo reserializado com `json.dumps` padrão depois de assinar o compacto | morto | `test_ass01_cabecalho_inteiro_e_corpo_e_o_payload_assinado` |
| M02 | (b) `errors` ignorado (`erros = None`) | morto | `test_err01_10020_com_http_200_e_credencial` |
| M03 | (b') `errors` só quando não há `data` (decide pelo 200 + data) | morto | `test_err01_errors_ganha_de_data_com_http_200` |
| M04 | (c) `ler_config` ignora `habilitado` (sempre ligado com bloco) | morto | `test_cfg01_…[bloco1]` |
| M05 | (c') `main` sempre com config (ligado mesmo sem bloco) | morto | `test_cfg01_…[None]` |
| M06 | (d) ramo da API nunca entra (sempre desligado) | morto | `test_pro01_linha_da_shopee_vira_ok_com_as_chaves_da_api` |
| M07 | (e) `originUrl` = URL do grupo | morto | `test_pro01_linha_da_shopee…` / `test_lnk01_…` |
| M08 | (f) abridor padrão (segue redirect) | morto | `test_res01_pedido_real_nao_segue_redirect` |
| M09 | (g) aceita o 1º nó sem conferir `itemId` | morto | `test_pro02_no_de_outro_item_divergente` |
| M10 | (g') aceita 20 nós (`len < 1`) | morto | `test_pro02_vinte_nos_caso_do_matchid_divergente` |
| M11 | (h) `Decimal(float(price))` | **SOBREVIVEU** | - (lacuna 1) |
| M12 | (i) `fora_do_programa` retido | morto | `test_pro02_falha_do_item_vira_9_com_motivo[fora_do_programa]` |
| M13 | (j) `api_limite` fora dos passageiros (vira `'9'`) | morto | `test_err01_falhas_da_api_retem_nunca_9[falha3]` |
| M14 | (j') `api_credencial` fora dos passageiros | morto | `test_err01_falhas_da_api_retem_nunca_9[falha0]` |
| M15 | (k) `MAX_PEDIDOS = 4` | morto | `test_res02_quatro_saltos_nao_reconhecida` |
| M16 | (l) aviso sem "conferir app_id/app_secret" | morto | `test_pau01_tres_seguidas_…` |
| M17 | (m) `app_id` no log de falha | morto | `test_seg01_nenhuma_saida_tem_credencial_nem_assinatura` |
| M18 | (m') `Authorization` impresso antes do POST | morto | `test_seg01_nenhuma_saida_…` |
| M19 | (n) `10030` → `api_indisponivel` | morto | `test_err01_10030_limite` |
| M20 | (o) `shopee_api_indisponivel` fora de `STATUS_RETER` (ponteiro avança) | morto | `test_fal01_timeout_retida_nada_gravado_ponteiro_travado` |
| M21 | `app_secret` no `detalhe` do `api_credencial` (vai ao Telegram) | morto | `test_seg01_nenhuma_saida_…` |
| M22 | comissão crua (`"0.13"`) em vez de percentual | morto | `test_pro01_um_no_do_item_vira_as_chaves_da_captura` |
| M23 | `id_produto_afiliado` só com o item | morto | idem |
| M24 | `download_image` removido | morto | `test_pro01_linha_da_shopee…` |
| M25 | motivo da pausa `PAGINA` em vez de `SHOPEE_API` | morto | `test_pau01_tres_seguidas_…` |
| M26 | 5xx/429 na resolução → `url_nao_reconhecida` | morto | `test_res_rede_ou_5xx_e_passageiro[resposta1]` |
| M27 | erro de rede na resolução → `url_nao_reconhecida` | morto | `test_res_rede_ou_5xx_e_passageiro[resposta0]` |
| M28 | ordem da assinatura trocada (secret antes do payload) | morto | `test_ass01_vetor_fixo` |
| M29 | `extrair_ids` sem conferir o host | morto | `test_res02_formato_estranho_…[exemplo.com.br]` |
| M30 | mensagem do 10020 vazia no `detalhe` | morto | `test_err01_10020_com_http_200_e_credencial` |
| M31 | lembrete sem o ramo `SHOPEE_API` | morto | `test_pau01_lembrete_mantem_o_motivo` |
| M32 | falha do `generateShortLink` ignorada | morto | `test_err01_falha_no_link_tambem_retem` |
| M33 | `url_final` = URL do grupo (link curto do terceiro) | **SOBREVIVEU** | - (lacuna 3; regra fora da letra da spec) |
| M34 | título sem `strip` | morto | `test_pro01_um_no_do_item_…` |
| M36 | `GET` em vez de `HEAD` na resolução | morto | `test_res01_pedido_real_nao_segue_redirect` |
| M37 | `shortLink` vazio aceito | morto | `test_lnk01_sem_short_link_retem` |
| M38 | `status != 200` → `status >= 500` | sobreviveu: **equivalente** | `urlopen` já levanta `HTTPError` para ≥ 400. A linha `shopee_api.py:133` só pega 2xx/3xx diferente de 200, e o mutante aceita 4xx que nunca chega ali. |
| M39 | `ts` em milissegundos | morto | `test_ass01_cabecalho_inteiro_…` |
| M40 | preço `0`/negativo aceito | morto | `test_pro02_preco_invalido_divergente[0]` |

**Total**: 39 mutantes. Mortos: 36. Sobreviventes: 3 (M11 relevante, M33 de baixa prioridade, M38 equivalente).

---

## Lacunas (ranqueadas)

1. **M11, regra 4 (`float(price)`), bloqueia o PASS.** Nenhum teste distingue `Decimal(str(price))` de
   `Decimal(float(price))`.
   - Onde: `tools/tests/test_shopee_api.py:131` parametriza só `"89.99"`, `"19.9"` e `"120"`, valores exatos em float
     depois do `quantize`.
   - Código hoje: `tools/capture-store-pages/core/shopee_api.py:63` está correto (sem `float`); a regra só não é
     travada por teste.
   - Correção sugerida: um caso que o float distorce, por exemplo `("12345678901234567.89", "12345678901234567.89")`.
     Como alternativa, `"19.995"`, mas aí o teste fixa também o modo de arredondamento.
2. **Gate intermitente sob carga (higiene de teste).** A 1ª execução da suíte completa deu 1 failed + 117 errors;
   a 2ª deu 506 passed; 6 repetições dos testes do ticket passaram. Mecanismo:
   - O servidor falso de `tools/tests/test_shopee_api.py:52` dorme (`atraso`) e depois escreve num socket que o
     cliente já fechou pelo timeout (`tools/tests/test_shopee_lote.py:268-272`, `tools/tests/test_shopee_api.py:228-231`).
   - A thread do handler sobrevive ao `fechar()`. O traceback de `socketserver` ("Exception occurred during
     processing of request") cai no stderr capturado do teste seguinte (`test_err01_falhas_da_api_retem_nunca_9[falha1]`).
   - No Windows pt-BR, com stdio em cp1252, a mensagem localizada do `WinError` corrompe o arquivo de captura do
     pytest (`UnicodeDecodeError` byte `0xe3`), e todos os testes seguintes da sessão viram ERROR.
   - Provável verde no CI Linux, mas a suíte do dono no PC pode ficar vermelha.
   - Correção sugerida: `fechar()` esperar as threads do handler (`daemon_threads=False` + `block_on_close`),
     ou o handler engolir `ConnectionError` ao escrever (`handle_error` silencioso).
3. **M33: `url_final` limpa não é asserida (baixa).** A decisão do autor (`main.py:507`, `url_final` =
   `https://shopee.com.br/product/<shop>/<item>`) é boa e segue o espírito da regra 3. Nenhum teste confere
   `DS_URL_FINAL` nem `url_besave`, e trocar por a URL do grupo passa. A regra 3 da spec só cita `originUrl` e
   `DS_URL_AFILIADO`, por isso é ⚠️ lacuna de precisão da spec, não defeito.
4. **Exceção fora do `try` no ramo da API (baixa, robustez; não é critério da spec).** O ramo
   `main.py:636-640` não está dentro do `try/except` do navegador.
   - `shopee_api.resolver` só captura `OSError`/`ValueError` (`shopee_api.py:260`), e `_chamar` captura
     `URLError`/`OSError`/`ValueError` (`shopee_api.py:130`).
   - `http.client.HTTPException` (`IncompleteRead`, `BadStatusLine`, `RemoteDisconnected` é `OSError`, os outros
     não) escaparia do lote inteiro, em vez de virar `api_indisponivel`.
   - Correção sugerida: incluir `http.client.HTTPException` nos dois `except`.
5. **Testes deixam pastas fora de `tmp_path` (baixa).** `test_shopee_lote.py` usa `img_root="img"`, e
   `_capturar_shopee_api` faz `os.makedirs` real. Cada `pytest` deixa `tools/img/{1,3,6}` vazias no checkout
   (invisíveis ao `git status`). O Verifier removeu as que a sua própria execução criou (vazias, dentro do worktree).
   Correção sugerida: `img_root=str(tmp_path)`.

Fora das lacunas: a pré-condição e os 5 passos reais na inst1 continuam **bloqueando o merge** (execução do dono).

---

## Code Quality

| Check | Pass? |
| ----- | ----- |
| Sem feature além da spec | ✅ |
| Sem abstração de uso único desnecessária | ✅ |
| Só arquivos da pasta do ticket (`tools/capture-store-pages/`, `tools/tests/`) | ✅ |
| Não "melhorou" código alheio | ✅ (o diff em `main.py` só acrescenta) |
| Segue o padrão do repo (`PausaLojas`, `STATUS_RETER`, config lida por lote) | ✅ |
| Testes mapeiam critério de aceite, não espelham implementação | ✅ (servidor HTTP real, expectativas calculadas à parte) |
| Valor asserido = valor da spec | ✅, exceto lacuna 1 (regra 4) |
| Evidência redigida (regra 11) | ✅ fixtures com `REDACTED` e credenciais fictícias; nada de caminho pessoal neste arquivo |

---

## Lições propostas (para o dono consolidar em `docs/DECISOES.md`/WORKFLOW)

1. **Teste com servidor HTTP falso e timeout precisa encerrar a thread do handler antes do próximo teste.** No
   Windows pt-BR, o traceback de `socketserver` com mensagem localizada derruba a captura do pytest e transforma o
   resto da sessão em ERROR. Isso parece regressão, mas é higiene de teste.
2. **Regra "nunca `float`" exige uma entrada que o `float` distorce** (mais de 15 dígitos significativos ou meio
   centavo). Com valores de 2 casas o mutante é indistinguível.
3. **Teste de lote usa `tmp_path` como `img_root`.** Pasta relativa cria lixo no checkout que o `git status` não
   mostra (é a lição 16, aplicada ao disco local).

---

## Iteração 3 — rebase sobre a BSV-57 (batimento)

**Result**: PASS ✅ para BAT-01 e BAT-02 (escopo desta iteração: só esses dois critérios).
**Date**: 2026-11-11
**Diff range**: `origin/develop` (`338602b`, merge da BSV-57) `..a411981`; a branch descende de `origin/develop`
(`git merge-base --is-ancestor` ok).
**Verifier**: Verifier sub-agente independente (autor ≠ verificador). Não alterou código nem testes.

### BAT-01 — cada linha da Shopee pela API renova o batimento

| evidência | file:line |
| --- | --- |
| Ramo da API dentro do mesmo `for pos, row in enumerate(rows)` das outras lojas, sem `continue`/`return`/`break` entre ele e o fim do laço | `tools/capture-store-pages/main.py:566`, `:636-640` |
| `bater_linha(out['status_captura'])` incondicional, logo depois de `out_rows.append(out)`, para toda linha (ok, `shopee_api_indisponivel` retida, `'9'`, `loja_pausada`) | `tools/capture-store-pages/main.py:912-913` |
| `bater_linha` só deixa de bater em `erro:` de navegador fechado; o caminho da API nunca produz esse status (devolve `ok`, `SHOPEE_API_INDISPONIVEL` ou o motivo) | `tools/capture-store-pages/core/batimento.py` (`navegador_fechado`, `bater_linha`); `main.py:485-517` |
| Teste: lote só de Shopee pela API (1 retida + 2 ok) → 3 batidas `linha`, prazo `13:10Z` = agora 13:00 + 10 min (regra da 57) | `tools/tests/test_shopee_lote.py:380-387` |
| Teste: linha que vira `'9'` (`fora_do_programa`) pela API → 1 batida `linha` | `tools/tests/test_shopee_lote.py:390-394` |

### BAT-02 — Shopee em pausa pela API: dorme sempre batendo, prazo = acordar + 10 min

| evidência | file:line |
| --- | --- |
| `dormir()` bate `dormindo` com `dorme_s=s` **antes** de `_esperar(s)`; é o único chamador de `_esperar` | `main.py:1027-1031` (grep: `_esperar(` só em `:317` def e `:1031`) |
| As três esperas do monitor passam por `dormir()`: banco fora, fila vazia (inclui fila só de lojas em pausa, com `retidas > 0`) e janela noturna | `main.py:1059-1060`, `:1061-1066`, `:1088-1090` |
| Toda volta bate `varredura` antes de ler a fila; validade bate antes de varrer | `main.py:1049`, `:1053` |
| Linha em pausa no meio do lote: ramo `pausa.em_pausa(loja)` → `loja_pausada`, sem rede, e cai no mesmo `bater_linha` | `main.py:632-635`, `:913` |
| Fila só de Shopee em pausa: `_sem_lojas_em_pausa` retém sem chamar a API, a fila fica vazia e o monitor vai a `dormir()` | `main.py:991-1002`, `:1061-1066` |
| Linha retida antes da pausa (1ª falha): o lote termina, o monitor relê na hora e bate `varredura`; nenhuma espera sem batida | `main.py:1079-1090` (sem `dormir()` fora da janela) |
| Outras esperas no arquivo: `time.sleep(2)` e `wait_for_timeout` estão no gate interativo de Chrome/login (antes do monitor) e no caminho do navegador, não no da API | `main.py:109`, `:135`, `:209`, `:656` |
| `bater` calcula `prazo = agora + dorme_s + 10 min` | `core/batimento.py` (`bater`, `PRAZO = timedelta(minutes=10)`) |
| Teste: pausa da Shopee pela API (3 erros de credencial), fila só de Shopee → esperas de 180 s, cada uma precedida de `dormindo` com prazo `13:13Z` = 13:00 + 3 min de sono + 10 min; a API não é chamada | `tools/tests/test_shopee_lote.py:420-435` |
| Teste: 1 falha passageira (retida, sem pausa) → fases `varredura, validade, linha, varredura, dormindo, varredura`; a única espera vem depois de `dormindo` | `tools/tests/test_shopee_lote.py:438-445` |

**Tempo máximo de uma linha pela API x prazo de 10 min.** `resolver` faz no máximo `MAX_PEDIDOS = 3` HEADs
(`core/shopee_api.py:203`, `:245-270`), depois `produto` e `link_afiliado` (1 POST cada, `:114-156`), todos com
`timeout = timeout_segundos` (padrão 20 s, `:19`; exemplo `conf/config.example.json:47` = 20), e a imagem com
`requests.get(..., timeout=30)` (`core/images.py:117`). Pior caso nominal: 3×20 + 2×20 + 30 = **130 s < 600 s**.
Sem `sleep` nem nova tentativa dentro do cliente. Ver lacuna 1 para os limites dessa conta.

**Valores asseridos vêm da spec**, não da implementação: 10 min (BSV-57, `PRAZO`), acordar + 10 min (13:00 + 3 min
de `intervalo_min=3` + 10 = 13:13), fases `linha`/`dormindo`/`varredura`. As batidas são capturadas trocando só
`gravar_atomico` e `agora_utc`; `bater`/`bater_linha` reais calculam o prazo.

### Sensor de discriminação (worktree descartável em scratchpad, removido com `git worktree remove`)

Comando por mutante: `cd tools && python -m pytest tests/test_shopee_lote.py tests/test_batimento_lojas.py -q`
(baseline: 44 passed).

| # | mutante | resultado | testes que pegaram |
| --- | --- | --- | --- |
| M1 | `bater_linha` só fora do caminho da API (`if not (loja == 'shopee' and shopee_cfg is not None)`) | **morto** (3 falhas) | `test_bat_api_cada_linha…`, `test_bat_api_linha_que_vira_9…`, `test_bat_retida_pela_api_antes_da_pausa…` |
| M2 | sem `bater_linha` no lote | **morto** (6) | os 3 acima + `test_bat07_linha_ok_renova`, `…_de_loja_em_pausa_renova`, `…_com_erro_comum_renova` |
| M3 | `dormir()` bate sem `dorme_s` (prazo = agora + 10) | **morto** (3) | `test_bat_pausa_api_shopee_dorme…`, `test_bat07_varredura_com_fila_vazia…`, `test_bat05_madrugada…` |
| M4 | `dormir()` chama `_esperar` antes de `bater` | **morto** (2) | `test_bat_pausa_api_shopee_dorme…`, `test_bat_retida_pela_api_antes_da_pausa…` |
| M5 | fila vazia bate `dormindo` só com `retidas == 0` | **morto** (2) | `test_bat_pausa_api_shopee_dorme…`, `test_bat07_fila_so_de_loja_em_pausa_renova` |

5/5 mortos, nenhum sobrevivente. Observação: o M4 só é pego pelos testes novos da BSV-59; os da 57 não checam a
ordem batida → espera (passam a checar indiretamente agora).

### Gates (lição 21)

| gate | resultado |
| --- | --- |
| `cd tools/capture-chat-groups && python -m unittest discover -s tests` | 15 tests OK |
| `cd tools && python -m pytest -q` | **650 passed** (217,99 s), 1ª execução, sem intermitência |
| `cd tools && python -m ruff check vps/ tests/` | All checks passed |
| `git status --porcelain` do worktree real antes e depois do sensor e dos gates | vazio nos dois |

### Lacunas (ranqueadas; nenhuma bloqueia BAT-01/BAT-02)

1. **Baixa — `timeout_segundos` sem teto** (`core/shopee_api.py:55-59`). A conta de 130 s só vale com o padrão:
   acima de ~114 s por chamada, 5 chamadas + imagem passam dos 10 min e o vigia pode reiniciar o robô no meio de
   uma linha. Além disso o timeout do `urllib` é por operação de socket (não total) e não cobre DNS. Sugestão:
   limitar `timeout_segundos` (p.ex. ≤ 60) em `ler_config`, com teste.
2. **Baixa, fora de BAT — exceção inesperada no caminho da API não é capturada** (`main.py:636-640` está fora do
   `try` do ramo do navegador). Não é espera sem batida (o processo cai e o vigia reinicia), mas um erro de
   parsing não previsto derruba o lote inteiro em vez de virar `erro:` na linha. As exceções de rede e JSON já
   são tratadas em `core/shopee_api.py:126-139` e `:260-262`.

Continua **bloqueando o merge**: a execução real do dono na inst1 (inclusive ver o batimento renovando durante
um lote de Shopee pela API e durante a pausa).
