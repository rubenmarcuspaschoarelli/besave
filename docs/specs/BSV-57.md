# BSV-57 · VPS: vigia externo dos robôs (batimento, reinício e Telegram)

**Papel:** Python (stdlib) + systemd · **Pasta:** `tools/vps/` (+ uma função de batimento em
`tools/capture-chat-groups/` e `tools/capture-store-pages/`, só a escrita do arquivo) ·
**Depende de:** BSV-54, **BSV-55** (sem ela, reiniciar o robô das lojas o deixa parado na pergunta da Shopee),
BSV-56 (sem ela, reiniciar o WhatsApp depois de uma parada brusca esbarra no contador). AD-107, AD-108

## Contexto
Em 02–05/11 o site ficou 3 dias sem oferta nova. O Telegram avisou ("nenhuma oferta nova há 32/56/80 h",
o alerta do worker por `DT_OFERTA`, AD-108), mas:
- **tarde:** o limiar é de 8 h;
- **sem dizer a causa:** nem qual robô, nem por quê. O robô das lojas estava `active (running)` no
  systemd, parado num `input()`;
- **sem tentar nada:** nenhum reinício automático.

O aviso do próprio robô do WhatsApp (BSV-51) roda **dentro** do processo: se o processo trava ou morre, ele
cai junto. E o robô das lojas não tem aviso nenhum.

Pedido do dono (05/11): um serviço que vigie os robôs e, se um ficar parado mais de **10 minutos**, fora
da madrugada, **tente reiniciar e avise no Telegram**.

## Saídas
1. **Batimento:** cada robô grava `batimento.json` na sua pasta de estado (`conf/` de cada robô; fora do
   git), por escrita atômica (arquivo temporário + `rename`):
   ```json
   {"robo":"lojas","pid":833317,"em":"2026-11-05T12:00:00Z","prazo":"2026-11-05T12:10:00Z","fase":"varredura"}
   ```
   - **WhatsApp:** a cada volta do rodízio.
   - **Lojas:** a cada linha processada e a cada varredura, inclusive com a fila vazia.
   - **Prazo:** `em` + 10 min. Antes de dormir (janela noturna, fila vazia), o robô grava
     `prazo` = hora de acordar + 10 min. É assim que a madrugada fica fora sem o vigia precisar ler a
     janela de cada robô.
   - **`fase`** é livre e curta (para a mensagem).
2. **Vigia:** `tools/vps/vigia_robos.py`, só stdlib, rodado por `besave-vigia-robos.timer` a cada 5 min
   (unidade `--user` do `besave`). Para cada robô, nesta ordem:
   1. Unidade parada de propósito (`inactive` sem falha) → nada a fazer.
   2. `prazo` vencido ou `pid` diferente do processo vivo → **parado**.
   3. Últimas linhas do log com pedido de QR, `ABORTADO:` ou pergunta (`[S = `) → **precisa de
      operador**: avisa, e **não** reinicia (reiniciar não resolve).
   4. Senão, `systemctl --user restart <unidade>` e aviso. **No máximo 2 reinícios por robô em 60 min.**
      Depois disso, só "precisa de operador" até o batimento voltar.
   5. Batimento voltou depois de um aviso → "voltou (parado por N min)".
3. **Mensagem** (Telegram, mesmo bot dos alertas do worker): robô, motivo (sem batimento há N min / QR /
   pergunta / `ABORTADO`), ação (reiniciado k/2 ou nada), última linha útil do log (cortada, sem URL de
   afiliado, sem token) e RSS do maior processo `chrome` do perfil daquele robô.
   - **Credencial:** token e chat vêm de `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` do `/srv/besave/worker.env`
     (o arquivo já existe, é `600` do `besave`). Nenhum segredo novo.
   - **Sem repetição:** 1 mensagem por ocorrência e lembrete a cada 2 h.
   - **Estado do vigia:** em `~/.local/state/besave/vigia_robos.json` (contagem de reinícios, ocorrência
     aberta).
4. `tools/vps/README.md`: como funciona, como silenciar um robô (parar a unidade) e como desligar o vigia.

## Regras
1. O vigia só age pela unidade (`systemctl --user`). Nunca `kill` por nome de processo.
2. Robô parado de propósito pelo operador nunca é religado.
3. Falha do vigia (log ilegível, Telegram fora) não derruba nada: registra no journal e segue. Sem
   Telegram, só journal.
4. O batimento não pode atrasar a captura: escrita pequena, falha de escrita só loga.
5. Sem dependência nova. Nenhum token, chat ou URL de afiliado em log, mensagem ou teste.

## Fora de escopo
- Máquina inteira fora do ar: o vigia local cai junto. O vigia da AWS (BSV-15) já avisa se o site parar.
  "Captura parada" vista de fora é ticket próprio, se preciso.
- Mudar o alerta de 8 h do worker (AD-108).
- Resolver o QR do WhatsApp (código de pareamento por Telegram: ticket próprio).

## Critério de aceite
Testes com relógio, `systemctl`, log, batimento e Telegram falsos. Nenhum espelha a implementação.

- **Parado:** prazo vencido há 11 min → 1 reinício e 1 aviso. Prazo vencido há 9 min → nada (fronteira).
- **Madrugada:** batimento com `prazo` = acordar + 10 min, relógio antes do prazo → nada, mesmo com `em`
  de horas atrás.
- **PID trocado** (processo novo sem batimento ainda, dentro de 10 min da partida) → nada. O mesmo PID
  velho com unidade nova → parado.
- **Precisa de operador:** log com pergunta da Shopee, com QR ou com `ABORTADO: contador atrasado` → aviso
  sem reinício.
- **Limite:** 3ª parada em 60 min → sem reinício, mensagem de operador. Depois de 60 min, volta a poder
  reiniciar.
- **Voltou:** batimento novo depois de ocorrência aberta → 1 mensagem "voltou" com a duração. Sem
  ocorrência aberta → nada.
- **Parado de propósito** (`inactive`, sem falha) → nada.
- **Mensagens:** sem token → só log; com token → texto com robô, motivo e ação; token ausente de toda
  saída capturada; URL `https://` da linha de log removida.
- **Robôs:** escrita atômica do batimento (arquivo nunca lido pela metade) e prazo de sono, em cada robô.
- **Gates:** `python -m unittest` dos três diretórios, ruff do CI de `tools/`, `shellcheck`,
  `systemd-analyze --user verify tools/vps/systemd/*`.
- **Real (dono, bloqueia o merge):** na inst1 com a branch:
  1. `kill -STOP` no python do robô das lojas (congela sem matar) → em ≤ 15 min, reinício e Telegram;
  2. `systemctl --user stop` → nenhum aviso;
  3. madrugada sem aviso falso (conferir o journal do vigia às 08:00).

## Definition of done
PR para `develop` com vigia, unidades, batimento nos dois robôs, README, testes, `validation.md` do Verifier
independente (com sensor de discriminação), evidência da execução real redigida (regra 11) e as decisões
propostas (10 min, 2 reinícios por hora, lembrete de 2 h, credencial do `worker.env`) para o
`docs/DECISOES.md`.
