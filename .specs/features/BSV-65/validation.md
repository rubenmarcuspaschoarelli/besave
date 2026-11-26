# Validation — BSV-65 — PASS

**Veredicto: PASS**

Verificador: Verifier independente (sub-agente distinto do autor; auto-verificação não conta como PASS).  
Branch: `rubenmarcus/rub-53-bsv-65`  
Data: 2026-11-25  
Ciclo de verificação: **2** (ciclo 1 deu FAIL por 4 mutantes sobreviventes, L1–L4; o autor fechou com o commit
`4a1e752`, só testes; este ciclo confirma PASS).  
Diff verificado: `af6cd54..4a1e752` (6 commits, c9fcaf8..4a1e752)

---

## Ciclo 2

`4a1e752` mexe só em `tools/tests/test_navegador_lote.py`, `tools/tests/test_navegador_recuperacao.py` e
`.specs/features/BSV-65/tasks.md`; nenhuma linha de produção mudou (`git show --stat 4a1e752`). Os testes novos
afirmam o resultado que a spec define:

| Lacuna | Teste novo | O que afirma (spec) | Mutante |
|---|---|---|---|
| L1 (Saída 6: `loja_pausada` não conta) | `tools/tests/test_navegador_lote.py:304` | depois de 1 linha sem `ok` (`tentativas_navegador == 1`), uma linha `loja_pausada` grava batimento e `tentativas_navegador` continua `1` | M24 **morto** |
| L3 (Saída 4/5: linha que vai para `'9'` não é retida) | `tools/tests/test_navegador_lote.py:321` | 3 timeouts da mesma linha (sequência isolada) → `NAV.retidas == 2` | M34 **morto** |
| L4 (Saídas 2/3a: aba nova nasce limpa) | `tools/tests/test_navegador_recuperacao.py:407` | evento `crash` + `Page crashed` na aba velha; no monitor a linha 1 é refeita na aba nova, `capturas == [1, 2]`, `erros == []`, **sem relançamento** (`lancados == []`), mensagens inteiras `[ABA_1, VOLTOU_1]` | M39 **morto** |
| L2 (Saída 3 no lote sem `--monitorar`) | `tools/tests/test_navegador_recuperacao.py:423` | `visitas == [(aba velha, 1), (nova, 1), (nova, 2), (nova, 3)]`, `out` com a retida duas vezes `[1, 1, 2, 3]`, `capturas == [1, 2, 3]`, `(gravadas, com_erro) == (3, 0)`, `[ABA_1, VOLTOU_1]` | M28 **morto** |

Sensor de novo, numa cópia isolada nova (`git worktree` em `4a1e752` no scratchpad, removida no fim;
`git status --porcelain` do worktree real igual ao de antes): **M24, M28, M34 e M39 mortos**, e a bateria inteira
rodada de novo sobre `4a1e752`: **42 mortos, 1 equivalente (M33), 0 sobreviventes**.

Gates do ciclo 2 (em `tools/`): `pytest tests/` **865 passed, 44 skipped** (270 s, exit 0); `ruff check vps/ tests/`
**All checks passed!**

L5 (vigia diz "voltou" depois de um reinício) fica registrada como **decisão do dono**, não bloqueia. L6 (D1, D2 e D5)
segue para confirmação do dono, também sem bloquear.

O que vem abaixo é o relatório do ciclo 1, mantido como evidência; as lacunas L1–L4 estão fechadas.

---

## Resumo (ciclo 1)

O código de produção cumpre as Saídas 1–9 e as Regras 1–5. **Não achei defeito de comportamento.** Todos os itens
listados no "Critério de aceite" da spec do dono têm teste e esse teste compara o valor que a spec define (mensagens
inteiras). Gates verdes no Windows e no WSL.

No ciclo 1 o veredito foi FAIL pelo sensor de discriminação: de 44 mutantes, **4 não equivalentes sobreviveram**
(M24, M28, M34, M39), comportamentos que a spec define (Saídas 2, 3, 5 e 6) sem teste. As quatro correções eram
**só de teste**; foram feitas no `4a1e752` (ver "Ciclo 2").

---

## Checagem por critério de aceite (spec do dono, `docs/specs/BSV-65.md` §Critério de aceite)

Caminhos relativos a `tools/`. "cód." = código; "teste" = asserção que prova.

| # | Critério | Veredito | Evidência |
|---|---|---|---|
| CA-1 | `Page crashed` no `goto`, `capture` e link de afiliado → linha `'0'`, `marcar_erro` não chamado, ponteiro travado, lote parado, aba nova; mutante sem `page crashed` morre | **PASS** | cód.: `capture-store-pages/main.py:841` (`quebrado = navegador.sinal(e)`), `main.py:1015-1019` (`oracle=retida(0)` + `_travar`), `main.py:1065` (`break`), `main.py:1234` (recupera no monitor), `core/link_afiliado.py:537` (relança). teste: `tests/test_navegador_lote.py:111` parametrizado em goto/capture/prepare/afiliado/imagens (`db.erros == []`, `ponteiro == [1]`, `3 not in amb.visitas`); aba nova: `tests/test_navegador_recuperacao.py:100` (`eventos == ["fecha_aba0","nova_aba@ctx0"]`) e `:268` (integração no monitor). M01 morto. |
| CA-2 | aba nova também quebrada → contexto fechado e relançado com o mesmo perfil; relançamento falhando → código 3 e nenhum batimento depois | **PASS** | cód.: `main.py:506` (escala), `main.py:477-492` (`_fechar_contexto` → `launch_persistent` → `preparar_contexto`), `main.py:470-474`. teste: `test_navegador_recuperacao.py:122` (`ctx0.fechado`, `lancados == [("PLAYWRIGHT", False)]`, `preparados == ["ctx1"]`), `:136` (perfil = `browser.PERFIL_DIR`), `:172` (`code == 3`, `[NAO_REABRIU]`), `:285` (nenhum `batimento:` depois de `launch`). |
| CA-3 | 3 relançamentos em 60 min → código 3; 2 → segue | **PASS** (com interpretação, ver D1) | cód.: `core/navegador.py:103-107`. teste: `test_navegador_recuperacao.py:188` (2 seguem), `:195` (3º em 59 min → `code == 3`, `len(lancados) == 2`), `:207` (61 min → segue). |
| CA-4 | 2 timeouts → só retidas; 3 → recuperação; `ok` no meio zera; mesma linha com 3 timeouts → `'9'` | **PASS** | cód.: `core/navegador.py:80-91`, `main.py:842-844`. teste: `test_navegador_lote.py:197`, `:206` (`pendente == "3 timeouts seguidos"`), `:214`, `:234` (`db.erros == [(1, "erro: TimeoutError: Page.goto: Timeout 60000ms exceeded")]`), `:244` (timeout fora do `goto` segue para `'9'`). |
| CA-5 | mensagens da Saída 5 inteiras; uma por ocorrência; "voltou" só depois de `ok` por navegador (Shopee não fecha) | **PASS** (D2) | cód.: `core/navegador.py:25,45-50`, `main.py:526-527`, `core/navegador.py:93-100`. teste: `test_navegador_recuperacao.py:8-11` (constantes inteiras), `:100` (`enviados == [ABA_1]`), `:112` (texto inteiro com `3 timeouts seguidos` e `3 linha(s)`), `:122` (`[ABA_1, RELANCADO_1]`), `:172` (`[NAO_REABRIU]`); `test_navegador_lote.py:254` (um "voltou" só), `:266` (Shopee API não fecha). M37 (2 mensagens) morto. |
| CA-6 | batimento: linha quebrada não renova; campos da Saída 6 atualizados (Shopee não mexe) | **PASS** (L1 fechada no ciclo 2: `tests/test_navegador_lote.py:304`) | cód.: `core/batimento.py:76-79,83-89,92-95`, `main.py:854-857`. teste: `test_navegador_lojas.py:48`, `:58` (valores ISO e contagem); `test_navegador_lote.py:280` (`bat == []`), `:286` (Shopee mantém `tentativas == 2`; ok zera). |
| CA-7 | vigia: 10 + 61 min → aviso; 9 ou 59 min → nada; sem campos → nada; sem reinício | **PASS** | cód.: `vps/vigia_robos.py:50-51,242-251,589-609`. teste: `tests/test_vigia_navegador.py:30` (aviso inteiro, `restarts() == []`), `:38` (61/9, 59/10, 60/10), `:44`, `:50` (lembrete em 2 h), `:67` ("voltou" inteiro), `:81`, `:91`. M10, M11, M12 mortos. |
| CA-8 | diagnóstico: `/proc` simulado → linha inteira; arquivo ilegível → `?`; evento `crash` → linha | **PASS** | cód.: `core/navegador.py:127-197`, `main.py:443-446`. teste: `test_navegador_lojas.py:97` (linha inteira), `:103`, `:116` (linha inteira com `?`), `:110`, `:129` (fora do Linux); `test_navegador_recuperacao.py:300`, `:308`. Conferido também no WSL contra o `/proc` real (sem exceção, todos os campos). |
| CA-9 | preventivo: 6 h e só entre lotes; `0` não relança; chave inválida → 6 com WARN; não conta para os 3 em 60 min; falha → código 3 | **PASS** | cód.: `main.py:1203-1204`, `main.py:530-535`, `core/navegador.py:109-118`, `core/estado.py:58-70`. teste: `test_navegador_recuperacao.py:326` (ordem `lote:inicio, lote:fim, fecha_contexto, launch`; sem Telegram; diagnóstico antes de fechar), `:337`, `:344`, `:351`, `:363`, `:373` (janela noturna); `test_navegador_lojas.py:142,148,153`. |
| CA-10 | `unittest discover` dos dois pacotes + `ruff` do job `tools` verdes; testes do vigia no WSL | **PASS** | ver Gates. |
| CA-11 | Execução real do dono (inst1) | **PENDENTE** — bloqueia o merge | ver última seção. |

### Saídas e Regras (conferência adicional)

| Item | Veredito | Evidência |
|---|---|---|
| Saída 1 (uma função; `navegador_fechado` usa) | PASS | `core/navegador.py:14-37`; `core/batimento.py:92-95` |
| Saída 2 (todas as fases, lote para) | PASS | `main.py:171` (ponte), `:770` (prepare), `:841` (goto/capture/imagens/afiliado), `:845-848` (evento `crash`), `:1065`; teste `test_navegador_lote.py:111,172` |
| Saída 3 a/b/c | PASS | `main.py:495-527`, `:477-492`, `:470-474` |
| Saída 4 | PASS | `core/navegador.py:80-91`; `main.py:842-844` |
| Saída 5 | PASS | ver CA-5 |
| Saída 6 | PASS (L1 fechada no ciclo 2) | `main.py:678,758,854`; `vps/vigia_robos.py:589-609` |
| Saída 7 (README) | PASS | `capture-store-pages/README.md:153` (seção), `:187` (código 3), `:213` (preventivo), `:225` (`DT_OFERTA >= SYSDATE - 1`) |
| Saída 8 | PASS | ver CA-8 |
| Saída 9 | PASS | ver CA-9; `conf/config.example.json:20` |
| Regra 1 | PASS | `main.py:1015-1019` (retida antes do ramo de `'9'`); M08 morto |
| Regra 2 | PASS | grep do diff: nenhum `in str(e)` novo; `SINAIS_*` só em `core/navegador.py` |
| Regra 3 | PASS | mensagens comparadas inteiras (CA-5, CA-7, CA-8) |
| Regra 4 | PASS | sem import novo fora da stdlib; chave opcional; sem unidade nem banco no diff |
| Regra 5 | PASS | mensagens e log novos sem URL (`_primeira_linha` só no motivo do relançamento; o Telegram usa texto fixo) |

### Ajustes em testes existentes (legítimos)

- `tests/conftest.py:48-49`: zera o estado de processo `batimento._navegador` por teste (isolamento; não afrouxa nada).
- `tests/test_batimento_lojas.py:206-209`: o dict comparado inteiro ganhou os dois campos da Saída 6 — a comparação
  continua exata.
- `tests/test_sem_perguntas.py:20-21`: `Pagina.on` falso, porque `_nova_page` agora registra o evento `crash`.

Só acréscimos; nenhuma asserção removida ou afrouxada.

### Divergências entre a spec do dono e as suposições do autor

| # | Ponto | Interpretação do autor | Avaliação |
|---|---|---|---|
| D1 | "3 relançamentos em 60 min" | o **3º pedido** de relançamento por falha em 60 min sai com código 3 **sem relançar** (só 2 relançamentos de fato) | Aceitável: bate com "3 → código 3; 2 → segue" e é a leitura mais conservadora. O dono confirma. |
| D2 | Escalonamento | relança quando quebra de novo **sem nenhum `ok` desde a recuperação anterior** (não só na 1ª navegação da aba nova); depois de um relançamento, nova quebra sem `ok` relança de novo; cada recuperação manda sua mensagem | Aceitável: mais estrito que a Saída 3b e limitado pelo D1. Efeito: uma sequência sem `ok` gera "aba nova" e depois "navegador relancado" (2 mensagens). Leio cada recuperação como uma ocorrência; o dono confirma. |
| D3 | `ultimo_ok_navegador` antes do 1º `ok` | instante do 1º batimento do processo | Aceitável, com efeito colateral: depois de um reinício (código 3 → vigia), o vigia manda "voltou a capturar pelo navegador" sem nenhum `ok` ainda (o campo andou). A spec diz "quando o campo volta a andar", então está conforme a letra, mas a mensagem pode enganar. Lacuna de precisão L5. |
| D4 | Testes em `tools/tests/` (pytest) | a spec do dono fala em `unittest discover` "dos dois pacotes" | Aceitável: é onde vivem os testes do robô das lojas e o que o job `tools` roda (`pytest`, `.github/workflows/ci.yml:170-172`). |
| D5 | Texto da Saída 5 `(<sinal>: Page crashed \| 3 timeouts seguidos)` | renderiza `(Page crashed)` / `(3 timeouts seguidos)`; com os sinais de "fechado", a primeira letra vira maiúscula (`Has been closed`) | Aceitável; precisão da spec (não diz a forma exata do sinal). |
| D6 | Texto do aviso do vigia | criado pelo autor (a spec não define) | Aceitável; testado inteiro (`tests/test_vigia_navegador.py:9-10`). |

---

## Gates

| Gate | Onde | Resultado |
|---|---|---|
| `python -m pytest -q -p no:cacheprovider tests/` | `tools/` (Windows) | **861 passed, 44 skipped**, 333 s, exit 0 |
| `python -m ruff check vps/ tests/` | `tools/` | **All checks passed!** |
| `python -m unittest discover -s tests` | `tools/capture-chat-groups/` | **Ran 15 tests, OK** |
| `python3 -m pytest … test_vigia_navegador.py test_vigia_robos.py test_navegador_lojas.py` | WSL (lição 32) | **99 passed** |
| `navegador.diagnostico()` contra o `/proc` real | WSL | linha completa, sem exceção |

---

## Sensor de discriminação

Cópia isolada em `git worktree` no scratchpad (removida no fim; `git status --porcelain` do worktree real igual ao de
antes). Base: 92 passed nos arquivos `test_navegador_*.py`, `test_vigia_navegador.py`, `test_batimento_lojas.py`
(+ `test_sem_perguntas.py` nas rodadas).

| # | Mutante | Resultado | Teste que matou |
|---|---|---|---|
| M01 | tirar `'page crashed'` da classificação | morto | `test_navegador_lojas.py:22` |
| M02 | `>=` → `>` em `TIMEOUTS_SEGUIDOS` | morto | `test_navegador_lote.py:206` |
| M03 | `>=` → `>` em `TIMEOUTS_POR_LINHA` | morto | `test_navegador_lote.py:234` |
| M04 | `ok` não zera `seq_timeouts` | morto | `test_navegador_lote.py:214` |
| M05 | `pode_relancar` com `<=` | morto | `test_navegador_recuperacao.py:195` |
| M06 | preventivo conta na janela de relançamentos | morto | `test_navegador_recuperacao.py:351` |
| M07 | sem o `break` do lote | morto | `test_navegador_lote.py:111` |
| M08 | `retida_navegador` cai em `marcar_erro` | morto | `test_navegador_lote.py:111` |
| M09 | não chama `_travar` | morto | `test_navegador_lote.py:111` |
| M10 | vigia com `>= 60 min` | morto | `test_vigia_navegador.py:38` |
| M11 | vigia com `> 10` | morto | `test_vigia_navegador.py:30` |
| M12 | vigia reinicia (`systemctl restart`) | morto | `test_vigia_navegador.py:30` |
| M13 | diagnóstico sem tratar `meminfo` ilegível | morto | `test_navegador_lojas.py:103` |
| M14 | diagnóstico sem tratar `/proc` ilegível | morto | `test_navegador_lojas.py:116` |
| M15 | preventivo fora do topo da volta (removido entre lotes) | morto | `test_navegador_recuperacao.py:326` |
| M16 | `ok` da Shopee API conta como navegador | morto | `test_navegador_lote.py:221` |
| M17 | `bater_linha` renova com navegador quebrado | morto | `test_navegador_lojas.py:48` |
| M18 | `link_afiliado.capturar` engole `Page crashed` | morto | `test_navegador_lojas.py:160` |
| M19 | relançamento falho não sai com código 3 | morto | `test_navegador_recuperacao.py:172` |
| M20 | sem escalar para relançamento | morto | `test_navegador_recuperacao.py:122` |
| M21 | relançamento sem `preparar_contexto` | morto | `test_navegador_recuperacao.py:122` |
| M22 | `prepare` engole navegador quebrado | morto | `test_navegador_lote.py:111[prepare]` |
| M23 | evento `crash` ignorado no fim da linha | morto | `test_navegador_lote.py:111[imagens]` |
| **M24** | **`loja_pausada` conta em `tentativas_navegador`** | sobreviveu no ciclo 1; **morto no ciclo 2** | `test_navegador_lote.py:304` |
| M25 | timeout fora do `goto` também retém | morto | `test_navegador_lote.py:244` |
| M26 | chave inválida sem WARN | morto | `test_navegador_lojas.py:153` |
| M27 | `0` não desliga o preventivo | morto | `test_navegador_recuperacao.py:344` |
| **M28** | **lote sem `--monitorar` não retoma a linha retida** (`rows[len(out):]`) | sobreviveu no ciclo 1; **morto no ciclo 2** | `test_navegador_recuperacao.py:423` |
| M29 | "voltou" não zera `retidas` | morto | `test_navegador_recuperacao.py:159` |
| M30 | vigia nunca manda "voltou" | morto | `test_vigia_navegador.py:67` |
| M31 | `tentativas` não zera no `ok` | morto | `test_navegador_lojas.py:58` |
| M32 | ponte engole navegador quebrado | morto | `test_navegador_lote.py:172` |
| M33 | linha retida pelo navegador entra na contagem da pausa da loja | **equivalente** | os status retidos (`erro: …`) não estão em `STATUS_RETER` nem são `ok`; o `if retida_navegador: pass` (`main.py:860`) é defensivo |
| **M34** | **linha que vai para `'9'` no 3º timeout soma em `retidas`** | sobreviveu no ciclo 1; **morto no ciclo 2** | `test_navegador_lote.py:321` |
| M35 | janela de relançamentos de 120 min | morto | `test_navegador_recuperacao.py:207` |
| M36 | grava batimento antes do código 3 | morto | `test_navegador_recuperacao.py:285` |
| M37 | duas mensagens por recuperação | morto | `test_navegador_recuperacao.py:100` |
| M38 | recuperação não abre a ocorrência | morto | `test_navegador_recuperacao.py:159` |
| **M39** | **aba nova não zera `NAV.crash`** | sobreviveu no ciclo 1; **morto no ciclo 2** | `test_navegador_recuperacao.py:407` |
| M40 | `ok` por navegador não registra no batimento | morto | `test_navegador_lote.py:286` |
| M41 | evento `crash` não marca a aba | morto | `test_navegador_recuperacao.py:300` |
| M42 | recuperação sem linha de diagnóstico | morto | `test_navegador_recuperacao.py:308` |
| M43 | monitor não chama a recuperação | morto | `test_navegador_recuperacao.py:268` |

**Total ciclo 1: 43 mutantes, 38 mortos, 4 sobreviventes, 1 equivalente. Ciclo 2 (bateria inteira sobre `4a1e752`): 42 mortos, 0 sobreviventes, 1 equivalente** (M12 rodado duas vezes: a 1ª versão morreu por
`NameError`, a 2ª com `amb.systemctl("restart", …)` morreu pela asserção `restarts() == []`).

---

## Lacunas ranqueadas (ciclo 1; L1–L4 fechadas no ciclo 2 pelo `4a1e752`; L5 = decisão do dono; L6 = confirmação do dono)

1. **L4 — evento `crash` não zerado na aba nova (M39)**. `capture-store-pages/main.py:516` (`NAV.crash = False`) não
   tem teste. Sem isso, depois de um `crash` toda linha da aba nova sairia como `Page crashed` e o robô relançaria
   à toa (Saídas 2/3a). **Correção:** em `tests/test_navegador_recuperacao.py`, no monitor, disparar
   `aba.handlers["crash"]` numa linha, deixar o `goto` da aba nova passar e afirmar que a linha seguinte sai `ok`,
   sem relançamento (`lancados == []`).
2. **L1 — `loja_pausada` não pode contar em `tentativas_navegador` (M24)**. Regra explícita da Saída 6;
   `capture-store-pages/main.py:741-744` e `:758` (o `por_navegador` só liga no ramo do navegador) sem teste.
   **Correção:** em `tests/test_navegador_lote.py:286`, rodar uma linha com `PausaFalsa.em_pausa → True` e afirmar
   `tentativas_navegador` inalterado.
3. **L2 — lote sem `--monitorar` (M28)**. `capture-store-pages/main.py:1253-1266` (`_lote_com_recuperacao`) não tem
   nenhum teste; a suposição do autor ("recupera e continua do ponto em que parou") não é provada. **Correção:**
   teste com `_processar_lote` real e `goto` quebrando só na aba velha: afirmar que a linha retida é refeita na aba
   nova (`visitas == [1, 1, 2]`), que as seguintes rodam e que `out_rows` tem a retida duas vezes ou o resultado
   final esperado.
4. **L3 — `N linha(s) retida(s)` (M34)**. `capture-store-pages/core/navegador.py:86-87`: a linha que vai para `'9'`
   no 3º timeout não deveria entrar em `retidas`. Nenhum teste combina "3º timeout da mesma linha" com a contagem
   da mensagem. **Correção:** em `tests/test_navegador_recuperacao.py` ou `test_navegador_lote.py`, afirmar
   `NAV.retidas` (ou a mensagem inteira) depois de uma linha ir para `'9'`.
5. **L5 — precisão da spec (não bloqueia):** "voltou" do vigia depois de um reinício (D3,
   `vps/vigia_robos.py:595-599` + `core/batimento.py:76-77`). Conforme a letra da Saída 6; o dono decide se o
   reinício deve contar como "andar". Se não, o robô precisaria de marcar no batimento que o `ultimo_ok` é de partida.
6. **L6 — precisão da spec (não bloqueia):** D1/D2 (contagem dos 3 relançamentos e escalonamento) e D5 (forma do
   sinal na mensagem) para o dono confirmar.

Riscos que só a execução real mostra (não são lacunas de teste): `page.close()`, `context.new_page()` e
`_fechar_contexto` num Chromium em `SIGSTOP` podem bloquear sem prazo (`main.py:511`, `:513`, `:480`); a saída nesse
caso depende do vigia pelo prazo do batimento — é o cenário 3 da execução real.

---

## Bloqueia o merge — execução real do dono (inst1, branch da PR)

1. `kill -9` no renderer da aba com uma linha de Amazon/ML na fila → log com navegador quebrado, linha retida, aba
   nova, Telegram, a mesma linha `ok` em seguida (e o "voltou").
2. `kill -9` no Chromium principal → relançado, Telegram, captura segue.
3. `kill -STOP` no Chromium principal → 3 timeouts → recuperação; esperado código 3 ou reinício pelo vigia em até
   ~10 min (`kill -CONT` se não sair). Conferir no log onde parou (ver riscos acima).
4. Consulta de leitura: nenhuma linha nova em `'9'` com `Page crashed`/`closed` durante o teste.
5. `batimento.json` com `ultimo_ok_navegador` e `tentativas_navegador` andando.
6. `relancar_navegador_horas = 0.1`: relançamento preventivo com a linha de diagnóstico e a captura seguinte `ok`;
   voltar ao padrão.
7. Evidência redigida (regra 11) antes de entrar na PR.
