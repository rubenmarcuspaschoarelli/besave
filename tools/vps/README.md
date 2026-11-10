# tools/vps — robôs na VPS (Ubuntu 24.04 ARM64)

Sobe os dois robôs na instância 1 da OCI (roteiro: `docs/infra/VPS-INSTANCIA-1.md`, Fases 5–7). No PC
Windows nada muda: `iniciar_captura.ps1` e `encerrar_captura.ps1` continuam valendo.

| robô | unidade `systemd --user` | sessão `tmux` | log |
|---|---|---|---|
| `capture-chat-groups` (WhatsApp) | `besave-captura-whatsapp` | `besave-whatsapp` | `capture-chat-groups/log/run_captura_DD_MM_HHMMSS.log` (um por partida) |
| `capture-store-pages` (lojas) | `besave-captura-lojas` | `besave-lojas` | `capture-store-pages/destino/log/main_monitorar.log` |

Cada robô tem a **própria tela VNC** (Xfce): lojas em `:1` (porta `5901`), WhatsApp em `:2` (porta `5902`),
as duas só em `localhost`. Telas separadas evitam que a interação numa janela roube o foco da outra e que as
duas dividam a área de transferência (o robô das lojas lê o link de afiliado dela, que só funciona com a
janela em foco). As telas de login pedem `input()`; o operador responde com `tmux attach`. Cada robô tem o
próprio servidor `tmux` (`-L <sessão>`).

| robô | tela | porta | unidade da tela |
|---|---|---|---|
| lojas | `:1` | `5901` | `besave-vnc@1` |
| WhatsApp | `:2` | `5902` | `besave-vnc@2` |

A tela `:1` roda o Xfce completo; a `:2` roda **só o gerenciador de janelas (`xfwm4`)**, sem painel nem
segunda sessão Xfce. Cada tela sobe sob o seu próprio barramento (`dbus-run-session`), para as duas
não dividirem o `dbus` do usuário (`xstartup-xfce.sh` e `xstartup-leve.sh`, escolhidos pelo
`iniciar_vnc.sh`). Falta conferir na prática as duas telas ao mesmo tempo (item do aceite da BSV-48).

## Instalar (uma vez, como o usuário `besave`)

```bash
sudo apt install -y tmux
sudo loginctl enable-linger besave            # como root/sudo: ver o motivo abaixo
cd /srv/besave/repo/tools/vps && chmod +x *.sh
mkdir -p ~/.config/systemd/user && cp systemd/*.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable besave-vnc@1 besave-vnc@2 besave-captura-whatsapp besave-captura-lojas
```

**Senha do VNC (passo próprio, interativo — uma vez, antes de subir as telas):**

```bash
vncpasswd        # pede a senha duas vezes (vale para as duas telas)
```

O TigerVNC 1.13 (Ubuntu 24.04) grava em `~/.config/tigervnc/passwd`; versões antigas usam `~/.vnc/passwd`
(na VPS o arquivo está em `/home/besave/.vnc/passwd`). A checagem aceita os **dois** caminhos e não
`~/.vncpasswd`. Sem nenhum dos dois (ou com o arquivo vazio) a tela **recusa subir**: o `journalctl --user -u besave-vnc@1` mostra
`ABORTADO: sem senha do VNC` e a unidade fica em `failed` (código 78, sem reinício em laço). Rode o
`vncpasswd` e suba de novo.

**Migrando da unidade única `besave-vnc` (BSV-42):**
`systemctl --user disable --now besave-captura-whatsapp besave-captura-lojas besave-vnc`, apague
`~/.config/systemd/user/besave-vnc.service`, copie as unidades novas e rode o `enable` acima.

**Por que `enable-linger`:** unidade `--user` só roda enquanto o usuário tem sessão aberta. Sem o linger,
depois de `sudo reboot` nada sobe até alguém entrar por SSH. Com ele, o `systemd` do usuário `besave`
sobe no boot e inicia as três unidades.

**A tela vira unidade-modelo (`besave-vnc@N`).** Ela substitui o `vncserver :1` manual da Fase 3 (se estiver
rodando à mão, `vncserver -kill :1` antes). Cada robô tem `Requires=` e `After=` na SUA tela
(`besave-vnc@1` para as lojas, `besave-vnc@2` para o WhatsApp) e espera o socket `/tmp/.X11-unix/XN`
aparecer (até 60 s) antes de lançar: o `After=` só garante que o VNC foi *iniciado*, não que a tela já
responde. Parar ou reiniciar uma tela para o robô dela junto.
Falha de partida (tela ainda subindo, perfil travado) não deixa a unidade em `failed`: tenta de novo a
cada 30 s, sem limite (`StartLimitIntervalSec=0`). Um erro permanente, como o perfil travado,
repete a mensagem no `journalctl` a cada 30 s até ser corrigido; para parar o ciclo,
`systemctl --user stop <unidade>`.

Pré-requisitos (Fase 5 do roteiro): `.venv` em cada robô, `conf/config.json` preenchido e, no
`capture-store-pages`, **`"navegador": {"canal": ""}`** (Chromium do Playwright; no Linux ARM64 não existe
Chrome). Chaves sem padrão no Linux, que o robô exige no `config.json`:
`s3.raiz` (store-pages) e `publicacao_s3.destino` (chat-groups). As unidades assumem o repositório em
`/srv/besave/repo`; se for outro caminho, ajuste as unidades antes de copiar.

## Subir

```bash
systemctl --user start besave-vnc@1 besave-vnc@2   # as telas (os robôs já puxam, mas assim fica explícito)
systemctl --user start besave-captura-whatsapp     # confere antes de subir (abaixo)
systemctl --user start besave-captura-lojas
systemctl --user status besave-captura-whatsapp besave-captura-lojas
```

O `iniciar_captura.sh` (chamado pela unidade do WhatsApp) recusa subir se: já há um `run_captura.py` vivo,
um navegador está segurando `user_data/` ou o scope do robô anterior ainda existe. Não confere mais o
contador: o `ID_OFERTA` vem da sequence do banco (BSV-56, abaixo). A unidade
falha com a mensagem no `journalctl`; corrija e suba de novo. Também funciona sem o `systemd`:
`tools/vps/iniciar_captura.sh` (sobe e volta) ou com `--aguardar`.

## Ver log

Cada partida do robô do WhatsApp abre um log novo, `run_captura_DD_MM_HHMMSS.log` (se existir, por duas partidas no mesmo
segundo, `_2`, `_3`… sem limite): o nome do log nunca impede a partida e nenhum log antigo é reaproveitado.

```bash
tail -f "$(ls -t /srv/besave/repo/tools/capture-chat-groups/log/run_captura_*.log | head -n 1)"   # o log mais recente
tail -f /srv/besave/repo/tools/capture-store-pages/destino/log/main_monitorar.log
journalctl --user -u besave-captura-whatsapp -f      # início, falhas e reinícios
```

## Atender a um pedido de login

Quando o robô pede login (lojas no PC, sem `--sem-perguntas`) ou o QR do WhatsApp: abra a tela do robô (túnel SSH para as duas portas;
no PC: `ssh -L 5901:localhost:5901 -L 5902:localhost:5902 besave@<vps>`; cliente VNC em `localhost:5901`
para as lojas e `localhost:5902` para o WhatsApp), e num terminal:

```bash
tmux -L besave-lojas attach          # ou: tmux -L besave-whatsapp attach
```

Responda ao prompt, faça o login no navegador que abriu e saia **sem parar o robô**: `Ctrl+b` e depois `d`.
A sessão fica salva no perfil (`.chrome_perfil/`, `user_data/`); não precisa repetir.

O robô das lojas sobe com `--sem-perguntas` (BSV-55) e **não faz pergunta nenhuma**: não há prompt para
responder no `tmux`. Para ele, veja a seção seguinte.

## Robô das lojas: partida sem perguntas e bloqueios (BSV-55)

**Sozinho**, sem ninguém na tela:

- A unidade roda `main.py --monitorar --sem-perguntas`: nenhum `input()`. Shopee e programas de afiliado
  valem pela sessão salva no perfil (`.chrome_perfil/`). Navegador aberto no arranque (só no Windows) → sai com
  código 2, sem fechar nada, e o `Restart=on-failure` tenta de novo. Sem a opção (PC, operador no terminal), as
  perguntas continuam.
- Captcha ou tela de login/verificação da loja (`bloqueado_ou_login`) e painel de afiliado da Shopee deslogado
  (`sessao_afiliado_ausente`) **não tiram a linha da fila**: ela fica em `ST_CAPTURA='0'`, nada é gravado em
  `OFERTA`, e o ponteiro de retomada não passa dela.
- **3 bloqueios seguidos da mesma loja** → aquela loja entra em **pausa** por `bloqueio.pausa_minutos`
  (padrão 60): as linhas dela ficam em `'0'` e são puladas (`loja_pausada` no log), as outras lojas seguem. No
  fim da pausa o robô tenta **uma** linha: passou, a loja volta; falhou, pausa de novo.

**No Telegram** (bloco `alerta` do `capture-store-pages/conf/config.json`, fora do git: `telegram_token`,
`telegram_chat_id`; sem eles só vai para o log `main_monitorar.log`, linhas `[alerta]` e `[bloqueio]`):

- "Robo das lojas: Shopee em pausa…" — loja, motivo (`pagina` = captcha/login da loja; `afiliado` = painel de
  afiliado), linhas retidas, "Entrar no VNC :1 e logar". Uma por entrada em pausa.
- "…continua em pausa há N h" — lembrete a cada 6 h enquanto durar.
- "…voltou" — uma vez, quando a sonda passa.

**Logar pela tela sem parar o robô:** túnel e VNC `localhost:5901` (acima). No navegador do robô, numa **aba
nova**, faça o login que o aviso pediu (loja ou `affiliate.shopee.com.br`, inclusive captcha/OTP) e deixe a aba
aberta ou feche-a; não feche a janela nem as abas do robô. Não precisa `tmux`, nem reiniciar: no fim da pausa a
sonda usa a sessão nova e o "voltou" chega no Telegram. Para não esperar a pausa inteira, reinicie a unidade
(`systemctl --user restart besave-captura-lojas`): sobe sem perguntas e com a contagem zerada.

## Robô das lojas: encurtador bloqueado e túnel residencial (BSV-58)

Alguns encurtadores (hoje o `amzn.promos.link`) bloqueiam o IP de datacenter da inst1 no Cloudflare ("Sorry,
you have been blocked"). Só o **redirect** desses domínios sai pelo IP residencial do PC do dono, por um túnel
SSH; a página da loja, as imagens, os logins de afiliado e a fila continuam na inst1.

- **Como funciona:** no PC, `tunel_residencial.ps1` mantém `ssh -N -R 127.0.0.1:1080` para a inst1. Lá a porta
  `1080` vira um proxy SOCKS que escuta **só no `127.0.0.1` da inst1** (o bind é explícito no `-R`, e o `sshd`
  não publica encaminhamento reverso em outra interface sem `GatewayPorts`, que fica desligado). O robô chama
  `curl --proxy socks5h://127.0.0.1:1080` sem seguir redirect, um salto por vez, até o primeiro destino fora da
  lista, e abre esse destino pelo navegador da inst1, direto. No log: `redirect (proxy) -> amazon`.
- **Configuração** (`conf/config.json` do robô das lojas, bloco `redirecionamento`; modelo em
  `conf/config.example.json`): `proxy`, `dominios`, `timeout_segundos`, `max_saltos`. Sem o bloco, ou com
  `dominios` vazio, o robô segue como antes.
- **PC desligado, túnel fora ou proxy bloqueado:** nada se perde. A linha fica `redirecionamento_indisponivel`
  (`oracle=retida(0)`, `ST_CAPTURA=0`, ponteiro travado). Três seguidas pausam o domínio (as outras lojas
  seguem) e chega no Telegram `promos.link em pausa: túnel residencial fora? N linha(s) retida(s)`, lembrete a
  cada 6 h e "voltou" quando o túnel volta; as retidas são processadas sozinhas.
- **Incluir um domínio:** acrescente em `redirecionamento.dominios` (sem `www`, sem caminho: `promos.link` vale
  para `amzn.promos.link`, não para `xpromos.link`). O monitor relê o bloco a cada varredura; não precisa
  reiniciar. Domínio **fora** da lista que cair na página de bloqueio do Cloudflare também não vira `'9'`: a
  linha fica retida e o log (e, depois de três seguidas, o Telegram) diz
  `<dominio> bloqueado pelo Cloudflare; incluir em redirecionamento.dominios?`.

### Túnel no PC (Windows, OpenSSH ≥ 7.6)

Destino e chave **não** vão para o repositório; ficam em variáveis do usuário (uma vez, num PowerShell):

```powershell
setx BESAVE_TUNEL_DESTINO "ubuntu@<ip-da-inst1>"
setx BESAVE_TUNEL_CHAVE "<pasta-do-usuario>\.ssh\<chave-da-inst1>"
```

Antes da tarefa, conecte uma vez à mão para aceitar a chave do host (o script usa `BatchMode=yes` e não
pergunta nada): `ssh -i <chave> ubuntu@<ip-da-inst1> exit`.

Tarefa agendada (ao logar, sem janela; reinicia se o PowerShell morrer):

```powershell
$acao = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "<repo>\tools\vps\tunel_residencial.ps1"'
$gatilho = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$ajustes = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName 'besave-tunel-residencial' -Action $acao -Trigger $gatilho -Settings $ajustes
Start-ScheduledTask -TaskName 'besave-tunel-residencial'
```

- **Log:** `%LOCALAPPDATA%\besave\tunel_residencial.log` (conectando / caiu, com o código de saída do `ssh`;
  sem IP nem chave; passou de 1 MB, fica com as últimas 500 linhas). Caiu, reconecta em 30 s.
- **Parar:** `Stop-ScheduledTask -TaskName 'besave-tunel-residencial'`; para não subir no próximo logon,
  `Disable-ScheduledTask -TaskName 'besave-tunel-residencial'`. Se sobrar um `ssh.exe` do túnel, feche-o no
  Gerenciador de Tarefas. Para testar à mão (e derrubar fechando a janela), com a tarefa parada:
  `powershell -NoProfile -ExecutionPolicy Bypass -File tools\vps\tunel_residencial.ps1`.
- **Conferir na inst1:**
  `curl -sS -o /dev/null -w '%{http_code} %{redirect_url}\n' --proxy socks5h://127.0.0.1:1080 https://amzn.promos.link/<codigo>`
  → `302 https://www.amazon.com.br/...`.

## Parar

```bash
systemctl --user stop besave-captura-lojas
systemctl --user stop besave-captura-whatsapp     # ou: tools/vps/encerrar_captura.sh
```

O `encerrar_captura.sh` para a unidade do WhatsApp (o `ExecStop=` dela para o scope do robô com `SIGINT`), manda `SIGINT` (Ctrl+C) ao `run_captura.py` (o `finally` salva
os marcadores), espera, usa `SIGKILL` no que sobrar, encerra o navegador do perfil e a sessão `tmux`.
Filtra por `run_captura.py` e `--user-data-dir`: nunca mata todo `python`. Para desligar de vez no boot:
`systemctl --user disable ...`.

## Identificação do navegador (lojas)

No Linux ARM64 o Chromium se identifica como `Linux aarch64`; o link curto do Mercado Livre (`meli.la`)
então mandou o navegador para a Play Store (6 ofertas perdidas em 20/10). A chave `navegador.user_agent` do
`capture-store-pages/conf/config.json` troca a identificação (ausente ou vazia = padrão do navegador, como no
PC). Vale também para `programas_ajuste/ml_login.py` e `shopee_login.py`.

Valor recomendado para a VPS (Chrome em Linux x86_64; troque o número da versão pela do Chromium do
Playwright instalado, que `navigator.userAgent` mostra antes da troca):

```json
"navegador": { "canal": "", "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36" }
```

Conferir: com o robô parado, abra o navegador por `programas_ajuste/ml_login.py` e, no console, rode
`navigator.userAgent` e `navigator.platform`. **Aviso:** identificação inconsistente (UA diz x86_64 e
`navigator.platform` diz `Linux aarch64`) pode piorar o captcha da Shopee; se aparecer captcha novo, volte
a chave para vazio.

## Janela noturna

Bloco `janela_noturna` no `config.json` de **cada** robô (ausente ou vazio = sem janela):

```json
"janela_noturna": { "inicio": "22:00", "fim": "08:00", "intervalo_minutos": 120 }
```

Dentro dela (relógio do sistema; na VPS, Brasília; pode cruzar a meia-noite; `fim` exclusivo) o robô faz
uma rodada a cada `intervalo_minutos` e dorme entre elas, com processo e navegador abertos. Às 08:00 volta
ao ritmo normal. Lojas: a fila acumula e é processada na rodada. WhatsApp: ao acordar retoma cada grupo
pelo marcador (catch-up), então nada se perde; os marcadores são salvos no `finally` como sempre. Mudou o bloco:
reinicie o robô (a janela é lida no arranque). No log: `Janela noturna ... uma rodada a cada 120 min`.

## Aviso cobrindo a tela do WhatsApp (BSV-51)

Um aviso do WhatsApp Web (ex.: "Confira suas ligações recentes…", em `#wa-popovers-bucket`) ou um diálogo
pode ficar por cima da lista e interceptar o clique no grupo. O robô do WhatsApp resolve sozinho, nesta ordem:

1. **Escape**, e clica de novo. Cada clique tem 5 s de limite (não o padrão do Playwright).
2. Se ainda estiver coberto, clica num botão de **lista fechada** dentro de `#wa-popovers-bucket` ou
   `[role="dialog"]`: `Fechar`, `OK`, `Agora não`, `Close`, `Not now`. Nada que mude conta, grupo ou mensagem.
3. Se nada resolver, a volta falha como erro tratado (o rodízio segue). Depois de `destravar.recarregar_voltas`
   voltas seguidas sem abrir nenhum grupo (padrão 8, ~10 min; repete a cada 8) o robô **recarrega o WhatsApp
   Web** e roda o resgate (catch-up pelo marcador de cada grupo): nada se perde, ids e marcadores não andam.

**No log** (`log/run_captura_DD_MM_HHMMSS.log`): `[destravar] Clique interceptado…`, `Escape destravou o clique` ou
`Fechei 'agora nao' do aviso: '<texto resumido>'`, `Recarregando o WhatsApp Web…`, e `Rodizio destravado apos N
volta(s) cega(s)`.

**No Telegram** (bloco `alerta` do `config.json`, fora do git; sem `telegram_token`/`telegram_chat_id` só vai
para o log): se, **fora da janela noturna**, nenhum grupo abrir por `alerta.sem_abrir_minutos` (padrão 45), chega
"Robô do WhatsApp parado…", com lembrete a cada 2 h, e uma mensagem "voltou" quando destravar. Dentro da janela
noturna o relógio do aviso fica zerado.

**Ainda é preciso entrar na tela** (VNC `:2`) quando chegar o aviso de "parado": é um diálogo que o robô não
conhece (não está na lista), um pedido de login/QR ou o navegador travado. Feche à mão e confira no log que a
linha `Rodizio destravado` apareceu. Chaves novas (ver `conf/config.example.json`): `alerta`, `destravar`.

## Reinício diário do WhatsApp e teto de memória (BSV-54)

A aba do WhatsApp Web cresce ~2,2 GB/dia (o `chrome --type=renderer` do `user_data` chegou a 6,4 GB em
3 dias e levou a máquina ao swap). Duas defesas:

1. **Reinício a cada 6 h (05:30, 11:30, 17:30, 23:30):** na medição da inst1 (06/11) o renderer cresceu ~0,2 GB/h de dia (1,26 → 3,48 GB entre 06:10 e 17:10) e ficou parado à noite; um reinício só às 05:30 não bastava. `besave-reinicio-whatsapp.timer` (`Persistent=false`) dispara o
   `besave-reinicio-whatsapp.service`, que roda `reiniciar_whatsapp.sh`. Ele registra o RSS do maior
   processo do perfil, faz `systemctl --user restart besave-captura-whatsapp` (SIGINT: o `finally` grava os
   marcadores) e espera até 3 min a unidade ficar `active` **e** o log novo ter
   `Grupo aberto`. Confirmou: só log. Não confirmou (perfil travado, QR pedido, falha de partida): mensagem
   no Telegram com o motivo (`python -m wa.avisar`, token e chat lidos do `alerta` do `config.json`; sem eles,
   só log). Unidade parada de propósito (`inactive`): não reinicia. Só `systemctl restart`; nunca mata
   processo por nome.
2. **Teto de memória no scope do robô:** o tmux do Ubuntu 24.04 põe cada painel num scope próprio
   (`app.slice/tmux-spawn-*.scope`), fora da unidade: `MemoryHigh`/`MemoryMax` na unidade não pegavam o
   Chromium, e o `KillSignal=SIGINT` da unidade chegava só ao servidor tmux (o python morria por SIGHUP, sem o
   `finally`). Por isso o `iniciar_captura.sh` roda o robô, dentro do painel, por
   `systemd-run --user --scope --unit=besave-whatsapp-robo -p MemoryHigh=… -p MemoryMax=… -p MemorySwapMax=… -p KillSignal=SIGINT -p TimeoutStopSec=30`.
   Os valores vêm do `Environment=` da unidade (`BESAVE_MEM_HIGH=3500M`, `BESAVE_MEM_MAX=4500M`, provisórios; `BESAVE_MEM_SWAP_MAX=0`).
   **Sem `MemorySwapMax` o teto vira thrashing, não reinício:** o `MemoryMax` não conta swap, então o kernel joga
   o excesso no swap e o robô fica lento dentro do teto, sem ser morto (visto na execução real de 05/11 com
   `MemoryMax=300M`). Com `MemorySwapMax=0` o kernel mata o scope ao bater o `MemoryMax`.
   Em `MemoryHigh` o kernel segura; em `MemoryMax` (com swap em 0) o kernel mata o scope (código de saída ≠ 0), a unidade falha
   e o `Restart=on-failure` sobe de novo. O `ExecStop=` da unidade faz `systemctl --user stop besave-whatsapp-robo.scope`
   (SIGINT, até 30 s: o `finally` grava os marcadores) antes de o tmux morrer; scope ausente não falha o stop.
   Se o scope ainda estiver ativo na partida, o lançador recusa subir (não duplica o robô). O `systemd-run` usa `--collect`:
   scope que termina em `failed` (OOM-kill, `kill -9`) seria mantido carregado e todo `systemd-run` seguinte com o
   mesmo `--unit` falharia com "already loaded", em laço. Na partida, com o scope inativo, o lançador ainda roda
   `systemctl --user reset-failed` e `revert` (resíduo de `set-property --runtime`), ignorando erros; se o robô morrer
   nos primeiros segundos, o `ABORTADO` traz a última linha do log (a mensagem do `systemd-run`). O robô das lojas não muda.

```bash
cp systemd/*.service systemd/*.timer ~/.config/systemd/user/ && systemctl --user daemon-reload
systemctl --user enable --now besave-reinicio-whatsapp.timer
systemctl --user list-timers besave-reinicio-whatsapp.timer           # próximo disparo
systemctl --user start besave-reinicio-whatsapp                        # testar agora, uma vez
journalctl _SYSTEMD_USER_UNIT=besave-reinicio-whatsapp.service         # resultado (RSS antes, OK ou AVISO)
systemctl --user disable --now besave-reinicio-whatsapp.timer          # desligar
```

Ver o teto e a memória do robô: `systemd-cgls --user-unit besave-whatsapp-robo.scope` e
`systemctl --user show besave-whatsapp-robo.scope -p MemoryHigh -p MemoryMax -p MemoryCurrent`.
Mudou a unidade ou os valores de `BESAVE_MEM_*`: `daemon-reload` e `systemctl --user restart besave-captura-whatsapp`.

## `ID_OFERTA` pela sequence do banco (BSV-56)

O id de cada oferta do WhatsApp vem de `SQ_OFERTA_FILA.NEXTVAL`, pedido logo antes de salvar a imagem (o id é o
nome do arquivo, a linha do CSV e o `P_ID_OFERTA`). O `controle.ultimo_id_processado` do `config.json` virou só
informativo (último id usado) e **não é mais lido**; por isso a partida não confere contador e um `kill -9`, OOM ou
queda da máquina não deixa o robô preso no laço "contador atrasado". A trigger `TRG_OFERTA_FILA_ID` preenche
`ID_OFERTA` quando ele vem nulo (outros produtores da fila, como o futuro robô de sites). Buracos na numeração são
normais (id pedido e mensagem que não gravou).

**Banco fora:** sem id nada é gravado (nem CSV) e o marcador do grupo não anda; nenhum grupo anda. O robô avisa no
Telegram ("Banco Oracle fora", bloco `alerta`), lembra a cada 2 h, tenta de novo a cada `db.espera_segundos`
(padrão 60) e, quando o banco volta, avisa "voltou" e roda o resgate (catch-up pelo marcador de cada grupo): a mesma
mensagem sai com id novo. Sem o bloco `db` ligado no `config.json` o robô nem sobe (código de saída 4).

**Ordem de virada** (uma vez, na inst1):

1. Parar o robô do WhatsApp (`systemctl --user stop besave-captura-whatsapp`) e conferir que nenhum
   `run_captura.py` está vivo (`pgrep -af run_captura.py`).
2. Aplicar `tools/capture-chat-groups/sql/BSV-56_sequence_id_oferta.sql` como `BESAVE` (o robô também conecta
   como `BESAVE`, dono da tabela e da sequence); o bloco de conferência imprime
   `OK: proximo id N > maior existente M`. O arquivo é reexecutável: com a sequence já criada ele só informa o
   `LAST_NUMBER` e confere de novo.
3. Atualizar o código na inst1 (branch da PR) e subir o robô.
4. Conferir no log a 1ª captura com id = valor inicial da sequence e `db=ok`.

**Conferência real depois da virada** (bloqueia o merge da PR):

1. `INSERT` de teste com `ID_OFERTA` nulo numa transação (`ROLLBACK` no fim): a trigger preenche o id.
2. `KILL SESSION` da conexão do robô e `kill -9` no `run_captura.py` (a unidade sobe de novo): o robô sobe sem
   conferência de contador e o id seguinte vem da sequence, **sem id repetido**. Não há aviso de "fora": o
   `proximo_id` reconecta sozinho.
3. Banco fora de verdade, de dia: `sudo iptables -I OUTPUT -p tcp --dport 1522 -j DROP` por ~3 min e depois
   `sudo iptables -D OUTPUT -p tcp --dport 1522 -j DROP`. Esperado: 1 "Banco Oracle fora (DPI-1067)" no
   Telegram em ~1 min depois da 1ª oferta da janela (30 s de `db.call_timeout_segundos` + a espera), nada novo no
   CSV, marcador do grupo parado; ao liberar, a mesma mensagem sai com id novo e chega o "voltou". Sem o
   `call_timeout`, a chamada congelaria até o timeout do TCP (~15 min). Se nenhuma oferta chegar na janela, nada
   é numerado e nada avisa.
4. `systemctl --user start besave-reinicio-whatsapp` à mão: reinício confirmado, sem aviso no Telegram.

Não pode haver dois robôs do WhatsApp (PC e VPS) em versões diferentes: o antigo numeraria pelo arquivo e
colidiria com a sequence.

## Voltar para o PC

1. Parar na VPS (acima).
2. Copiar o `conf/config.json` da VPS de volta (marcadores do WhatsApp) para o PC.
3. No PC, com o código desta versão (id pela sequence): `iniciar_captura.ps1` (WhatsApp) e `python main.py --monitorar`
   (lojas). No PC deixe `navegador.canal` como `"chrome"` (ou sem a chave).

Nunca rode o mesmo robô nos dois lugares ao mesmo tempo (os marcadores dos grupos são do `config.json`).

## Testes

```bash
cd tools && pip install -r requirements-dev.txt && pytest
shellcheck vps/*.sh
systemd-analyze --user verify vps/systemd/*.service     # na VPS
```
