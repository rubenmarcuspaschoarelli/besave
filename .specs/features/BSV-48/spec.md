# BSV-48 Robôs na VPS: telas separadas, identificação e janela noturna Specification

Fonte: `docs/specs/BSV-48.md`. Roteiro: `docs/infra/VPS-INSTANCIA-1.md`; AD-104.

## Problem Statement

No primeiro dia dos robôs na VPS, os dois navegadores dividiram a tela `:1` (foco e área de transferência
compartilhados; oferta 37827 sem link de afiliado), o Chromium `Linux aarch64` foi desviado pelo link curto
do Mercado Livre para a Play Store (6 ofertas perdidas), o VNC sem senha reiniciava a cada 10 s sem dizer
por quê, e a CPU de 1 OCPU saturou. O dono pediu captura a cada 2 h das 22h às 8h.

## Goals

- [ ] Cada robô na sua tela VNC (`:1` lojas, `:2` WhatsApp), só em `localhost`.
- [ ] `navegador.user_agent` opcional troca a identificação do navegador.
- [ ] VNC sem senha recusa subir com mensagem clara e sem laço.
- [ ] `janela_noturna` opcional nos dois robôs; sem as chaves, comportamento idêntico ao atual.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Captura local (BSV-46), API da Shopee (BSV-44), WhatsApp na instância 2, worker (BSV-47) | spec |
| Mudança de banco, procedure, CSV ou dependência de runtime | regra 2 da spec |
| Execução real na VPS e no Windows (noite de teste, 1 h no PC) | dono; bloqueia o merge |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Formato dos horários | `"HH:MM"`; `fim` exclusivo; `inicio == fim` = sem janela | Evita janela de 24 h por engano | n |
| Bloco inválido (hora ruim, intervalo ≤ 0) | Sem janela (ritmo normal) | Erro de config não pode parar a captura | n |
| Pausa dentro da janela | `min(intervalo, tempo até o fim)` | Às 08:00 volta ao ritmo normal sem esperar o intervalo inteiro | n |
| Lojas na janela | Depois de um lote também dorme (não relê a fila na hora) | Senão a fila acumulada gira sem pausa | n |
| WhatsApp ao acordar | A pausa conta como parada: a guarda existente de lacuna (≥ 10 min) dispara o catch-up pelo marcador | Reaproveita o mecanismo que já retoma por marcador | n |
| Janela lida | No arranque do robô | Simples; documentado no README | n |
| Código de saída da recusa sem senha | 78 + `RestartPreventExitStatus=78` | Sem laço de reinício; falha visível no `journalctl` | n |
| `iniciar_captura.sh` à mão | Padrão `BESAVE_DISPLAY=:2` | É o WhatsApp; `:1` é das lojas | n |
| Exemplos de config | Bloco `janela_noturna` com campos vazios | Copiar o exemplo não liga a janela | n |

Open questions: none

---

## User Stories

### P1: Telas separadas ⭐ MVP

**Acceptance Criteria**:

1. TEL-01: A unidade-modelo `besave-vnc@.service` SHALL subir `iniciar_vnc.sh %i` (tela `:%i`, só `localhost`) e parar com `vncserver -kill :%i`.
2. TEL-02: A unidade das lojas SHALL depender de `besave-vnc@1` e rodar com `BESAVE_DISPLAY=:1`; a do WhatsApp de `besave-vnc@2` com `BESAVE_DISPLAY=:2`, cada uma esperando o socket X da sua tela.
3. TEL-03: O README SHALL trazer o túnel SSH das portas 5901 e 5902.

### P1: Senha do VNC ⭐ MVP

**Acceptance Criteria**:

1. VNC-01: WHEN `~/.vnc/passwd` falta ou está vazio THEN `iniciar_vnc.sh` SHALL sair com 78, escrever mensagem citando `vncpasswd` e não chamar o `vncserver`.
2. VNC-02: WHEN há senha THEN SHALL executar `vncserver :N -fg -localhost yes -geometry 1600x900 -xstartup /usr/bin/startxfce4`.
3. VNC-03: WHEN N não é número de 1 a 99 THEN SHALL sair com 2 sem chamar o `vncserver`.
4. VNC-04: A unidade SHALL ter `RestartPreventExitStatus=78` e o README o passo `vncpasswd` à parte.

### P1: Identificação do navegador ⭐ MVP

**Acceptance Criteria**:

1. UA-01: WHEN `navegador.user_agent` está ausente, vazia ou inválida THEN os argumentos do navegador SHALL ser idênticos aos de hoje.
2. UA-02: WHEN preenchida THEN `montar_kwargs` SHALL incluir `user_agent` (sem espaços nas pontas) e mais nada mudar; `launch_persistent` SHALL passá-la.
3. UA-03: `ml_login.py` e `shopee_login.py` SHALL usar `launch_persistent`; o README SHALL trazer o valor recomendado, a conferência (`navigator.userAgent`, `navigator.platform`) e o aviso de captcha.

### P1: Janela noturna ⭐ MVP

**Acceptance Criteria**:

1. JAN-01: WHEN `janela_noturna` está ausente ou inválida THEN nenhum robô SHALL mudar o ritmo, a qualquer hora.
2. JAN-02: WHEN `agora` está antes de `inicio` THEN SHALL estar fora; em `inicio` e depois, dentro; em `fim` e depois, fora; também com janela que cruza a meia-noite.
3. JAN-03: WHEN dentro da janela THEN a pausa entre rodadas SHALL ser `min(intervalo_minutos, tempo até o fim)`; fora, o ritmo normal.
4. JAN-04: WHEN o robô das lojas está na janela THEN SHALL dormir também depois de processar um lote.
5. JAN-05: WHEN o WhatsApp termina uma rodada dentro da janela THEN SHALL dormir em fatias de até 5 s sem fechar processo ou navegador, e o estado SHALL continuar sendo salvo no `finally`.
6. JAN-06: Os `config.example.json` SHALL documentar a chave sem ligar a janela.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| TEL-01 | Telas separadas | Execute | Done |
| TEL-02 | Telas separadas | Execute | Done |
| TEL-03 | Telas separadas | Execute | Done |
| VNC-01 | Senha do VNC | Execute | Done |
| VNC-02 | Senha do VNC | Execute | Done |
| VNC-03 | Senha do VNC | Execute | Done |
| VNC-04 | Senha do VNC | Execute | Done |
| UA-01 | Identificação | Execute | Done |
| UA-02 | Identificação | Execute | Done |
| UA-03 | Identificação | Execute | Done |
| JAN-01 | Janela noturna | Execute | Done |
| JAN-02 | Janela noturna | Execute | Done |
| JAN-03 | Janela noturna | Execute | Done |
| JAN-04 | Janela noturna | Execute | Done |
| JAN-05 | Janela noturna | Execute | Done |
| JAN-06 | Janela noturna | Execute | Done |

---

## Success Criteria

- [ ] `pytest` verde; `shellcheck` e `systemd-analyze verify` limpos (rodam na VPS/CI Linux).
- [ ] Real (dono), VPS: telas em 5901/5902; uma noite com a janela; 1 dia sem Play Store; oferta ML com link de afiliado com o dono usando a outra tela; `encerrar_captura.sh` para tudo e o contador fica certo.
- [ ] Real (dono), Windows: 1 h dos dois robôs no PC sem diferença no log.
