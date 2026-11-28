# BSV-67 — Validation

**Verdict**: PASS
**Result**: PASS (ciclo 4)

- **Verificou:** Verifier sub-agente independente (autor ≠ verificador). Não alterou código nem testes.
- **Ciclo 4** (28/11/2026): delta `67ad979..400940e` (T8). Só testes e `tasks.md`:
  `test_perfil_ainda_em_uso_pula_a_copia_e_avisa` passou a ser parametrizado com o perfil no meio
  (`" --no-first-run"`) e no fim da linha do `ps` (`""`), em `tools/tests/test_reinicio_whatsapp.py:315-330`. Fecha a
  L7 do ciclo 3. Nenhum código de produção mudou.
- **Histórico:** ciclo 3 (`be75a8b..67ad979`) FAIL por M45; ciclo 2 (`b39d155..be75a8b`) PASS; ciclo 1
  (`b39d155..a8902a5`) FAIL por M19. Detalhes abaixo.

## Ciclo 4 — gates

| gate | onde | resultado |
|---|---|---|
| `python -m pytest -q -p no:cacheprovider` (de `tools/`) | Windows | **922 passed, 45 skipped**, 281 s (+1 = a variante "fim de linha") |
| `pytest tests/test_reinicio_whatsapp.py` | Windows | 20 passed |
| `pytest tests/test_reinicio_whatsapp.py` (`--basetemp=/tmp/bsv67-ver4`) | WSL | 20 passed |
| `python -m ruff check vps/ tests/` | Windows | All checks passed |
| `shellcheck vps/*.sh` | Windows | rc 0 |

## Ciclo 4 — sensor de discriminação

Worktree descartável do `400940e` (removido ao fim); `tests/test_reinicio_whatsapp.py` inteiro por mutante.

| # | mutante | resultado | teste que matou |
|---|---|---|---|
| M45 | sem o caso "fim de linha" (só `index($0, p " ")`) | **morto** | `test_perfil_ainda_em_uso_pula_a_copia_e_avisa[]` |
| M41 | sem a checagem de perfil em uso | morto | `test_perfil_ainda_em_uso_pula_a_copia_e_avisa[ --no-first-run]` |
| M42 | casa por prefixo `index($0, p)` (pegaria `user_data.copia`) | morto | `test_outros_perfis_no_ps_nao_seguram_a_copia` |
| M44 | `-gt 0` → `-gt 1` | morto | `test_perfil_ainda_em_uso_pula_a_copia_e_avisa[ --no-first-run]` |

**Ciclo 4: 4 injetados, 4 mortos, 0 sobreviventes.** Árvore real: só este `validation.md` alterado, antes e
depois do sensor.

## Lacunas restantes (nenhuma bloqueia)

1. L2: `TimeoutStartSec=300` só aperta no pior caso; medir o tempo total no passo 1 do teste real.
2. L5: a espera por `Grupo aberto` conta a partir do `start` por construção; não tem teste próprio.
3. Fora do delta: o `awk` do RSS do passo 2 (`reiniciar_whatsapp.sh:56`) casa por prefixo; afeta só o número no log.
4. **Bloqueia o merge (dono, inst1, branch da PR):** os 5 passos reais da spec.

---

# Histórico — ciclo 3 (`be75a8b..67ad979`, veredito do ciclo: reprovado)

## Ciclo 3 — evidência por critério

| critério (spec.md revisado) | evidência | confere? |
|---|---|---|
| COP-03: processo ainda com o perfil nos argumentos → pula a cópia, avisa, parte mesmo assim | código `tools/vps/reiniciar_whatsapp.sh:86-94`; teste `tools/tests/test_reinicio_whatsapp.py:315-329`: sem `user_data.copia`, `ps` chamado 2 vezes com o comando inteiro `-eo rss=,args=` (passo 2 e antes da cópia), linha de log inteira por regex ancorada `copia da sessao: pulada (perfil ainda em uso por 1 processo(s))`, aviso inteiro `Reinicio diario do robo do WhatsApp: a copia da sessao falhou (perfil ainda em uso por 1 processo(s); a anterior continua valendo); a captura parte mesmo assim.`, `start` depois | sim |
| COP-02: só o perfil exato conta (`user_data.copia` e outros perfis não seguram a cópia) | `test_reinicio_whatsapp.py:332-346`: `ps` com `…/user_data.copia` e `--user-data-dir=/outro/perfil` → cópia feita, sem aviso | sim |
| Perfil exato no **fim** da linha também conta | `reiniciar_whatsapp.sh:89` (`substr(...) == p`) | **sem teste** (M45 sobrevive, L7) |
| PAR-02: número recusado → `WhatsApp desconectado: o campo nao aceitou o numero do config (***1234); ler o QR pela tela VNC :2.` | código `tools/capture-chat-groups/wa/pareamento.py:76-78,279`; testes `tools/tests/test_pareamento.py:142-151` (lista inteira com `***0000`, sem número no log, não avança, não conta no teto) e `tools/tests/test_pareamento_pagina.py:134-136` (Chromium, `__avancos == 0`) | sim |
| DOC | `tools/capture-chat-groups/README.md` (linha nova da mensagem; a do VNC deixou de citar a máscara) e `tools/vps/README.md` (checagem do perfil em uso) | sim |

## Ciclo 3 — gates

| gate | onde | resultado |
|---|---|---|
| `python -m pytest -q -p no:cacheprovider` (de `tools/`) | Windows | **921 passed, 45 skipped**, 281 s (+2 = os dois testes novos do perfil) |
| `python -m ruff check vps/ tests/` | Windows | All checks passed |
| `shellcheck vps/*.sh` | Windows | rc 0 |
| `python -m unittest discover -s tests` (de `tools/capture-chat-groups`) | Windows | OK |
| `pytest tests/test_pareamento_pagina.py`, Playwright 1.61.0 + Chromium real | Windows (venv de teste) | **11 passed** |
| `pytest test_vigia_pareamento test_vigia_robos test_reinicio_whatsapp test_sessao_whatsapp test_pareamento` (`--basetemp=/tmp/bsv67-ver3`) | WSL | **129 passed, 0 skipped** |

## Ciclo 3 — sensor de discriminação

Worktree descartável do `67ad979` (removido ao fim); arquivo de teste inteiro por mutante; mutantes de bash no Git
Bash pelo próprio teste.

| # | mutante | resultado | teste que matou |
|---|---|---|---|
| M41 | sem a checagem de perfil em uso (`if false`) | morto | `test_perfil_ainda_em_uso_pula_a_copia_e_avisa` |
| M42 | casa por prefixo `index($0, p)` (pegaria `user_data.copia`) | morto | `test_outros_perfis_no_ps_nao_seguram_a_copia` |
| M43 | número recusado volta à mensagem do VNC | morto | `test_campo_com_ddi_duplicado_nao_avanca_e_manda_o_vnc` |
| M43b | mensagem do número recusado sem a máscara (número inteiro) | morto | idem |
| M44 | `-gt 0` → `-gt 1` | morto | `test_perfil_ainda_em_uso_pula_a_copia_e_avisa` |
| M45 | **sem o caso "fim de linha"** (só `index($0, p " ")`) | **SOBREVIVEU** (19 passed) | — |
| M46 | perfil em uso pula sem avisar | morto | `test_perfil_ainda_em_uso_pula_a_copia_e_avisa` |
| M47 | perfil em uso avisa mas copia mesmo assim (sem `return 1`) | morto | idem |

**Ciclo 3: 8 injetados, 7 mortos, 1 sobrevivente (M45).** Não é equivalente: um processo cujo último argumento é
`--user-data-dir=<raiz>/user_data` deixa de ser contado e a cópia lê um perfil em uso (regra 2 da spec do dono:
"a cópia nunca é lida enquanto o Chromium usa o perfil"). O risco real é baixo, porque o Chromium do Playwright
costuma ter argumentos depois do perfil. Mesmo assim, o código implementa esse caso e o arquiteto o pediu ("espaço
ou fim de linha"), e nenhum teste o prova. Árvore real: `git status --porcelain` vazio antes e depois.

## Ciclo 3 — lacunas

1. **L7 (motivo do FAIL)**: `tools/tests/test_reinicio_whatsapp.py`: falta um caso com o perfil exato no fim da
   linha do `ps`. Por exemplo, parametrizar `test_perfil_ainda_em_uso_pula_a_copia_e_avisa` com
   `f"3400000 /usr/lib/chromium/chromium --type=browser {perfil}"` (sem argumento depois). Mata o M45.
2. L2 e L5 dos ciclos anteriores continuam abertas e não bloqueiam (ver ciclo 2).
3. Observação, fora do delta: o `awk` do passo 2 (RSS, `reiniciar_whatsapp.sh:56`) continua casando por prefixo
   (`index($0, p)`). Ali só soma memória para o log, então um `user_data.copia` aberto à mão inflaria o número sem
   efeito no comportamento. Não bloqueia.
4. **Bloqueia o merge (dono, inst1, branch da PR):** os 5 passos reais da spec.

---

# Histórico — ciclo 2 (`b39d155..be75a8b`, veredito do ciclo: aprovado)

## Ciclo 2 — gates

| gate | onde | resultado |
|---|---|---|
| `python -m pytest -q -p no:cacheprovider` (de `tools/`) | Windows | **919 passed, 45 skipped**, 282 s (+2 = teste novo do teto diário e a variante `numero`) |
| `python -m ruff check vps/ tests/` | Windows | All checks passed |
| `shellcheck vps/*.sh` | Windows | rc 0 |
| `python -m unittest discover -s tests` (de `tools/capture-chat-groups`) | Windows | 15 tests OK |
| `pytest tests/test_pareamento_pagina.py`, Playwright 1.61.0 + Chromium real | Windows (venv de teste) | **11 passed** |
| `pytest test_vigia_pareamento test_vigia_robos test_reinicio_whatsapp test_sessao_whatsapp test_pareamento` (`--basetemp=/tmp/bsv67-ver2`) | WSL | **127 passed, 0 skipped** |

## Ciclo 2 — lacunas do ciclo 1

| lacuna | estado | evidência |
|---|---|---|
| L1 (M19): voltou ao campo do número antes da validade → pede outro | **fechada** | `tools/tests/test_pareamento.py:188-201`, parametrizado `[qr, numero]`, pedidos às 12:00 e 12:02 |
| L3: 13º pedido no dia pelo `Vinculo`, mensagem inteira | **fechada** | `test_pareamento.py:234-244`: 1ª mensagem `WhatsApp desconectado: limite de codigos atingido; proximo pedido as 00:00 (Brasilia).`, um pedido só às 00:00, lista inteira `[teto, codigo, vinculado]` |
| L4: avisos de cópia falha e de stop falho comparados inteiros | **fechada** | `tools/tests/test_reinicio_whatsapp.py:291-292` e `:304-305` (`amb.avisos == [...]` com o texto inteiro) |
| L5: espera contada a partir do `start` | aberta (aceita) | por construção (`reiniciar_whatsapp.sh:137`, depois do `start` em `:116`); sem teste dedicado |
| L6: continuação de linha | **fechada** | `vigia_robos.py:574-575` |
| L2: `TimeoutStartSec=300` | aberta, **não bloqueia** | ver abaixo |

**L2 (o coordenador pediu uma opinião).** O comentário foi corrigido. Conta no pior caso: `stop` até 45 s
(`TimeoutStopSec=45` em `besave-captura-whatsapp.service:32`), mais a cópia (segundos para ~260 MB), mais o `start`
(o `ExecStartPre` só espera o X2 se ele não existir, até 60 s), mais até 180 s de espera e um intervalo de 5 s.
No caso normal dá ~190–235 s e cabe em 300 s. Só estoura se tudo for lento ao mesmo tempo (stop de 45 s + X2
ausente + cópia lenta + 180 s sem `Grupo aberto`). Nesse caso o systemd mata o script durante a espera e o aviso
"nao confirmei a retomada" não sai; a captura não é afetada (a unidade já partiu) e a cópia em `.nova` nunca
vira válida. Não vejo necessidade de mudar a unidade agora (regra 4). Recomendo conferir o tempo total no passo 1
do teste real: o log já traz o horário do `stop`, a linha da cópia e o `OK`.

## Ciclo 2 — sensor de discriminação

Worktree descartável do `be75a8b` (removido ao fim), lotes de 5 a 8, só o arquivo de teste relevante (ou o teste
novo, nos mutantes "b").

| # | mutante | resultado | teste que matou |
|---|---|---|---|
| M19 | expira só ao voltar ao QR (`estado in (QR,)`) | **morto** | `test_pagina_voltou_ao_qr_ou_ao_numero_pede_outro_antes_da_validade[numero]` |
| M19b | expira só ao voltar ao número (`estado in (NUMERO,)`) | morto | `…[qr]` |
| M01 | sem teto de códigos | morto | `test_quarto_pedido_na_mesma_hora_nao_sai_e_virou_a_hora_sai` |
| M02 | teto 4/h | morto | idem |
| M03 | teto do dia `>` no lugar de `>=` | morto | `test_teto_por_hora_e_por_dia` |
| M28 | aviso de teto a cada volta | morto | `test_quarto_pedido_na_mesma_hora_nao_sai_e_virou_a_hora_sai` |
| M37 | teto do dia libera na hora seguinte | morto | `test_teto_por_hora_e_por_dia` |
| M37b | idem, só o teste novo do `Vinculo` | morto | `test_decimo_terceiro_no_dia_nao_sai_e_avisa_a_meia_noite` |
| M40 | teto diário ignorado | morto | `test_teto_por_hora_e_por_dia` |
| M40b | idem, só o teste novo do `Vinculo` | morto | `test_decimo_terceiro_no_dia_nao_sai_e_avisa_a_meia_noite` |
| M04 | RSS `>=` no lugar de `>` (depois da quebra de linha nova) | morto | `test_rss_no_limite_ou_abaixo_nao_dispara[2500]` |
| M27 | memória dispara fora do `rodizio` (mesma condição reformatada) | morto | `test_rss_alto_fora_do_rodizio_nao_dispara[dormindo]` |
| M08 | exceção do QR em `pareamento` vencido | morto | `test_pareamento_vencido_reinicia_como_hoje` |
| M09 | aviso de memória no 1º disparo | morto | `test_rss_acima_do_limite_dispara_o_reinicio_programado` |
| M10 | `pareamento` em dia tratado como normal | morto | `test_pareamento_em_dia_sem_reinicio_sem_laco_sem_aviso` |
| M18 | janela de memória 40 min | morto | `test_um_por_60_min_e_aviso_so_no_segundo_em_6_h` |
| M05 | cópia sem checar `Grupo aberto` | morto | `test_sem_grupo_aberto_na_partida_parada_nao_copia` |
| M24 | `stop` falho ainda copia | morto | `test_stop_que_falha_nao_copia_e_parte` |
| M38 | aviso de cópia falha sem "a anterior continua valendo" | morto | `test_copia_que_falha_avisa_e_parte_mesmo_assim` |
| M39 | aviso de stop falho sem o estado | morto | `test_stop_que_falha_nao_copia_e_parte` |

**Ciclo 2: 20 injetados, 20 mortos, 0 sobreviventes.** Árvore real: `git status --porcelain` só com este
`validation.md` antes e depois.

## Ciclo 2 — lacunas restantes (nenhuma bloqueia)

1. L2: `TimeoutStartSec=300` aperta só no pior caso; medir no passo 1 do teste real.
2. L5: espera desde o `start` sem teste dedicado (por construção).
3. Os desvios aceitos do ciclo 1 continuam valendo (abaixo).
4. **Bloqueia o merge (dono, inst1, branch da PR):** os 5 passos reais da spec; nenhum foi executado aqui.

---

# Histórico — ciclo 1 (`b39d155..a8902a5`, Verdict: FAIL)

## Gates (job `tools` do CI + Chromium + WSL)

| gate | onde | resultado |
|---|---|---|
| `python -m pytest -q -p no:cacheprovider` (de `tools/`) | Windows | **917 passed, 45 skipped**, 291 s |
| `python -m ruff check vps/ tests/` | Windows | All checks passed |
| `shellcheck vps/*.sh` | Windows (shellcheck do venv) | rc 0, sem achados |
| `python -m unittest discover -s tests` (de `tools/capture-chat-groups`) | Windows | 15 tests OK |
| `pytest tests/test_pareamento_pagina.py` com Playwright 1.61.0 + Chromium real | Windows (venv de teste) | **11 passed** (no pytest do sistema esse arquivo é 1 skip: sem Playwright, como no CI) |
| `pytest test_vigia_pareamento test_vigia_robos test_reinicio_whatsapp test_sessao_whatsapp test_pareamento` (`--basetemp=/tmp/bsv67-ver`) | WSL (lição 32) | **125 passed, 0 skipped** |

Nos arquivos da BSV-67 o Windows pula só `test_pareamento_pagina.py` (sem Playwright no Python do sistema):
65 passed, 1 skipped; o arquivo roda inteiro no venv com Chromium.

## Checagem ancorada na spec (critério de aceite de `docs/specs/BSV-67.md`)

| critério | evidência (teste `arquivo:linha` → asserção) | valor confere com a spec? |
|---|---|---|
| Login com cópia não tentada → restaura uma vez e marca `restaurada_em` | `tools/tests/test_sessao_whatsapp.py:96` `eventos == ["lancar:perdida","close","lancar:boa"]`; `:102` `restaurada_em == "2026-11-27T15:00:00Z"`; `:105-107` log `[sessao] tela de login; restaurando a copia de 2026-11-27T08:30:12Z`, `[sessao] copia restaurada; sessao ok` e aviso inteiro `WhatsApp: sessao perdida e restaurada da copia de 27/11 05:30 (sem acao).` | sim (código `capture-chat-groups/wa/sessao.py:46-57,71-88`) |
| Cópia já tentada → código | `test_sessao_whatsapp.py:115-118` eventos `["lancar:perdida","vinculo"]`, número do config, `user_data` intocado; `:138-140` partida seguinte não repete | sim |
| `user_data/` movido para `user_data.qr/`, nunca apagado | `test_sessao_whatsapp.py:100` `user_data.qr/.../sessao.txt == "perdida"` (substitui a `antiga`), `:141` | sim (`sessao.py:51-54`, `os.replace`) |
| Código da fixture → mensagem inteira com `***`+4 e sem o número | `tools/tests/test_pareamento.py:108-112` lista inteira de mensagens (`…digite TEST-E123 (pedido as 12:00, Brasilia).`, `WhatsApp: vinculado de novo pelo codigo; captura retomada.`); `:115-119` log com `***0000`, sem número nem código | sim (`pareamento.py:70-73,267,289`) |
| 4º pedido na mesma hora não sai; virou a hora → sai | `test_pareamento.py:214-219` pedidos 12:00/12:10/12:20/13:00 e aviso de teto inteiro `…proximo pedido as 13:00 (Brasilia).` uma vez, entre o 3º e o 4º | sim |
| 13º no dia não sai | `test_pareamento.py:222-234` (`Teto.proximo` → 00:00 de Brasília = 03:00 UTC) | sim, só no nível de `Teto` (lacuna L3) |
| Sem `pareamento.numero` → VNC, sem clicar, sem sair | `test_pareamento.py:246-251` mensagem inteira, `acoes == []`, 3 h de batidas (voltou de `aguardar` sem exceção) | sim |
| Batimento `fase:"pareamento"` a cada volta | `test_pareamento.py:160-178` uma batida por volta de 5 s, `fase == "pareamento"` e `prazo - em == 15 min`; fiação no monitor `test_sessao_whatsapp.py:193-195` (`prazo == em + 15 min`, `cfg is estado`) | sim |
| Vigia: `pareamento` em dia → sem reinício e sem aviso de laço | `tools/tests/test_vigia_pareamento.py:41-48` (com laço de 3 partidas montado: sem restart, sem start, sem mensagem); controle `:51-55` | sim |
| Vigia: `pareamento` vencido → reinício como hoje | `test_vigia_pareamento.py:74-80` comando inteiro `["systemctl","--user","restart",…]`, log com o banner do QR (pede_qr seria verdadeiro) | sim |
| Lembrete só depois de 6 h | `test_vigia_pareamento.py:58-68` nada às 5h55; mensagens inteiras `…ha 6 h.` e `…ha 12 h.` | sim |
| Reinício: sem `Grupo aberto` → não copia | `tools/tests/test_reinicio_whatsapp.py:265-274` | sim |
| Com `Grupo aberto` → copia sem os caches, troca por `mv` | `test_reinicio_whatsapp.py:244-262` lista exata de arquivos da cópia (`FICAM + copiada_em`, sem caches, sem `restaurada_em`), `.nova`/`.velha` ausentes, linha `copia da sessao: N MB em S s` | sim |
| Cópia falhando → aviso e `start` mesmo assim | `test_reinicio_whatsapp.py:277-293` | sim; aviso conferido por trecho (lacuna L4) |
| Ordem `stop`, cópia, `start` (comando inteiro) | `test_reinicio_whatsapp.py:250-253` `eventos[0] == "--user stop besave-captura-whatsapp.service"`, cópia ausente no stop e presente no start, `len == 4` | sim |
| Vigia RSS 2501 saudável → dispara; 2499 → não | `test_vigia_pareamento.py:91-98` (`START_REINICIO` inteiro, log, `reinicios == []`); `:101-105` (2499 **e** 2500) | sim |
| 2501 com batimento vencido → regra de parado | `test_vigia_pareamento.py:108-113` | sim |
| 2º disparo em 50 min → não; aviso só no 2º em 6 h | `test_vigia_pareamento.py:124-149` (mensagem inteira com `2700 MB`; 3º sem aviso; 2º depois de 6 h sem aviso) | sim |
| Mutantes da spec (teto, `>=` no RSS, cópia sem `Grupo aberto`) | M01, M04, M05 abaixo | mortos |

### Requisitos EARS sem linha própria acima

| req | evidência |
|---|---|
| TEL-01 | `test_pareamento.py:281-295` (5 seletores → tela); `test_pareamento_pagina.py:69-75` com Chromium nas fixtures pt e en; `:91-100` link por texto sem o testid |
| TEL-02 | `test_pareamento.py:298-304` `TimeoutError` com o relógio em 300 s |
| PAR-01 | `test_pareamento_pagina.py:78-88` (pt e en: valor `+55 11 98765-0000`, código `TESTE123`, 1 avanço); `:109-121`; `test_pareamento.py:122-136` (código inválido não vai ao Telegram, novo pedido) |
| PAR-02 | `test_pareamento.py:146-154`; com a página `test_pareamento_pagina.py:123-135` (`__avancos == 0`) |
| PAR-04 | `test_pareamento.py:184-204` (validade e volta ao **QR**); volta ao **número** sem teste (M19, L1) |
| PAR-07 | `test_pareamento.py:115-119,139-140,153` |
| FIX-01 | `test_pareamento.py:97-102` (código `T,E,S,T,E,1,2,3`, sem `<script`, `kpm`, `class=`, nem sequência de 8+ dígitos) |
| VIG-01/02, MEM-01/02 | acima; limite do ambiente `test_vigia_pareamento.py:152-155` |
| COP-01..03 | acima; stop falho → sem cópia e parte `test_reinicio_whatsapp.py:296-305` |
| DOC-01 | revisão: `tools/capture-chat-groups/README.md:6-67` (todas as mensagens novas, chave `pareamento`, VNC, `user_data.copia/`/`user_data.qr/`, restauração à mão); `conf/config.example.json` com `pareamento {numero:"", validade_min:10, _obs}`; `.gitignore` com as pastas novas e `pareamento_pedidos.json` |

## Sensor de discriminação

Worktree descartável do HEAD (`git worktree add --detach`, removido ao fim); cada mutante rodou só o arquivo de
teste relevante, em lotes de 10 (lição 13). Mutantes de bash rodaram no Git Bash pelo próprio teste.

| # | mutante | arquivo | resultado | teste que matou |
|---|---|---|---|---|
| M01 | **sem teto de códigos** (`proximo = None`) | pareamento.py | morto | `test_quarto_pedido_na_mesma_hora_nao_sai_e_virou_a_hora_sai` |
| M02 | teto 4/h | pareamento.py | morto | idem |
| M03 | teto do dia `>` no lugar de `>=` | pareamento.py | morto | `test_teto_por_hora_e_por_dia` |
| M04 | **RSS `>=` no lugar de `>`** | vigia_robos.py | morto | `test_rss_no_limite_ou_abaixo_nao_dispara[2500]` |
| M05 | **cópia sem checar `Grupo aberto`** | reiniciar_whatsapp.sh | morto | `test_sem_grupo_aberto_na_partida_parada_nao_copia` |
| M06 | não marca `restaurada_em` | sessao.py | morto | `test_login_com_copia_nao_tentada_restaura_uma_vez` |
| M07 | apaga `user_data` em vez de mover | sessao.py | morto | idem |
| M08 | exceção do QR vale em `pareamento` vencido | vigia_robos.py | morto | `test_pareamento_vencido_reinicia_como_hoje` |
| M09 | aviso de memória no 1º disparo | vigia_robos.py | morto | `test_rss_acima_do_limite_dispara_o_reinicio_programado` |
| M10 | vigia trata `pareamento` em dia como normal | vigia_robos.py | morto | `test_pareamento_em_dia_sem_reinicio_sem_laco_sem_aviso` |
| M11 | número inteiro no log | pareamento.py | morto | `test_codigo_da_fixture_vai_ao_telegram_com_a_mensagem_inteira` |
| M12 | cópia depois do `start` (ordem trocada) | reiniciar_whatsapp.sh | morto | `test_copia_sem_os_caches_entre_stop_e_start` |
| M13 | não exclui `Default/Code Cache` | reiniciar_whatsapp.sh | morto | idem |
| M14 | espera viva sai do processo (VNC) | pareamento.py | morto | `test_sem_numero_manda_o_vnc_uma_vez_sem_clicar_e_espera_viva` |
| M15 | sem batimento na espera | pareamento.py | morto | `test_espera_viva_bate_a_cada_volta_com_fase_pareamento` |
| M16 | não confere os dígitos do campo | pareamento.py | morto | `test_campo_com_ddi_duplicado_nao_avanca_e_manda_o_vnc` |
| M17 | lembrete a cada 5 h | vigia_robos.py | morto | `test_lembrete_so_depois_de_6_h_e_a_cada_6_h` |
| M18 | janela de memória 40 min | vigia_robos.py | morto | `test_um_por_60_min_e_aviso_so_no_segundo_em_6_h` |
| M19 | **expira só ao voltar ao QR, não ao campo do número** (`estado in (QR,)`) | pareamento.py:261 | **SOBREVIVEU** (28 passed) | — |
| M20 | troca por `cp -r` em vez de `mv` | reiniciar_whatsapp.sh | morto | `test_copia_sem_os_caches_entre_stop_e_start` |
| M21 | marcas da cópia vão para `user_data/` | sessao.py | morto | `test_login_com_copia_nao_tentada_restaura_uma_vez` |
| M22 | hora do código em UTC | pareamento.py | morto | `test_codigo_da_fixture_vai_ao_telegram_com_a_mensagem_inteira` |
| M23 | `restart` em vez de `start --no-block` do reinício | vigia_robos.py | morto | `test_rss_acima_do_limite_dispara_o_reinicio_programado` |
| M24 | `stop` falho ainda copia | reiniciar_whatsapp.sh | morto | `test_stop_que_falha_nao_copia_e_parte` |
| M25 | ignora `restaurada_em` (restaura em laço) | sessao.py | morto | `test_copia_ja_tentada_vai_direto_ao_codigo` |
| M26 | disparo por memória entra na conta dos reinícios de parado | vigia_robos.py | morto | `test_rss_acima_do_limite_dispara_o_reinicio_programado` |
| M27 | memória dispara fora do `rodizio` | vigia_robos.py | morto | `test_rss_alto_fora_do_rodizio_nao_dispara[dormindo]` |
| M28 | aviso de teto a cada volta | pareamento.py | morto | `test_quarto_pedido_na_mesma_hora_nao_sai_e_virou_a_hora_sai` |
| M29 | `user_data.qr` anterior não substituída | sessao.py | morto | `test_login_com_copia_nao_tentada_restaura_uma_vez` |
| M30 | não avisa "vinculado" | pareamento.py | morto | `test_codigo_da_fixture_vai_ao_telegram_com_a_mensagem_inteira` |
| M31 | sem o texto `Next` (en) | pareamento.py | morto (Chromium) | `test_do_qr_ao_codigo_pelos_seletores_reais[en]` |
| M32 | não limpa o campo (`fill("")`) | pareamento.py | morto (Chromium) | `test_do_qr_ao_codigo_pelos_seletores_reais[pt]` |
| M33 | limite padrão 3500 | vigia_robos.py | morto | `test_limite_vem_do_ambiente` |
| M34 | horas do lembrete contadas do último aviso | vigia_robos.py | morto | `test_lembrete_so_depois_de_6_h_e_a_cada_6_h` |
| M35 | sem `copiada_em` | reiniciar_whatsapp.sh | morto | `test_copia_sem_os_caches_entre_stop_e_start` |
| M36 | sem o texto do link en (reserva por texto) | pareamento.py | morto (Chromium) | `test_link_por_texto_quando_o_testid_some` |

**Total: 36 injetados, 35 mortos, 1 sobrevivente (M19).** M19 não é equivalente: com o mutante, a página que
volta ao campo do número só gera pedido novo depois de `validade_min` (12:10 em vez de 12:02 no cenário do teste
da volta ao QR). Árvore real: `git status --porcelain` vazio antes e depois do sensor.

## Lacunas (ordenadas)

1. **L1 — PAR-04 / Saída 3, "voltou ao campo do número" sem teste (M19, motivo do FAIL).**
   `tools/tests/test_pareamento.py`: falta um caso como `test_pagina_voltou_ao_qr_pede_outro_antes_da_validade`
   (`:192-204`) em que a página vai para `p.NUMERO` (não `p.QR`) antes da validade e o 2º pedido sai às 12:02.
2. **L2 — risco de tempo da unidade oneshot.** `tools/vps/systemd/besave-reinicio-whatsapp.service` mantém
   `TimeoutStartSec=300` (comentário ainda fala em "restart"); agora cabem nele `stop` + cópia (~260 MB) + `start`
   + espera de até 180 s. Com disco lento a cópia pode empurrar o script além de 300 s (o systemd mata a espera; a
   cópia em `.nova` nunca vira válida, então não corrompe). Medir no passo 1 do teste real; a regra 4 só permite
   mexer na unidade se o `stop`+`start` exigir.
3. **L3 — teto diário só no nível de `Teto`.** `test_pareamento.py:222-234` prova `proximo` às 00:00 de Brasília,
   mas não há cenário de `Vinculo` com 12 pedidos no dia mandando
   `WhatsApp desconectado: limite de codigos atingido; proximo pedido as 00:00 (Brasilia).` (mensagem inteira).
4. **L4 — aviso da cópia falha comparado por trecho.** `test_reinicio_whatsapp.py:290-291` usa `in`. A spec não
   fixa o texto (só "aviso no Telegram"), mas a regra 3 / lição 14 pedem mensagem inteira; o mesmo vale para o
   aviso de `stop` falho (`:304`).
5. **L5 — "espera por `Grupo aberto` conta a partir do `start`"** sem teste dedicado; vale por construção
   (`decorrido=0` em `reiniciar_whatsapp.sh:137`, depois do `start` em `:116`).
6. **L6 — estilo:** `tools/vps/vigia_robos.py:574` tem uma condição com ~17 espaços no meio da linha (barra de
   continuação perdida). Funciona e o ruff passa; só legibilidade.

## Desvios e lacunas de precisão da spec

- **`start --no-block`** no lugar do `start` da Saída 6 (`vigia_robos.py:600`): justificado; a unidade é
  oneshot de até 300 s e o vigia espera cada `systemctl` até 150 s (`TIMEOUT_SYSTEMCTL_S`, `vigia_robos.py:53`).
  O vigia não age enquanto a unidade do reinício está `activating/active` (`:512`). Aceito.
- **Máscara divergente:** além de não avançar, o robô passa ao modo VNC e não pede de novo nessa partida
  (`pareamento.py:271-275`). A spec diz "divergente → não avança, log sem o número e mensagem do VNC"; a premissa
  do spec.md registra a escolha. Aceito.
- **Teto por hora cheia e dia de calendário de Brasília** (`pareamento.py:116-126`): a spec diz "3 por hora e
  12 por dia… espera a próxima hora cheia" sem fixar janela deslizante ou calendário; a escolha é coerente com
  "virou a hora → sai". Persistido em `conf/pareamento_pedidos.json` (fora do git).
- **Aviso de teto "uma vez":** uma vez por próximo horário e por partida (estado em memória do `Vinculo`); um
  reinício do processo pode repetir a mensagem. A spec não define além de "uma vez".
- **`<data Brasilia>` da Saída 2** sai como `DD/MM HH:MM`; a spec não fixa formato.
- **Código que não aparece ou é inválido conta no teto** (registrado antes de avançar, `pareamento.py:276`):
  coerente com a regra 5 (o WhatsApp registrou o pedido).
- **FIX-01 do spec.md** fala em tela do código "em pt e en"; só há `codigo_pt.html` (a spec do dono só traz o
  pt e o agente não pediu código, como manda a Saída 7). Fixture do código a conferir no passo 3 do teste real.
- **Lembrete do vigia:** o 1º sai 6 h depois de o vigia **ver** a fase `pareamento` (não do início da espera do
  robô); N = horas desde que viu. Diferença de no máximo um ciclo do vigia.
- **Bloqueia o merge (dono, inst1, branch da PR):** os 5 passos reais da spec; nenhum foi executado aqui.

## Lições propostas

- Mutante de "OU" na condição de saída (`estado in (A, B)`) exige um teste por alternativa: o teste de uma só
  deixa a outra viva (M19).
- Quando um ticket aumenta o trabalho de uma unidade oneshot, a spec deve pedir revisão do `TimeoutStartSec`
  com a soma medida das fases (L2).
