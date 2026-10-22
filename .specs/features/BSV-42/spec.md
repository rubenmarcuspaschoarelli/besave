# BSV-42 Robôs no Linux ARM da VPS Specification

Fonte: `docs/specs/BSV-42.md`. Pastas: `tools/capture-store-pages/`, `tools/capture-chat-groups/`, `tools/vps/` (novo), `tools/tests/` (novo).

## Problem Statement

Os dois robôs rodam só no PC Windows. A instância 1 da OCI é Ubuntu 24.04 ARM64: sem Google Chrome para
Playwright, com padrões de caminho `E:\…`, `tasklist`/`taskkill` e lançadores `.ps1`.

## Goals

- [ ] Os dois robôs sobem na VPS com um comando e voltam sozinhos após reinício da máquina.
- [ ] No PC Windows nada muda: mesmo navegador, mesmos flags, mesmos prompts, mesmos arquivos de saída.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Instalar a VPS | roteiro do dono |
| Worker e envio na VPS | BSV-43 |
| Shopee por API | BSV-44 |
| Beleza na Web, WhatsApp por API (OpenWA) | spec |
| Ajustes de `programas_ajuste/` além de `ml_login.py`/`shopee_login.py` | spec; esses dois já usam `launch_persistent`, que passa a respeitar a chave |
| Job de CI para `tools/` | `.github/` fica fora da pasta da spec; vai no resumo do PR |
| Execução real (Windows 1 h, VPS, reboot) | bloqueia o merge, é do dono |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Ausência de `navegador.canal` | `"chrome"` (comportamento atual) | Regra 1: Windows inalterado | n |
| `navegador.canal` vazio ou `null` | `null`/tipo inválido = `"chrome"`; só a string vazia escolhe o Chromium do Playwright | Evita trocar de navegador por config malformada | n |
| Padrão de caminho do S3 sem chave | Windows mantém `E:\Work\besave\server\s3` e `…\ofertas\img`; Linux levanta erro citando a chave (`s3.raiz`, `publicacao_s3.destino`) | Saída 2 | n |
| Onde ficam as funções de processo do Windows | `core/processos.py` (sem dependência de Playwright), importado por `main.py` | Testável sem navegador | n |
| `iniciar_captura.sh`: processo vivo | Qualquer `run_captura.py` vivo (≥ 1) recusa, como o `.ps1`; a conferência usa `pgrep`, sobrescrevível por `BESAVE_PGREP` | Mesmas conferências do `.ps1`; testes simulam processos | n |
| Perfil livre | Processo cujo cmdline tem `--user-data-dir=<raiz>/user_data` recusa | Equivale ao item 2 do `.ps1` | n |
| Python do robô | `BESAVE_PY`, padrão `<raiz>/.venv/bin/python` | Mesma pasta `.venv` do Windows | n |
| Execução sob systemd | `rodar_em_tmux.sh` cria a sessão `tmux` com o robô, espera e sai com o código do robô; a unidade é `Type=simple`, `Restart=on-failure` | systemd enxerga o fim do robô e reinicia; o operador anexa o `tmux` | n |
| Log | `tee -a` do robô para a pasta atual: chat `log/run_captura_DD_MM.log`; lojas `destino/log/main_DD_MM.log` | "logs nas pastas de log atuais" | n |
| `DISPLAY` | `:1` por padrão, `BESAVE_DISPLAY` sobrescreve | Spec | n |
| Sem `shellcheck`/`ruff` na máquina do autor | Instalados em venv temporário para o gate; `shellcheck` roda onde existir | O gate é do runner | n |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Navegador configurável ⭐ MVP

**User Story**: Como dono, quero escolher o Chromium do Playwright na VPS sem mudar o Chrome do PC.

**Acceptance Criteria**:

1. NAV-01: WHEN `navegador.canal` é `"chrome"` ou ausente THEN `launch_persistent` SHALL abrir com `channel='chrome'`, args `['--disable-blink-features=AutomationControlled', '--profile-directory=Default']` e os demais parâmetros de hoje.
2. NAV-02: WHEN `navegador.canal` é `""` THEN `launch_persistent` SHALL abrir sem `channel`, com args `['--disable-blink-features=AutomationControlled']` e os demais parâmetros iguais.
3. NAV-03: The `conf/config.example.json` SHALL documentar `navegador.canal`.

**Independent Test**: `pytest tools/tests/test_navegador.py`.

### P1: Portabilidade ⭐ MVP

**User Story**: Como dono, quero que o robô falhe com mensagem clara em vez de gravar em caminho de Windows no Linux.

**Acceptance Criteria**:

1. POR-01: IF a plataforma é Linux e `s3.raiz` falta no `config.json` THEN `ler_raiz_s3` SHALL levantar erro cuja mensagem cita `s3.raiz`.
2. POR-02: IF a plataforma é Linux e `publicacao_s3.destino` falta THEN a publicação de imagem do chat SHALL levantar erro cuja mensagem cita `publicacao_s3.destino`.
3. POR-03: WHILE a plataforma é Windows, `ler_raiz_s3` e o destino de imagem SHALL devolver os mesmos padrões de hoje.
4. POR-04: WHILE a plataforma não é Windows, `chrome_aberto` SHALL devolver falso sem chamar `tasklist`, e o fechamento forçado SHALL não chamar `taskkill`.
5. POR-05: The código de produção (`main.py`, `core/`, `stores/`, `run_captura.py`, `wa/`) SHALL não conter `tasklist`, `taskkill` nem `.exe` fora de `core/processos.py`.

**Independent Test**: `pytest tools/tests/test_portabilidade.py`.

### P1: Subida no Linux ⭐ MVP

**User Story**: Como dono, quero subir e parar a captura do WhatsApp na VPS com as conferências que já evitaram incidentes.

**Acceptance Criteria**:

1. SH-01: IF há dois processos `run_captura.py` vivos THEN `iniciar_captura.sh` SHALL sair com código ≠ 0, sem lançar o robô e sem rodar `checa_contador.py`.
2. SH-02: IF há processo segurando `user_data` THEN `iniciar_captura.sh` SHALL sair com código ≠ 0 sem lançar o robô.
3. SH-03: IF `diag/checa_contador.py` sai com código ≠ 0 THEN `iniciar_captura.sh` SHALL sair com código ≠ 0 sem lançar o robô.
4. SH-04: WHEN as três conferências passam THEN `iniciar_captura.sh` SHALL lançar `run_captura.py -u` numa sessão `tmux` com `DISPLAY=:1` e confirmar que o processo está vivo.
5. SH-05: WHEN há processo do robô ou do perfil THEN `encerrar_captura.sh` SHALL encerrá-los filtrando por `run_captura.py` e por `user_data` (nunca todo `python`) e informar o que restou.
6. SH-06: The unidades `systemd --user` dos dois robôs SHALL rodar o robô por `rodar_em_tmux.sh`, com `Restart=on-failure` e sem senha na unidade.

**Independent Test**: `pytest tools/tests/test_iniciar_captura.py` com `pgrep`, `tmux` e Python simulados.

### P2: Documentação

**Acceptance Criteria**:

1. DOC-01: The `tools/vps/README.md` SHALL cobrir instalar, subir, parar, ver log, atender pedido de login e voltar para o PC.
2. DOC-02: The `tools/requirements-dev.txt` SHALL listar só `pytest` e `ruff`.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| NAV-01 | Navegador | Execute | Pending |
| NAV-02 | Navegador | Execute | Pending |
| NAV-03 | Navegador | Execute | Pending |
| POR-01 | Portabilidade | Execute | Pending |
| POR-02 | Portabilidade | Execute | Pending |
| POR-03 | Portabilidade | Execute | Pending |
| POR-04 | Portabilidade | Execute | Pending |
| POR-05 | Portabilidade | Execute | Pending |
| SH-01 | Subida no Linux | Execute | Pending |
| SH-02 | Subida no Linux | Execute | Pending |
| SH-03 | Subida no Linux | Execute | Pending |
| SH-04 | Subida no Linux | Execute | Pending |
| SH-05 | Subida no Linux | Execute | Pending |
| SH-06 | Subida no Linux | Execute | Pending |
| DOC-01 | Documentação | Execute | Pending |
| DOC-02 | Documentação | Execute | Pending |

## Success Criteria

- [ ] `pytest`, `ruff check` e `shellcheck` limpos.
- [ ] Comportamento Windows provado por teste (NAV-01, POR-03).
