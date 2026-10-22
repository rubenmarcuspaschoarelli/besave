# tools/vps — robôs na VPS (Ubuntu 24.04 ARM64)

Sobe os dois robôs na instância 1 da OCI (roteiro: `docs/infra/VPS-INSTANCIA-1.md`, Fases 5–7). No PC
Windows nada muda: `iniciar_captura.ps1` e `encerrar_captura.ps1` continuam valendo.

| robô | unidade `systemd --user` | sessão `tmux` | log |
|---|---|---|---|
| `capture-chat-groups` (WhatsApp) | `besave-captura-whatsapp` | `besave-whatsapp` | `capture-chat-groups/log/run_captura_DD_MM.log` |
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
Falha de partida (tela ainda subindo, contador atrasado) não deixa a unidade em `failed`: tenta de novo a
cada 30 s, sem limite (`StartLimitIntervalSec=0`). Um erro permanente, como o contador atrasado,
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
um navegador está segurando `user_data/`, ou `diag/checa_contador.py` acusa o contador atrasado. A unidade
falha com a mensagem no `journalctl`; corrija e suba de novo. Também funciona sem o `systemd`:
`tools/vps/iniciar_captura.sh` (sobe e volta) ou com `--aguardar`.

## Ver log

```bash
tail -f /srv/besave/repo/tools/capture-chat-groups/log/run_captura_$(date +%d_%m).log
tail -f /srv/besave/repo/tools/capture-store-pages/destino/log/main_monitorar.log
journalctl --user -u besave-captura-whatsapp -f      # início, falhas e reinícios
```

## Atender a um pedido de login

Quando o robô pede login (Mercado Livre, Shopee) ou o QR do WhatsApp: abra a tela do robô (túnel SSH para as duas portas;
no PC: `ssh -L 5901:localhost:5901 -L 5902:localhost:5902 besave@<vps>`; cliente VNC em `localhost:5901`
para as lojas e `localhost:5902` para o WhatsApp), e num terminal:

```bash
tmux -L besave-lojas attach          # ou: tmux -L besave-whatsapp attach
```

Responda ao prompt, faça o login no navegador que abriu e saia **sem parar o robô**: `Ctrl+b` e depois `d`.
A sessão fica salva no perfil (`.chrome_perfil/`, `user_data/`); não precisa repetir.

## Parar

```bash
systemctl --user stop besave-captura-lojas
systemctl --user stop besave-captura-whatsapp     # ou: tools/vps/encerrar_captura.sh
```

O `encerrar_captura.sh` para a unidade do WhatsApp, manda `SIGINT` (Ctrl+C) ao `run_captura.py` (o `finally` salva
o contador), espera, usa `SIGKILL` no que sobrar, encerra o navegador do perfil e a sessão `tmux`.
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
pelo marcador (catch-up), então nada se perde; o contador é salvo no `finally` como sempre. Mudou o bloco:
reinicie o robô (a janela é lida no arranque). No log: `Janela noturna ... uma rodada a cada 120 min`.

## Voltar para o PC

1. Parar na VPS (acima).
2. Copiar o `conf/config.json` da VPS de volta (contador e marcadores do WhatsApp) para o PC.
3. No PC: `diag\checa_contador.py`, depois `iniciar_captura.ps1` (WhatsApp) e `python main.py --monitorar`
   (lojas). No PC deixe `navegador.canal` como `"chrome"` (ou sem a chave).

Nunca rode o mesmo robô nos dois lugares ao mesmo tempo (o contador de `ID_OFERTA` é do `config.json`).

## Testes

```bash
cd tools && pip install -r requirements-dev.txt && pytest
shellcheck vps/*.sh
systemd-analyze --user verify vps/systemd/*.service     # na VPS
```
