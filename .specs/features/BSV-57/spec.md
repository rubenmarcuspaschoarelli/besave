# BSV-57 Vigia externo dos robôs Specification

Fonte: `docs/specs/BSV-57.md` (com a revisão 10/11). Lições 11, 14, 16, 29. AD-107, AD-108.
Depende de BSV-54, 55, 56 (em `develop`).

## Problem Statement

Em 02–05/11 o site ficou 3 dias sem oferta e, em 07–09/11, o WhatsApp ficou vivo e quebrado. O aviso do
próprio robô cai junto com o processo e o robô das lojas não avisa nada. Falta um vigia fora dos robôs que
detecte parada, tente reiniciar e avise no Telegram com a causa.

## Goals

- [ ] Cada robô grava `conf/batimento.json` só quando há progresso.
- [ ] `vigia_robos.py` (timer de 5 min) reinicia pela unidade, no máximo 2 vezes por hora, e avisa.
- [ ] Robô das lojas no próprio scope (`besave-lojas-robo`), como o WhatsApp.
- [ ] Rotação diária dos logs.

## Out of Scope

Máquina inteira fora do ar; alerta de 8 h do worker (AD-108); resolver o QR; execução real (dono).

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Quando o robô está parado | `agora > prazo` (tolerância 0); `prazo == agora` não é parado | Decisão do dono (10/11): a linha 132 da spec falava de `em`, não do prazo | y |
| Partida recente sem batimento do PID novo | Indeterminado (nada) por 10 min a partir do `ActiveEnterTimestamp` do scope | "PID trocado" da spec | n |
| Nova mensagem na mesma ocorrência | Só quando muda a ação (reiniciado 1/2, 2/2, operador); senão lembrete a cada 2 h | "1 mensagem por ocorrência" sem esconder a escalada | n |
| Pedido de QR | Log mais recente com `Aguardando o WhatsApp Web carregar` sem `Sessao autenticada` depois | A frase "Se aparecer o QR Code" sai em toda partida | n |
| "Voltou" | Batimento válido, pid no scope, prazo em dia e `em` posterior ao início da ocorrência | "batimento novo depois de ocorrência aberta" | n |
| Idade do log do laço de partidas | Data do nome `run_captura_DD_MM_HHMMSS*.log` (não o mtime) | mtime de log ativo engana | n |
| `activating` da unidade | Nada (a partida ainda está em curso) | Evita reinício duplo | n |
| Lojas com banco fora | Renova (a varredura segue) | Spec: a cada varredura | n |

Open questions: none

---

## User Stories

### P1: Batimento dos robôs ⭐ MVP

**Acceptance Criteria**:

1. BAT-01: WHEN uma volta do rodízio do WhatsApp abre ao menos um grupo, THE SYSTEM SHALL gravar `batimento.json` com `prazo` = agora + 10 min.
2. BAT-02: WHEN todos os grupos de uma volta falham, THE SYSTEM SHALL NOT renovar o batimento.
3. BAT-03: WHILE o banco está fora, THE SYSTEM SHALL renovar o batimento com `fase` de banco fora.
4. BAT-04: THE SYSTEM SHALL gravar em `grupos_falhando` o grupo que falhou desde o instante da 1ª falha, e SHALL removê-lo na primeira volta em que abrir.
5. BAT-05: WHEN o robô vai dormir (janela noturna ou intervalo), THE SYSTEM SHALL gravar `prazo` = hora de acordar + 10 min.
6. BAT-06: THE SYSTEM SHALL gravar o batimento por arquivo temporário e `rename`, e IF a escrita falha, THEN SHALL só logar.
7. BAT-07: WHEN o robô das lojas conclui uma linha ou uma varredura (inclusive fila vazia ou loja em pausa), THE SYSTEM SHALL renovar o batimento.
8. BAT-08: IF a linha termina em exceção de navegador fechado, THEN THE SYSTEM SHALL NOT renovar o batimento.

### P1: Scope das lojas

1. ESC-01: THE SYSTEM SHALL subir o robô das lojas por `systemd-run --user --scope --collect --unit=besave-lojas-robo -p KillSignal=SIGINT -p TimeoutStopSec=30 -- <python> -u main.py --monitorar --sem-perguntas` dentro do tmux.
2. ESC-02: WHEN o scope está ativo na partida, THE SYSTEM SHALL recusar subir; com o scope inativo SHALL rodar `reset-failed` e `revert` antes do tmux.
3. ESC-03: THE SYSTEM SHALL parar o scope no `ExecStop` da unidade das lojas por `parar_scope.sh`: `SIGINT` só ao python do scope, esperar até 20 s ele sair e então `systemctl --user stop` do scope (SIGINT a todos e, em 30 s, SIGKILL).
4. ESC-04: WHEN o operador para a unidade das lojas e o python sai por `SIGINT`, THE SYSTEM SHALL deixar a unidade `inactive`, não `failed`, inclusive quando o `close()` do contexto passa dos 20 s e o 2º SIGINT do `stop` do scope faz o python sair com 130 (`SuccessExitStatus=130` na unidade; queda real sai com outro código e segue em `on-failure`); o robô loga `[monitor] contexto fechado em N s` (inst1, 11/11: o `stop` do scope mandava SIGINT ao node do Playwright, o `BrowserContext.close` estourava e o python saía com 1).

### P1: Vigia ⭐ MVP

1. VIG-01: WHEN `agora > prazo` do batimento do pid vivo no scope, THE SYSTEM SHALL reiniciar a unidade e avisar uma vez; `agora == prazo` SHALL NOT agir.
2. VIG-02: WHILE o relógio está antes do `prazo` (inclusive prazo de sono), THE SYSTEM SHALL NOT agir, mesmo com `em` antigo.
3. VIG-03: IF o pid do batimento não está no scope e o scope subiu há 10 min ou menos, THEN THE SYSTEM SHALL NOT agir; passados 10 min SHALL tratar como parado.
4. VIG-04: IF o log mais recente pede QR ou tem `ABORTADO:`, THEN THE SYSTEM SHALL avisar o operador e NOT reiniciar.
5. VIG-05: IF o grupo está em `grupos_falhando` há 2 h ou mais, THEN THE SYSTEM SHALL avisar o operador com o nome, sem reiniciar, e avisar "voltou" ao sair do mapa.
6. VIG-06: IF 3 ou mais logs de partida dos últimos 30 min não têm `Grupo aberto`, THEN THE SYSTEM SHALL avisar o operador sem reiniciar.
7. VIG-07: THE SYSTEM SHALL fazer no máximo 2 reinícios por robô em 60 min; a 3ª parada SHALL virar aviso de operador.
8. VIG-08: WHEN um batimento novo chega com ocorrência aberta, THE SYSTEM SHALL enviar uma mensagem "voltou" com a duração; sem ocorrência SHALL NOT enviar nada.
9. VIG-09: IF a unidade está `inactive`, ou o reinício diário do WhatsApp está em andamento, THEN THE SYSTEM SHALL NOT agir.
11. VIG-11: THE SYSTEM SHALL reiniciar só unidade `active` ou `activating`; IF a unidade está `failed`, THEN THE SYSTEM SHALL NOT reiniciar e SHALL avisar o operador ("unidade failed: o systemd já desistiu"), 1 aviso por ocorrência e lembrete a cada 2 h (inst1, 11/11: o vigia religou uma unidade parada pelo operador, que acabou em `failed`).
10. VIG-10: THE SYSTEM SHALL agir só por `systemctl --user restart <unidade>` e ler os pids do `cgroup.procs` do scope, nunca por `kill` ou nome de processo.

### P1: Mensagens e estado

1. MSG-01: WHEN não há token e chat, THE SYSTEM SHALL só logar; com eles SHALL enviar texto com robô, motivo, ação, última linha útil do log, memória do scope e RSS do maior `chrome`, todos medidos ANTES do restart (depois dele o scope, os pids e o log são outros: a mensagem saía com `n/d`).
2. MSG-02: THE SYSTEM SHALL NOT incluir token nem URL `https://` em log, mensagem ou erro.
3. MSG-03: THE SYSTEM SHALL manter 1 mensagem por ocorrência e lembrete a cada 2 h, com estado em `vigia_robos.json`.
4. MSG-04: THE SYSTEM SHALL mostrar ao operador horários em Brasília (offset fixo -03:00, ex.: `11/11 08:42`; CLAUDE.md regra 5) e manter o estado em `vigia_robos.json` em UTC (`Z`).

### P2: Rotação de logs

1. ROT-01: WHEN o vigia roda pela primeira vez no dia, THE SYSTEM SHALL apagar `run_captura_*.log` com mais de 14 dias, nunca o mais recente.
2. ROT-02: WHEN `main_monitorar.log` passa de 50 MB, THE SYSTEM SHALL copiá-lo para `main_monitorar_AAAAMMDD.log` e truncá-lo no mesmo inode; cópias com mais de 14 dias SHALL ser apagadas.
3. ROT-03: THE SYSTEM SHALL tocar só esses nomes, nessas duas pastas.

### P2: Unidades e README

1. UNI-01: THE SYSTEM SHALL trazer `besave-vigia-robos.service` e `.timer` (5 min) válidos em `systemd-analyze --user verify`, e README com como silenciar e desligar.

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| BAT-01 | Batimento dos robôs | Execute | Pending |
| BAT-02 | Batimento dos robôs | Execute | Pending |
| BAT-03 | Batimento dos robôs | Execute | Pending |
| BAT-04 | Batimento dos robôs | Execute | Pending |
| BAT-05 | Batimento dos robôs | Execute | Pending |
| BAT-06 | Batimento dos robôs | Execute | Pending |
| BAT-07 | Batimento dos robôs | Execute | Pending |
| BAT-08 | Batimento dos robôs | Execute | Pending |
| ESC-01 | Scope das lojas | Execute | Pending |
| ESC-02 | Scope das lojas | Execute | Pending |
| ESC-03 | Scope das lojas | Execute | Pending |
| ESC-04 | Scope das lojas | Execute | Pending |
| VIG-01 | Vigia | Execute | Pending |
| VIG-02 | Vigia | Execute | Pending |
| VIG-03 | Vigia | Execute | Pending |
| VIG-04 | Vigia | Execute | Pending |
| VIG-05 | Vigia | Execute | Pending |
| VIG-06 | Vigia | Execute | Pending |
| VIG-07 | Vigia | Execute | Pending |
| VIG-08 | Vigia | Execute | Pending |
| VIG-09 | Vigia | Execute | Pending |
| VIG-10 | Vigia | Execute | Pending |
| VIG-11 | Vigia | Execute | Pending |
| MSG-01 | Mensagens e estado | Execute | Pending |
| MSG-02 | Mensagens e estado | Execute | Pending |
| MSG-03 | Mensagens e estado | Execute | Pending |
| MSG-04 | Mensagens e estado | Execute | Pending |
| ROT-01 | Rotação de logs | Execute | Pending |
| ROT-02 | Rotação de logs | Execute | Pending |
| ROT-03 | Rotação de logs | Execute | Pending |
| UNI-01 | Unidades e README | Execute | Pending |

## Success Criteria

- [ ] `python -m unittest discover -s tests` (WhatsApp), `pytest` em `tools/`, `ruff check vps/ tests/`, `shellcheck vps/*.sh`, `systemd-analyze --user verify tools/vps/systemd/*` verdes.
- [ ] Execução real na inst1, passos 1–5 e 4b da spec (dono; bloqueia o merge).
