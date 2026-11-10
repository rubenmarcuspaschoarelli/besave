# BSV-57 Validation

**Verificador:** sub-agente independente (autor != verificador), sessão separada da implementação. Não editou o worktree real; sensor rodado em worktree git descartável fora dele (removido; `git status --porcelain` do real idêntico ao baseline).
**Data:** 2026-11-10
**Diff range:** `git diff 59f727c..HEAD` (HEAD = `33324bc`; ciclo 1 verificou `306584c`, ciclo 2 re-verificou `33324bc`).

## Validation

**Result:** PASS

Ciclo 2 (HEAD `33324bc`): o G1 (testes de `test_unidades.py` apagados no ciclo 1) foi corrigido, e G2, G3, G4 e G5 ganharam testes que matam os mutantes sobreviventes, exceto `x5` (menor, abaixo). O ciclo 1 foi FAIL só por G1. Todos os gates executáveis aqui passam. Pendentes fora do alcance do verificador: `systemd-analyze` e a execução real na inst1 (riscos no fim), que bloqueiam o merge por regra da spec, não este relatório.

### Ciclo 2: o que foi conferido

- `git diff 59f727c..HEAD -- tools/tests/test_unidades.py`: as únicas linhas removidas são as 3 asserções que a BSV-57 muda (lista de unidades, regex do `ExecStart`, `test_lojas_roda_o_main_em_modo_monitor`); nenhum teste antigo foi apagado. Total do arquivo 26 testes.
- Outras mudanças de teste do ciclo 2 (`git diff 306584c..HEAD`): `test_batimento_lojas.py` troca `[:2] == [varredura, dormindo]` por `[:3] == [varredura, validade, dormindo]` e os índices `gravados[1]` por `[2]` (consequência do novo `bater('validade')`, sem afrouxar); `test_batimento_whatsapp.py` passa o resgate falso a devolver `False` por padrão (`resgate_ok=False`, o caso realista) e acrescenta `test_bat_resgate_pendente_sem_concluir_nao_renova` e `test_bat_resgate_concluido_renova`.
- Mudança de produção: `wa/monitor.py:1280-1281` (`if feito: batimento.bater("resgate")`, só depois do resgate concluído) e `capture-store-pages/main.py:1006` (`batimento.bater('validade')` antes de `_varrer_validade`).
- Gates reexecutados: 122 passed (vigia x3, batimentos x2, unidades); 47 passed (scope lojas, scope whatsapp, iniciar_captura); `ruff check vps/ tests/` limpo; `shellcheck vps/*.sh` rc 0; `unittest` do `capture-chat-groups` 15 OK; `--collect-only` = 531 testes (504 no ciclo 1; base 427).
- Sensor do ciclo 2 (worktree descartável em `HEAD`, removido; `git status --porcelain` do real igual ao baseline): **15 mutantes, 14 mortos, 1 sobrevivente**.

| Mutante | Resultado | Teste que mata |
| --- | --- | --- |
| a2 `>=` no ramo "processo sumiu" | morto | `test_vigia_robos.py::test_g2_scope_vazio_com_prazo_igual_ao_agora_nao_age` |
| x12 ramo nunca parado | morto | `test_g2_scope_vazio_com_prazo_vencido_e_parado` |
| q6 `activating` sem proteger | morto | `test_g3_unidade_activating_e_ignorada` |
| x11 sem timestamp não cai no prazo | morto | `test_g3_sem_hora_de_partida_usa_o_prazo_do_batimento_como_referencia` |
| x6 `seek(0)` | sobrevive, **equivalente** (`f.read()` ainda lê o arquivo todo; só custa mais) | |
| z1 cauda = primeiros 64 KB (substitui x6) | morto | `test_g4_mensagem_traz_a_ultima_linha_do_log_nao_a_primeira` |
| l "voltou" sem checar `em > ultima_acao` | morto | `test_g4_voltou_exige_batimento_posterior_a_ultima_acao_mesmo_para_o_laco` |
| x5 `ultima_acao` não avança | **sobrevive** | lacuna menor (G6) |
| n4 `log()` sem redigir | morto | `test_vigia_mensagens.py::test_g5_log_do_vigia_redige_token` |
| n6 `avisar()` sem redigir | morto | `test_g5_avisar_redige_token_e_url_antes_de_enviar` |
| y1 resgate concluído não renova | morto | `test_batimento_whatsapp.py::test_bat_resgate_concluido_renova` |
| y2 renova com resgate pendente (`if True`) | morto | `test_bat02_volta_com_todos_os_grupos_falhando_nao_renova` |
| y3 renova só se NÃO concluiu (`if not feito`) | morto | idem |
| y4, y5 lojas: validade não bate | mortos | `test_batimento_lojas.py::test_bat07_varredura_com_fila_vazia_renova_e_dorme_com_prazo` |

Total acumulado (ciclos 1 e 2): 109 mutantes distintos (103 + z1, y1-y5), **100 mortos**; 9 não mortos: o9, q1, q4, q9, q17, q20, x2, x6 (equivalentes ou precisão de spec, ver abaixo) e x5 (G6). G1-G5 do ciclo 1 estão fechadas.

**G6 (menor, não bloqueia):** `x5`, a `ultima_acao` não avançar (V:383) não é pega: falta um teste com batimento entre a 1ª ação e um aviso posterior (ex.: lembrete) que ainda não conta como "voltou". Efeito prático: "voltou" um pouco cedo depois de um lembrete. Aceitável como decisão do dono ou teste extra.

**q9 (ABORTADO além das 20 últimas linhas):** fica como decisão proposta ao dono, não defeito (spec fala em "últimas linhas" sem número).

Observação sobre os testes de resgate: `resgate_ok=False` como padrão do falso é correto (o `True` antigo é o que renovaria o batimento em toda volta cega); só o par `bat_resgate_*` exercita o `True`.

## Tarefas

T1-T6 marcadas `[x]` em `.specs/features/BSV-57/tasks.md`. Nenhuma bloqueada ou parcial.

## Gates (rodados pelo verificador, de `tools/`)

| Gate | Resultado |
| --- | --- |
| `python -m pytest -q` nos 6 arquivos Python (vigia x3, batimento x2, unidades) | 95 passed (2,6 s) |
| `python -m pytest -q tests/test_scope_lojas.py tests/test_scope_whatsapp.py tests/test_iniciar_captura.py` (bash real no Windows) | 47 passed (128 s) |
| Suíte inteira | não reexecutada (3 min); `--collect-only` = **504** testes, igual aos 504 que o autor reportou passando. Base `59f727c` = 427. |
| `python -m ruff check vps/ tests/` | All checks passed |
| `shellcheck.exe vps/*.sh` (sem `-x`, como o CI) | rc 0, sem saída |
| `cd capture-chat-groups && python -m unittest discover -s tests` | Ran 15 tests, OK |
| `systemd-analyze --user verify tools/vps/systemd/*` | **NÃO EXECUTADO** (inexistente no Windows). Unidades lidas à mão: `besave-vigia-robos.service` (`Type=oneshot`, `ExecStart` absoluto, `TimeoutStartSec=120`), `.timer` (`OnBootSec=5min`, `OnUnitActiveSec=5min`, `Persistent=false`, `WantedBy=timers.target`) e `besave-captura-lojas.service` (`ExecStart=…/iniciar_lojas.sh --aguardar`, `ExecStop=-/usr/bin/systemctl --user stop besave-lojas-robo.scope`, `TimeoutStopSec=45`) sem erro de sintaxe visível. Fica para a inst1. |

Integridade de testes: +91 testes novos, mas `test_unidades.py` caiu de 24 para 10 casos (G1). Nenhum outro arquivo de teste teve teste removido ou asserção afrouxada (`git diff` só tem remoções em `test_unidades.py`).

## Spec-anchored: critério de aceite de `docs/specs/BSV-57.md`

Linhas de teste referem-se aos arquivos em `tools/tests/`; código em `tools/vps/vigia_robos.py` (V) e nos robôs.

| Critério | Resultado esperado (spec) | Teste (file:line + asserção) | Código | Resultado |
| --- | --- | --- | --- | --- |
| Parado: `em` há 11 min | 1 reinício + 1 aviso | `test_vigia_robos.py:27` `restarts()==[restart lojas]`, `len(enviados)==1`, "reiniciado 1/2", "sem batimento ha 11 min" | V:395 `agora > bat.prazo`, V:468 | PASS |
| Parado: `em` há 9 min | nada | `test_vigia_robos.py:35` | V:398 | PASS |
| Fronteira `prazo == agora` (decisão do dono) | não é parado | `test_vigia_robos.py:41`; vencido por 1 s age: `:47` | V:395 | PASS (mutante `>=` morto) |
| Madrugada: prazo = acordar + 10, relógio antes | nada, mesmo com `em` de horas | `test_vigia_robos.py:53`; depois do prazo vira parado `:59` | V:395-398 | PASS |
| Robô grava prazo de sono (cada robô) | prazo = acordar + 10 min | wa `test_batimento_whatsapp.py:187,197`; lojas `test_batimento_lojas.py:144,153` | wa `batimento.py:72`, `monitor.py:1368`; lojas `main.py:980-984`, `batimento.py:158` | PASS |
| PID trocado dentro de 10 min da partida | nada | `test_vigia_robos.py:76`; fronteira exata de 10 min `:83` | V:399-407 | PASS |
| Mesmo PID velho com unidade nova | parado | `test_vigia_robos.py:90` | V:404-406 | PASS |
| Operador: QR ou `ABORTADO:` | aviso sem reinício | QR `:127`, ABORTADO lojas `:150`; ABORTADO com robô saudável não incomoda `:158` | V:450-455, 252-261 | PASS |
| QR só em log anterior ao mais recente | não conta | `test_vigia_robos.py:142` | V:233-242 (maior mtime) | PASS |
| Vivo e quebrado: voltas cegas 11 min | prazo vence, parado, 1 reinício + aviso | robô: `test_batimento_whatsapp.py:137` (nenhuma volta cega renova), `:144` (volta com grupo aberto renova); vigia: `test_vigia_robos.py:65` | wa `batimento.py:91`, `monitor.py:1314` | PASS (mutante "renova toda volta" morto em `batimento.py` e em `monitor.py`) |
| Grupo morto 2 h 01 / 1 h 59 | aviso com nome sem reinício / nada | `test_vigia_robos.py:168` e `:175` | V:487-499 | PASS |
| Grupo: lembrete só depois de 2 h; "voltou" do grupo | idem | `test_vigia_robos.py:181` (1 h 59 nada, 2 h 01 "Lembrete", saiu do mapa "voltou", depois nada) | V:362-371, 500-505 | PASS |
| Laço: 3 logs/30 min sem `Grupo aberto` | operador sem reinício | `test_vigia_robos.py:220`; 2 logs `:229`; 3 com `Grupo aberto` `:237`; >30 min `:246`; idade pelo nome `:255` | V:279-299 | PASS |
| Banco fora | batimento renovado → nada | vigia `test_vigia_robos.py:380` (não discrimina `fase`: o vigia não lê `fase`); robô `test_batimento_whatsapp.py:150` | wa `monitor.py:1130-1132` | PASS (a parte que discrimina é a do robô; mutante `d` morto) |
| Reinício diário ativo + prazo vencido | nada; não protege lojas | `test_vigia_robos.py:366`, `:373` | V:436-437 | PASS |
| Pausa de loja | nada | vigia `test_vigia_robos.py:386` (trivial: o vigia não lê o log em robô saudável); robô `test_batimento_lojas.py:85,160` | lojas `main.py:1002` | PASS |
| Scope: pid fora/dentro do `cgroup.procs`; cgroup falso com pids distintos | parado / vivo | `test_vigia_robos.py:97` (pid do tmux fora do scope, sem `MainPID`), `:107` | V:142-151, 394 | PASS (mutantes MainPID e `pid in pids` mortos) |
| Limite: 3ª parada em 60 min | sem reinício + operador; após 60 min volta a reiniciar | `test_vigia_robos.py:272` (limites 59/61/66 min) | V:421-422, 459-460 | PASS |
| Voltou | 1 mensagem com duração; sem ocorrência, nada | `test_vigia_robos.py:307` ("parado por 19 min"), `:323`, `:333` | V:478-483 | PASS |
| Parado de propósito (`inactive`) | nada | `test_vigia_robos.py:348`, fecha ocorrência sem "voltou" `:355` | V:431-433 | PASS |
| Mensagens: sem token só log; com token texto completo; token ausente de toda saída; URL removida | idem | `test_vigia_mensagens.py:24,33,54,63,70,84` | V:66-72, 330-359 | PASS |
| Robôs: escrita atômica e prazo de sono | idem | wa `test_batimento_whatsapp.py:205,226`; lojas `test_batimento_lojas.py:172,184` | wa `batimento.py:35-52`; lojas `batimento.py:131-148` | PASS |
| Scope das lojas: comando inteiro (lição 14), `--collect` + `--unit`; ordem; scope ativo recusa | idem | `test_scope_lojas.py:58` (lista inteira `COMANDO` + cauda), `:74` (lista exata das 4 linhas), `:85` | `scope.sh:11-42`, `iniciar_lojas.sh:87-88` | PASS |
| Rotação | 15 d apagado, 13 mantido, mais recente nunca; 51 MB copiado e truncado (mesmo inode); 49 MB intocado; outro nome intocado | `test_vigia_rotacao.py:31,39,45,52,65,73,84,104,122` | V:511-543 | PASS |
| Gates | unittest dos 3 dirs, ruff, shellcheck, systemd-analyze | ver tabela de gates | | PASS, exceto `systemd-analyze` (não executado) |

### Requisitos EARS de `spec.md`

| ID | Evidência | Resultado |
| --- | --- | --- |
| BAT-01..06 | `test_batimento_whatsapp.py:127,137,144,150,157,175,187,197,205,226` | PASS |
| BAT-07, BAT-08 | `test_batimento_lojas.py:77,85,91,101-106,144,160,166` | PASS |
| ESC-01, ESC-02 | `test_scope_lojas.py:58,74,85` | PASS |
| ESC-03 | `test_unidades.py:53-61` (ExecStop e `TimeoutStopSec` iguais; comparação de string inteira) | PASS |
| VIG-01..10 | tabela acima | PASS (VIG-09 `activating` sem teste: G5) |
| MSG-01..03 | `test_vigia_mensagens.py:24,33,54,63,70,84,89,96,104,114,133` | PASS |
| ROT-01..03 | `test_vigia_rotacao.py` | PASS |
| UNI-01 | `test_unidades.py:63-71` (conteúdo); README cobre silenciar e desligar (`tools/vps/README.md`, seções "Silenciar um robô" e "Desligar o vigia") | PASS no conteúdo; `systemd-analyze verify` não executado |

### Lacunas de precisão da spec (não são falha de teste)

- "`main_monitorar.log` acima de 50 MB": exatamente 50 MB não é definido; `>` e `>=` são indistinguíveis (mutante o9).
- "Grupo falhando há **2 h ou mais**" (spec.md VIG-05) contra "há 2 h 01 min → aviso; 1 h 59 → nada" (spec do dono): o caso exatamente 2 h não está definido nem testado (mutante q4 sobrevive). O código avisa em 2 h exatas, de acordo com VIG-05.
- "Lembrete a cada 2 h": 2 h exatas não definido (mutante q1).
- "Últimas linhas do log" para `ABORTADO:`: o código usa as últimas 20 linhas não vazias; a spec não fixa o número (mutante q9).
- "Banco fora" e "Pausa de loja" no vigia são critérios que o vigia atende por não olhar `fase` nem o log; o teste do vigia não discrimina (o do robô sim).

## Sensor de discriminação (ciclo 1; o ciclo 2 está acima)

Scratch isolado: `git worktree add --detach` em `…\Temp\claude\verif-bsv57` (e outro na base, só para contar testes), ambos removidos com `git worktree remove --force` e `prune`. Baseline `git status --porcelain` do worktree real vazio antes e depois: **igual**. Cada mutante rodou só os testes relevantes (`pytest -x`), um processo por vez, em lotes de 10-12; harness em arquivo do scratchpad (não versionado).

**103 mutantes: 87 mortos, 16 sobreviveram** (5 equivalentes ou de precisão de spec; 11 em tabela de gaps).

Mortos (87), por grupo:
- (a) `>` para `>=` no pid vivo (a1); (b) tolerância extra de 10 min (b); (g) limite 2 para 3, janela 60 para 120, `>=` para `>` no limite, sem limite, reinícios sem expirar, reinício não registrado (g1, g2, q15, x7, x9, x10); (h) grupo morto 2 h para 2 min, com reinício, `<=` não; grupos não vigiados (h1, h2, q18); (i) laço 3 para 2, janela 30 para 60, ignora `Grupo aberto`, laço ignorado, ano do nome, idade do mtime (i1, i2, q8, q16, q19); (j) QR e ABORTADO não bloqueiam, QR ignora autenticada (j1, j2, q10); (k) `bat.pid in pids` removido, MainPID no lugar do cgroup (k1, k2); (m) reinício acoplado à mensagem (m), reinicia mesmo com operador (m2); (n) URL, token, segredo conhecido e conjunto sem redação (n1, n2, n3, n5); (o) apaga o mais recente, apaga fora do padrão, apaga `main_monitorar_antigo.log`, não trunca no mesmo inode, limite 50 para 5 MB, 14 para 7 dias, rotação todo ciclo, `<` para `<=` em 14 d (o1-o8); partida 10 para 20 min e `>=` (p1, p2); lembrete 2 h para 1 h, grupo "voltou" sem limpar, `<=` não, inactive sem limpar, reinício diário `active` sem proteger, menor chrome em vez do maior, qualquer processo como chrome, log mais antigo, "voltou" com duração até agora, sem aviso de mudança de ação, restart falho não dito (q2, q3, q5, q7, q11, q12, q14, x3, x4, x8).
- Robôs: (c) "renova em toda volta" em `batimento.py` e em `monitor.py` (c1, c2; x1 isola os testes bat02), grupo aberto marcado como falha (c3); (d) banco fora não renova; (f) prazo sem tempo de sono, `PRAZO` 5 min, sono com `dorme_s=0`, sono não gravado (f1-f6, l3, l4); (e) navegador fechado renova, sempre False, menos sinais (e1-e3); (r) escrita não atômica nos dois robôs, `.tmp` não limpo, falha propaga (r1, r2, r3, r4); grupos: não sai do mapa, "desde" anda, não gravado (g3-g5); lojas: linha, varredura e sono sem batimento, pid errado (l1, l2, l5).
- (p), (q) Bash e unidade: sem `--collect`, ordem trocada, scope ativo sobe, sem `revert`, sem `reset-failed`, sem `KillSignal`, `TimeoutStopSec` 60, sem `--sem-perguntas`, nome do scope, sem `scope_preparar`; unidade sem `ExecStop`, `TimeoutStopSec=30`, `ExecStop` sem `-`, sem `--aguardar` (p_a..p_j, q_a..q_d). O teste de comando montado (lição 14) pega todos.

Sobreviventes (16):

| Mutante | O que muda | Classificação |
| --- | --- | --- |
| a2, x12 | ramo "unidade ativa e nenhum processo no scope, com batimento" (V:409-413): `>=` e "nunca parado" | **Lacuna real** (G2) |
| q6 | `activating` deixa de proteger (V:434-435) | **Lacuna real** (G3) |
| x11 | sem `ActiveEnterTimestamp`, o vigia não cai no `bat.prazo` (V:402-403) | **Lacuna real** (G3) |
| x6 | `ler_cauda` lê o início do arquivo em vez do fim (V:223-230) | **Lacuna real** (G4) |
| l, x5 | guarda `bat.em > ultima_acao` do "voltou" (V:480) e avanço de `ultima_acao` (V:383) | **Lacuna real** (G4) |
| q9 | janela de 20 linhas do `ABORTADO:` | Lacuna de precisão da spec; teste faltando para ABORTADO antigo (G5) |
| q1, q4 | fronteiras exatas de 2 h (lembrete, grupo morto) | Precisão da spec (G5) |
| n4, n6 | `redigir` em `log()` e em `avisar()` (camadas redundantes com `montar_mensagem`) | Defesa em profundidade sem teste: a mensagem de "voltou" e a de grupo passam só por `avisar()`; `log()` recebe `{e}` em V:556 (G5) |
| o9 | `>` para `>=` em 50 MB | Equivalente por precisão da spec |
| q17 | laço de partidas também nas lojas | Equivalente (a pasta de log das lojas não tem `run_captura_*`) |
| q20 | aceita log com data no futuro | Equivalente na prática (só com relógio atrasado) |
| x2 | `ErroSemId` não marca o grupo como aberto | Equivalente: `_esperar_banco` renova logo em seguida (`monitor.py:1317`) |

## Lacunas do ciclo 1 (histórico; G1-G5 fechadas no ciclo 2, ver acima)

**G1 (bloqueia o PASS) — testes de unidade apagados.** `tools/tests/test_unidades.py` (commit `d59638f`): removidas `test_robo_depende_da_tela_vnc`, `test_robo_nao_fica_failed_por_falha_de_partida`, `test_vnc_e_unidade_modelo_da_tela_n_so_em_localhost`, `test_readme_explica_o_linger_e_a_unidade_do_vnc`, `test_robo_para_com_sigint_e_da_tempo_de_salvar`, `test_robo_falha_se_a_tela_nao_aparece`, `test_vnc_detalhes_da_tela`, `test_timer_do_reinicio_a_cada_6h_sem_persistent`, `test_service_do_reinicio_e_oneshot_e_chama_o_script`, `test_whatsapp_teto_vem_do_environment_e_nao_da_unidade`, `test_whatsapp_execstop_para_o_scope_do_robo`. Prova: o arquivo de `59f727c` copiado para o scratch contra o código de `HEAD` dá 22 passed, 3 failed; as 3 falhas são as asserções que a própria BSV-57 muda (lista de unidades, regex do `ExecStart` das lojas, `test_lojas_roda_o_main_em_modo_monitor`). Os demais 14 casos passam e foram apagados sem motivo. Correção: restaurar o arquivo de `59f727c` e só alterar essas 3 asserções (acrescentar `iniciar_lojas` ao regex, `besave-vigia-robos.service` à lista, e o teste novo das lojas). Total esperado: 24 para cerca de 26 casos neste arquivo.

**G2 — ramo "processo sumiu" sem teste** (`vigia_robos.py:409-413`). Teste que falta: scope vazio (`m.scope_pids("lojas", set())`) com batimento de prazo vencido há 1 s → 1 reinício (PARADO); com `prazo == agora` e com prazo futuro → nada. Hoje só o ramo sem batimento (`test_vigia_robos.py:404`) existe.

**G3 — `activating` e fallback sem timestamp.** Testes que faltam: (i) `m.estados[UNIDADE] = "activating"` com batimento vencido → nada; (ii) scope com pid novo, batimento velho, `ActiveEnterTimestamp` vazio e prazo do batimento vencido há mais de 10 min → parado, e vencido há menos → nada.

**G4 — cauda do log e "voltou".** (i) log com mais de 64 KB e `ABORTADO:`/QR só no fim (e outro `ABORTADO:` no começo) para provar que lê o fim; (ii) ocorrência aberta por laço de partidas (batimento saudável) que depois some: nenhum "voltou" até haver batimento com `em` posterior à última ação.

**G5 — menores.** Teste de `ABORTADO:` com mais de 20 linhas depois dele em robô parado (decidir com o dono se um `ABORTADO` antigo deve bloquear); teste de redação no `log()` com exceção que carrega URL (V:556 imprime `{e}`) e no texto de "grupo/voltou" via `avisar()`; fronteiras de 2 h se o dono quiser fixá-las.

## Verificação de evidência (regra 11)

`git diff 59f727c..HEAD` varrido por `C:\Users\`, `/home/<usuário>`, IPs, `uid=`, hostnames internos, `ubuntu@`, tokens de bot (`\d{6,}:[A-Za-z0-9_-]{20,}`) e chat_ids. Únicos achados: `TOKEN = "123456789:AAFakeTokenParaTesteNaoEReal_abcdefghij"` e `CHAT = "-1001234567890"` em `tools/tests/vigia_falso.py:15-16`, ambos fictícios e óbvios. Os caminhos `/srv/besave/...` são o padrão do repositório já usado nas unidades existentes. Não há arquivo de evidência (log, print, relatório) nesta mudança. Nada a trocar por `REDACTED`.

## Qualidade de código (resumo)

Sem recurso além do pedido; só stdlib no vigia; `batimento.py` duplicado entre os dois robôs de propósito (docstring explica: não compartilham pacote). Estilo de cada robô respeitado (aspas simples nas lojas). Nenhum defeito de produção encontrado.

## Riscos para a execução real na inst1 (não verificados aqui)

1. `systemctl --user show -p ActiveEnterTimestamp --timestamp=unix --value <scope>` (V:163) e o formato `@epoch`: o teste usa um systemctl falso que devolve `@epoch`; a existência da opção `--timestamp=unix` e o formato real **não foram verificados fora do Linux**. Se a saída diferir, `inicio_unidade` devolve `None` e o ramo cai no prazo do batimento (e G3/x11 mostra que isso não tem teste). Conferir na inst1 antes do passo 1 do real.
2. `systemctl --user show -p ControlGroup --value <scope>` mais `/sys/fs/cgroup/<cg>/cgroup.procs`: testado só com cgroup falso. Na inst1, conferir que o `besave` lê o `cgroup.procs` do scope de usuário (cgroup v2, permissões) e que o pid do python (filho direto do `systemd-run --scope`) aparece lá, senão todo batimento viraria "pid fora do scope" após 10 min.
3. `systemctl --user is-active` de unidade em `activating (auto-restart)` (RestartSec=30): o código trata `activating` como "nada"; sem teste (G3).
4. Operações longas sem batimento: WhatsApp no arranque/resgate de lacuna (`monitor.py:1195-1250`, `_recuperar_lacuna`) e as lojas em `_varrer_validade`/linha muito longa podem passar de 10 min sem bater e disparar reinício falso. Não medido; conferir `t_*` do primeiro dia na inst1 e, se preciso, bater dentro desses laços ou alargar o prazo.
5. `systemd-analyze --user verify` e o `ExecStop` do scope das lojas (SIGINT, depois SIGKILL em 30 s; `TimeoutStopSec=45`): só lido à mão. Os passos 1-5 e 4b do real são do dono e bloqueiam o merge.
6. Os testes bash rodaram no Git Bash do Windows com comandos falsos; o comportamento real de `systemd-run --collect` com scope `failed` não foi exercitado.

## Resumo

Cobertura dos critérios: completa e discriminante (87 de 103 mutantes mortos, todos os obrigatórios (a)-(r) mortos, exceto os pontos listados em G2-G5). Defeito de processo: G1 (testes apagados) impede o PASS até ser corrigido.
