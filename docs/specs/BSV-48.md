# BSV-48 · Robôs na VPS: telas separadas, identificação de computador e janela noturna

**Papel:** Python (+ unidades `systemd`) · **Pastas:** `tools/capture-store-pages/`,
`tools/capture-chat-groups/`, `tools/vps/` · **Depende de:** BSV-42 (PR #81) mergeada. BSV-46 (captura
local) só começa depois desta: mexe nos mesmos arquivos. AD-104; `docs/infra/VPS-INSTANCIA-1.md`

## Contexto
Primeiro dia dos robôs na VPS (20/10):
1. Os dois navegadores dividem a mesma tela virtual (`:1`): interação numa janela rouba o foco da outra, e
   a área de transferência é uma só. O robô das lojas lê o link de afiliado da área de transferência, que
   só funciona com a janela em foco; a oferta 37827 saiu sem link de afiliado.
2. O link curto do Mercado Livre (`meli.la`) mandou o Chromium da VPS para a Play Store
   (`play.google.com/store/apps/details?id=com.mercadolibre`): 6 ofertas perdidas até o dono recusar o
   pedido de abrir o app. Suspeita: o navegador se identifica como `Linux aarch64`.
3. Sem senha do VNC, `besave-vnc` reinicia a cada 10 s sem dizer por quê.
4. A CPU de 1 OCPU fica perto de 100% com os dois robôs. Pedido do dono: das 22h às 8h, captura a cada
   2 h nos dois robôs, sem parar os processos.
5. Itens do aceite da BSV-42 não executados: `encerrar_captura.sh` real e 1 h no Windows.

## Objetivo
Cada robô na sua própria tela, o Mercado Livre abrindo a página do produto, falhas de configuração com
mensagem clara e ritmo noturno configurável, sem mudar o comportamento no PC.

## Saídas
1. **Uma tela por robô:** unidade-modelo `besave-vnc@.service` (tela `:N`, porta `590N`, só `localhost`);
   lojas em `:1`, WhatsApp em `:2`; as unidades dos robôs dependem da sua tela. README com o túnel das
   duas portas.
2. **Identificação do navegador:** chave `navegador.user_agent` no `config.json` do `capture-store-pages`
   (ausente = padrão do navegador, como hoje), usada também por `programas_ajuste/ml_login.py` e
   `shopee_login.py`. O valor recomendado para a VPS vai no README, com a forma de conferir
   (`navigator.userAgent` e `navigator.platform`) e o aviso de que a identificação inconsistente pode
   piorar o captcha.
3. **Senha do VNC:** a unidade recusa subir sem `~/.vnc/passwd`, com mensagem clara e sem laço de
   reinício; README com o `vncpasswd` em passo próprio (é interativo).
4. **Janela noturna** nos dois robôs: bloco `janela_noturna` no `config.json`
   (`inicio`, `fim`, `intervalo_minutos`; ausente = sem janela). Dentro dela, o robô dorme entre as rodadas
   em vez de varrer no ritmo normal; processo e navegador continuam abertos; ao sair da janela, volta ao
   ritmo normal na rodada seguinte. O WhatsApp retoma de cada grupo pelo marcador, como hoje (nada se
   perde); a fila das lojas acumula e é processada na rodada.

## Regras
1. Sem as chaves novas, comportamento idêntico ao de hoje no PC e na VPS (teste prova).
2. Nenhuma mudança de banco, procedure ou formato de CSV; sem dependência de runtime nova.
3. O relógio da janela é o do sistema (fuso de Brasília na VPS); a lógica recebe o "agora" para teste.
4. O contador do WhatsApp continua salvo no `finally` (SIGINT), também ao entrar e sair da janela.

## Fora de escopo
Captura local (BSV-46), API da Shopee (BSV-44), mover o WhatsApp para a instância 2, worker (BSV-47).

## Critério de aceite
- `pytest`: argumentos do navegador com e sem `user_agent`; janela noturna (antes, dentro, cruzando a
  meia-noite, saída) com relógio injetado nos dois robôs; unidades com a tela certa e a recusa sem senha.
- `shellcheck` limpo; `systemd-analyze verify` nas unidades.
- **Real (dono), VPS:** as duas telas em `localhost:5901` e `5902`; uma noite com a janela ligada (log com
  rodadas a cada 2 h e retomada às 8 h, sem oferta perdida); 1 dia sem desvio para a Play Store; uma
  oferta do ML com link de afiliado capturada enquanto o dono usa a outra tela; `encerrar_captura.sh` para
  tudo e o contador fica certo.
- **Real (dono), Windows:** 1 h dos dois robôs no PC sem diferença no log (pendência da BSV-42).

## Definition of done
PR com testes verdes, README da VPS atualizado, `validation.md` do Verifier independente e a noite de
teste real antes do merge.
