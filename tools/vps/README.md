# tools/vps — robôs na VPS (Ubuntu 24.04 ARM64)

Sobe os dois robôs na instância 1 da OCI (roteiro: `docs/infra/VPS-INSTANCIA-1.md`, Fases 5–7). No PC
Windows nada muda: `iniciar_captura.ps1` e `encerrar_captura.ps1` continuam valendo.

| robô | unidade `systemd --user` | sessão `tmux` | log |
|---|---|---|---|
| `capture-chat-groups` (WhatsApp) | `besave-captura-whatsapp` | `besave-whatsapp` | `capture-chat-groups/log/run_captura_DD_MM.log` |
| `capture-store-pages` (lojas) | `besave-captura-lojas` | `besave-lojas` | `capture-store-pages/destino/log/main_monitorar.log` |

Os robôs rodam dentro do `tmux` com `DISPLAY=:1` (a tela VNC do Xfce). As telas de login pedem `input()`;
o operador responde com `tmux attach`. Cada robô tem o próprio servidor `tmux` (`-L <sessão>`).

## Instalar (uma vez, como o usuário `besave`)

```bash
sudo apt install -y tmux
loginctl enable-linger besave                 # as unidades sobem no boot, sem login
cd /srv/besave/repo/tools/vps && chmod +x *.sh
mkdir -p ~/.config/systemd/user && cp systemd/*.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable besave-captura-whatsapp besave-captura-lojas
```

Pré-requisitos (Fase 5 do roteiro): `.venv` em cada robô, `conf/config.json` preenchido e, no
`capture-store-pages`, **`"navegador": {"canal": ""}`** (Chromium do Playwright; no Linux ARM64 não existe
Chrome). Chaves sem padrão no Linux, que o robô exige no `config.json`:
`s3.raiz` (store-pages) e `publicacao_s3.destino` (chat-groups). As unidades assumem o repositório em
`/srv/besave/repo`; se for outro caminho, ajuste as unidades antes de copiar.

## Subir

```bash
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

Quando o robô pede login (Mercado Livre, Shopee) ou o QR do WhatsApp: abra a tela VNC (túnel SSH,
`localhost:5901`), e num terminal:

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
```
