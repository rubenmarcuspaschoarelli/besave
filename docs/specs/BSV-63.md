# BSV-63 · Publicador do canal do WhatsApp na inst2

**Papel:** Python + Playwright + shell · **Pasta:** `tools/publish-whatsapp-channel/` (nova) (+ `tools/vps/` para
unidades, VNC e vigia, `tools/tests/`) · **Depende de:** BSV-62 mergeada e o SQL dela rodado. BSV-57 (vigia).
Lições 16, 19, 24, 28, 29, 31

## Contexto
A BSV-62 enche `ENVIO_WHATSAPP` (linhas `P`, legenda pronta) com cada oferta confirmada no Telegram. Falta
quem poste no canal **"BeSave - Preços Baixos e Ofertas incríveis"**. Não há API oficial para canal, então o
publicador usa o WhatsApp Web.

Decisões do dono (13/11):
- **número próprio**, admin do canal, com tempo de uso e contatos;
- **outra máquina** (inst2) e outro perfil de navegador;
- a captura não muda: um banimento do número de publicação não derruba a captura, e o inverso também vale.

## Pré-condições (dono, antes do teste real; não bloqueiam o código)
1. O número de publicação é **admin** do canal (convite feito pelo número dono).
2. Inst2 com tela por túnel (`tools/vps/iniciar_vnc.sh`, como a inst1), Python 3.12 e Chromium do Playwright
   ARM64. Instant Client e wallet já vêm da BSV-61.
3. Primeiro login: QR lido pelo VNC, com o perfil em `tools/publish-whatsapp-channel/.chrome_perfil`
   (fora do git).

## Saídas
1. **Programa** `tools/publish-whatsapp-channel/` (`main.py` + `pub/`), independente dos robôs: não importa
   nada de `capture-*`. O que precisar de lá (lançar o perfil persistente, conexão Oracle com reconexão) é
   copiado e reduzido ao mínimo.
2. **Laço:**
   - a cada `intervalo_minutos` (padrão 15, com variação aleatória de ±30%), dentro da janela do canal 2
     (`PARAMETROS_ENVIO`, lido a cada volta);
   - se `enviados_hoje < QT_MAX_DIA` e o ritmo da BSV-40 (`esperado` com `L = 1`) permitir, pega **1** linha
     `P` do canal 2, a mais recente.
3. **Descarte, antes de postar:** a linha vira `X` com o motivo quando a oferta:
   - está inativa (`ST_ATIVO = 0`): `expirou`;
   - está na fila há mais de `max_horas_fila` (padrão 3): `velha`;
   - ficou pendente de um dia anterior: `outro_dia`.

   O teto do dia não descarta nada sozinho: o que sobra vira `outro_dia` na volta seguinte à virada do dia.
4. **Postar:**
   1. baixa `https://besave.com.br/img/ofertas/{id}.webp` e faz o quadrado 800×800 JPEG de fundo branco com o
      Pillow (JPEG: WebP pode virar figurinha). Sem foto da oferta (404, timeout, imagem inválida) → placeholder da área,
      `https://besave.com.br/img/placeholder/{DS_AREA_SLUG}.webp`, igual ao Telegram, com WARN. **Todo post leva
      imagem.** Se nem o placeholder baixar, a tentativa conta como falha antes do clique (linha volta a
      `P`), e o post não sai sem foto;
   2. abre o canal pelo nome (`CANAL_ENVIO.DS_CHAT_ID`), anexa a foto, cola a legenda (área de
      transferência ou digitação, o que o WhatsApp Web aceitar sem perder a marcação) e envia;
   3. confirma que um balão novo com o começo da legenda apareceu no canal, em até `timeout_post_segundos`
      (padrão 60).
5. **Estados, sem reenvio às cegas:**
   - grava `D` (`DS_MOTIVO 'enviando'`) **antes** de clicar em enviar;
   - confirmou → `E` com `DT_ENVIO`;
   - falhou antes do clique (canal não abriu, anexo falhou) → volta a `P` e conta uma falha;
   - não confirmou depois do clique → fica `D`. Linha `D` **nunca** é reenviada pelo programa; o dono decide.
6. **Limpeza:** depois de cada tentativa, `Escape` até fechar modais e a página volta ao canal. Exceção na
   página → recarrega uma vez; browser morto → sai com código ≠ 0, e o systemd reinicia (padrão da captura).
7. **Pausa e aviso** (bot de alertas, `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` do `.env`):
   - 3 falhas seguidas → pausa de 60 min e aviso, com lembrete a cada 6 h;
   - na volta, aviso "voltou";
   - linha `D` nova → aviso com o id ("conferir no canal se saiu");
   - sessão deslogada (QR na tela) → aviso "ler o QR pelo VNC", sem tentar postar.
8. **Config** `conf/config.json` (fora do git; `config.example.json` com `_obs`):
   - `habilitado` (lido a cada volta: `false` para sem reiniciar);
   - `intervalo_minutos`, `max_horas_fila`, `timeout_post_segundos`;
   - `oracle` e `id_canal` (padrão 2).

   Sem segredo no JSON além do que a captura já guarda; o arquivo é gravado em `600` (BSV-60).
9. **Batimento e vigia:**
   - o publicador grava `conf/batimento.json` só com progresso (volta concluída, mesmo sem post), no formato
     da BSV-57;
   - `tools/vps/vigia_robos.py` ganha o robô `publicador` e a escolha por máquina (`BESAVE_VIGIA_ROBOS`;
     padrão = `lojas,whatsapp`, o de hoje);
   - na inst2: `BESAVE_VIGIA_ROBOS=publicador`.
10. **Unidades** (`tools/vps/systemd/`): `besave-publicador-whatsapp.service` (scope como os robôs,
    `SuccessExitStatus=130`) e o timer do vigia na inst2. README com instalação, QR, pausa e o que fazer com
    linha `D`.

## Regras
1. Um post por vez, no ritmo do canal 2; nunca mais que `QT_MAX_DIA` no dia (Brasília).
2. Linha `D` nunca é reenviada automaticamente. Postar duas vezes é pior que deixar de postar uma.
3. Não lê nem responde mensagens, não entra em grupos, não mexe em contatos: o número só posta no canal.
4. Sem dependência Python nova (Playwright, Pillow e oracledb já estão nos robôs; lista própria em
   `requirements.txt`).
5. Nenhum número de telefone, link de convite, token, IP ou host no repositório nem na evidência (regra 11).
   Os prints do canal são redigidos e sem o número.
6. A captura (`capture-chat-groups`, inst1) não muda.

## Fora de escopo
- Avisos e "Oferta encerrada" no WhatsApp.
- Reenviar `D`.
- Mais de um canal do WhatsApp.
- Mover a captura de número.

## Critério de aceite
Lógica com fakes (Oracle, relógio, página); DOM com fixture HTML gravada do WhatsApp Web real e redigida.
O agente captura os seletores reais pelo VNC e documenta de onde vieram.
- **Ritmo:** teto 40, janela 8–22 → um dia simulado com voltas de 15 min dá ≤ 40 posts, nenhum fora da
  janela; 07:59 → 0. O mutante sem teto falha.
- **Escolha:** 3 linhas `P` → posta a mais recente. Oferta inativa → `X expirou`. Fila de 4 h → `X velha`.
  Pendente de ontem → `X outro_dia`.
- **Estados:** confirmado → `E`; falha antes do clique → `P` e falha contada; sem confirmação depois do
  clique → `D` e aviso. Na volta seguinte, `D` não é tentada (o fake da página conta 0 envios para aquele
  id). O mutante que reenvia `D` falha.
- **Pausa:** 3 falhas → pausa + 1 aviso; dentro da pausa, 0 tentativas; volta → "voltou".
- **Desligar:** `habilitado: false` → 0 tentativas na volta seguinte, sem reiniciar.
- **Foto:** saída 800×800 JPEG de fundo branco, proporção preservada; `404` da oferta → placeholder da área da linha; `404` também no
  placeholder → linha volta a `P`, sem post e sem `D`. O mutante que posta sem foto falha.
- **Vigia:** `BESAVE_VIGIA_ROBOS=publicador` → só o publicador vigiado; ausente → `lojas,whatsapp`, igual a
  hoje (os testes da BSV-57 continuam verdes).
- **Gates:** `cd tools && python -m pytest -q`; ruff do CI de `tools/`; `shellcheck tools/vps/*.sh`.
- **Real (dono, bloqueia o merge), na inst2 com a branch:**
  1. QR lido; um dia com `QT_MAX_DIA 40`: posts no canal iguais à legenda da fila (negrito, riscado, cupom
     em monoespaçado, link `utm_source=whatsapp`), foto quadrada sem virar figurinha, nenhum post repetido;
  2. derrubar a rede da inst2 durante um envio (lição 29): a linha fica `D`, chega o aviso e nada é reenviado;
  3. `habilitado: false` → para na volta seguinte;
  4. `free -m` e RSS do Chromium após 24 h;
  5. prints do canal, redigidos.

## Definition of done
PR para `develop` com o programa, unidades, vigia, README, testes, fixture redigida, prints olhados
antes da PR (lição 19), `validation.md` do Verifier independente (com sensor de discriminação) e as
decisões propostas: publicador independente da captura; `D` nunca reenvia; teto por número novo.
