# BSV-54 - validation.md

**Verificador:** sub-agente independente (autor != verificador), Claude Sonnet 5.5, sobre o commit c7be830.
**Veredito geral: PASS COM RESSALVAS** (2 ajustes recomendados antes do merge, 3 mutantes sobreviventes nao críticos; execução real pendente do dono).

## Gates executados

| gate | resultado |
|---|---|
| `cd tools && python -m pytest -q` | 248 passed (62 s) |
| `python -m ruff check tests capture-chat-groups/wa/avisar.py` | All checks passed |
| `shellcheck tools/vps/*.sh` | NÃO VERIFICÁVEL AQUI (não instalado no Windows). Rodar: `shellcheck tools/vps/*.sh` |
| `systemd-analyze --user verify tools/vps/systemd/*` | NÃO VERIFICÁVEL AQUI. Rodar na inst1: `systemd-analyze --user verify tools/vps/systemd/*` |

## Critério de aceite

| # | critério | veredito | evidência |
|---|---|---|---|
| 1 | shellcheck / systemd-analyze limpos | PENDENTE (não verificável aqui) | comandos acima; revisão manual do script sem achados óbvios (variáveis entre aspas, `set -u`, `|| true` nos pontos certos) |
| 2a | partida confirmada -> sem aviso | PASS | script `tools/vps/reiniciar_whatsapp.sh:76-83`; teste `tools/tests/test_reinicio_whatsapp.py:91` (REI-01), `:100` (REI-01b); log de ontem não confirma `:106` |
| 2b | `ABORTADO: contador atrasado` -> aviso com o motivo | PASS | `reiniciar_whatsapp.sh:90-92,98`; teste `test_reinicio_whatsapp.py:113` |
| 2c | unidade não sobe em 3 min -> aviso | PASS | `reiniciar_whatsapp.sh:27,93-94,98`; teste `:122`; restart que falha `:130`, script `:56-59` |
| 2d | parada de propósito -> não reinicia | PASS | `reiniciar_whatsapp.sh:42-46` (só `inactive`); testes `:137` e `:146` (failed ainda reinicia) |
| 2e | mutante "sempre/nunca avisa" falha | PASS | M1, M2 mortos (tabela) |
| 3 | entrada de aviso: sem token -> só log, 0; com token -> chama envio; token não aparece | PASS | `tools/capture-chat-groups/wa/avisar.py:27-31` (sem token, retorno 0), `:33` (envio), `:34-35` (só o tipo do erro); testes `tools/tests/test_avisar.py:19,25,30,37,47`; M14 manual morto |
| 3b | token/chat fora da linha de comando | PASS | `reiniciar_whatsapp.sh:36` passa só o texto; token lido do config em `avisar.py:21-28` |
| 4 | timer 05:30 provado pelo arquivo | PASS | `tools/vps/systemd/besave-reinicio-whatsapp.timer:117` `OnCalendar=*-*-* 05:30:00`, `Persistent=false`; teste `test_unidades.py:118`; M15, M16 mortos |
| 5 | Teto de memória só no robô do WhatsApp | PASS | `besave-captura-whatsapp.service:28-29` `MemoryHigh=3G`, `MemoryMax=4G`; `Restart=on-failure` `:22`; teste `test_unidades.py:132`; M17, M18 mortos |
| 6 | README: horário, onde ver, como desligar | PASS | `tools/vps/README.md:184-201` (journalctl, disable --now) |
| 7 | Regra 1: sem matar processo por nome | PASS | script só usa `systemctl restart`; teste `test_reinicio_whatsapp.py:168`; M11 (pkill) morto |
| 8 | Real na inst1 (dono) | PENDENTE | ver lista abaixo |

## Sensor de discriminação (mutantes)

Testes relevantes rodados por mutante; arquivos restaurados (`git status` limpo ao final).

| mutante | alvo | resultado |
|---|---|---|
| M1 sempre avisa | reiniciar_whatsapp.sh | morto |
| M2 nunca avisa (avisar vira `true`) | reiniciar_whatsapp.sh | morto |
| M3 ignora `inactive` | reiniciar_whatsapp.sh | morto |
| M4 `!= active` em vez de `= inactive` (failed não reinicia) | reiniciar_whatsapp.sh | morto |
| M5 ignora estado `active` na confirmação | reiniciar_whatsapp.sh | morto |
| M6 confirma com log antigo | reiniciar_whatsapp.sh | morto |
| M7 motivo sem ABORTADO | reiniciar_whatsapp.sh | morto |
| M8 padrão só `Grupo aberto` | reiniciar_whatsapp.sh | morto |
| M9 `journalctl --since` com data futura | reiniciar_whatsapp.sh | **SOBREVIVEU** (journalctl falso ignora os argumentos) |
| M10 ignora falha do restart | reiniciar_whatsapp.sh | morto |
| M11 `pkill -f chrome` | reiniciar_whatsapp.sh | morto |
| M12 RSS = primeiro processo > 0 em vez do maior | reiniciar_whatsapp.sh | **SOBREVIVEU** (fixture lista o maior primeiro) |
| M13 sem token retorna 1 | avisar.py | morto |
| M14 (manual) token/erro completo impresso na falha | avisar.py:35 | morto |
| M15 OnCalendar 06:30 | timer | morto |
| M16 Persistent=true | timer | morto |
| M17 MemoryMax=8G | captura service | morto |
| M18 remove MemoryHigh | captura service | morto |
| M19 espera padrão 180 -> 10 | reiniciar_whatsapp.sh | **SOBREVIVEU** (testes usam `BESAVE_ESPERA_MAX=1`; nada afirma os 3 min padrão) |
| M20 `Type=simple` | reinicio service | morto |

## Achados

1. **Recomendado corrigir (baixo risco):** `tools/vps/reiniciar_whatsapp.sh` está com modo git `100644` (os demais `.sh` de `tools/vps` são `100755`). O service o executa direto (`besave-reinicio-whatsapp.service:107`). O README (`:32`) manda `chmod +x *.sh` na instalação, o que mitiga, mas o correto é `git update-index --chmod=+x tools/vps/reiniciar_whatsapp.sh`.
2. **Gaps de teste (não bloqueiam):** M9 (argumento `--since` do journal), M12 (o "maior" RSS: pôr o maior processo fora da primeira posição na fixture) e M19 (afirmar `ESPERA_MAX` padrão 180 e `TimeoutStartSec` > espera). Sugestão: fixture do ps com o maior em segundo lugar; journalctl falso que registra os argumentos.
3. Lógica revisada sem defeito: log novo é detectado por nome (o lançador nunca reaproveita arquivo, sufixos `_b`..`_h` em `iniciar_captura.sh:72-77`); estado `activating` apenas continua o laço; `set -u` sem variável sem valor padrão; `journalctl --since` tem resolução de segundo (risco teórico de pegar linha do robô antigo no mesmo segundo, só se ela contiver o padrão de OK; baixo).
4. A casa do caminho `ExecStart=/srv/besave/repo/...` é igual à do `besave-captura-whatsapp.service:20`; consistente.
5. **Regra 11:** busca por `C:\Users`, token de bot e IPs nos arquivos novos: nenhum achado. Não há arquivos de evidência de execução real no commit (ainda não existem).

## Pendente do dono (bloqueia o merge)

1. Na inst1: `shellcheck tools/vps/*.sh` e `systemd-analyze --user verify tools/vps/systemd/*`.
2. Instalar com a branch, `systemctl --user daemon-reload`, `enable --now besave-reinicio-whatsapp.timer`.
3. `systemctl --user start besave-reinicio-whatsapp` uma vez; conferir `journalctl _SYSTEMD_USER_UNIT=besave-reinicio-whatsapp.service` (RSS antes + "OK"), captura retomada e contador.
4. Confirmar que o `--user-data-dir` visto no `ps` do Chromium real bate com `$RAIZ/user_data` (`pwd -P`), senão o RSS sai 0 MB (só afeta o log).
5. Deixar 2 noites; anotar RSS antes de cada reinício (esperado <= ~2,5 GB) e `free -h` às 08:00 (redigir antes de commitar, regra 11).
6. Testar o aviso real: `cd tools/capture-chat-groups && .venv/bin/python -m wa.avisar "teste"` com o config real.
7. Decisões a propor ao DECISOES.md: horários 05:30/11:30/17:30/23:30 (a cada 6 h, medição de 06–07/11), `MemoryHigh=3500M`/`MemoryMax=4500M` (mantidos) (com a medição real).

---

# Rodada 2 - teto no scope do tmux (commit 6d199c9 sobre ad8cbc7)

**Verificador:** sub-agente independente (autor != verificador), Claude Sonnet 5.5.
**Veredito: PASS COM RESSALVAS** (1 mutante sobrevivente de baixo risco; execucao real na inst1 pendente do dono).

## Gates

| gate | resultado |
|---|---|
| `cd tools && python -m pytest -q` | 254 passed (70 s) |
| `python -m ruff check tests` | All checks passed |
| shellcheck / `systemd-analyze --user verify` | NAO VERIFICAVEL AQUI (Windows) - rodar na inst1 |

## Itens do pedido

| # | item | veredito | evidencia |
|---|---|---|---|
| 1 | robo no painel por `systemd-run --user --scope --unit=besave-whatsapp-robo -p MemoryHigh/Max -p KillSignal=SIGINT -p TimeoutStopSec=30 -- cmd`, valores do Environment, so WhatsApp | PASS | `tools/vps/iniciar_captura.sh:35-37` (defaults 3500M/4500M), `:112-114` (comando); lojas inalteradas (`test_unidades.py:140`). Teste compara o comando inteiro: `test_scope_whatsapp.py:28-39` (prefixo, -p, `--`, python, argumentos; `interno` e `DISPLAY=:2` antes) e `:42-47` (valores customizados, 3500M ausente). Fallback sem systemd-run: `:111-116`, teste `:59-64` |
| 1b | cadeia de rc | PASS (parcial de ponta a ponta) | `rodar_em_tmux.sh` `interno` (`rc=${PIPESTATUS[0]}`, grava o arquivo, `exit "$rc"`) + `esperar`; teste `test_scope_whatsapp.py:67-79` roda `interno` e `esperar` reais com systemd-run falso rc 137. Nao passa pelo tmux nem pela unidade (isso so a inst1 prova) |
| 2 | ExecStop para o scope, tolera ausente, sem encerrar_captura.sh | PASS | `besave-captura-whatsapp.service` ExecStop=`-/usr/bin/systemctl --user stop besave-whatsapp-robo.scope`; teste `test_unidades.py:143-147` (igualdade exata; `TimeoutStopSec >= 40` cobre scope 30 s + folga; unidade = 45) |
| 3 | scope existente na partida -> falha com mensagem clara | PASS | `iniciar_captura.sh:76-78` (antes do contador e do tmux); teste `test_scope_whatsapp.py:50-56` (rc != 0, mensagem, sem `new-session`, contador nem roda) |
| 4 | MemoryHigh/Max fora da unidade; README/comentarios sem "SIGINT da unidade chega ao robo" | PASS | `test_unidades.py:132-140`; Environment com BESAVE_MEM_HIGH/MAX na unidade; comentarios da unidade, `iniciar_captura.sh:16-18` e `reiniciar_whatsapp.sh:11-12` descrevem o scope |
| 5 | testes com systemctl/systemd-run falsos, comando inteiro; ExecStop e Environment pelo arquivo | PASS | `test_scope_whatsapp.py` (fixture `amb`), `test_unidades.py:132-147` |

Frouxidoes avaliadas: `test_sem_segredo` (`test_unidades.py:40-44`) ainda passa porque a unidade nao contem `token/senha/secret/pass=` (os nomes BESAVE_MEM_* nao casam). `systemctl` ausente: `is-active` com `2>/dev/null` e `if` -> falha vira "scope inexistente" e o lancador segue (comportamento desejado; sem teste dedicado). ExecStop com `-`: so tolera scope ausente, mas tambem esconde falha real do stop (o scope vivo apos o stop nao e detectado ali; o proximo `iniciar` recusa pela checagem 2b).

## Sensor de discriminacao (21 mutantes, testes: scope_whatsapp + unidades + iniciar_captura)

Arquivos restaurados (`git status` limpo).

| mutante | resultado |
|---|---|
| M1 sem MemoryMax / M2 sem MemoryHigh | morto |
| M3 SIGTERM no lugar de SIGINT | morto |
| M4 sem `--` | morto |
| M5 sem `--scope` | morto |
| M6 `--unit` diferente | morto |
| M7 sem checagem do scope | morto |
| M8 sem TimeoutStopSec=30 no systemd-run | morto |
| M9 sem ExecStop | morto |
| M10 ExecStop sem `-` | morto |
| M11/M12 defaults 3000M / 4000M | morto |
| M13 Environment da unidade 3G | morto |
| M14 MemoryMax=4G de volta na unidade | morto |
| M15 rc engolido no `interno` (`exit 0`) | morto |
| M16 ExecStop chama encerrar_captura.sh | morto |
| M17 TimeoutStopSec da unidade 15 | morto |
| M18 ExecStop para outro scope | morto |
| M19 fallback sempre direto | morto |
| M21 rc de `tee` (PIPESTATUS[1]) | morto |
| **M20 `is-active` sem `--user`** | **SOBREVIVEU**: o systemctl falso casa so " is-active ". Sugestao: o falso exigir `--user` (ex.: `case " $* " in *" --user is-active --quiet besave-whatsapp-robo.scope "*`). Em producao sem `--user` consultaria o gerenciador do sistema e nunca veria o scope: a protecao 2b sumiria silenciosamente |

## Riscos que so a inst1 prova

1. `systemd-run --user --scope` faz exec do comando: o rc do `interno` deve ser o do python. Morte por sinal (OOM = SIGKILL) tem de virar rc 137 no `PIPESTATUS`; conferir com um `kill -9` do python e `systemctl --user status`.
2. O scope precisa existir sem sessao grafica: depende de `loginctl enable-linger besave` e do bus de usuario dentro do tmux (`XDG_RUNTIME_DIR`/`DBUS_SESSION_BUS_ADDRESS` herdados pelo painel). Sem isso `systemd-run --user` falha ("Failed to connect to bus") e o painel sai na hora (a unidade falha e reinicia a cada 30 s).
3. Escopo vs. painel: se o painel morrer (fim do `interno`), o scope termina junto com o python; conferir que nao sobra scope em `deactivating`/`failed` (`systemctl --user list-units 'besave-whatsapp*'`). Scope `failed` de OOM tem de ser limpo (`reset-failed`), senao o nome pode bloquear a partida seguinte (a checagem usa `is-active`, entao `failed` nao bloqueia, mas confirmar).
4. Restart: o ExecStop espera o scope sair (ate 30 s, KillSignal=SIGINT do scope) e a unidade tem 45 s; confirmar na pratica que o `finally` grava o contador em < 30 s e que o reinicio das 05:30 nao cai em `activating` com scope ainda `deactivating` (o lancador falharia com a mensagem do scope e o Restart=on-failure tentaria de novo em 30 s).
5. `MemoryHigh/Max` no scope: confirmar com `systemctl --user show besave-whatsapp-robo.scope -p MemoryHigh -p MemoryMax` e `systemd-cgls` que python e Chromium estao DENTRO do scope; controlador `memory` delegado ao usuario (cgroup v2 com delegacao; sem ela o scope sobe sem teto e sem erro).
6. Fallback `AVISO ... SEM teto`: so aparece em stderr/journal; se systemd-run faltar na inst1 o teto some silenciosamente.

## Pendente do dono (bloqueia o merge)

1. inst1: `shellcheck tools/vps/*.sh`, `systemd-analyze --user verify tools/vps/systemd/*`.
2. Reinstalar a unidade, `daemon-reload`, `restart`; provar: `systemctl --user show besave-whatsapp-robo.scope -p MemoryHigh -p MemoryMax` = 3500M/4500M, python e Chromium no scope (`systemd-cgls`).
3. `systemctl --user stop besave-captura-whatsapp` -> o `finally` grava o contador (log) e nenhum scope sobra.
4. `kill -9` no python -> unidade `failed` -> reinicia em 30 s sem scope preso.
5. Ensaio de OOM (MemoryMax baixo, ex.: BESAVE_MEM_MAX=300M) -> rc != 0 e Restart=on-failure.
6. Disparar `reiniciar_whatsapp.sh` uma vez e conferir "OK".
7. (recomendado) fechar M20 no teste antes do merge.

---

# Rodada 3 - scope `failed` nao trava a partida (commit bfafcab sobre 0f2d406)

Verifier independente (autor != verificador), Sonnet 5.5. Nenhum codigo alterado alem de mutantes temporarios (restaurados; `git status` limpo).

## Gates
- `cd tools && python -m pytest -q`: 257 passed (70 s).
- `python -m ruff check tests`: All checks passed.
- Sem systemd/tmux nesta maquina (Windows + Git Bash): tudo com systemctl/systemd-run/tmux falsos. O que so a inst1 prova esta marcado [inst1].

## Itens do pedido (evidencia file:line)
| # | item | evidencia | teste |
|---|---|---|---|
| 1 | `systemd-run ... --collect` | `tools/vps/iniciar_captura.sh:111` | `test_scope_whatsapp.py:11,35-47` (comando inteiro, `PREFIXO` com `--collect` na posicao exata) |
| 2 | `reset-failed` e `revert` so com scope inativo, erros ignorados | `iniciar_captura.sh:78-80` (guarda `is-active` que aborta) -> `:85-86` (`>/dev/null 2>&1 \|\| true`) | `test_scope_whatsapp.py:91-99` (ordem: is-active, reset-failed, revert, tmux new-session), `:102-105` (scope ativo: so o is-active, nada tocado) |
| 3 | mensagem do systemd-run no ABORTADO | `iniciar_captura.sh:126-127` (ultima linha nao vazia do log, 300 col) | `test_scope_whatsapp.py:108-122` |
| 4 | testes | acima; mutante sem `--collect` morre | ver mutantes |

## Sensor de discriminacao (16 mutantes em `iniciar_captura.sh`, teste: `test_scope_whatsapp.py`, um por vez)
| mutante | resultado |
|---|---|
| M1 sem `--collect` | MORREU |
| M2 sem `reset-failed` | MORREU |
| M3 sem `revert` | MORREU |
| M4 reset/revert depois do tmux | MORREU |
| M5 reset/revert antes do `is-active` (tocariam scope ativo) | MORREU |
| M6 `\|\| true` removido | SOBREVIVEU - **equivalente**: o script usa `set -u`, sem `-e` (`iniciar_captura.sh:26`); rc do systemctl nao aborta nada |
| M7 sem a mensagem do systemd-run no ABORTADO | MORREU |
| M8 `--collect` depois do `--unit` | MORREU (teste compara a lista inteira) |
| M9 `is-active` sem `--user` | MORREU |
| M10 `reset-failed` sem `--user` | MORREU |
| M11 `revert` sem `--user` | MORREU |
| M12 `revert` antes de `reset-failed` | MORREU |
| M13 `reset-failed` sem o sufixo `.scope` | MORREU |
| M14 ordem do texto do ABORTADO (mensagem antes de "captura nao subiu") | SOBREVIVEU - cosmetico, teste usa `in`; aceito |
| M15 `tail -n 1` -> `head -n 1` na ultima linha | SOBREVIVEU - **lacuna real, menor**: o log falso tem 1 linha so. Um log com 2+ linhas (ex.: aviso e depois o erro) nao e coberto. Sugestao: SCO-07 com duas linhas e exigir a ultima |
| M16 `--collect` so no ramo sem systemd-run | MORREU |

Dos 16: 13 mortos, 1 equivalente (M6), 1 cosmetico (M14), 1 lacuna menor (M15).

## O que ainda pode travar a partida em laco (analise)
1. **Contador de logs do dia (`iniciar_captura.sh:96-101`): risco real, nao corrigido nesta rodada.** Ha 8 nomes por dia (base + `b..h`); cada partida que passa do `checa_contador` cria um log (o `tee -a` cria mesmo se o robo morre na hora). Com `Restart=on-failure`/`RestartSec=30` e `StartLimitIntervalSec=0`, qualquer falha persistente logo apos o passo 4 (sem bus de usuario, "already loaded" antes desta correcao, tela ainda subindo) esgota os 8 em ~4 minutos; dali a unidade falha com "muitos logs para hoje" (que esconde a causa) ate virar o dia. Mesmo sem laco: 8 partidas/dia e pouco (reinicio das 05:30 + cada OOM/crash + restarts manuais). Recomendacao ao dono: nome por `HHMMSS` (ou sufixo numerico sem limite) e rotacao dos antigos. Fora do pedido desta rodada; registrado como pendencia/decisao.
2. `revert` em unidade transitoria: `systemctl --user revert` num scope transitorio pode responder erro ("transient"/"not loaded"); como o erro e ignorado nao trava. Nota: `revert` faz um daemon-reload do gerenciador de usuario, inofensivo mas nao verificado. [inst1]
3. Scope em `deactivating`/`stopping`: `is-active` devolve nao-zero (so `active` e 0), entao o lancador segue, `reset-failed` e no-op e o `systemd-run` pode falhar com "already loaded". Agora isso nao e mais mudo: o ABORTADO traz a mensagem e o `Restart` tenta em 30 s. Janela estreita porque o `ExecStop` espera o scope sair (ate 30 s). Fecha so com o teste de restart real. [inst1]
4. `reset-failed` num scope ja descarregado (caso normal com `--collect`): erro "not loaded", ignorado; a chamada so e util para o residuo de scopes criados antes do `--collect` (por isso fica como defesa). [inst1 para confirmar a mensagem]
5. `--collect` x `ExecStop=-systemctl --user stop ...scope` (`besave-captura-whatsapp.service:27`): com o scope ja coletado o `stop` devolve "not loaded" e o `-` ignora; o `is-active` de scope inexistente tambem e nao-zero. Coerente, mas [inst1].
6. `--collect` em `--scope`: a opcao existe no `systemd-run` desde o systemd 236; que ela de fato descarregue um **scope** em `failed` (e nao so servicos) so a inst1 prova: `kill -9` no python, `systemctl --user list-units 'besave-whatsapp*' --all` vazio e o proximo `systemd-run` subindo. [inst1]
7. A mensagem do systemd-run chega ao log via `2>&1 | tee -a` do `interno` (`rodar_em_tmux.sh:54`) e entra como ultima linha; so vale se o systemd-run for o ultimo a escrever (nao ha mais saida depois dele). Coberto no teste por simulacao do tmux, nao por processo real.

## Veredito rodada 3: PASS (com ressalvas)
Os 4 itens do pedido estao implementados e discriminados pelos testes; mutante sem `--collect` morre. Ressalvas: M15 (lacuna menor de teste) e o contador de 8 logs/dia (risco operacional, fora do escopo pedido).

## Pendente do dono (bloqueia o merge)
1. Tudo da rodada 2 continua valendo (shellcheck, `systemd-analyze --user verify`, show MemoryHigh/Max, stop com `finally`, `kill -9`, OOM, `reiniciar_whatsapp.sh`).
2. Prova do bug original corrigido na inst1: com um scope `failed` carregado (reproduzir com `kill -9` no python, ou `systemctl --user list-units --failed`), subir a unidade: o lancador deve limpar e subir o robo; e sem scope residuo depois de um novo `kill -9` (efeito do `--collect`).
3. Decidir o contador de logs (8/dia): nome por hora ou sufixo sem limite; recomendado antes de agendar, para nao esconder a causa em laco de falhas.
4. (opcional) fechar M15 com um log de 2 linhas no SCO-07.

---

# Rodada 4 - nome do log (Verifier independente, autor != verificador)
Escopo: so o item "nome do log" (commit `99ecb53` sobre `61f2f57`). Executado em 05/11/2026.

## Evidencia 1-4
| # | Requisito | Evidencia |
|---|---|---|
| 1 | log `run_captura_DD_MM_HHMMSS.log`; se existir, `_2`, `_3`... sem limite; some o "muitos logs para hoje" | `tools/vps/iniciar_captura.sh:98-104` (`base`, `n=2`, `while [ -e "$log" ]`); `grep "muitos logs" tools/vps` = vazio |
| 2 | nao reaproveita log de run anterior | mesmo laco `:101-104`; teste `test_sh04_nao_sobrescreve_log_preexistente` e `..._nao_colidem_e_nao_reaproveitam` (confere conteudo intacto dos 10 logs) em `tools/tests/test_iniciar_captura.py` |
| 3 | consumidores por nome | `tools/vps/reiniciar_whatsapp.sh:54` (`logs_antes`), `:63-71` (`novos_logs`: `grep -qxF`, linha inteira); `tools/vps/README.md:8,90-94,169` (`ls -t ... \| head -n 1`); `tools/tests/test_scope_whatsapp.py` SCO-07 (log = argumento `*.log` do tmux); `test_reinicio_whatsapp.py` REI-02/02b |
| 4 | testes | `test_sh04_dez_partidas_no_mesmo_dia_geram_dez_logs_distintos` (10 partidas, 10 nomes, todas sobem), `test_sh04_partidas_no_mesmo_segundo_nao_colidem_e_nao_reaproveitam` (10 no mesmo segundo: base, `_2`.. `_10`), `test_sh04_nao_sobrescreve_log_preexistente`, `test_log_novo_com_sufixo_nao_se_confunde_com_o_antigo` |

Outros consumidores do padrao antigo (grep `run_captura_`/`muitos logs` em tools/ e docs/): `encerrar_captura.sh` usa so `run_captura\.py` (processo), nao o log; `diag/` nao le logs por nome; `.gitignore` usa glob `run_captura_*.log` (continua valido); `RESUMO.md` e historico. **Unica inconsistencia: `tools/capture-chat-groups/iniciar_captura.ps1:64-70` (PC/Windows) mantem `DD_MM` + `_b.._h` + falhar "muitos logs para hoje"**. Nao e perigosa para a VPS (outra maquina, outro lancador, ninguem a le junto), mas tem o mesmo defeito de limite. Fora de `tools/vps`; fica como decisao do dono (ticket proprio, `tools/capture-*` exige ticket explicito).

## Gates
- `cd tools && python -m pytest -q`: **260 passed** (97 s). `python -m ruff check tests`: All checks passed.

## Mutantes (um por vez, foreground; `git checkout` apos cada; `git status` limpo no fim)
| # | mutante | resultado |
|---|---|---|
| M1 limite reintroduzido (`[ "$n" -le 8 ] \|\| falhar "muitos logs para hoje"` dentro do laco) | MORREU (`..._mesmo_segundo_nao_colidem...`) |
| M2 sem sufixo (laco faz `break`, reaproveita o log) | MORREU (mesmo teste) |
| M3 sem HHMMSS (`'+%d_%m'`) | MORREU (`..._dez_partidas...`) |
| M4 contador comecando em 1 (`base_1.log`) | MORREU (espera `_2`). Analise: com `n=1` nao colidiria com o nome base (`base.log` != `base_1.log`), so mudaria a convencao; o teste fixa `_2` |
| M5 `[ -e` -> `[ -f` | SOBREVIVEU - **equivalente** para arquivos regulares; so difere para diretorio ou symlink quebrado com esse nome (nao ocorre) |
| M7 `grep -qxF` -> `grep -qF` (sem `-x`) em `novos_logs` | SOBREVIVEU - **equivalente**: o sufixo vem antes de `.log`, entao `X.log` nunca e substring de `X_2.log` nem vice-versa (paths completos, mesmo diretorio); `-x` e defesa, nao ha entrada que a separe |
| M8 todo log conta como novo (remove o filtro) | MORREU (`test_log_de_ontem_nao_confirma`) |
| M9 nenhum log conta como novo | MORREU (`test_partida_confirmada_nao_avisa`) |
| M10 `logs_antes=""` | MORREU (`test_log_de_ontem_nao_confirma`) |
| M11 laco desligado (`while false`, sempre append no base) | MORREU |

Dos 10: 8 mortos, 2 equivalentes (M5, M7). Mutante que reintroduz limite morre (M1).

## Riscos
1. **`date` sem `BESAVE_DATE`**: default `date`; se falhasse, o nome seria `run_captura_.log` e o laco `-e` ainda daria `_2`... (continua partindo). OK.
2. **Relogio recuando (NTP/ajuste)**: pode gerar nome de hora ja usada; o laco `-e` desambigua (`_2`). `reiniciar_whatsapp.sh` usa diferenca de conjuntos antes/depois (nao ordem por nome/mtime), logo imune. Sem horario de verao no Brasil desde 2019. OK.
3. **Colisao entre anos** (`DD_MM` sem ano): so se o mesmo dia/mes/hora/min/seg se repetir; e mesmo assim sai `_2`. **Nao ha limpeza de logs em lugar nenhum** (grep: nenhum `rm`/logrotate para `log/`): o diretorio so cresce (e esta no `.gitignore`).
4. **Crescimento do `log/`**: com falha persistente que passe do passo 4 (`Restart=on-failure`, `RestartSec=30`, `StartLimitIntervalSec=0`) sao ate ~2 partidas/min incl. os 8 s de espera, isto e, **ate ~2.000-2.900 arquivos/dia**, cada um pequeno (poucas linhas). Efeitos: (a) `ls "$RAIZ"/log/run_captura_*.log` em `reiniciar_whatsapp.sh:54` e no README expande o glob na linha de comando de um `ls` exec'ado: o ARG_MAX tipico do Linux (~2 MB) so estoura com ~15-20 mil arquivos (~1 semana de falha continua); com o estouro, `ls` falha, `|| true` zera `logs_antes` e **todo** log passaria a ser "novo" (pode confirmar a retomada com log velho: falso OK), nao ha aviso. (b) `novos_logs` roda um `grep` por arquivo a cada poll: O(N) processos por poll (N=3.000 -> alguns segundos), tolerado dentro de `ESPERA_MAX`. (c) o `for f in "$RAIZ"/log/...` e expansao interna do shell, sem ARG_MAX. Mitigacao sugerida (nao feita, fora do pedido): rotacao (`find log -name 'run_captura_*.log' -mtime +14 -delete` no timer do reinicio) e/ou trocar `ls` por `printf '%s\n' glob` (builtin, sem ARG_MAX). A causa raiz de uma falha em laco e agora visivel (cada log traz a mensagem), que era o objetivo.

## Veredito rodada 4: PASS
Itens 1-4 implementados e discriminados; limite reintroduzido morre; 2 sobreviventes equivalentes justificados; 260 testes e ruff verdes.

## Pendencias do dono
1. Decidir limpeza/rotacao de `log/` (nao existe) e, se quiser, trocar o `ls` do `reiniciar_whatsapp.sh:54` por `printf` (builtin) para eliminar o risco de ARG_MAX.
2. `iniciar_captura.ps1` (PC) ainda tem o limite `_b.._h` e "muitos logs para hoje": ticket proprio se o PC ainda for usado.
3. Continuam valendo as pendencias de execucao real das rodadas 2 e 3 (inst1).

---

## Rodada 5 - 5d25ea1

Verifier independente (autor != verificador). Escopo: so o commit 5d25ea1 (`PADRAO_OK='Grupo aberto'` em `tools/vps/reiniciar_whatsapp.sh:30`; `grep -qxF -- "$f" <<<"$logs_antes"` em `:69`; testes REI-07/REI-08 e ajustados em `tools/tests/test_reinicio_whatsapp.py:92-134`, `:168-172`).

Execucao: `test_reinicio_whatsapp.py` 13 passed; suite `tools/tests` 262 passed; `ruff check` do arquivo de teste verde.

### Criterios
| item | evidencia | resultado |
|---|---|---|
| So `Grupo aberto` confirma; `Retomando contador` sozinho nao (falso positivo de 08/11) | `reiniciar_whatsapp.sh:30,83`; `test_reinicio_whatsapp.py:121-127` (REI-07: exige returncode != 0, 1 aviso com "sem 'Grupo aberto'", sem "OK:") | PASS |
| Motivo do aviso atualizado | `reiniciar_whatsapp.sh:99`; asserts em `test_reinicio_whatsapp.py:111,127` | PASS |
| `printf\|grep -qxF` trocado por here-string em `novos_logs` | `reiniciar_whatsapp.sh:69` | PASS no codigo; teste REI-08 nao discrimina (ver abaixo) |

### Mutantes (um por vez, arquivo restaurado e `cmp` com copia apos cada)
| # | mutante | resultado |
|---|---|---|
| M1 | `PADRAO_OK='Retomando contador\|Grupo aberto'` | MORTO (REI-07) |
| M2 | `PADRAO_OK=''` | MORTO (3 testes: log_de_ontem, REI-07, contador_atrasado) |
| M3 | `PADRAO_OK='.'` | MORTO (REI-07, contador_atrasado) |
| M4 | `grep -Eq "$PADRAO_OK"` trocado por `true` (sempre casa) | MORTO (3 testes) |
| M5 | remove a checagem `est = active` (`true && printf ...`) | SOBREVIVEU - lacuna real, ver nota 1 |
| M6 | volta a `printf '%s\n' "$logs_antes" \| grep -qxF` | SOBREVIVEU - REI-08 nao detecta, ver nota 2 |
| M7 | `grep -qxF` -> `grep -qx` (sem `-F`) | SOBREVIVEU - equivalente na pratica: `.` do path casa a si mesmo e `-x` ja exige linha inteira; so difere se o nome tiver metacaractere que case outro arquivo (nomes sao `run_captura_DD_MM_HHMMSS[_n].log`) |
| M8 | `grep -qxF` -> `grep -qF` (sem `-x`) | SOBREVIVEU - equivalente (mesmo argumento do M7 da rodada 4: sufixo antes de `.log`, nenhum path e substring de outro) |
| M9 | `false && continue` (todo log conta como novo) | MORTO (3 testes) |
| M10 | `true && continue` (nenhum log conta como novo) | MORTO (4 testes) |
| M11 | `logs_antes=$(true; for ...)` | EQUIVALENTE (no-op; mutante mal formado, nao conta) |

Dos 10 validos (M1-M10): 7 mortos, 2 equivalentes (M7, M8), 2 sobreviventes que exigem nota (M5, M6) - M6 e a limitacao do REI-08.

### Notas
1. **M5 (lacuna de teste, severidade baixa).** Nenhum teste tem unidade `!= active` junto com `Grupo aberto` no log novo; `test_unidade_que_nao_sobe_avisa` (REI-04) nao poe o padrao no log. Sem a checagem `est=active`, uma unidade morta com log novo contendo `Grupo aberto` confirmaria OK. Pre-existente (nao foi tocado pelo commit), mas o commit reescreveu esse caminho. Sugestao: REI-04 com `log_novo = "Grupo aberto\n"` e `estado_depois = "failed"`.
2. **REI-08 (`test_sem_broken_pipe_no_stderr`) nao pega o mutante M6.** O ambiente tem 1 log antigo (`logs_antes` com ~60 bytes): `printf` termina de escrever antes de o `grep -q` fechar o pipe, entao nunca ha `EPIPE`. O erro so aparece com a lista maior que o buffer do pipe (64 KB, ~800+ logs). Tentei reproduzir fora do teste (git-bash/MSYS no Windows, lista de 3.000 paths = 204 KB, 3 tentativas): sem mensagem de erro nem com o codigo antigo - o MSYS nao reproduz; sem WSL para testar em Linux. Logo: nao confirmei o defeito aqui, so o raciocinio (que e correto no Linux), e o teste e fraco/ornamental. Para ficar discriminante: criar >= 1.000 logs antigos no `Ambiente` (nomes longos) - ainda so valida em Linux/VPS. Registrado como limitacao.
3. **Residual (fora do diff, informativo).** `reiniciar_whatsapp.sh:83` (`printf '%s\n' "$texto" | grep -Eq`) e `:93` (`| grep -E ... | tail -n 1`, esse sem `-q`, ok) mantem o mesmo padrao `printf | grep -q`; `texto` e log novo + journal (pequeno), risco baixo, mas o mesmo `Broken pipe` pode aparecer se o journal passar de 64 KB. Trocar por `grep -Eq "$PADRAO_OK" <<<"$texto"` por consistencia.

### Veredito rodada 5: PASS (com ressalvas)
Mudanca funcional correta e discriminada (M1-M4, M9, M10 mortos; REI-07 pega o falso positivo de 08/11). Ressalvas nao bloqueantes: M5 (sem teste para `est != active` + `Grupo aberto`) e REI-08 sem poder de discriminacao do mutante printf|grep.

### Rodada 5 - follow-up do 5d25ea1 (autor, depois do Verifier)
- M5 (remover `est=active`) sobreviveu no 5d25ea1: REI-04 passou a trazer `Grupo aberto` no log com `estado_depois=failed`; o mutante M5 agora morre (`test_unidade_que_nao_sobe_avisa`).
- Resíduo `printf | grep` das linhas 83 e 93 trocado por here-string (mesmo risco de Broken pipe com journal > 64 KB).
- REI-08 segue limitado: só discriminaria com ~1000+ logs, no Linux; registrado, não forçado.

### Rodada 6 - REI-08 discriminante
- Causa do Broken pipe: o systemd ignora SIGPIPE (`IgnoreSIGPIPE=yes`); com SIGPIPE ignorado, `printf lista | grep -qxF` escreve `write error: Broken pipe` quando a lista passa de 64 KB e o grep sai no 1º acerto (reproduzido pelo dono na inst1: antigo 3/3, here-string 0/3).
- REI-08 agora roda o script com `trap '' PIPE; exec bash ...` e 500 logs antigos de nome longo (> 64 KB de `logs_antes`).
- Mutante M6 (voltar `printf | grep -qxF`): **morto** (`test_sem_broken_pipe_no_stderr`). Limitação anterior removida. Suíte: 262 passed.
