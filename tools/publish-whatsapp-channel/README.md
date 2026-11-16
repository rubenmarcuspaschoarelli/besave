# tools/publish-whatsapp-channel — publicador do canal do WhatsApp (BSV-63)

Posta no canal **"BeSave - Preços Baixos e Ofertas incríveis"** as linhas `P` de `ENVIO_WHATSAPP` que o
`besave-envio` enfileira (BSV-62, CONTRATO §11.3–11.4). Não há API de canal: o publicador usa o WhatsApp Web
num Chromium do Playwright, com **número próprio** (admin do canal), **na inst2** e com **perfil próprio**.
Não importa nada de `capture-*`: um banimento de um número não derruba o outro programa.

## O que ele faz, a cada volta

A volta acontece a cada `intervalo_minutos` (padrão 15, ±30% aleatório). Em ordem:

1. relê `conf/config.json`; `habilitado: false` → nada (para sem reiniciar);
2. em pausa → nada; sessão deslogada (QR na tela) → aviso "ler o QR pelo VNC" e nada;
3. descarta as `P` do canal: oferta inativa → `X expirou`; da fila de um dia anterior (Brasília) →
   `X outro_dia`; na fila há mais de `max_horas_fila` (padrão 3) → `X velha`;
4. lê `PARAMETROS_ENVIO` do canal (`id_canal`, padrão 2): fora da janela, no teto (`QT_MAX_DIA`, contando `E`
   e `D` do dia) ou adiantado no ritmo (`esperado` da BSV-40 com `L = 1`) → nada;
5. pega a `P` mais recente; baixa `https://besave.com.br/img/ofertas/{id}.webp` (sem ela, o placeholder da
   área) e faz o quadrado 800×800 JPEG de fundo branco;
6. abre o canal (nome = `CANAL_ENVIO.DS_CHAT_ID` do `id_canal`; se o cabeçalho já é o do canal, não navega;
   senão Canais → busca → célula → confere o cabeçalho; divergiu = falha, nada enviado), põe a foto no input
   oculto do footer e cola a legenda na prévia, conferindo cru com cru (`*…*` e `_…_` aparecem crus na caixa);
   divergiu duas vezes → fecha a prévia, falha, sem `D`;
7. grava `D 'enviando'`, clica em "Enviar 1 item selecionado" e espera, por `timeout_post_segundos` (padrão 60),
   a confirmação **positiva**: a prévia fechou, apareceu um balão **novo** cuja legenda tem `besave.io/{ID_OFERTA}`
   e cujo status (`msg-meta`) é Enviada, Entregue ou Lida → `E`. Qualquer outra coisa → a linha fica `D` e chega
   um aviso.

Um post por volta. **Linha `D` nunca é reenviada pelo programa**: postar duas vezes é pior que deixar de
postar uma.

| situação | linha | conta falha? | aviso |
|---|---|---|---|
| confirmado | `E` (`DT_ENVIO`) | zera | "voltou" se havia pausa |
| falha antes do clique (canal não abriu, anexo, legenda diferente, sem foto) | continua `P` | sim | — |
| clicou e não confirmou (rede caiu, navegador caiu) | `D` | sim | "linha N ficou D: conferir no canal" |
| 3 falhas seguidas | — | — | pausa de 60 min (1 aviso; lembrete a cada 6 h) |

Navegador morto → sai com código 1 e o `systemd` reinicia. Exceção inesperada na página → recarrega uma vez
(as falhas previstas — cabeçalho, anexo, legenda — só fecham a prévia com `Escape`).

## Instalar na inst2 (uma vez, como `besave`)

Pré-requisitos (dono): o número de publicação é **admin** do canal; inst2 com Python 3.12, Instant Client e
wallet (BSV-61) e a tela VNC (`tools/vps/iniciar_vnc.sh`, unidade `besave-vnc@1`).

```bash
cd /srv/besave/repo/tools/publish-whatsapp-channel
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
install -m 600 conf/config.example.json conf/config.json     # e preencher o bloco oracle (modo 600!)
cd ../vps && chmod +x *.sh
mkdir -p ~/.config/systemd/user/besave-vigia-robos.service.d
cp systemd/besave-vnc@.service systemd/besave-publicador-whatsapp.service \
   systemd/besave-vigia-robos.service systemd/besave-vigia-robos.timer ~/.config/systemd/user/
cp systemd/inst2/besave-vigia-robos.service.d/robos.conf ~/.config/systemd/user/besave-vigia-robos.service.d/
systemctl --user daemon-reload
systemctl --user enable --now besave-vnc@1 besave-publicador-whatsapp besave-vigia-robos.timer
```

O drop-in `robos.conf` põe `BESAVE_VIGIA_ROBOS=publicador`: na inst2 o vigia olha só o publicador. Na inst1
**não** instalar o drop-in (sem a variável o vigia segue com `lojas,whatsapp`).

Avisos: `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` do ambiente ou do `/srv/besave/worker.env` (o mesmo do vigia;
outro caminho em `BESAVE_WORKER_ENV`). Senha do Oracle: `BESAVE_ORACLE_PASS` vence a do JSON.

## Primeiro login (QR)

1. Túnel para a tela: `ssh -L 5901:localhost:5901 besave@<inst2>` e cliente VNC em `localhost:5901`.
2. `systemctl --user start besave-publicador-whatsapp`; o Chromium abre o WhatsApp Web na tela `:1`.
3. No celular do **número de publicação**: Aparelhos conectados → ler o QR. A sessão fica em `.chrome_perfil/`
   (fora do git; equivale a credencial).
4. O log diz `Sessao autenticada`; o publicador segue sozinho. Se a sessão cair, chega o aviso "ler o QR pelo
   VNC" e nada é postado até lá (o vigia também avisa, sem reiniciar).

Log: `log/run_publicador_DD_MM_HHMMSS.log` (um por partida). Tela do processo: `tmux -L besave-publicador attach`
(sair sem parar: `Ctrl+b` `d`).

## Pausar, parar e religar

- Parar na volta seguinte, sem reiniciar: `"habilitado": false` no `conf/config.json`. Religar: `true`.
- Parar já: `systemctl --user stop besave-publicador-whatsapp` (sai com 130 e a unidade fica `inactive`; o vigia
  não religa unidade parada de propósito).
- Pausa automática (3 falhas seguidas): 60 min; não precisa fazer nada. Se repetir, ver o log.

## Linha `D` (duvidosa)

`D` = clicou em enviar e não viu o balão confirmado. O post **pode ter saído**. O programa nunca a reenvia.

1. Abrir o canal e procurar o post pelo título (o aviso traz a linha e a oferta).
2. Saiu → `UPDATE ENVIO_WHATSAPP SET ST_ENVIO = 'E', DS_MOTIVO = NULL WHERE ID_ENVIO_WA = <id>; COMMIT;`
3. Não saiu e ainda vale postar → `UPDATE ENVIO_WHATSAPP SET ST_ENVIO = 'P', DS_MOTIVO = NULL, DT_ENVIO = NULL
   WHERE ID_ENVIO_WA = <id>; COMMIT;` (volta à fila; se ficou velha, será descartada).
4. Não saiu e não vale mais → `ST_ENVIO = 'X', DS_MOTIVO = 'dono'`.

Um `D` conta no teto do dia (`DT_ENVIO` = hora do clique) até ser resolvido.

## Seletores

Mapeados pelo dono no WhatsApp Web real em **16/11/2026** (canal aberto depois de 2 posts de teste). Só
`data-testid`, `aria-label`, `role` e `title`; nunca classes `x…`, XPath ou ids dinâmicos `_r_…_`. Os ícones são
`<svg><title>NOME</title>`, não `data-icon`. Recorte redigido em `tools/tests/fixtures/whatsapp_canal_real.html`.

| passo | seletor |
|---|---|
| logado | `#side` ou `#pane-side` |
| aba Canais | `button[aria-label="Canais"]` |
| busca | o primeiro input de texto visível do painel aberto pela aba: `[data-testid="newsletter-tab-drawer"] input[type="text"]` (id dinâmico, `aria-label` vazio) |
| célula do canal | `[data-testid="newsletter-tab-newsletter-cell"][aria-label="Canal {nome}"]` (o realce da busca quebra o título em spans: usa o `aria-label`, não o texto) |
| canal aberto | `[data-testid="conversation-info-header-chat-title"]` com texto normalizado igual ao nome |
| caixa do canal | `[data-testid="conversation-compose-box-input"][contenteditable="true"]` |
| anexar | `#main footer button[aria-label="Anexar"]` |
| input de foto | `#main footer input[type="file"][accept="image/*"]` (oculto) → `set_input_files`; sem ele, Anexar e espera 5 s; sem ele ainda, o item "Fotos e vídeos" dentro de `expect_file_chooser` (o diálogo do sistema nunca abre solto) |
| legenda da prévia | `[data-testid="media-caption-input-container"][contenteditable="true"][role="textbox"]` |
| enviar da prévia | `div[role="button"][aria-label="Enviar 1 item selecionado"]` |
| balão | `[data-testid^="conv-msg-"]` |
| legenda do balão | `[data-testid~="image-caption"]` (o valor é `image-caption selectable-text`) |
| status do balão | `[data-testid="msg-meta"] [aria-label]` (real: `" Enviada "`, ícone `wds-ic-delivered`); aceitos, sem caixa e sem espaços: enviada, entregue, lida |

A prévia de mídia não estava no arquivo gravado: o bloco dela na fixture foi transcrito do mapeamento do dono.
O QR (`canvas[aria-label*="QR"]`/`"Scan"`/`"Escaneie"`) e o relógio de pendente não foram capturados: confirmar
no primeiro QR. Para gravar o DOM de novo (seletores mudaram), com o canal aberto:

```bash
.venv/bin/python main.py --gravar-dom     # grava dom/whatsapp_<hora>.html redigido; revisar nomes antes de usar
```

## Config (`conf/config.json`, modo 600)

| chave | padrão | |
|---|---|---|
| `habilitado` | `true` | relido a cada volta |
| `intervalo_minutos` | 15 | ±30% |
| `max_horas_fila` | 3 | acima → `X velha` |
| `timeout_post_segundos` | 60 | espera do balão confirmado |
| `id_canal` | 2 | `CANAL_ENVIO`/`PARAMETROS_ENVIO` |
| `modo_legenda` | `colar` | `colar` (cai para `digitar` se o texto não chegar idêntico) ou `digitar` |
| `oracle` | — | igual ao bloco `db` da captura |

## Testes

```bash
cd tools && python -m pytest -q tests/test_pub_*.py tests/test_vigia_publicador.py
```

Os testes do Chromium (`test_pub_canal_web.py`, parte 2) rodam sobre a fixture real com
`tests/fixtures/whatsapp_simulador.js` (comportamento simulado: enviar, status, anexo); nenhum toca o WhatsApp.
Pulam sem Playwright (o CI só instala `requirements-dev.txt`); rodam no PC e no WSL com `requirements.txt` e
`playwright install chromium` (no WSL sem sudo: `apt-get download libnss3 libnspr4 libasound2t64`, `dpkg -x`
numa pasta e `LD_LIBRARY_PATH` apontando para ela).
