# BSV-63 Publicador do canal do WhatsApp na inst2 Specification

Fonte: `docs/specs/BSV-63.md`. Contrato: `docs/CONTRATO.md` §11.3–11.4 (legenda do WhatsApp, fila `ENVIO_WHATSAPP`).

## Problem Statement

A BSV-62 enche `ENVIO_WHATSAPP` com linhas `P` (legenda pronta). Falta quem poste no canal do WhatsApp. Sem API
oficial de canal, um programa independente da captura posta pelo WhatsApp Web, com outro número e outra máquina
(inst2), um post por vez, sem nunca postar duas vezes.

## Goals

- [ ] Programa `tools/publish-whatsapp-channel/` (`main.py` + `pub/`), sem importar nada de `capture-*`.
- [ ] Ritmo do canal 2 (janela, teto, `esperado` com `L = 1`), descarte `expirou`/`velha`/`outro_dia`, estados P→D→E.
- [ ] Foto 800×800 JPEG de fundo branco com placeholder; legenda idêntica a `DS_LEGENDA`, num envio só.
- [ ] Pausa, avisos, `habilitado`, batimento; vigia com `BESAVE_VIGIA_ROBOS`; unidades e README.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Avisos e "Oferta encerrada" no WhatsApp | spec |
| Reenviar linha `D` | spec, regra 2 |
| Mais de um canal | spec |
| Mudar a captura (`capture-chat-groups`) | spec, regra 6 |
| Pôr Playwright no CI | o job `tools` só instala `requirements-dev.txt`; os testes de DOM pulam lá e rodam no ambiente local (proposta no PR) |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Fuso | Brasília -03:00 fixo; datas do Oracle são hora local (igual ao worker, `BESAVE_ORACLE_TZ` padrão) e vão como `datetime` ingênuo | CLAUDE.md regra 5; `SQL_ENFILEIRAR_WHATSAPP` grava `DT_FILA` local | n |
| Contagem do dia | `ST_ENVIO IN ('E','D') AND DT_ENVIO >= 00:00 de Brasília`; `D` grava `DT_ENVIO` no instante do clique | Um `D` pode ter saído: contá-lo garante "nunca mais que `QT_MAX_DIA`" | n |
| Ritmo | `esperado = min(MAX, 1 + floor(MAX·(min − INI·60)/((FIM−INI)·60)))`, `None` fora de `[INI, FIM)`; posta se `esperado − enviados ≥ 1` | `apps/worker/src/envio/janela.rs` com `L = 1` | n |
| Ordem dos descartes | `expirou` > `outro_dia` > `velha`; varredura de todas as `P` do canal a cada volta habilitada, antes da escolha | "pendente de ontem" vira `outro_dia` mesmo velha; o teto não descarta sozinho | n |
| Oferta sem linha em `OFERTA` | `expirou` | Expurgo não apaga do Oracle; ausência = não publicável | n |
| Escolha | a `P` restante de maior `DT_FILA` (empate: maior `ID_ENVIO_WA`) | "a mais recente" | n |
| Falha | falha antes do clique e `D` contam para as 3 seguidas; post confirmado zera | `D` repetido indica rede/sessão ruim | n |
| Pausa | 60 min; 1 aviso por ocorrência e lembrete a cada 6 h; ao fim da pausa o contador zera; "voltou" no primeiro `E` depois da ocorrência | spec item 7 | n |
| Confirmação | balão novo cujo texto normalizado contém o começo da 1ª linha da legenda (sem `*_~\``) **e** sem relógio de pendente (`msg-time`) | Com a rede caída o WhatsApp mostra o balão local com relógio: só o balão daria `E` falso (teste real 2) | n |
| Legenda | modo `colar` (evento `paste` com `text/plain`) e conferência do texto do editor; diferente → limpa e `digitar` (linhas com `insert_text`, quebra com `Shift+Enter`); diferente de novo → falha antes do clique | spec 4.2: o texto tem de chegar idêntico | n |
| Sessão deslogada | QR na tela → aviso "ler o QR pelo VNC" (1 por ocorrência, lembrete 6 h), sem tentar; o log tem as marcas do robô da captura (`Aguardando o WhatsApp Web carregar` / `Sessao autenticada`) para o `pede_qr` do vigia | spec 7; vigia BSV-57 | n |
| Batimento | depois de toda volta concluída (com ou sem post, em pausa, fora da janela, em QR, desligado); `prazo = agora + sono + 10 min` | spec 9, formato BSV-57 | n |
| Credencial do aviso | `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` do ambiente; senão do arquivo `BESAVE_WORKER_ENV` (padrão `/srv/besave/worker.env`) | igual ao vigia | n |
| Permissão do config | o publicador não grava o config; na partida, modo com bits de grupo/outros → WARN; README instala com `install -m 600` | spec 8 (BSV-60) | n |
| Seletores e fixture | fixture **sintética**, montada com as âncoras estáveis conhecidas (`#pane-side`, `data-icon`, `aria-label`, `span[title]`); captura real e `--gravar-dom` (DOM redigido) ficam com o dono na inst2 | o agente não tem acesso ao VNC da inst2 nem ao número; a spec pede seletor real — bloqueia o merge | n |
| Tela | `besave-vnc@1` e `DISPLAY=:1` na inst2 (só um robô lá) | inst2 não roda a captura | n |
| Memória | scope com `MemoryHigh=1500M`, `MemoryMax=2000M`, `MemorySwapMax=0`, provisórios | o dono fecha com o `free -m` de 24 h (teste real 4) | n |
| Pillow no CI | entra em `tools/requirements-dev.txt` (já é dependência dos dois robôs) | os testes da foto precisam rodar no CI; não é dependência nova do projeto | n |

**Open questions:** seletores reais (dono, teste real).

---

## User Stories

### P1: Publicar a fila no canal ⭐ MVP

**Acceptance Criteria (EARS):**

- **RIT-01** WHEN `QT_MAX_DIA = 40`, janela 8–22 and voltas de 15 min por um dia THEN the publicador SHALL postar ≤ 40, nenhum fora de `[08:00, 22:00)`.
- **RIT-02** WHEN são 07:59 ou 22:00 de Brasília THEN the publicador SHALL fazer 0 tentativas.
- **RIT-03** WHEN `esperado − enviados_hoje < 1` THEN the publicador SHALL fazer 0 tentativas naquela volta.
- **RIT-04** The publicador SHALL dormir `intervalo_minutos × U(0,7; 1,3)` entre voltas e ler `PARAMETROS_ENVIO` do canal a cada volta.
- **ESC-01** WHEN há 3 linhas `P` válidas THEN the publicador SHALL postar a de maior `DT_FILA`.
- **ESC-02** WHEN a oferta da linha `P` tem `ST_ATIVO = 0` (ou não existe) THEN the linha SHALL virar `X` com `DS_MOTIVO = 'expirou'`, sem post.
- **ESC-03** WHEN a linha `P` está na fila há mais de `max_horas_fila` (padrão 3) THEN it SHALL virar `X velha`.
- **ESC-04** WHEN a linha `P` é de um dia anterior (Brasília) THEN it SHALL virar `X outro_dia`.
- **EST-01** WHEN o post é confirmado THEN the linha SHALL virar `E` com `DT_ENVIO`, depois de ter passado por `D 'enviando'` antes do clique.
- **EST-02** WHEN a tentativa falha antes do clique THEN the linha SHALL voltar a `P` e uma falha SHALL ser contada.
- **EST-03** WHEN não há confirmação em `timeout_post_segundos` depois do clique THEN the linha SHALL ficar `D` e um aviso com o id SHALL ser enviado.
- **EST-04** The publicador SHALL nunca tentar uma linha `D` (só lê `P`).
- **FOT-01** The foto SHALL ser JPEG 800×800, fundo branco, imagem inteira centralizada com a proporção preservada.
- **FOT-02** WHEN a foto da oferta falha (404, timeout, inválida) THEN the publicador SHALL usar o placeholder de `DS_AREA_SLUG` com WARN.
- **FOT-03** WHEN o placeholder também falha THEN the tentativa SHALL ser falha antes do clique (linha `P`), sem post e sem `D`.
- **LEG-01** WHEN a legenda é escrita THEN the editor SHALL receber texto idêntico a `DS_LEGENDA`, com as linhas em branco, num envio só (quebra = `Shift+Enter`, nunca `Enter`).
- **LEG-02** WHEN o texto do editor difere de `DS_LEGENDA` depois dos dois modos THEN the tentativa SHALL ser falha antes do clique.
- **PAU-01** WHEN há 3 falhas seguidas THEN the publicador SHALL pausar 60 min com 1 aviso; dentro da pausa, 0 tentativas; lembrete a cada 6 h.
- **PAU-02** WHEN um post é confirmado depois de uma pausa THEN the publicador SHALL avisar "voltou".
- **QR-01** WHEN a sessão está deslogada (QR) THEN the publicador SHALL avisar "ler o QR pelo VNC" sem tentar postar.
- **CFG-01** WHEN `habilitado` é `false` THEN the volta seguinte SHALL fazer 0 tentativas, sem reiniciar (config relido a cada volta).
- **CFG-02** The config SHALL ter padrões `intervalo_minutos 15`, `max_horas_fila 3`, `timeout_post_segundos 60`, `id_canal 2`, e o repositório SHALL trazer só `config.example.json` com `_obs`.
- **BAT-01** WHEN uma volta termina THEN the publicador SHALL gravar `conf/batimento.json` (formato BSV-57, `robo: publicador`).
- **LIM-01** WHEN a página levanta exceção THEN the publicador SHALL recarregar uma vez; WHEN o browser morre THEN it SHALL sair com código ≠ 0.
- **VIG-01** WHEN `BESAVE_VIGIA_ROBOS=publicador` THEN the vigia SHALL vigiar só o publicador; WHEN ausente THEN `lojas,whatsapp` como hoje.
- **UNI-01** `tools/vps/systemd/besave-publicador-whatsapp.service` SHALL rodar no scope `besave-publicador-robo` com `SuccessExitStatus=130`, `Restart=on-failure`, sem segredo; o drop-in da inst2 SHALL definir `BESAVE_VIGIA_ROBOS=publicador`.
- **ISO-01** The programa SHALL não importar `capture-*` nem conter telefone, link de convite, token, IP ou host.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| RIT-01 | P1 | Execute | Pending |
| RIT-02 | P1 | Execute | Pending |
| RIT-03 | P1 | Execute | Pending |
| RIT-04 | P1 | Execute | Pending |
| ESC-01 | P1 | Execute | Pending |
| ESC-02 | P1 | Execute | Pending |
| ESC-03 | P1 | Execute | Pending |
| ESC-04 | P1 | Execute | Pending |
| EST-01 | P1 | Execute | Pending |
| EST-02 | P1 | Execute | Pending |
| EST-03 | P1 | Execute | Pending |
| EST-04 | P1 | Execute | Pending |
| FOT-01 | P1 | Execute | Pending |
| FOT-02 | P1 | Execute | Pending |
| FOT-03 | P1 | Execute | Pending |
| LEG-01 | P1 | Execute | Pending |
| LEG-02 | P1 | Execute | Pending |
| PAU-01 | P1 | Execute | Pending |
| PAU-02 | P1 | Execute | Pending |
| QR-01 | P1 | Execute | Pending |
| CFG-01 | P1 | Execute | Pending |
| CFG-02 | P1 | Execute | Pending |
| BAT-01 | P1 | Execute | Pending |
| LIM-01 | P1 | Execute | Pending |
| VIG-01 | P1 | Execute | Pending |
| UNI-01 | P1 | Execute | Pending |
| ISO-01 | P1 | Execute | Pending |

## Success Criteria

- [ ] `cd tools && python -m pytest -q` verde; `ruff check vps/ tests/ publish-whatsapp-channel/`; `shellcheck vps/*.sh`.
- [ ] Teste real na inst2 (dono): os 5 passos da spec.
