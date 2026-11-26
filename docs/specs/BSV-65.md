# BSV-65 · Robô das lojas: navegador quebrado não queima linha, reabre e avisa

**Papel:** Python (stdlib + Playwright) · **Pasta:** `tools/capture-store-pages/` (+ `tools/vps/vigia_robos.py` e
`tools/tests/` só para a Saída 6) · **Depende de:** nada (BSV-55, 57 e 58 em `main`). AD-113, AD-115, AD-116;
lições 14, 29, 33

## Contexto
De **18/11 16:20 a 23/11 12:29** o Chromium do robô das lojas ficou quebrado e ninguém soube:
- 16:20–16:28 de 18/11: 19 linhas com `TimeoutError: Page.goto: Timeout 60000ms exceeded` (≈ 61 s cada);
- a partir de 16:28: `Error: Page.goto: Page crashed` em **toda** navegação, em 0 s. O processo Python seguiu
  vivo, a aba do Playwright morta;
- **3.697 linhas** de Amazon, Mercado Livre, Beleza na Web, Época e Natura foram para `ST_CAPTURA='9'`
  (756 com oferta de até 24 h no fim do incidente). Só a Shopee, pela API (AD-117), gravou: 201 ofertas em 5 dias;
- o dono achou olhando o VNC em 23/11. Reiniciar a unidade resolveu.

**Repetiu em 24/11**, 20 h depois do reinício: `TimeoutError` de 08:24 a 08:31, `Page crashed` em toda navegação a
partir de 08:32, **794 linhas** em `'9'` até o reinício das 17:34. Nos dois incidentes o journal do kernel não tem
OOM e a instância tinha ~4,3 GB disponíveis: não é falta de memória da máquina. A causa não se sabe; por isso
esta spec também coleta o diagnóstico (Saída 8) e relança o navegador de forma preventiva (Saída 9).

Por que nada avisou (código em `main`):
1. `_processar_lote` (`main.py`) trata qualquer exceção do `goto` como erro da **linha**: `_status_erro` →
   `db.marcar_erro` → `'9'`. Não existe "erro do navegador".
2. `core/batimento.py` já conhece navegador fechado (`SINAIS_NAVEGADOR_FECHADO`: `has been closed`,
   `target closed`, `target page, context or browser`), mas **não** `Page crashed`. E mesmo para "fechado",
   `bater('varredura')` a cada 3 min renova o batimento: o vigia (AD-115) nunca vê o robô parado.
3. `_monitorar` só abre aba nova quando `page.is_closed()`; aba **crashada** não está fechada.
4. O alerta de "nenhuma oferta nova" (AD-108) via as ofertas da Shopee.

A pausa por loja da BSV-55 (captcha, login, sessão de afiliado) funcionou no mesmo período (Mercado Livre em
pausa 720 min em 17/11, com aviso e "voltou"): o caso aqui é outro, o navegador inteiro.

## Saídas
1. **Classificar "navegador quebrado"** numa função só (em `core/`), usada pelo lote e pelo batimento:
   exceção do Playwright cuja mensagem (minúsculas) contém `page crashed`, `target crashed` ou um dos
   sinais que já existem em `SINAIS_NAVEGADOR_FECHADO`. `batimento.navegador_fechado` passa a usar essa função
   (linha com navegador quebrado continua sem renovar o batimento).
2. **Linha não queima:** exceção de navegador quebrado em qualquer fase da captura por navegador (`goto`,
   `prepare`, `capture`, imagens, link de afiliado) deixa a linha em `'0'` (`oracle=retida(0)`, trava o
   ponteiro como `STATUS_RETER`), nunca `'9'`, sem gravar `DS_CAPTURA`. O lote **para** ali: as linhas
   seguintes da varredura não são tentadas nessa aba.
3. **Recuperar o navegador**, nesta ordem, antes da próxima linha:
   a. fechar a aba quebrada e abrir outra no mesmo contexto (`_nova_page`);
   b. se a primeira navegação da aba nova também der navegador quebrado, ou se abrir a aba falhar: fechar o
      contexto (`_fechar_contexto`) e relançar `launch_persistent` com o mesmo perfil, refazendo o
      `link_afiliado.preparar_contexto` como no arranque;
   c. se o relançamento falhar, ou se houver **3 relançamentos em 60 min**: sair com **código 3** (novo,
      documentado no README; 0/1/2 já existem), sem gravar batimento depois da decisão. O vigia reinicia pela
      regra que já existe (prazo do batimento).
   Nenhuma pergunta no terminal (`--sem-perguntas`, AD-113).
4. **Timeouts seguidos:** `TimeoutError` de navegação em loja por navegador deixa a linha em `'0'` (retida) e
   conta numa sequência; **3 seguidos** (qualquer loja por navegador, sem uma linha `ok` no meio) disparam a
   recuperação da Saída 3. Linha que acumular **3 timeouts próprios** (contados na execução do robô) vai para
   `'9'` com o motivo de hoje: um link morto não pode travar o ponteiro para sempre. Uma linha `ok` zera a
   sequência.
5. **Aviso no Telegram**, pelo mesmo caminho dos avisos da BSV-55 (bloco `alerta` do `config.json`), uma
   mensagem por ocorrência:
   - `Robo das lojas: navegador quebrou (<sinal>: Page crashed | 3 timeouts seguidos); <aba nova | navegador relancado>. N linha(s) retida(s).`
   - `Robo das lojas: navegador nao reabriu; saindo (codigo 3) para o vigia reiniciar.`
   - `Robo das lojas: navegador voltou (N linha(s) retida(s) voltam a ser processadas).` na primeira linha `ok`
     de loja por navegador depois da ocorrência.
   Sem URL de afiliado, credencial ou caminho de usuário na mensagem (regra 11).
6. **Vigia vê captura por navegador** (defesa por fora, lição 33): o batimento ganha dois campos opcionais,
   `ultimo_ok_navegador` (ISO UTC da última linha `ok` de loja por navegador) e `tentativas_navegador`
   (linhas de loja por navegador concluídas sem `ok` desde então; `loja_pausada` não conta). O vigia avisa
   (sem reiniciar) quando `tentativas_navegador ≥ 10` **e** `ultimo_ok_navegador` tem mais de 60 min; repete a
   cada 2 h como os outros avisos e manda "voltou" quando o campo volta a andar. Batimento sem os campos
   (versão antiga) = sem essa conferência. A Shopee pela API não conta como navegador.
7. **README do robô:** "Navegador quebrado" (sinais, o que acontece com a linha, código 3, mensagens), o
   relançamento preventivo (Saída 9) e o SQL de reprocessar por motivo, com o filtro por idade da oferta
   (`DT_OFERTA >= SYSDATE - 1`).
8. **Diagnóstico da causa:** em cada ocorrência (Saída 3) e no evento `crash` da `page` do Playwright, uma linha
   de log `[navegador] diagnostico:` com: `MemAvailable` de `/proc/meminfo`; quantidade e soma do RSS dos
   processos Chromium filhos do robô (lidos de `/proc`, sem `ps` nem root); RSS do maior deles; tempo desde o
   último lançamento do navegador; navegações desde então. Leitura que falhar vira `?`, nunca exceção. Fora do
   Linux, só os campos que existirem. Nada disso vai ao Telegram.
9. **Relançamento preventivo:** a cada `monitor.relancar_navegador_horas` (chave **opcional** no `config.json`,
   padrão `6`; `0` desliga; inválida = padrão com WARN), **entre lotes** (nunca no meio de uma linha), o robô
   fecha o contexto e relança o navegador pelo mesmo caminho da Saída 3b, com o log de diagnóstico antes de
   fechar. Não conta para os "3 relançamentos em 60 min" e não manda Telegram quando dá certo; se falhar, segue a
   Saída 3c (código 3 e mensagem de "não reabriu"). Na janela noturna, só na rodada.

## Regras
1. Nenhuma linha vai para `'9'` por causa do navegador (Saídas 2 e 4); `'9'` continua para o que é da oferta.
2. A classificação é uma função só (Saída 1); nada de `in str(e)` espalhado.
3. Teste de mensagem compara a mensagem inteira (lição 14).
4. Sem dependência nova. Sem mudança de banco, de unidade systemd ou de chave obrigatória no `config.json`
   (a da Saída 9 é opcional e entra no `config.example.json`).
5. O log continua sem URL de afiliado nem `stderr` de proxy (AD-116).

## Fora de escopo
- Reprocessar as linhas do incidente (SQL do dono, feito à parte).
- Corrigir a causa do crash (versão do Chromium, flags, teto de memória no scope): ticket próprio, com os dados
  da Saída 8. Reinício da unidade por timer (como o do WhatsApp, AD-113): só se o relançamento preventivo não
  bastar.
- Robô do WhatsApp, publicador, Shopee pela API.

## Critério de aceite
- Testes (sem navegador real; `page`/`context` simulados), derivados das Saídas:
  - `Page crashed` no `goto`, no `capture` e no link de afiliado → linha `'0'`, `marcar_erro` não chamado,
    ponteiro travado, lote parado, aba nova aberta; mutante que tira `page crashed` da classificação morre;
  - aba nova também quebrada → contexto fechado e relançado com o mesmo perfil; relançamento falhando → saída
    com código 3 e nenhum batimento gravado depois;
  - 3 relançamentos em 60 min → código 3; 2 → segue;
  - 2 timeouts seguidos → só retidas; 3 → recuperação; `ok` no meio zera; a mesma linha com 3 timeouts → `'9'`;
  - mensagens da Saída 5 comparadas inteiras; uma por ocorrência; "voltou" só depois de `ok` por navegador
    (`ok` da Shopee não fecha);
  - batimento: linha com navegador quebrado não renova; campos da Saída 6 atualizados (Shopee não mexe);
  - vigia: `tentativas 10` + 61 min → aviso; `tentativas 9` ou 59 min → nada; batimento sem os campos → nada;
    sem reinício por essa regra;
  - diagnóstico: `/proc` simulado → linha de log com os campos da Saída 8 comparada inteira; arquivo ilegível →
    `?` sem exceção; evento `crash` da `page` → linha de diagnóstico;
  - preventivo: relógio simulado → relança depois de 6 h e só entre lotes (lote em andamento espera); `0` não
    relança; chave inválida → 6 h com WARN; o preventivo não conta para os 3 em 60 min; falha → código 3.
- `python -m unittest discover` dos dois pacotes e o `ruff` do job `tools` verdes; os testes de `tools/tests/`
  do vigia rodam no WSL (lição 32).
- **Real (dono, inst1, branch da PR; bloqueia o merge):**
  1. robô no ar com a branch; com uma linha de Amazon ou ML na fila, `kill -9` no processo **renderer** da aba
     do Playwright (`ps` no scope `besave-lojas-robo`) → log com navegador quebrado, linha retida, aba nova,
     Telegram, a mesma linha `ok` em seguida;
  2. `kill -9` no processo principal do Chromium do scope → relançado, Telegram, captura segue;
  3. `kill -STOP` no Chromium principal → 3 timeouts → recuperação (o `STOP` não deixa fechar: espera-se o
     código 3 e o reinício pelo vigia em até ~10 min; `kill -CONT` se não sair);
  4. nenhuma linha nova em `'9'` com `Page crashed`/`closed` durante o teste (consulta de leitura);
  5. `batimento.json` com os dois campos novos andando;
  6. com `relancar_navegador_horas` em `0.1` (6 min, só no teste), o log mostra o relançamento preventivo com a
     linha de diagnóstico e a captura seguinte `ok`; depois volta ao padrão.

## Definition of done
PR para `develop` com código, testes, README, `validation.md` do Verifier independente (sensor de
discriminação) e evidência redigida.
