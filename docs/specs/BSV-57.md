# BSV-57 · VPS: vigia externo dos robôs (batimento, reinício e Telegram)

**Papel:** Python (stdlib) + systemd · **Pasta:** `tools/vps/` (+ uma função de batimento em
`tools/capture-chat-groups/` e `tools/capture-store-pages/`, só a escrita do arquivo e, no WhatsApp, a
conta de grupos falhando) ·
**Depende de:** BSV-54, **BSV-55** (sem ela, reiniciar o robô das lojas o deixa parado na pergunta da Shopee),
BSV-56 (sem ela, reiniciar o WhatsApp depois de uma parada brusca esbarra no contador), **todas mergeadas em
`develop` antes de abrir o worktree**. AD-107, AD-108; lições 11, 14, 16, 29

**Revisão 06/11 (o que a execução real da BSV-54 e da BSV-55 mudou):**
- O processo do robô **não fica no cgroup da unidade**: o tmux do Ubuntu 24.04 põe cada painel em
  `app.slice/tmux-spawn-*.scope`. A BSV-54 levou o WhatsApp para o scope `besave-whatsapp-robo.scope`
  (`systemd-run --scope --collect`, com teto de memória e `ExecStop` que para o scope). O robô das lojas
  **ainda não**: o `KillSignal=SIGINT` da unidade não chega ao python, e um python congelado (`kill -STOP`)
  sobrevive ao `restart` e segura o perfil do Chromium. Por isso esta spec leva as lojas ao mesmo desenho
  (Saída 0).
- O log do WhatsApp agora é um por partida (`log/run_captura_DD_MM_HHMMSS.log`, sem limite) e o das lojas é
  um só, `destino/log/main_monitorar.log`, aberto em `tee -a`. Nenhum dos dois tem rotação (Saída 5).
- Com `--sem-perguntas` (BSV-55) o robô das lojas não pergunta mais nada; loja em pausa é estado normal,
  avisado pelo próprio robô. A BSV-56 tira a frase "Retomando contador" e o `ABORTADO: contador atrasado`.

**Revisão 10/11 (incidentes de 06–09/11 e virada da BSV-56):**
- **Vivo e quebrado:** em 07/11 ~21:00 o renderer do Chromium do WhatsApp morreu (3,56 GB) e o python seguiu
  8,5 h dando a volta do rodízio só com erro (`#side`), sem capturar nada. Um batimento gravado "a cada volta"
  continuaria em dia e o vigia não veria nada. O batimento passa a exigir **progresso**, não só volta (Saída 1).
- **Um grupo morto com o robô vivo:** de 06/11 08:12 a 09/11 o grupo `@achadinhoscomcarol` (renomeado no
  WhatsApp) falhou em **todas** as voltas, ~25% do volume, sem ninguém notar. Os outros dois grupos
  capturavam. Reiniciar não resolve: é aviso de operador por grupo (Saída 2, passo 4b).
- **Laço de partidas:** em 08/11 o reinício das 05:30 caiu no QR e a unidade relançou o robô 84 vezes
  (05:30→13:02), um log por partida. O passo 4 já pega o QR no log mais recente; agora também conta
  partidas sem `Grupo aberto`, com ou sem a palavra QR (Saída 2, passo 4c).
- A BSV-56 está em `develop`: sem contador no arquivo, partida sem conferência; "banco fora" é estado do robô
  (avisa e espera, aviso próprio no Telegram) e **não** é robô parado.
- O alerta de "nenhuma oferta nova há 8 h" que chega de madrugada (o WhatsApp não captura das 23h às 07h)
  é do worker (AD-108) e continua fora desta spec (ticket próprio em `apps/worker`).

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
0. **Robô das lojas no próprio scope**, igual à BSV-54: o python roda por `systemd-run --user --scope
   --collect --unit=besave-lojas-robo -p KillSignal=SIGINT -p TimeoutStopSec=30` dentro do painel do tmux.
   Reaproveitar a lógica do `iniciar_captura.sh` (extrair um trecho comum), sem duplicar. Na partida, com o
   scope inativo, `reset-failed` e `revert`; scope ativo na partida → recusa subir (não duplica o robô).
   `besave-captura-lojas.service` ganha `ExecStop=-/usr/bin/systemctl --user stop besave-lojas-robo.scope` e
   `TimeoutStopSec=45`. Sem teto de memória por ora (o Chromium das lojas não cresce; reavaliar com medição).
   O stop do scope manda SIGINT e, vencido o prazo, SIGKILL, que também mata processo parado por `SIGSTOP`.
1. **Batimento:** cada robô grava `batimento.json` na sua pasta de estado (`conf/` de cada robô; fora do
   git), por escrita atômica (arquivo temporário + `rename`):
   ```json
   {"robo":"lojas","pid":833317,"em":"2026-11-05T12:00:00Z","prazo":"2026-11-05T12:10:00Z","fase":"varredura"}
   ```
   - **WhatsApp:** a cada volta do rodízio **em que ao menos um grupo abriu** (`Grupo aberto`). Volta em que
     todos os grupos falharam não renova o prazo (caso de 07/11). Banco fora (BSV-56) renova: o robô está
     esperando de propósito e já avisa sozinho.
   - **WhatsApp, por grupo:** o batimento leva `"grupos_falhando": {"<nome>": "<desde, ISO UTC>"}`, com o
     grupo que falhou em todas as voltas desde aquele instante; sai do mapa na primeira volta em que abrir.
   - **Lojas:** a cada linha concluída (ok, retida, pausada, rejeitada) e a cada varredura, inclusive com a
     fila vazia **e com lojas em pausa** (BSV-55): loja pausada não é robô parado. Exceção do navegador
     (página ou contexto fechado) não renova.
   - **Prazo:** `em` + 10 min. Antes de dormir (janela noturna, fila vazia), o robô grava
     `prazo` = hora de acordar + 10 min. É assim que a madrugada fica fora sem o vigia precisar ler a
     janela de cada robô.
   - **`fase`** é livre e curta (para a mensagem).
2. **Vigia:** `tools/vps/vigia_robos.py`, só stdlib, rodado por `besave-vigia-robos.timer` a cada 5 min
   (unidade `--user` do `besave`). Para cada robô, nesta ordem:
   1. Unidade parada de propósito (`inactive` sem falha) → nada a fazer.
   2. Reinício diário em andamento (`besave-reinicio-whatsapp.service` `activating`/`active`) → nada para o
      WhatsApp; esse script já confere a partida e avisa sozinho (BSV-54).
   3. `prazo` vencido ou `pid` fora do scope do robô (`besave-whatsapp-robo.scope` /
      `besave-lojas-robo.scope`, pids lidos de `systemctl --user show -p ControlGroup` + `cgroup.procs`;
      **não** o `MainPID` da unidade, que é o tmux) → **parado**.
   4. Últimas linhas do log com pedido de QR ou `ABORTADO:` → **precisa de operador**: avisa, e **não**
      reinicia (reiniciar não resolve). O log lido é o **mais recente** do robô (WhatsApp: maior mtime em
      `log/run_captura_*.log`; lojas: `destino/log/main_monitorar.log`), só o fim do arquivo.
      - **4b. Grupo morto:** grupo em `grupos_falhando` há mais de `BESAVE_GRUPO_FALHA_HORAS` (padrão 2) → aviso de operador **por grupo** ("grupo X falha em todas as voltas desde …;
        nome mudou ou o número saiu?"), sem reinício. O robô segue sendo vigiado normalmente.
      - **4c. Laço de partidas:** 3 ou mais logs `run_captura_*.log` criados nos últimos 30 min sem
        `Grupo aberto` em nenhum deles → precisa de operador, mesmo sem a palavra QR. Conta pelos arquivos,
        não pelo journal.
   5. Senão, `systemctl --user restart <unidade>` e aviso. **No máximo 2 reinícios por robô em 60 min.**
      Depois disso, só "precisa de operador" até o batimento voltar.
   6. Batimento voltou depois de um aviso → "voltou (parado por N min)".
3. **Mensagem** (Telegram, mesmo bot dos alertas do worker): robô, motivo (sem batimento há N min / QR /
   pergunta / `ABORTADO`), ação (reiniciado k/2 ou nada), última linha útil do log (cortada, sem URL de
   afiliado, sem token), `MemoryCurrent` do scope do robô e RSS do maior processo `chrome` dele (lido dos
   pids do scope, não por padrão de nome).
   - **Credencial:** token e chat vêm de `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` do `/srv/besave/worker.env`
     (o arquivo já existe, é `600` do `besave`). Nenhum segredo novo.
   - **Sem repetição:** 1 mensagem por ocorrência e lembrete a cada 2 h.
   - **Estado do vigia:** em `~/.local/state/besave/vigia_robos.json` (contagem de reinícios, ocorrência
     aberta).
4. `tools/vps/README.md`: como funciona, como silenciar um robô (parar a unidade) e como desligar o vigia.
5. **Rotação de logs** (achado da BSV-54: falha persistente gera 2–3 mil logs/dia), rodada pelo vigia uma vez
   por dia (marca no estado do vigia):
   - WhatsApp: apaga `log/run_captura_*.log` com mais de `BESAVE_LOG_DIAS` dias (padrão 14), nunca o mais
     recente.
   - Lojas: `main_monitorar.log` acima de `BESAVE_LOG_MB` (padrão 50) é copiado para
     `main_monitorar_AAAAMMDD.log` e truncado no lugar (o `tee -a` continua escrevendo; não renomear). Cópias
     com mais de `BESAVE_LOG_DIAS` dias são apagadas.
   - Só esses padrões de nome, só nessas duas pastas. Nada fora delas.

## Regras
1. O vigia só age pela unidade (`systemctl --user restart <unidade>`; o `ExecStop` leva o scope junto).
   Nunca `kill` por nome de processo.
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

- **Parado:** `em` há 11 min (prazo vencido há 1 min) → 1 reinício e 1 aviso. `em` há 9 min (prazo ainda não vencido) → nada (fronteira).
- **Madrugada:** batimento com `prazo` = acordar + 10 min, relógio antes do prazo → nada, mesmo com `em`
  de horas atrás.
- **PID trocado** (processo novo sem batimento ainda, dentro de 10 min da partida) → nada. O mesmo PID
  velho com unidade nova → parado.
- **Precisa de operador:** log com QR ou com `ABORTADO:` → aviso sem reinício. QR só em log anterior ao mais
  recente → não conta.
- **Vivo e quebrado:** robô do WhatsApp dando voltas com todos os grupos falhando por 11 min → o prazo vence
  e é **parado** (1 reinício + aviso). Uma volta com 1 grupo aberto renova. Mutante que renova em toda volta
  falha.
- **Grupo morto:** grupo em `grupos_falhando` há 2 h 01 min, de dia → 1 aviso de operador com o nome, sem
  reinício; há 1 h 59 min → nada. Lembrete só depois de 2 h; grupo saiu do
  mapa → "voltou" do grupo.
- **Laço de partidas:** 3 logs novos em 30 min sem `Grupo aberto` e sem QR → operador, sem reinício; 2 logs →
  nada; 3 logs com `Grupo aberto` no último → nada.
- **Banco fora:** batimento renovado com fase de banco fora → nada do vigia (o robô avisa sozinho).
- **Reinício diário:** `besave-reinicio-whatsapp.service` ativo e prazo vencido → nada.
- **Pausa de loja:** log com `oracle=pausada(0)` e batimento em dia → nada.
- **Scope:** pid do batimento fora do `cgroup.procs` do scope → parado; dentro → vivo. Cgroup falso com pids
  distintos para a unidade (tmux) e o scope (lição 11).
- **Limite:** 3ª parada em 60 min → sem reinício, mensagem de operador. Depois de 60 min, volta a poder
  reiniciar.
- **Voltou:** batimento novo depois de ocorrência aberta → 1 mensagem "voltou" com a duração. Sem
  ocorrência aberta → nada.
- **Parado de propósito** (`inactive`, sem falha) → nada.
- **Mensagens:** sem token → só log; com token → texto com robô, motivo e ação; token ausente de toda
  saída capturada; URL `https://` da linha de log removida.
- **Robôs:** escrita atômica do batimento (arquivo nunca lido pela metade) e prazo de sono, em cada robô.
- **Scope das lojas:** comando montado comparado inteiro (lição 14), com `--collect` e
  `--unit=besave-lojas-robo`; ordem is-active → reset-failed → revert → tmux; scope ativo → recusa.
- **Rotação:** log de 15 dias apagado, de 13 mantido, o mais recente nunca; `main_monitorar.log` de 51 MB
  copiado e truncado (mesmo inode), de 49 MB intocado; arquivo de outro nome na pasta intocado.
- **Gates:** `python -m unittest` dos três diretórios, ruff do CI de `tools/`, `shellcheck`,
  `systemd-analyze --user verify tools/vps/systemd/*`.
- **Real (dono, bloqueia o merge):** na inst1 com a branch:
  1. `kill -STOP` no python do robô das lojas (congela sem matar) → em ≤ 15 min, reinício e Telegram; o
     python congelado **some** (só o novo aparece no scope) e o robô volta a capturar;
  2. o mesmo no WhatsApp (`kill -STOP` no `run_captura.py`) → reinício e Telegram;
  3. `systemctl --user stop` de cada unidade → nenhum aviso e nenhum religamento;
  4. madrugada sem aviso falso e os reinícios das 23:30 e 05:30 sem aviso do vigia (journal do vigia às 08:00);
  4b. grupo morto: no `config.json` do WhatsApp (robô parado, com backup), trocar o nome de um grupo por um
     inexistente, subir; em ~2 h, 1 aviso com o nome do grupo e nenhum reinício; desfazer (backup) e ver o
     "voltou" do grupo;
  5. rotação: contagem de logs apagados no journal do vigia no 1º dia.

## Definition of done
PR para `develop` com vigia, unidades, batimento nos dois robôs, README, testes, `validation.md` do Verifier
independente (com sensor de discriminação), evidência da execução real redigida (regra 11) e as decisões
propostas (10 min, 2 reinícios por hora, lembrete de 2 h, credencial do `worker.env`, scope das lojas sem
teto, rotação 14 dias/50 MB, batimento só com progresso, grupo morto em 2 h, laço = 3 partidas em 30 min)
para o
`docs/DECISOES.md`.
