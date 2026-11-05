# BSV-54 · VPS: reinício diário do robô do WhatsApp e teto de memória

**Papel:** Shell/systemd + Python · **Pasta:** `tools/vps/` (+ `tools/capture-chat-groups/` só para o
envio ao Telegram, ver Saída 3) · **Depende de:** BSV-48, BSV-51 (no ar). AD-104, AD-107; lições 28, 29

## Contexto
A inst1 (1 OCPU / 8 GB, swap de 4 GB) parou duas vezes por memória:
- **27–28/10:** travou ~21:10, sem OOM (swap em thrashing); reboot 28/10 12:11.
- **02/11:** a partir das 08:15 navegações de 60–200 s e `db` de 15–57 s no robô das lojas; às ~09:56 ele
  deixou de responder. Depois do restart das instâncias, o robô das lojas ficou parado na pergunta da
  Shopee (`input()`) até 05/11: **3 dias sem oferta nova no site** (ids 43967–46041 na fila).

Medido em 05/11 08:50, com o robô das lojas parado:

| processo | RSS | tempo de vida |
|---|---|---|
| `chrome --type=renderer` do perfil `capture-chat-groups/user_data` | **6,4 GB** | 2 d 20 h |
| demais (VNC, Xfce, outros `chrome`) | < 160 MB cada | |

`free -h`: 6,9 GB usados, swap 3,4/4,0 GB. A aba do WhatsApp Web cresce ~**2,2 GB/dia** (abre os grupos em
rodízio sem parar); a máquina enche em ~3 dias. Reiniciar o robô devolveu a memória (05/11 09:21).

## Objetivo
O Chromium do WhatsApp nunca acumula mais que um dia de memória, e se mesmo assim crescer, só o robô do
WhatsApp é parado — não a máquina, o worker e o site junto.

## Saídas
1. **Reinício diário programado:** `besave-reinicio-whatsapp.service` (oneshot) + `.timer` em
   `tools/vps/systemd/`, unidades `--user` do `besave`. Horário padrão **05:30** (dentro da janela noturna
   22:00–08:00, AD-107), `Persistent=false`. O service roda `tools/vps/reiniciar_whatsapp.sh`, que:
   1. registra no log o RSS do maior processo do perfil `user_data` antes de parar;
   2. `systemctl --user restart besave-captura-whatsapp` (SIGINT; o `finally` grava o contador);
   3. espera até 3 min e confere que a unidade está `active` **e** que o log novo do robô tem
      `[monitor] Retomando contador` ou `Grupo aberto`;
   4. se não confirmou (contador atrasado, QR pedido, falha de partida), avisa no Telegram (Saída 3) com o
      motivo visto no log. Confirmou: só log, sem mensagem.
2. **Teto de memória** em `besave-captura-whatsapp.service`: `MemoryHigh=3G` e `MemoryMax=4G` (valores
   propostos; justificar no PR com a medição). Ao bater no teto o systemd mata só esse robô e o
   `Restart=on-failure` o sobe de novo.
3. **Aviso no Telegram** reaproveitando `wa/alerta.py` (`enviar_telegram`, token e chat de
   `alerta.telegram_token`/`telegram_chat_id` do `config.json`, fora do git). Um ponto de entrada de linha
   de comando pequeno (ex.: `python -m wa.avisar "<texto>"`) que o shell chama. Token e chat nunca no log
   nem na linha de comando visível no `ps` (lidos do `config.json` pelo Python).
4. `tools/vps/README.md`: o reinício diário, o horário, onde ver o resultado
   (`journalctl _SYSTEMD_USER_UNIT=besave-reinicio-whatsapp.service`) e como desligar
   (`systemctl --user disable --now besave-reinicio-whatsapp.timer`).

## Regras
1. Não matar navegador nem processo por padrão de nome amplo: só `systemctl restart` da unidade (o
   `encerrar_captura.sh`/`KillSignal=SIGINT` já cuidam do perfil).
2. O reinício não roda se a unidade do WhatsApp estiver parada de propósito (`inactive` sem falha): só
   registra e sai.
3. Sem dependência nova; sem mudar a lógica de captura, contador ou marcadores.
4. Nada de segredo, IP ou nome de host no repositório nem nos logs de evidência (regra 11).

## Fora de escopo
- Partida sem perguntas do robô das lojas e vigia externo de batimento: **BSV-55** (spec própria).
- `ID_OFERTA` por sequence (fim do contador em arquivo): **BSV-56**.
- Detecção do QR/código de pareamento do WhatsApp: ticket próprio.
- Reinício diário do robô das lojas (o Chromium dele não cresce; e hoje a partida pede resposta).

## Critério de aceite
- `shellcheck tools/vps/*.sh` e `systemd-analyze --user verify tools/vps/systemd/*` limpos.
- Teste do `reiniciar_whatsapp.sh` com `systemctl`/log falsos (padrão de `tools/vps` existente):
  partida confirmada → sem aviso; log com `ABORTADO: contador atrasado` → aviso com esse motivo; unidade
  não sobe em 3 min → aviso; unidade parada de propósito → não reinicia. Cada caso discrimina (um mutante
  que sempre avisa ou nunca avisa falha em algum).
- Teste do ponto de entrada de aviso: sem token/chat → só log, código 0; com token → chama o envio com o
  texto; o token não aparece em nenhuma saída.
- Timer às 05:30 provado pelo arquivo (`OnCalendar`), não por comentário.
- **Real (dono, bloqueia o merge):** instalar na inst1 com a branch; disparar o service à mão uma vez
  (`systemctl --user start besave-reinicio-whatsapp`) e conferir log, captura retomada e contador; deixar
  2 noites e anotar o RSS do renderer antes de cada reinício (esperado ≤ ~2,5 GB) e `free -h` às 08:00.

## Definition of done
PR para `develop` com unidades, script, ponto de entrada de aviso, README, testes verdes,
`validation.md` do Verifier independente, a medição de memória da execução real (redigida, regra 11) e
as decisões propostas (horário, `MemoryHigh`/`MemoryMax`) para o dono levar ao `docs/DECISOES.md`.
