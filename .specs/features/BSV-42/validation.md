# BSV-42 · validation.md

**Veredito: PASS** (todos os critérios cobertos com evidência; 16/16 ACs e o critério de aceite automatizável da spec). Há 3 achados médios e 14 mutantes sobreviventes que recomendo virar tarefas antes do merge (ver "Achados"). Nenhum deles viola a letra de um AC.

**Verificador:** Verifier independente (sub-agente, autor ≠ verificador; Claude Sonnet 5.5), read-only no worktree; mutações só em cópias em `$TEMP` (já removidas).
**Faixa do diff:** `b1412fc..HEAD` (4 commits de código + specs: 23 arquivos, +1147/-38).
**Plataforma do verificador:** Windows 10, Git Bash. `tmux`, `pgrep` e `systemctl` NÃO existem aqui: tudo o que depende deles real está em "Risco não coberto".

## Gates

| Gate | Resultado |
|---|---|
| `pytest` em `tools/` | 33 passed, 0 skipped, 0 failed (14,7 s; rodado por último, sem carga) |
| `ruff check` nos arquivos novos (`tests/*`, `core/processos.py`) e tocados limpos (`core/browser.py`, `core/estado.py`) | All checks passed |
| `ruff check` em `main.py`, `wa/storage.py`, `run_captura.py` vs `b1412fc` | Nenhuma violação nova. `main.py` 19 → 16 (saíram 1 BLE001 e 2 PLW1510 com a remoção do `subprocess`); `storage.py` 8 → 8 e `run_captura.py` 1 → 1 (conjuntos idênticos, sem número de linha) |
| `shellcheck vps/*.sh` | exit 0, sem avisos |
| Contagem de testes | 0 → 33 (suíte nova; nenhum teste apagado ou enfraquecido) |

## Verificação spec-anchored

| AC | Resultado definido na spec | Evidência (teste → código) | Resultado |
|---|---|---|---|
| NAV-01 | `channel='chrome'`, args `[AutomationControlled, --profile-directory=Default]`, demais iguais | `tools/tests/test_navegador.py:21` `montar_kwargs("chrome") == _esperado("chrome",[FLAG,"--profile-directory=Default"])`; ausente: `:24-29`; → `capture-store-pages/core/browser.py:30-41` | PASS |
| NAV-02 | sem `channel`, args só `AutomationControlled` | `test_navegador.py:33` e `:36-39` (config `""`), `:48-61` (passa por `launch_persistent`) → `browser.py:16-22,36-45` | PASS |
| NAV-03 | exemplo documenta `navegador.canal` | `test_navegador.py:64-66` → `conf/config.example.json:3` | PASS |
| POR-01 | erro cita `s3.raiz` (Linux) | `tests/test_portabilidade.py:22-26` `pytest.raises(..., match=r"s3\.raiz")` → `core/estado.py:109-113` | PASS |
| POR-02 | erro cita `publicacao_s3.destino` (Linux) | `test_portabilidade.py:33-35` → `wa/storage.py:49-62` | PASS no nível da função; ver A1 (o robô nem sempre "para") |
| POR-03 | Windows devolve os padrões de hoje | `test_portabilidade.py:42-44` (`E:\Work\besave\server\s3` e `...\ofertas\img`) → `estado.py:109-110`, `storage.py:55-56`. Diff vs `b1412fc` confere: mesmos literais | PASS |
| POR-04 | fora do Windows: sem `tasklist`/`taskkill` | `test_portabilidade.py:47-53` (`subprocess.run` proibido) e `:56-69` (comando inteiro no Windows) → `core/processos.py:10-31`, `main.py:69,81,83` | PASS |
| POR-05 | sem `tasklist`/`taskkill`/`.exe` no código de produção | `test_portabilidade.py:72-86`; varredura própria em `main.py core stores run_captura.py wa` sem ocorrência (ver precisão P3) | PASS |
| SH-01 | 2 processos → ≠0, sem lançar, sem `checa_contador` | `tests/test_iniciar_captura.py:91-97` (`returncode != 0`, sem `new-session`, `py.log == ""`) e `:100-105` (1 processo) → `vps/iniciar_captura.sh:49-55` | PASS |
| SH-02 | processo no `user_data` → ≠0, sem lançar | `test_iniciar_captura.py:108-114` → `iniciar_captura.sh:57-63` | PASS |
| SH-03 | contador ≠0 → ≠0, sem lançar | `test_iniciar_captura.py:117-123` → `iniciar_captura.sh:68` | PASS |
| SH-04 | tmux + `DISPLAY=:1` + confirma vivo | `test_iniciar_captura.py:126-134` (`-L besave-whatsapp new-session -d -s`, `-c`, `DISPLAY=:1`, `run_captura.py`, `-u`) e `:137-142` (morreu → "captura nao subiu") → `iniciar_captura.sh:83-93`, `rodar_em_tmux.sh:46` | PASS |
| SH-05 | encerra filtrando por `run_captura.py` e `user_data`; informa o que restou | `test_iniciar_captura.py:145-153` (PIDs 111/333/334 em `kill.log`, `kill-session`, "Restantes: python=0  navegador=0"), `:156-160`, `:163-168` → `vps/encerrar_captura.sh:27-28,49-79` | PASS, mas o "filtrando" só é provado pelo mock (ver A2) |
| SH-06 | unidades via `rodar_em_tmux.sh`, `Restart=on-failure`, sem senha | `tests/test_unidades.py:23-31,34-38,41-44,47-52` → `vps/systemd/besave-captura-lojas.service:13-15`, `...-whatsapp.service:14-16` | PASS (WhatsApp usa `iniciar_captura.sh --aguardar`, que chama o `rodar_em_tmux.sh`; coerente com a spec) |
| DOC-01 | README cobre os 6 temas | `vps/README.md:14,31,44,52,64,76` (instalar, subir, log, login, parar, voltar ao PC). Sem teste (a matriz da spec diz "none") | PASS |
| DOC-02 | `requirements-dev.txt` só com `pytest` e `ruff` | `tools/requirements-dev.txt:1-2` | PASS |
| Aceite `docs/specs/BSV-42.md` — pytest/shellcheck/ruff | cobertos acima | ver Gates | PASS |
| Aceite — execução real (Windows 1 h, VPS, reboot) | do dono | fora do verificador | PENDENTE (bloqueia o merge) |

### Windows idêntico ao original (comparado com `b1412fc`)
- `launch_persistent`: mesmos argumentos (`PERFIL_DIR`, `channel='chrome'`, `headless`, `no_viewport=True`, `args` com `--profile-directory=Default`, `ignore_default_args`) com a chave ausente (`browser.py:16-22,30-45`). Única diferença: lê `conf/config.json` a cada abertura via `_ler_config` (que devolve `{}` e imprime aviso se o arquivo faltar; ver P1).
- `ler_raiz_s3` / `destino_s3`: Windows devolve os mesmos literais; valor presente continua vencendo (`estado.py:105-110`, `storage.py:51-56`).
- `chrome_aberto` / `fechar_chrome_forcado`: mesmos comandos (`tasklist /FI "IMAGENAME eq chrome.exe" /NH`, `taskkill /IM chrome.exe /F`); `main.py` agora chama `core.processos`. Diferenças menores: `except Exception` → `except OSError` (`processos.py`), `check=False` explícito. Nenhum `programas_ajuste/*` importava `_chrome_aberto` (grep).
- `run_captura.py`: só docstring.

## Sensor de discriminação

46 mutantes de comportamento, em cópia isolada em `$TEMP` (normalizada para LF; baseline 33 passed). **32 mortos, 14 sobreviveram.** `git status --porcelain` do worktree principal: vazio antes e depois; scratch removido.

Mortos (32): browser: M2 (profile-dir no Chromium), M3 (if invertido), M9 (`""` vira chrome); plataforma invertida em `estado` (M4), `storage` (M5) e `processos` (M6); mensagens sem a chave (M7, M8); `chrome_aberto` sempre falso (M10); padrões do Windows alterados (M11, M12); iniciar: S1 (≥2 em vez de ≥1), S2 (sem checagem de perfil), S3 (ignora rc do contador), S9 (sem checagem pós-lançamento), X3, X8 (sem `-u`), X9 (sem `-c`); rodar_em_tmux: S4 (sem DISPLAY), S5 (sem `-L`), S15 (esperar ignora rc); encerrar: S6, S7, S11, X4; unidades: U1..U7 (incl. U4 `--monitorar`).
Observação: S6, X3 e X4 morreram **pelo motivo errado**: o `pgrep` falso casa por glob na string do padrão (`*run_captura*`, `*user-data-dir*`), então mudar o padrão só faz o mock não casar; não provam que o regex filtra certo (ver A2).

Sobreviventes (14):

| Mutante | O que muda | Classe |
|---|---|---|
| M1 `channel='chrome'` fixo | um canal ≠ `chrome`/`""` (ex. `msedge`) vira `chrome` | Equivalente pela spec (só `chrome` e `""` definidos); ver P2 |
| S13 encerrar usa `-KILL` direto | perde o SIGTERM antes do SIGKILL | REAL (A3) |
| S8 encerrar não manda TERM ao navegador | só o KILL final | quase equivalente (o PID ainda aparece em `kill.log`) |
| S12 sem `exec ... esperar` no `--aguardar` | a unidade do WhatsApp sairia na hora e o systemd a trataria como terminada | REAL (A4) |
| S10 `rc=0` fixo em `interno` | código do robô perdido, `Restart=on-failure` nunca dispararia | REAL (A4) |
| X11 `interno` não grava o rc | idem | REAL (A4) |
| X12 `interno` sem `wait-for -S` | `esperar` não acorda | REAL (A4) |
| X10 `interno` sem `tee -a` | sem log em arquivo | REAL (A4): "logs nas pastas de log atuais" não é testado |
| X1 / X2 padrão frouxo `run_captura` | regex ancorado deixa de ser verificado | REAL (A2) |
| X5 encerrar não faz `systemctl stop` | `Restart=on-failure` religaria o robô | REAL, menor (A5) |
| X6 log sobrescreve (sem `_b`..`_h`) | reaproveita log de run anterior | REAL, menor |
| X7 não confere o python do venv | mensagem clara perdida | REAL, menor |
| S14 `iniciar` não falha se o tmux falha | a checagem pós-lançamento ainda pega | quase equivalente (fake tmux nunca falha) |

## Achados (ranqueados)

**Médios**
- **A1 · POR-02 só levanta no nível da função; o robô nem sempre para.** `wa/storage.py:49-62` levanta `ConfigFaltando`, mas `publicar_s3` é "best-effort" (docstring) e dois dos três caminhos que chegam nela estão dentro de `try/except Exception`: `salvar_imagem` (`storage.py:694,708`, o `except` engole e tenta de novo/cai no fallback) e `renomear_imagem` (`storage.py:729`, o `except` imprime "Falha ao renomear imagem" e devolve `old_path`, **depois** de `old.replace(novo)` já ter movido o arquivo, então o caminho devolvido não existe mais). No Windows nada muda (`destino_s3` nunca levanta lá). No Linux sem a chave, o mais provável é o robô seguir, perder a publicação da imagem e logar a mensagem a cada oferta, e não "parar com mensagem clara" como diz a Saída 2. Sugestão: validar a chave uma vez na partida do `run_captura.py` no Linux (ou deixar `ConfigFaltando` fora do `except`), com teste. O mesmo vale para `ler_raiz_s3`, que roda no `import` de `imagens_oferta.py:32`/`imagens_produto.py:29` (aqui para de fato, na importação, com mensagem clara).
- **A2 · O regex de `pgrep` não é testado.** `PADRAO_RUN='^[^ ]*python[0-9.]* -u run_captura\.py$'` (`iniciar_captura.sh:31`, `encerrar_captura.sh:27`) e `--user-data-dir=<raiz>/user_data` só são exercitados contra um `pgrep` falso que casa por glob; mutantes X1/X2 (padrão `run_captura`) sobrevivem e S6/X3/X4 morrem por artefato. Conferi o ERE com `grep -E`: casa `/.../.venv/bin/python -u run_captura.py` e `python3.12 -u run_captura.py`; não casa a linha do wrapper `bash ... rodar_em_tmux.sh interno ...`, a do `tmux new-session ...`, nem caminho com espaço. **Mas também não casa `... -u run_captura.py --seg-grupo 8`, `--max 40` nem execução sem `-u`** (o README do próprio robô documenta esses usos). O `.ps1` casa `run_captura\.py` em qualquer posição (`iniciar_captura.ps1:37`). Logo a conferência 1 do `.sh` é mais fraca que a do `.ps1` e a spec ("qualquer `run_captura.py` vivo", Assumptions) diz o contrário. Sugestão: `^[^ ]*python[0-9.]* .*run_captura\.py( |$)` (continua sem casar tmux/bash por causa do `^[^ ]*python`) e um teste que roda o regex com `grep -E` sobre linhas reais de `ps`.
- **A3 · "SIGTERM e o `finally` salva o contador" é falso.** `encerrar_captura.sh:6` e o README afirmam isso, mas o robô só trata `KeyboardInterrupt` (`wa/monitor.py:1254-1258`); não há `signal.signal` nem `atexit` em `tools/` (grep). O SIGTERM padrão do Python termina o processo sem rodar o `finally`, e `systemctl --user stop` (TimeoutStopSec=30) também manda SIGTERM. Atenuante: o `config.json` é persistido a cada leitura (`monitor.py:812,1363`), então a perda é de no máximo o último passo, mas é exatamente o cenário "contador atrasado" que o `checa_contador` barra na subida seguinte. Sugestão: `kill -INT` (vira `KeyboardInterrupt`) no `encerrar` e `KillSignal=SIGINT` nas unidades, ou handler de SIGTERM; corrigir o texto. O teste S13 não existe: nada afirma TERM antes de KILL.
- **A4 · O fluxo do `rodar_em_tmux.sh` (`interno`/`esperar`) só é provado com tmux falso.** Não há teste do código de saída do robô propagado (S10, X11), do `wait-for -S` (X12), do `tee -a` (X10) nem do `exec esperar` do `--aguardar` (S12). Tudo isso é o que faz o `Restart=on-failure` funcionar. Sugestão: teste de `interno` com um `tmux` falso que registra o `wait-for -S`, rc via arquivo e linha no log; e um teste de `iniciar_captura.sh --aguardar` verificando a chamada `esperar`.

**Menores**
- A5 · `systemctl --user stop` do `encerrar_captura.sh:35-37` roda de verdade se `systemctl` existir no host de teste e `BESAVE_UNIDADE` não estiver definido: numa máquina Linux com a unidade instalada, `pytest` pararia a unidade real. Os testes devem definir `BESAVE_UNIDADE` para uma unidade inexistente. Também não testa que o `stop` aconteça (X5).
- A6 · A suíte depende do `bash` do `PATH`: no Windows com WSL, `shutil.which("bash")` pode resolver para o `bash.exe` do WSL e quebrar com `C:/...` (`test_iniciar_captura.py:216`). Aqui rodou com Git Bash.
- A7 · Não há job de CI para `tools/` (declarado fora de escopo na spec); sem ele a suíte só roda na mão. Entra no resumo do PR.

### Lacunas de precisão da spec
- P1: "`navegador.canal` ausente = chrome" não diz o que fazer com `conf/config.json` ilegível ou com cwd diferente (o caminho é relativo, `estado.py:16`): cai em `chrome`. Em `programas_ajuste/*_login.py` rodados de outra pasta, na VPS, abririam `chrome` e falhariam alto, o que é aceitável.
- P2: canal ≠ `chrome`/`""` (ex. `msedge`, ou `" "`) não está definido; hoje o valor passa direto (`browser.py:22`; `" "` vira `""` pelo `strip()`, divergindo do "só a string vazia escolhe o Chromium", sem teste).
- P3: POR-05 enumera `core/` mas `core/processos.py` é o único lugar permitido; `diag/` e `programas_ajuste/` ficam fora da varredura e ainda contêm `.exe`/`tasklist` (fora do "caminho de produção" pela spec).
- P4: SH-05 "filtrando por `run_captura.py` e `user_data`" não diz se o filtro é exato (como no código) ou frouxo; ver A2.

## Risco real não coberto por teste (o dono verá na VPS)
Não verifiquei nada disto em execução (sem tmux/systemd/pgrep aqui); são leituras do código e da documentação conhecida do tmux/systemd.
1. **Ordem de subida no boot.** As unidades são `--user` com `loginctl enable-linger` e `WantedBy=default.target`, mas a tela `:1` vem de outro serviço do VNC ("Fase 6" do roteiro, `docs/infra/VPS-INSTANCIA-1.md:83`). Sem `After=` possível entre unidade de usuário e de sistema, o primeiro start pode ocorrer sem `:1`; com `RestartSec=30`, `StartLimitBurst=5`/`StartLimitIntervalSec=900`, 5 falhas em ~150 s deixam a unidade em `failed` até intervenção. Conferir no teste de `sudo reboot`. Também não verifiquei se o `Xvnc` exige `XAUTHORITY` (o Chromium vê `~/.Xauthority` por padrão).
2. **Corrida `interno` x `esperar`.** Se o robô sair antes de o `wait-for` iniciar, o `wait-for -S` sem esperador deveria marcar o canal como acordado, mas não confirmei isso no tmux instalado; se o servidor tmux já tiver encerrado (último pane morreu), `tmux wait-for` falha e o código segue para ler o arquivo de rc (`rodar_em_tmux.sh:63`), que o `interno` já gravou antes do `-S` (`:57-58`). Comportamento aceitável, mas sem teste. Se o rc faltar, devolve 1.
3. **`printf %q` + shell do tmux.** O comando do `new-session` (`rodar_em_tmux.sh:46-47`) usa `%q` do bash e o tmux o executa com o shell padrão do usuário (`default-shell`). Para caminhos comuns (letras, `/`, `.`, `-`, espaço) o resultado é POSIX-válido; caracteres de controle gerariam `$'...'`, que `dash` não entende. O `besave` com bash está ok; não verifiquei o `default-shell` na VPS.
4. **Caminhos com espaço.** O regex `[^ ]*python` não casa um python em caminho com espaço; o repositório está em `/srv/besave/repo`, sem espaço.
5. **Match de perfil.** O padrão usa `$(pwd -P)` da raiz; o robô passa `Path(__file__).resolve()` (`wa/browser.py:17`) ao Playwright. Iguais, exceto se o Playwright reescrever o argumento. Não verifiquei o cmdline real do Chromium em ARM64.
6. **`input()` sob `tee`.** O robô roda como `... 2>&1 | tee -a log` (`rodar_em_tmux.sh:55`): stdout é pipe, stdin continua o pty do tmux. Prompts de `input()` aparecem (o `-u` flusha), mas a saída deixa de ser TTY, o que pode mudar formatação/progresso; não verifiquei o `capture-store-pages` nesse modo. O `main.py --monitorar` usa `-u` na unidade (confere em `lojas.service:14`).
7. **Servidor tmux dentro do cgroup da unidade.** `KillMode` padrão mata o tmux junto com a unidade; na prática bom (sem sessão órfã), mas significa que `systemctl --user restart` descarta o login feito na tela, só o perfil do disco fica (`README.md:61`).
8. **Dois lançadores do WhatsApp:** subir a unidade com uma sessão manual do `iniciar_captura.sh` ativa falha na conferência e reinicia a cada 30 s até esgotar o limite; é o comportamento desejado, mas o log do `journalctl` ficará barulhento.

## Itens do dono (bloqueiam o merge, fora do verificador)
Windows 1 h sem diferença de log; VPS: `systemctl --user start` dos dois, uma oferta de cada grupo ponta a ponta, `sudo reboot`, `encerrar_captura.sh`; virada no roteiro (Fase 7).

## Verificações de código (Code Quality)
Sem recurso além do pedido; `processos.py` é o único arquivo novo de produção e a spec o justifica. Tests mapeiam 1:1 aos ACs. Uma dependência de dev (`pytest`, `ruff`) sem pins (DOC-02 não exige pin). Nenhuma mudança em SQL/CSV/schema.

## Correções após o Verifier (autor)

Achados A1, A2, A3, A5, A6 corrigidos no commit seguinte, com teste: `validar_destino_s3()` na partida do
`run_captura.py` (A1), regex da conferência aceita argumentos e falta de `-u` (A2), `SIGINT` no
`encerrar_captura.sh` e `KillSignal=SIGINT` nas unidades (A3), `BESAVE_UNIDADE` fictícia nos testes (A5),
`bash.exe` do WSL ignorado (A6). A4 (tmux real) e A7 (CI de `tools/`) ficam para a execução real do dono e
para um ticket com `.github/`.
