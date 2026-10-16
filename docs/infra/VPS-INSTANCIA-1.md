# VPS · Instância 1 (`bsv-auto-db-2026`) — produção de captura e publicação

Roteiro do dono para tirar do PC os robôs, o worker e o envio (AD-104). Cada fase termina num
**ponto de conferência**; só avance com ele verde. Volta (rollback) em todas as fases: religar no PC.

Convenções: `inst1` = `bsv-auto-db-2026` (10.0.0.230, IP público efêmero `<IP_INST1>`, sem entrada da
internet); `inst2` = `bsv-agent-2026` (10.0.0.29, IP público; serviços de apoio do produto: mensageria,
e-mail, backup; sem compilação nem agentes de desenvolvimento); `<IP_INST2>` e `<IP_CASA>` são placeholders (o repositório é público).

---

## Fase 0 · Decisões e console da OCI (antes de instalar qualquer coisa)

| # | o quê | por quê |
|---|---|---|
| 0.1 | ~~Confirmar arquitetura e sistema~~ **feito (16/10):** `aarch64`, Ubuntu 24.04.5 LTS | Ampere A1 (**ARM64**): sem Google Chrome, Instant Client e binários do worker para ARM. |
| 0.2 | ~~Redistribuir memória~~ **feito (16/10):** inst1 1 OCPU / **8 GB**; inst2 1 OCPU / **4 GB** | O Always Free é 2 OCPU + 12 GB **no total**. Produção roda 2 navegadores com tela + desktop + worker. Conferir na Fase 5, com os navegadores abertos (`free -h`). |
| 0.3 | ~~Converter a conta para Pay As You Go~~ **feito (16/10)**; falta o orçamento com alerta de US$ 1 | Instância ociosa (CPU, rede e memória < 20% por 7 dias) é parada pela Oracle; em PAYG não há reclamação e o Always Free continua grátis. O alerta avisa se algo sair da faixa gratuita. |
| 0.4 | ~~IP público efêmero na inst1~~ **feito (16/10)**; falta conferir que **nenhuma regra de entrada** da internet chega a ela (0.5) | A sub-rede é pública: sem IP público a inst1 não sai para a internet. Teste: `curl -sS https://api.telegram.org -o /dev/null -w '%{http_code}\n'` na inst1. |
| 0.5 | **Regras de rede (NSG ou security list):** inst1 entrada só TCP 22 de `10.0.0.0/24`; inst2 entrada só TCP 22 de `<IP_CASA>/32` (ou usar o Bastion da OCI, grátis) | Nada de VNC/RDP exposto: tela sempre por túnel SSH. |
| 0.6 | **ACL do banco** (Autonomous → Rede → "acesso só de IPs e VCNs permitidos"): IP de saída da inst1, da inst2 e do PC | O banco Always Free **não aceita endpoint privado nem fica dentro da VCN**: a conexão sai pela internet (ou pelo Service Gateway, se existir na VCN — aí a ACL pode usar a VCN). O IP de casa muda: quando mudar, atualizar a ACL ou acessar o banco pela inst2. |
| 0.7 | Corrigir o nome do volume de boot da inst2 (está igual ao da inst1) | Evita apagar o volume errado. |

**Conferência 0:** inst1 com saída para a internet e sem entrada da internet; ACL do banco ativa e o
PC ainda conectando.

---

## Fase 1 · Acesso do PC às máquinas

`~/.ssh/config` no PC (chave própria, nunca senha):
```
Host bsv-agent
  HostName <IP_INST2>
  User ubuntu
  IdentityFile ~/.ssh/besave_oci
Host bsv-auto
  HostName 10.0.0.230
  User ubuntu
  IdentityFile ~/.ssh/besave_oci
  ProxyJump bsv-agent
  LocalForward 5901 localhost:5901
```
`ssh bsv-auto` entra na inst1 passando pela inst2 e já abre o túnel da tela (VNC em `localhost:5901`).
Cliente de VNC no Windows: TigerVNC Viewer ou RealVNC Viewer.

Na inst2 (porta de entrada), antes de tudo: `PasswordAuthentication no` e `PermitRootLogin no` em
`/etc/ssh/sshd_config`, `sudo apt install -y fail2ban`, atualizações automáticas (Fase 2.1).

**Conferência 1:** `ssh bsv-auto` funciona do PC; nenhuma porta além da 22 aberta na inst2.

---

## Fase 2 · Base do Ubuntu (inst1)

```bash
# 2.1 sistema
sudo apt update && sudo apt -y full-upgrade
sudo apt install -y unattended-upgrades git unzip curl rsync htop jq python3-venv python3-pip
sudo timedatectl set-timezone America/Sao_Paulo      # OBRIGATÓRIO: os robôs gravam hora local
sudo locale-gen pt_BR.UTF-8
# 2.2 swap de 4 GB (folga para picos dos navegadores)
sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
# 2.3 usuário de serviço e pastas
sudo adduser --disabled-password --gecos "" besave
sudo mkdir -p /srv/besave/{bin,logs,imagens,oracle} && sudo chown -R besave:besave /srv/besave
```
Firewall: **não** ative o `ufw`. A imagem Ubuntu da OCI já traz regras de `iptables` próprias e o `ufw`
conflita com elas; o controle de entrada fica nas regras de rede da Fase 0.5.

**Conferência 2:** `date` mostra hora de Brasília (-03); `free -h` mostra a swap.

---

## Fase 3 · Tela remota (para os robôs com navegador visível)

```bash
sudo apt install -y xfce4 xfce4-terminal dbus-x11 tigervnc-standalone-server fonts-noto-color-emoji fonts-liberation
sudo -iu besave vncpasswd                     # senha só do VNC
sudo -iu besave vncserver :1 -localhost yes -geometry 1600x900 -xstartup /usr/bin/startxfce4
```
`-localhost yes`: a tela só é acessível pelo túnel SSH. Serviço `systemd` para o VNC subir no boot na
Fase 6. Fontes de emoji: os nomes dos grupos têm emoji.

**Conferência 3:** do PC, `ssh bsv-auto` e o viewer em `localhost:5901` mostram o desktop.

---

## Fase 4 · Oracle Instant Client (ARM64) e wallet

1. Baixe de oracle.com o **Instant Client Basic para Linux ARM (aarch64)**, versão 23.x, para
   `/srv/besave/oracle/` e descompacte (`instantclient_23_x`).
2. Dependência e registro da biblioteca:
   ```bash
   sudo apt install -y libaio1t64
   # o Ubuntu 24.04 renomeou a libaio; o Instant Client procura libaio.so.1
   sudo ln -s /usr/lib/aarch64-linux-gnu/libaio.so.1t64 /usr/lib/aarch64-linux-gnu/libaio.so.1
   echo /srv/besave/oracle/instantclient_23_x | sudo tee /etc/ld.so.conf.d/oracle.conf && sudo ldconfig
   ```
3. Wallet: copie do PC (`scp`) só `cwallet.sso`, `ewallet.pem`, `tnsnames.ora`, `sqlnet.ora` para
   `/srv/besave/oracle/wallet/`, `chmod 600`. No `sqlnet.ora`: `DIRECTORY="/srv/besave/oracle/wallet"`
   e **sem** as linhas `TRACE_*`.

**Conferência 4:** teste com o Python de um robô (Fase 5) conectando em `bsvdb_tp` e lendo `SYSDATE`
(hora de Brasília) e `MAX(ID_OFERTA)`.

---

## Fase 5 · Código e robôs (sem ligar a captura ainda)

```bash
sudo -iu besave
git clone https://github.com/rubenmarcuspaschoarelli/besave.git /srv/besave/repo
cd /srv/besave/repo/tools/capture-store-pages && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/playwright install --with-deps chromium
cd ../capture-chat-groups && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/playwright install --with-deps chromium
```
`config.json` de cada robô (copiado do PC, nunca pelo git), bloco `db` no Linux:
`"instant_client_dir": ""` (no Linux a biblioteca vem do `ldconfig`), `"config_dir": "/srv/besave/oracle/wallet"`,
`"dsn": "bsvdb_tp"`. Pasta de imagens apontando para `/srv/besave/imagens/ofertas/img`.

**Bloqueios conhecidos (ticket antes da Fase 7):**
- `capture-store-pages/core/browser.py` abre o **Google Chrome** (`channel='chrome'`). Não há Chrome
  para Linux ARM64 instalável pelo Playwright hoje; precisa virar configuração (Chromium na VPS).
- `capture-chat-groups/wa/storage.py` tem o caminho padrão das imagens fixo em `E:\Work\...`.
- `iniciar_captura.ps1` é PowerShell: as conferências dele (uma instância só, contador) viram unidade
  `systemd` + `diag/checa_contador.py` antes de subir.

**Conferência 5:** com tela (VNC), rodar os testes de loja do robô (`programas_ajuste/teste_link_afiliado.py`
e uma captura com `--csv`, sem gravar no banco) para Amazon, Mercado Livre e Shopee. **É o maior risco
do plano:** lojas bloqueiam IP de datacenter com mais força que IP residencial. Se a taxa de
"bloqueado_ou_login" subir muito, a captura de lojas fica no PC até termos solução.

---

## Fase 6 · Worker e envio

1. Binário Linux ARM64, gerado fora das VPS (decisão do dono: nada de compilar Rust nelas). Recomendado:
   job do GitHub Actions com runner Linux ARM, disparado em `main` (ticket próprio; o artefato é baixado e
   copiado). Alternativa: compilação cruzada no PC (`cargo zigbuild --target aarch64-unknown-linux-gnu`).
   Copiar `besave-ciclo` e `besave-envio` para `/srv/besave/bin/` (sempre do commit de `main`, AD-060).
2. `/srv/besave/worker.env` (`chmod 600`, dono `besave`): o mesmo do PC, trocando
   `BESAVE_ORACLE_CLIENT_DIR` (vazia), `TNS_ADMIN=/srv/besave/oracle/wallet`,
   `BESAVE_IMAGENS_DIR=/srv/besave/imagens/ofertas/img`, e acrescentando `BESAVE_LOG_DIR=/srv/besave/logs`,
   `BESAVE_LOCK` e `BESAVE_ENVIO_LOCK` (no Linux não existe `LOCALAPPDATA`).
3. Dois timers `systemd` de 5 min (`besave-ciclo.timer`, `besave-envio.timer`), `Persistent=false`.
4. Imagens: copiar do PC para `/srv/besave/imagens/` pelo menos as ofertas dos últimos 2 dias (o envio
   usa a foto local, AD-080; o worker só envia ao S3 imagem que ainda não existe lá).

**Conferência 6 (na virada):** desabilitar as tarefas `Besave Worker` e `Besave Envio` **no PC**,
ligar os timers na inst1. Primeiro ciclo: zero escritas, leitura do banco em < 2 s (mesma região).
Nunca os dois lugares ao mesmo tempo: o envio postaria em dobro no canal.

---

## Fase 7 · Virada dos robôs (um por vez)

1. **`capture-store-pages`:** parar no PC → logar Mercado Livre e Shopee no Chromium da inst1 (pela tela)
   → subir como serviço `systemd --user` com `DISPLAY=:1` → acompanhar 1 hora.
2. **`capture-chat-groups`:** parar no PC (`encerrar_captura.ps1`) → copiar `config.json` (contador e
   marcadores) → `diag/checa_contador.py` → abrir e escanear o QR do WhatsApp na tela → subir o serviço.

**Conferência 7:** uma oferta nova de cada grupo do começo ao fim (grupo → fila → loja → site → canal).
Dois dias estáveis → desligar o PC da operação (o XE local pode ser desinstalado depois).

---

## Fase 8 · Operação

- `logrotate` para `/srv/besave/logs` e os logs dos robôs; `manutencao_arquivos.py` semanal (cron).
- O vigia na AWS (BSV-15) continua avisando se o site parar.
- **Backup do banco** (o Always Free não faz restauração): export diário por Data Pump, cópia no bucket da
  OCI **e** no S3 — fica no plano da inst2.
