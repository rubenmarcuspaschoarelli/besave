# BSV-67 Robô do WhatsApp religa pelo celular, reinicia antes do teto de memória e guarda a sessão — Specification

Fonte: `docs/specs/BSV-67.md`. Pasta: `tools/capture-chat-groups/` (+ `tools/vps/`, `tools/tests/`, `.gitignore`).

## Problem Statement

De 26/11 10:24 a 27/11 o robô do WhatsApp não capturou: o Chromium bateu no `MemoryHigh`, o reinício
caiu na tela do QR e o robô saiu a cada 5,5 min (254 partidas) sem ninguém poder ler o QR.

## Goals

- [ ] Sessão perdida volta sozinha da cópia guardada no reinício programado.
- [ ] Sem cópia boa, o dono religa pelo código de 8 caracteres no celular, recebido pelo Telegram.
- [ ] O robô espera vivo; o vigia entende a espera e reinicia o robô antes do teto de memória.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Publicador do canal (inst2) | ticket próprio depois do teste real |
| Causa do crescimento de memória | medida pela Saída 6 |
| Telegram como fonte e captura web fora do PC | tickets próprios |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Seletores | `data-testid` colhidos da página real em 27/11 (perfil temporário): `link_device_qr_phone_number_link`, `phone-number-input`, `link-device-phone-number-entry-screen`; "Avançar"/"Next" por texto; canvas por `aria-label*="QR code"` (pt e en); código por `link-with-phone-number-code-cells` (tabela do dono) | regra 8; testid estável, texto como reserva | n |
| Hora e dia do teto de códigos | hora cheia e dia de calendário em Brasília (-03:00) | "virou a hora → sai"; o dono lê Brasília | n |
| Teto atingido no dia | próximo pedido às 00:00 de Brasília do dia seguinte; no da hora, na hora cheia seguinte | Saída 3 | n |
| Persistência do teto | `conf/pareamento_pedidos.json` (instantes UTC das últimas 24 h), fora do git | partida nova não zera o teto (regra 5) | n |
| Datas da cópia | `user_data.copia/copiada_em` (ISO UTC, gravado pelo script) e `user_data.copia/restaurada_em` (ISO UTC, gravado pelo robô); nenhum dos dois vai para o `user_data/` restaurado | Saída 2 pede a data e a marca no diretório da cópia | n |
| Número divergente na máscara | não avança; manda a mensagem própria (revisão do arquiteto) e espera vivo, sem novo pedido nessa partida | Saída 3 | n |
| Código inválido ou que não aparece em 30 s | conta como pedido (o WhatsApp registrou), log de erro e novo pedido na volta seguinte (dentro do teto) | Saída 1 "erro e novo pedido"; regra 5 | n |
| Intervalo da espera viva | 5 s entre voltas; batimento `fase: "pareamento"` com prazo `em + 15 min` | Saída 3 | n |
| Disparo do reinício por memória | `systemctl --user start --no-block besave-reinicio-whatsapp.service` | a unidade é oneshot (até 300 s); `start` bloqueante estouraria o timeout de 150 s do vigia | n |
| Aviso de memória | só quando o disparo é o 2º dentro de 6 h | "Telegram só no 2º disparo em 6 h" | n |
| Open questions: nenhuma | — | — | — |
| Lembrete da espera | 1º lembrete 6 h depois de o vigia ver a fase `pareamento`, depois a cada 6 h; N = horas desde que viu | Saída 4 | n |
| `pareamento` vencido | regra de parado sem a exceção do QR pendente (reinicia) | critério "`pareamento` vencido → reinício como hoje" | n |
| Log da partida parada (cópia) | o `run_captura_*.log` de maior mtime antes do `stop` | Saída 5 | n |

---

## User Stories

### P1: Detectar a tela de login ⭐ MVP

**Acceptance Criteria**:

1. WHEN o WhatsApp Web abre THEN o robô SHALL esperar até 5 min pelo primeiro de: `#pane-side` (logado), tela do QR, tela do número ou tela do código, por `data-testid`/`aria-label`/texto visível pt e en, nunca por classe. (TEL-01)
2. WHEN nenhuma das telas aparece em 5 min THEN o robô SHALL sair com `TimeoutError` como hoje. (TEL-02)

### P1: Restaurar a sessão guardada ⭐ MVP

1. WHEN cai na tela de login AND `user_data.copia/` existe sem `restaurada_em` THEN o robô SHALL fechar o contexto, gravar `restaurada_em`, mover `user_data/` para `user_data.qr/` (substituindo a anterior), copiar a cópia para `user_data/`, relançar e voltar a TEL-01, com o log `[sessao] tela de login; restaurando a copia de <data UTC>`. (RES-01)
2. WHEN a restauração abre a sessão THEN o robô SHALL logar `[sessao] copia restaurada; sessao ok` e mandar `WhatsApp: sessao perdida e restaurada da copia de <data Brasilia> (sem acao).` (RES-02)
3. WHEN a cópia já tem `restaurada_em` ou não existe THEN o robô SHALL ir direto ao pareamento; nunca apaga `user_data/`. (RES-03)

### P1: Código de pareamento pelo Telegram ⭐ MVP

1. WHEN sem sessão AND `pareamento.numero` preenchido THEN o robô SHALL abrir a tela do número, limpar o campo, digitar `+` e os dígitos, conferir os dígitos do `value`, avançar, ler `data-link-code` (8 `[A-Z0-9]`) e mandar `WhatsApp desconectado. No celular: WhatsApp > Aparelhos conectados > Conectar aparelho > Conectar com numero de telefone e digite ABCD-EFGH (pedido as HH:MM, Brasilia).` (PAR-01)
2. WHEN os dígitos do campo divergem do config THEN o robô SHALL não avançar, logar sem o número e mandar `WhatsApp desconectado: o campo nao aceitou o numero do config (***1234); ler o QR pela tela VNC :2.` (PAR-02, revisão do arquiteto)
3. WHILE espera o vínculo THEN o robô SHALL ficar vivo, gravar batimento `fase: "pareamento"` com prazo de 15 min a cada volta e, quando `#pane-side` aparecer, logar `[sessao] vinculado pelo codigo` e mandar `WhatsApp: vinculado de novo pelo codigo; captura retomada.` (PAR-03)
4. WHEN o código expira (página voltou ao QR ou ao número, ou passou `pareamento.validade_min`, padrão 10) THEN o robô SHALL pedir outro. (PAR-04)
5. WHEN já houve 3 pedidos na hora ou 12 no dia THEN o robô SHALL não pedir, mandar uma vez `WhatsApp desconectado: limite de codigos atingido; proximo pedido as HH:MM (Brasilia).` e pedir de novo a partir do próximo horário. (PAR-05)
6. WHEN `pareamento.numero` está vazio THEN o robô SHALL mandar uma vez por partida `WhatsApp desconectado e sem pareamento.numero no config: ler o QR pela tela VNC :2.`, não clicar em nada e esperar vivo como em PAR-03. (PAR-06)
7. WHEN qualquer log ou mensagem cita o número THEN SHALL mostrar só `***` + 4 últimos dígitos; o código não vai ao log. (PAR-07)

### P1: Vigia entende a espera

1. WHEN o batimento está em dia com `fase == "pareamento"` THEN o vigia SHALL não reiniciar, não contar laço de partidas, não avisar e só lembrar a cada 6 h `Vigia dos robos: whatsapp aguardando vinculo pelo celular ha N h.` (VIG-01)
2. WHEN o batimento vence na fase `pareamento` THEN o vigia SHALL aplicar a regra de parado (reinício). (VIG-02)

### P1: Cópia da sessão boa

1. WHEN o reinício programado roda THEN o script SHALL fazer `stop`, cópia e `start`, nessa ordem, e contar a espera por `Grupo aberto` a partir do `start`. (COP-01)
2. WHEN o log da partida parada tem `Grupo aberto` THEN o script SHALL copiar `user_data/` sem os caches da lista para `user_data.copia.nova/`, gravar `copiada_em`, trocar por `mv` e logar `copia da sessao: N MB em S s`; sem `Grupo aberto` SHALL não copiar. (COP-02)
3. WHEN a cópia falha, ou algum processo ainda tem o perfil nos argumentos (`ps` do passo 2), THEN o script SHALL pular a cópia, avisar no Telegram e partir a unidade mesmo assim. (COP-03, revisão do arquiteto)

### P1: Reinício antes do teto de memória

1. WHEN o whatsapp está saudável na fase `rodizio` AND o maior Chromium do scope passa de `BESAVE_WHATSAPP_RSS_MAX_MB` (padrão 2500) THEN o vigia SHALL disparar o reinício programado, no máximo 1 por 60 min, fora da conta dos 2 reinícios/h, sempre com log. (MEM-01)
2. WHEN é o 2º disparo em 6 h THEN o vigia SHALL mandar `Vigia dos robos: whatsapp reiniciado por memoria 2 vezes em 6 h (maior chrome: N MB).` (MEM-02)

### P2: Fixtures e README

1. WHEN os testes de página rodam THEN SHALL usar recortes redigidos da página real (QR, número e código em pt e en; código `TESTE123`) em `tools/tests/fixtures/whatsapp/`. (FIX-01)
2. WHEN o dono lê o README THEN SHALL achar cada mensagem nova, a chave `pareamento`, o VNC, `user_data.copia/` e `user_data.qr/` e a restauração à mão; `config.example.json` traz `pareamento`. (DOC-01)

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| TEL-01 | Detectar a tela | Execute | Pending |
| TEL-02 | Detectar a tela | Execute | Pending |
| PAR-01 | Código de pareamento | Execute | Pending |
| PAR-02 | Código de pareamento | Execute | Pending |
| PAR-03 | Código de pareamento | Execute | Pending |
| PAR-04 | Código de pareamento | Execute | Pending |
| PAR-05 | Código de pareamento | Execute | Pending |
| PAR-06 | Código de pareamento | Execute | Pending |
| PAR-07 | Código de pareamento | Execute | Pending |
| FIX-01 | Fixtures | Execute | Pending |
| RES-01 | Restaurar a sessão | Execute | Pending |
| RES-02 | Restaurar a sessão | Execute | Pending |
| RES-03 | Restaurar a sessão | Execute | Pending |
| COP-01 | Cópia da sessão | Execute | Pending |
| COP-02 | Cópia da sessão | Execute | Pending |
| COP-03 | Cópia da sessão | Execute | Pending |
| VIG-01 | Vigia | Execute | Pending |
| VIG-02 | Vigia | Execute | Pending |
| MEM-01 | Vigia | Execute | Pending |
| MEM-02 | Vigia | Execute | Pending |
| DOC-01 | README | Execute | Pending |

---

## Success Criteria

- [ ] `pytest` e `ruff check vps/ tests/` do job `tools` verdes; testes do vigia e do script também no WSL.
- [ ] Mutantes do critério morrem: sem teto de códigos, `>=` no RSS, cópia sem checar `Grupo aberto`.
