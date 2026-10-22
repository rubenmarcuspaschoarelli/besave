# BSV-51 · Robô do WhatsApp: destravar sozinho quando uma janela cobre a tela, e avisar captura parada

**Papel:** Python · **Pasta:** `tools/capture-chat-groups/` (+ `tools/vps/README.md`) ·
**Depende de:** BSV-48 (no ar). AD-107, AD-108; lições 29 e 31

## Contexto
Em 22/10, na VPS, um aviso do próprio WhatsApp Web ("Confira suas ligações recentes ou inicie uma nova…",
um `span` dentro de `#wa-popovers-bucket`) ficou sobre a lista de conversas e **interceptou o clique** no
grupo. O `item.click()` de `wa/browser.py` (`abrir_grupo`) repete o clique até o tempo padrão do
Playwright, falha, e a volta seguinte tenta de novo: das 13:33 às 19:00 o robô girou sem capturar nada
(5h30; último ID 39044). A guarda de voltas cegas (`VOLTAS_CEGAS_RESGATE` em `wa/monitor.py`, criada para
um modal parecido em 03/08) só deixa o resgate pendente — e o resgate também clica, então também falha.
Ninguém foi avisado: o alerta de "nenhuma oferta nova" do worker é de 8 h (AD-108). Na mesma manhã já
tinha acontecido por ~9 min.

## Objetivo
Nenhuma janela por cima da tela trava a captura por mais que alguns minutos, e captura parada de dia
chega ao Telegram em menos de uma hora.

## Saídas
1. **Destravar sobreposição:** quando o clique em `abrir_grupo` (ou qualquer clique do rodízio e do
   catch-up) for interceptado por outro elemento, o robô, nesta ordem: tecla `Escape`; procura e clica no
   botão de fechar de avisos e diálogos conhecidos (`#wa-popovers-bucket`, `[role="dialog"]`, botões
   "Fechar"/"OK"/"Agora não"); tenta o clique de novo. O que fechou vai para o log (texto do aviso
   resumido).
2. **Clique com tempo máximo:** cliques do robô com tempo próprio curto (ordem de segundos, não o padrão
   do Playwright); falha vira erro tratado da volta, nunca um laço de horas no mesmo clique.
3. **Recarregar como último recurso:** se depois dos passos acima os grupos continuarem sem abrir por N
   voltas seguidas (configurável; padrão ~10 min de bloqueio), o robô recarrega o WhatsApp Web
   (`page.reload` e espera `#pane-side`), e o resgate (catch-up) roda depois do recarregamento — nada se
   perde, ele retoma pelo marcador de cada grupo.
4. **Aviso de captura parada:** se, **dentro do horário de captura normal (fora da janela noturna,
   AD-107)**, o robô passar mais de `alerta.sem_abrir_minutos` (padrão 45) sem abrir nenhum grupo, manda
   uma mensagem no Telegram (mesmo bot dos alertas; token e chat no `config.json`, fora do git, opcional:
   sem as chaves, só log) e uma de "voltou" quando destravar. No máximo uma mensagem por ocorrência, com
   lembrete a cada 2 h.
5. README da VPS: o que o robô faz sozinho, o que aparece no log e no Telegram, e quando ainda é preciso
   entrar na tela.

## Regras
1. Comportamento sem bloqueio idêntico ao de hoje (teste prova); no PC, igual.
2. O contador e os marcadores dos grupos nunca andam por causa do destravamento; o recarregamento passa
   pelo mesmo caminho de resgate que já existe (lacuna/catch-up).
3. O robô nunca clica em botões que mudem conta, grupo ou mensagem (sair do grupo, apagar, responder):
   lista fechada de textos e seletores de "fechar".
4. Sem dependência nova; segredo só no `config.json` (AD-017, regra 11).
5. Falha se prova com a falha real (lição 29): o teste real reproduz a sobreposição.

## Fora de escopo
Robô das lojas, OpenWA, mudar o rodízio ou a janela noturna, alertas do worker.

## Critério de aceite
- `pytest` com página simulada: clique interceptado → `Escape` resolve; não resolve → botão de fechar
  resolve; nada resolve → erro tratado dentro do tempo máximo (sem laço) e, depois de N voltas,
  recarregamento + resgate; aviso de captura parada dispara depois do limite fora da janela noturna, não
  dispara dentro dela, e "voltou" sai uma vez; sem chaves de Telegram, só log.
- Lista de botões permitidos conferida inteira (lição 14).
- **Real (dono), VPS:** com o robô rodando, abrir à mão um aviso/diálogo do WhatsApp Web por cima da lista
  (ou esperar o de ligações reaparecer) → o robô fecha e segue em até alguns minutos, com a linha no log;
  com a tela travada de propósito por mais de 45 min (ex.: diálogo que o robô não conhece), chega o aviso
  no Telegram e o "voltou" depois.

## Definition of done
PR com testes verdes no CI `tools`, README da VPS atualizado, `validation.md` do Verifier independente e o
teste real do dono antes do merge.
