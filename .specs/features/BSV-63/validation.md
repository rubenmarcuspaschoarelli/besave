# BSV-63 — Validação

## Validation: BSV-63 - PASS

**Result**: PASS (ciclo 2, faixa `3d61c84..0eaf0a6`). No ciclo 1 (`3d61c84..1f0711d`) o veredito foi reprovado
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
