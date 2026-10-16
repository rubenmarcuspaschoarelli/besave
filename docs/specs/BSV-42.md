# BSV-42 · Robôs: rodar no Linux ARM da VPS

**Papel:** Python · **Pastas:** `tools/capture-store-pages/`, `tools/capture-chat-groups/` (+ `tools/vps/`, novo) ·
**Depende de:** PR #75 (robôs no repo, no ar). AD-100, AD-101, AD-104; `docs/infra/VPS-INSTANCIA-1.md` (Fases 5–7)

## Contexto
Os robôs rodam no PC Windows do dono. Vão para a instância 1 da OCI: Ubuntu 24.04, **ARM64**, 1 OCPU,
8 GB, área de trabalho Xfce com VNC (`DISPLAY=:1`). O teste de 16/10 (modo `--csv`, Chromium do Playwright)
deu Amazon 15/15 e Mercado Livre 9/9 depois do login, com pico de 2 GB de memória. Três coisas impedem a
virada:
1. `capture-store-pages/core/browser.py` abre o Google Chrome (`channel='chrome'`), que não existe para
   Linux ARM64 no Playwright. No PC o Chrome continua necessário (comentário do código: captcha da
   Shopee).
2. Os padrões de caminho são do Windows (`E:\Work\besave\server\s3`, em `core/estado.py` e
   `wa/storage.py`), e `main.py` usa `tasklist`/`taskkill` para achar Chrome aberto.
3. A subida e a parada da captura do WhatsApp são `iniciar_captura.ps1`/`encerrar_captura.ps1`, com as
   conferências que já evitaram três incidentes (um processo só, perfil livre, contador não atrasado).

## Objetivo
Os dois robôs sobem na VPS com um comando, sobrevivem a reinício da máquina e continuam rodando no PC
exatamente como hoje.

## Saídas
1. **Navegador configurável** no `capture-store-pages`: chave `navegador.canal` no `config.json`
   (`"chrome"` = padrão atual; `""` = Chromium do Playwright). Mesmos flags nos dois casos, menos
   `--profile-directory` no Chromium. `config.example.json` documenta a chave.
2. **Portabilidade:** sem caminho de Windows como padrão silencioso no Linux (no Linux, sem a chave no
   `config.json`, o robô para com mensagem clara dizendo qual chave falta); `_chrome_aberto` e o
   fechamento forçado só no Windows (`sys.platform`); nenhum outro `tasklist`/`taskkill`/`.exe` no
   caminho de produção (`main.py`, `core/`, `stores/`, `run_captura.py`, `wa/`).
3. **Subida no Linux** (`tools/vps/`): `iniciar_captura.sh` com as mesmas conferências do `.ps1` (um
   `run_captura.py` vivo no máximo, perfil `user_data/` livre, `diag/checa_contador.py` ok antes de subir)
   e `encerrar_captura.sh`; unidades `systemd --user` para os dois robôs que rodam **dentro de uma sessão
   `tmux`** com `DISPLAY=:1` (as telas de login pedem `input()`; o operador responde com `tmux attach`),
   reinício automático em falha, logs nas pastas de log atuais.
4. `tools/vps/README.md`: instalar, subir, parar, ver log, atender a um pedido de login, voltar para o PC.

## Regras
1. **Comportamento no Windows inalterado:** mesmo navegador, mesmos flags, mesmos prompts, mesmos arquivos
   de saída. Teste que prova isso (montagem dos argumentos do navegador com e sem a chave).
2. Nenhuma mudança em SQL, procedures, colunas ou formato de CSV.
3. Sem dependência de runtime nova (regra 7); `pytest` só como dependência de desenvolvimento, num
   `requirements-dev.txt`, justificado no PR. `tmux` e `systemd` são do sistema.
4. Segredos continuam só no `config.json` (fora do git, AD-017); nada de senha em unidade `systemd`.
5. Os ajustes de `programas_ajuste/` ficam fora, a não ser os de login (`ml_login.py`, `shopee_login.py`),
   que precisam abrir o mesmo navegador do robô.

## Fora de escopo
Instalar a VPS (roteiro do dono), worker e envio (BSV-43), Shopee (BSV-44), Beleza na Web, WhatsApp por
API (OpenWA).

## Critério de aceite
- `pytest` (novo em `tools/`, sem rede nem navegador): argumentos do navegador com `canal="chrome"` e
  `canal=""`; erro claro sem a chave de caminho no Linux; conferências do `iniciar_captura.sh` (dois
  processos → recusa; contador atrasado → recusa) com processos e arquivos simulados.
- `shellcheck` sem avisos nos `.sh`; `ruff check` limpo nos arquivos tocados.
- **Real (dono), Windows:** os dois robôs rodam 1 hora no PC sem diferença no log.
- **Real (dono), VPS:** `systemctl --user start` dos dois; uma oferta de cada grupo do começo ao fim
  (grupo → fila → loja → site); `sudo reboot` e os dois voltam sozinhos; `encerrar_captura.sh` para tudo.

## Definition of done
PR com os testes verdes, README da VPS, `validation.md` do Verifier independente e a virada no roteiro
(Fase 7) feita pelo dono antes do merge.
