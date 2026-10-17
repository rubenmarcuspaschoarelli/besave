# BSV-42 · validation.md (2ª rodada)

## Validation — PASS

**Veredito: PASS com ressalvas.** Os 16 ACs e o critério de aceite automatizável da spec têm evidência `file:line`; os três
gates estão verdes. O sensor de discriminação matou 79 de 113 mutantes; sobreviveram 34, dos quais 6 são equivalentes (ou
quase) e 28 são lacunas reais de teste, **nenhuma contradiz a letra de um AC**. As 3 lacunas médias (A8–A10) protegem
correções feitas depois da 1ª rodada (A1 e A3) e devem virar teste antes do merge. Execução real (Windows 1 h, VPS, reboot) continua do dono e bloqueia o merge.

**Verificado por:** sub-agente independente (Verifier, autor ≠ verificador; Claude Sonnet 5.5), 2ª rodada, sobre o HEAD `c4d050b`.
Mutantes rodados em cópias temporárias (`git archive HEAD` extraído em scratch, removidas ao fim); o worktree não foi tocado.
`git status --porcelain` igual antes e depois (vazio). Nenhum teste novo foi escrito pelo Verifier.
**Plataforma:** Windows 10, Git Bash. Não existem `tmux`, `pgrep` nem `systemctl` aqui: tudo o que depende deles real fica em "Risco não coberto".

## Gates

| Gate | Resultado |
|---|---|
| `cd tools && pytest` (venv de dev) | 53 passed, 0 skipped, 0 falhas (27,6 s; antes dos mutantes, sem carga). Eram 33 na 1ª rodada. Nenhum teste apagado ou enfraquecido |
| `ruff check tests` | All checks passed |
| `shellcheck vps/*.sh` | exit 0, sem avisos |

## Verificação spec-anchored (código final)

| AC | Evidência (teste → código) | Resultado |
|---|---|---|
| NAV-01 | `tools/tests/test_navegador.py:20-21` (`montar_kwargs("chrome")` com `--profile-directory=Default`), `:24-29` (chave ausente) → `capture-store-pages/core/browser.py:16-24,30-42` | PASS |
| NAV-02 | `test_navegador.py:32-33`, `:36-39`, `:48-61` (passa por `launch_persistent`) → `browser.py:38-47` | PASS |
| NAV-03 | `test_navegador.py:64-66` → `capture-store-pages/conf/config.example.json:3` | PASS |
| POR-01 | `tools/tests/test_portabilidade.py:22-26` (`match=r"s3\.raiz"`, inclui valor em branco) → `capture-store-pages/core/estado.py:101-113` | PASS |
| POR-02 | `test_portabilidade.py:33-35` → `capture-chat-groups/wa/storage.py:49-62`; a partida no Linux também falha: `test_portabilidade.py:89-95` → `storage.py:583-589` e `run_captura.py:85-90` (ver A8: a chamada em `run_captura.py` não tem teste) | PASS no nível da função e do `validar_destino_s3`; fiação em `run_captura` sem teste |
| POR-03 | `test_portabilidade.py:42-44`, `:98-103` (Windows sem chaves nem recusa a partida), `:106-109` (chave vazia) → `estado.py:109-110`, `storage.py:55-56` | PASS (mutantes que fazem o Windows recusar morreram) |
| POR-04 | `test_portabilidade.py:47-53` (`subprocess.run` proibido fora do Windows), `:56-69` (comando inteiro no Windows) → `capture-store-pages/core/processos.py:6-31`, `main.py:69,81,83` | PASS |
| POR-05 | `test_portabilidade.py:72-86` | PASS |
| SH-01 | `tools/tests/test_iniciar_captura.py:94-108` (2 e 1 processo; sem `new-session`, `py.log` vazio) → `tools/vps/iniciar_captura.sh:49-55` | PASS |
| SH-02 | `test_iniciar_captura.py:111-117` → `iniciar_captura.sh:57-63` | PASS (padrão do perfil só provado por glob do `pgrep` falso: A11) |
| SH-03 | `test_iniciar_captura.py:120-126` → `iniciar_captura.sh:68` | PASS |
| SH-04 | `test_iniciar_captura.py:129-145` (`-L besave-whatsapp new-session -d -s`, `-c`, `DISPLAY=:1`, `-u`; processo que morre) → `iniciar_captura.sh:83-93`, `rodar_em_tmux.sh:46-47` | PASS |
| SH-05 | `test_iniciar_captura.py:148-171,190-193` (PIDs, `kill-session`, "Restantes", SIGINT antes do KILL) → `tools/vps/encerrar_captura.sh:27-28,39-79` | PASS; o filtro de `encerrar` só é provado pelo mock (A9, A11) |
| SH-06 | `tools/tests/test_unidades.py:27-34,44-47,50-56,59-63,66-72,75-84` e `test_iniciar_captura.py:228-289` → `tools/vps/systemd/besave-captura-lojas.service:7-23`, `besave-captura-whatsapp.service:7-24`, `besave-vnc.service:5-18`, `rodar_em_tmux.sh:29-71`, `iniciar_captura.sh:103-105` | PASS: unidades por `rodar_em_tmux.sh`/`iniciar_captura.sh --aguardar`, `Restart=on-failure`, `Requires=`/`After=` do VNC, `StartLimitIntervalSec=0`, `ExecStartPre` esperando o socket, sem senha |
| DOC-01 | `tools/vps/README.md:14,18,25,29-32,44,58,66,78,90,99` (instalar, linger, VNC, subir, log, login, parar, voltar ao PC); `test_unidades.py:87-91` confere `enable-linger` e `besave-vnc` | PASS |
| DOC-02 | `tools/requirements-dev.txt:1-2` (`pytest`, `ruff`) | PASS |
| Aceite `docs/specs/BSV-42.md` (pytest/shellcheck/ruff) | ver Gates | PASS |
| Aceite, execução real (Windows 1 h, VPS, reboot) | do dono | PENDENTE, bloqueia o merge |

Os achados da 1ª rodada foram conferidos: A1 (`validar_destino_s3`, `storage.py:583-589`), A2 (regex aceita argumentos e falta de `-u`,
`iniciar_captura.sh:31`, teste `:196-209`), A3 (`kill -INT`, `encerrar_captura.sh:51,62`; `KillSignal=SIGINT` nas unidades), A4 (fluxo `interno`/`esperar`/`executar`/`--aguardar`
agora testado, `test_iniciar_captura.py:228-289`), A5 (`BESAVE_UNIDADE` fictícia, `:68`) e A6 (`bash.exe` do WSL ignorado, `:12-14`) estão corrigidos no código.

## Sensor de discriminação

113 mutantes de comportamento (46 da 1ª rodada, reconstruídos a partir da tabela, mais 67 novos), cada um aplicado numa cópia limpa de `HEAD`
e executado contra a suíte inteira (`pytest -x`). **79 mortos, 34 sobreviventes.**
Observação de método: S11, X3 e X4 foram reconstruídos por mim (a tabela original só trazia o nome); aqui sobrevivem, enquanto na 1ª rodada
"morriam pelo motivo errado". A comparação mutante a mutante com a 1ª rodada vale para os demais.

### Mortos (79)
- Navegador: M2, M3, M9; plataforma e mensagens: M4–M8, M10–M12; `ler_raiz_s3`/`destino_s3` ignorando o valor configurado; Windows passando a recusar sem chave (`N-WinRefuse`, `N-WinRefuse2`); Linux deixando de recusar (`N-LinNoRefuse`, `N-LinNoRefuse2`); `validar_destino_s3` sem efeito ou ignorando `ativo=false`.
- `iniciar_captura.sh`: S1, S2, S3, S9, X1b, X1c, X8, `N-IniCount`, `N-IniAg*` (sempre/nunca aguardar, sessão errada); S12 (`--aguardar` sem `exec esperar`).
- `rodar_em_tmux.sh`: S4, S5, S10 (rc fixo), S15 (`esperar` ignora rc), X9, X10 (`tee` sem `-a`), X11 (não grava rc), X12 (sem `wait-for -S`), `N-Rod{Rm,ExecEsp,WaitFor,Canal,RcDef,Pipe}`.
- `encerrar_captura.sh`: S6, S7, S13 (`-KILL` direto), `N-EncExit`.
- Unidades de robô (lojas e WhatsApp, os dois lados): sem `Requires`, sem `After`, sem `StartLimitIntervalSec`, `RestartSec=2`, sem `ExecStartPre`, `$$(` virando `$(`, socket `X2`; U1–U7.
- VNC: sem `-fg`, sem `-localhost` e `-localhost no`, display `:2`, sem `Restart`, sem `ExecStop`, sem `StartLimitIntervalSec`, `WantedBy` errado.

### Sobreviventes (34) e classificação

**Equivalentes ou quase (6), sem ação**

| Mutante | O que muda | Justificativa |
|---|---|---|
| M1 | `channel` fixo em `chrome` | Equivalente pela spec: só `chrome` e `""` são definidos (P2 da 1ª rodada) |
| X1 | regex do `iniciar` sem `( \|$)` | Continua ancorado em `^[^ ]*python`; só difere para `run_captura_x.py`, que não existe |
| S14 | `iniciar` não aborta se o `tmux` falha | A checagem pós-lançamento (`iniciar_captura.sh:88-93`) devolve o mesmo código; muda só a mensagem |
| N-RodExecExit | `executar` ignora falha do `iniciar` | Sem sessão, o `esperar` não acha o rc e sai 1; muda só a mensagem |
| N-IniOrder | `true;` antes de um comentário | Cosmético |
| N-IniLog | sem `tail` do log ao morrer | Só diagnóstico (o exit continua ≠ 0) |

**REAIS (28), ranqueados**

| # | Mutante(s) | O que ficou sem prova | Teste sugerido |
|---|---|---|---|
| 1 | `N-RunNoCall`, `N-RunRc` | `run_captura.main()` chamar `validar_destino_s3()` e devolver 2 (a correção do A1 está só em `storage.py`; apagar a chamada não quebra nada) | importar `run_captura` com `wa.monitor` stubado em `sys.modules`, `validar_destino_s3` levantando `ConfigFaltando`, e assertar `main() == 2` com a mensagem impressa |
| 2 | `N-KS-L`, `N-KS-W` | `KillSignal=SIGINT` nas unidades (correção do A3; sem ele o `systemctl stop` manda SIGTERM e o `finally` não salva o contador) | em `test_unidades.py`, `servico["KillSignal"] == "SIGINT"` nos dois robôs |
| 3 | `X2b`, `X2c` | o regex de `encerrar_captura.sh` não tem teste algum (o teste do regex só lê `iniciar_captura.sh:31`); sem âncora ele passaria a casar o wrapper `bash`/`tmux` | parametrizar `test_sh01_pega_run_com_argumentos_e_sem_u` pelos dois scripts |
| 4 | `N-EncKillPy`, `N-EncKillCh` | o SIGKILL de reserva (`encerrar_captura.sh:59,64`) nunca é exigido | `kill` falso que ignora `-INT` e só remove o PID com `-KILL`; assertar "Restantes: python=0 navegador=0" e `-KILL <pid>` no `kill.log` |
| 5 | `X3`, `X4` | padrão de perfil (`--user-data-dir=<raiz>/user_data`) só casa por glob `*user-data-dir*` do `pgrep` falso; trocar o caminho passa | `pgrep` falso que aplica `grep -E` sobre uma lista fixa de linhas de `ps` (com perfil de outra pasta, que não deve casar) |
| 6 | `N-Sleep-L`, `N-Sleep-W`, `N-TS-L`, `N-TS-W` | o `ExecStartPre` devolver falha sem tela (`exit 1`) e `TimeoutStopSec` | asserts de `exit 1` no fim do `ExecStartPre` e `TimeoutStopSec` ≥ `BESAVE_GRACA`+margem |
| 7 | `N-EncUnidade`, `X5` | nome padrão da unidade no `encerrar` e o `systemctl --user stop` | teste do nome padrão contra o arquivo `.service`; `systemctl` falso no `PATH` registrando a chamada |
| 8 | `N-RodKill`, `N-RodMkdir`, S11, S8 | `iniciar` matar sessão velha, criar a pasta do log; `encerrar` fazer `kill-session` quando nada roda; INT no navegador antes do KILL | asserts em `tmux.log`/`kill.log` (ordem INT→KILL) e log em pasta inexistente |
| 9 | `X6`, `X7` | sufixo `_b`..`_h` do log e a checagem do python do venv | duas execuções no mesmo dia; `BESAVE_PY` inexistente → "python do venv nao encontrado" |
| 10 | `N-V-pre`, `N-V-pre2`, `N-V-geo`, `N-V-xs` | `ExecStartPre=-vncserver -kill :1` (prefixo `-` e existência), geometria e `-xstartup` do VNC | asserts em `test_vnc_e_a_tela_1_...` |
| 11 | `N-Main-proc` | `main.py` consultar `processos.chrome_aberto()` (fiação do gate no Windows); `main.py` não é importável sem Playwright | teste estático/AST de que `main.py` chama `processos.chrome_aberto` e `fechar_chrome_forcado`, ou aceitar a lacuna (POR-04 está provado em `processos.py`) |

## Achados (ranqueados)

**Médios (corrigir antes do merge)**
- **A8 · A fiação do A1 não tem teste** (#1): `run_captura.py:85-90` pode perder a chamada sem que nada falhe; a partida no Linux sem `publicacao_s3.destino` voltaria a ser engolida pelos `try/except` do salvamento.
- **A9 · O regex de `encerrar_captura.sh` não é testado** (#3) e o fallback SIGKILL (#4) também não: são as duas defesas contra "matar todo python" e contra perfil travado.
- **A10 · `KillSignal=SIGINT` sem teste** (#2): é a metade em unidade da correção do A3.

**Menores**
- A11 · O padrão do perfil (`X3`/`X4`) e o `ExecStartPre`/`TimeoutStopSec` (#5, #6) só são provados indiretamente.
- A12 · #7–#11: lacunas de baixo risco listadas acima.
- A13 (da 1ª rodada, segue) · Não há job de CI para `tools/` (fora de escopo na spec); a suíte só roda à mão. Entra no resumo do PR.

Lacunas de precisão da spec (P1–P4 da 1ª rodada) seguem como estavam; nenhuma bloqueia.

## Risco real não coberto por teste (o dono verá na VPS)
Não verificado em execução (sem tmux/systemd/pgrep aqui); leitura do código.
1. **Ordem de subida no boot.** Agora tratada: `besave-vnc.service` + `Requires=`/`After=` + `ExecStartPre` esperando `/tmp/.X11-unix/X1` + `StartLimitIntervalSec=0`. Falta provar com `sudo reboot` que o `vncserver -fg` se mantém em primeiro plano no TigerVNC instalado e cria o socket `X1`, e se exige `XAUTHORITY`.
2. **Corrida `interno` x `esperar`** (`wait-for -S` sem esperador; servidor tmux já encerrado): o rc é gravado antes do `-S` (`rodar_em_tmux.sh:56-57`) e o `esperar` lê o arquivo mesmo se o `wait-for` falhar; não confirmado com tmux real.
3. **`printf %q` + shell do tmux** (`rodar_em_tmux.sh:46-47`): seguro para caminhos comuns; `default-shell` da VPS não verificado.
4. **Caminhos com espaço** não casam em `^[^ ]*python`; `/srv/besave/repo` não tem espaço.
5. **Cmdline real do Chromium em ARM64** vs `--user-data-dir=<raiz>/user_data` (`$(pwd -P)` x `Path.resolve()`).
6. **`input()` sob `tee`** e `capture-store-pages` sem TTY no stdout.
7. **`systemctl --user restart`** descarta o login feito na tela (o servidor tmux fica no cgroup da unidade); só o perfil em disco permanece.
8. **`KillSignal=SIGINT`** só salva o contador se o `KeyboardInterrupt` chegar ao `finally` do robô com o tmux no meio (o sinal vai para o cgroup, não para o robô só); confirmar na execução real que o `config.json` fecha o contador.
9. **`ExecStartPre` com `$$(`**: a regra do systemd (`$$` → `$`) foi lida da documentação, não executada; `systemd-analyze verify` na VPS confirma.

## Itens do dono (bloqueiam o merge, fora do verificador)
Windows 1 h sem diferença de log; VPS: `systemctl --user start` das três unidades, uma oferta de cada grupo ponta a ponta, `sudo reboot`, `encerrar_captura.sh`; virada no roteiro (Fase 7).

## Verificações de código
Sem recurso além do pedido; `processos.py` continua o único arquivo novo de produção. Uma dependência de dev (`pytest`, `ruff`), sem pins, DOC-02 não exige. Nenhuma mudança em SQL/CSV/schema/contrato. Evidências: nenhum arquivo de log ou print comitado por esta rodada.

## Correções após a 2ª rodada (autor)
Cada sobrevivente real virou teste; os testes novos foram checados contra o mutante correspondente (falham com a falha injetada, passam sem ela). Rodada final do autor: `pytest` 70 passed, `ruff check tests` e `shellcheck vps/*.sh` limpos. Não é nova verificação independente.

| sobrevivente | teste novo |
|---|---|
| N-RunNoCall, N-RunRc (A8) | `test_portabilidade.py::test_por02_run_captura_sai_com_2_sem_destino` e `..._com_destino_segue_...` |
| N-KS-L, N-KS-W (A10) | `test_unidades.py::test_robo_para_com_sigint_e_da_tempo_de_salvar` |
| X2b, X2c (A9) | `test_sh01_pega_run_com_argumentos_e_sem_u` parametrizado pelos dois scripts |
| N-EncKillPy, N-EncKillCh, S8, S11 (A9) | `test_sh05_sigkill_de_reserva_depois_do_sigint` (ordem INT < KILL, "Restantes: 0") |
| X3, X4 | `test_sh05_padroes_reais_so_pegam_o_robo_e_o_perfil_do_projeto` (regex real sobre linhas de `ps` fixas) |
| N-Sleep-L/W, N-TS-L/W | `test_robo_falha_se_a_tela_nao_aparece`, `test_robo_para_com_sigint_e_da_tempo_de_salvar` |
| N-EncUnidade, X5 | `test_sh05_para_a_unidade_antes_de_matar` (nome padrão e personalizado) |
| N-RodKill, N-RodMkdir | `test_sh06_iniciar_mata_sessao_velha_antes_e_cria_pasta_do_log` |
| S11 (kill-session sem nada rodando) | `test_sh05_nada_rodando_ainda_derruba_a_sessao_tmux` |
| X6, X7 | `test_sh04_nao_reaproveita_log_do_mesmo_dia`, `test_sh04_sem_python_do_venv_aborta_com_mensagem` |
| N-V-pre, N-V-pre2, N-V-geo, N-V-xs | `test_vnc_detalhes_da_tela` |
| N-Main-proc | `test_main_de_lojas_usa_o_modulo_processos` (fonte de `main.py`; o `main.py` não é importável sem Playwright) |

Equivalentes (sem teste, justificativa da 2ª rodada acima): M1, X1, S14, N-RodExecExit, N-IniOrder, N-IniLog.

Achado A13/A7 (CI de `tools/`): não corrigido. Exige `.github/`, fora da pasta autorizada pela spec; vai no resumo da PR como ticket próprio.
