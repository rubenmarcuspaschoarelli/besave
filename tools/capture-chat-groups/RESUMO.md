# Resumo do projeto — Agente de Captura WhatsApp

_Última atualização: 22/09/2026_

## ONDE PARAMOS (22/09/2026, ~10h) — 7 semanas de operação sem sessão; **captura NO AR**

**TEM RUN VIVO.** Lançado hoje 09:38 (`run_captura_22_09.log`, CSV `captura/22_09_2026_09_38.csv`),
`.err` vazio, **0 erro em todo o log**. Retomou em `ultimo_id_processado=29725`, catch-up
inicial 20 (Ly) + 8 (#03) + 11 (carol), Oracle conectado (thick) e gravando.

⚠️ **Não lançar um 2º run** — mata o primeiro (armadilha de 03/08 21:26). Para parar:
`.\encerrar_captura.ps1`. Para subir: `.\iniciar_captura.ps1` (ele já confere run vivo,
perfil travado e contador atrasado — quem lança é o usuário).

⚠️ **Enquanto o run está vivo, NÃO editar `conf/config.json`** — o processo reescreve o
arquivo inteiro a cada leitura (contador + marcadores); uma edição manual é sobrescrita, e no
pior caso leva o contador junto. Mexer no config só com a captura parada.

### O intervalo 04/08 → 22/09 — operação pura, sem desenvolvimento

O código está **congelado desde 04/08** (`wa/monitor.py` 04/08 00:48, `run_captura.py`
04/08 00:36, os dois `.ps1` 04/08 09:24). Nenhuma sessão de trabalho foi registrada no período:
o usuário lançou a captura à mão dia a dia. O que os dados mostram:

- **24.285 ofertas** capturadas em 50 dias (agosto 16.823, setembro 8.686), em 45 dias com dado.
- **5 dias zerados:** 15/08, 22/08, 05/09, 13/09, 19/09 (máquina desligada / captura não lançada).
- Cobertura média: **13,3 h/dia em agosto, ~11 h/dia em setembro** — a captura não roda de
  madrugada porque a máquina não fica ligada. A diferença de volume mês a mês é isso, não
  perda: nenhum dia ficou fraco (< 60 ofertas) quando a captura esteve no ar.
- Por grupo: #03 11.461, Ly 7.248, carol 5.576. Por tipo: PRODUTO 23.696, CUPOM 589.
- **0 erro de Oracle em todos os logs de setembro** — nenhum `SP retornou FALSE`, nenhum
  `Erro ao inserir`. CSV e banco batem linha a linha (8.672 x 8.673 em setembro; a diferença é
  a linha que entrou enquanto eu contava).

### ✅ As duas guardas de 03-04/08 rodaram em produção — e funcionaram

A guarda de **voltas cegas** disparou **14 vezes** entre 04/08 e 21/09, sempre seguida de
recuperação. O `_relatar_bloqueio` fez o que foi escrito para fazer: **identificou os modais
reais**, que não eram os que eu tinha chutado:

| O que bloqueou | Dias |
|---|---|
| `Câmera não encontrada` ("não é possível fazer ligações…") | 04/08, 12/08 |
| `Ocorreu um erro ao executar o WhatsApp. Carregue o aplicativo novamente` + botão **Recarregar** | 17/08, 18/08 (2x), 21/08 |
| Visualizador de **Mídia / Documentos / Links** | 18/08 |
| Sem modal, `#pane-side` **ausente** (WhatsApp recarregando) | 08/08, 16/09 |
| Sem modal, `#pane-side` presente (clique travado) | 20/08, 20/09 (2x) |

**Consequência prática:** os dois primeiros casos são **fecháveis** (têm botão OK/Recarregar) e
hoje só são observados. Fechar o modal automaticamente é a evolução natural da guarda — mas
exige cuidado: `Recarregar` recarrega a página inteira e derruba o estado da viewport.
Nada disso custou dia zerado até agora, então **não é urgente**.

A guarda de **browser morto** (saída 3) **nunca precisou disparar** — não houve repetição do
episódio de 03/08 21:26 (a `iniciar_captura.ps1` cortou a causa na raiz).

### 🔍 Auditoria dos campos — o que está e o que **não** está sendo gravado

Conferido no Oracle (`OFERTA_FILA_CAPTURA`) contra os CSVs, setembro inteiro (8.672 linhas):

| Campo | Preenchido | Leitura |
|---|---|---|
| `DS_OFERTA`, `DS_URL_ORIGEM`, `DT_*` | 99,7-100% | ok |
| `DS_IMAGEM_OFERTA` | 96,9% | ok (3% são mensagens sem foto) |
| `VL_PRECO_POR` | 94,7% | ok |
| `VL_PRECO_DE` | 84,1% | **a maioria é real**: muita promo só publica o preço final |
| `DS_OFERTA_AVISO` | 69,4% | ok |
| `DS_CUPOM` / `DS_CUPOM_LOJA` | 31,5% / 32,3% | só existe quando a mensagem traz cupom |
| `DS_DESCRICAO_PAGAMENTO` | 15,1% | ok ("via Pix", "à vista"…) |
| `DS_CUPOM_COMENTARIO` | 0,8% | raro por natureza |

**Os 3 buracos reais encontrados:**

1. 🎯 **`DS_LOJA` da tabela nunca foi gravada — 0 de 29.227 linhas.** A coluna existe
   (`VARCHAR2(100)`), mas a SP `STP_OFERTA_FILA_CAPTURA_INSERT` **não tem parâmetro para ela**
   (17 IN, nenhum `P_DS_LOJA`) e o `inserir_oferta` não manda. O marketplace só é registrado
   em `DS_CUPOM_LOJA`, que por desenho é a loja **do cupom** — ou seja, **67,7% das ofertas
   ficam sem marketplace**, mesmo com a URL dizendo qual é (setembro: meli.la 1.915,
   amzn.divulguei.app 1.564, s.shopee.com.br 1.009, link.amazon 711, amazon.com.br 370…).
   O parser **já sabe** deduzir (`_loja_do_campo(text, url)`); falta caminho até o banco.
   **Destravar exige mexer na SP (lado do banco) — decisão do usuário.**
2. **`DS_CUPOM_LOJA` mistura nome canônico e domínio cru.** `_LOJAS` só tem 6 lojas
   (MERCADO LIVRE, SHOPEE, AMAZON, MAGALU, ALIEXPRESS, NATURA); o resto cai no fallback
   documentado "domínio provisório, mapear depois" e nunca foi mapeado: `blz.to` 152,
   `epocacosmeticos.com.br` 105, `achadinhoscomcarol.com.br` 23, `skelt.com.br` 3,
   `on.ltk.com` 2, `onelink.shein.com` 1, `zzmall.com.br` 1. São ~290 linhas a normalizar.
3. **Conversa fiada continua virando PRODUTO** (pendência antiga, agora com exemplos):
   convite de grupo `chat.whatsapp.com` (ID 29626), "Recebemos uma missão da Shopee" (29657),
   "CUPONS | MERCADO LIVRE :" com `DS_OFERTA` = `-` (29733, 29738). São as linhas sem preço
   **e** sem imagem — dá para separá-las por essa assinatura.


### ✅ O que foi feito hoje sobre a auditoria (decisões do usuário, 22/09)

**Loja da oferta (item 1) — plumbing pronto, falta aplicar a SP.**
- `wa/parser.py`: novo campo **`loja`** em `parse_campos`, preenchido em **toda** linha com
  `_loja_do_campo(text, url)`. O `loja_cupom` continua sendo a loja DO CUPOM, intacto.
- `wa/storage.py`: nova coluna **`DS_LOJA`** no fim de `COLUNAS` (o CSV do próximo run passa de
  17 para 18 colunas — quem lê por nome não sente; quem lê por posição precisa saber).
- `wa/monitor.py`: `_montar_linha` mapeia `campos["loja"]` -> `DS_LOJA`.
- `wa/oracle_db.py`: `inserir_oferta` manda `P_DS_LOJA` **só se a SP tiver o parâmetro** —
  ao conectar, `_sp_aceita("P_DS_LOJA")` consulta `USER_ARGUMENTS` e loga o que encontrou.
  Isso remove a janela de erro: código novo com banco velho continua gravando (a loja vai só
  para o CSV), e banco novo com código velho também (o parâmetro tem `DEFAULT NULL`).
- ✅ **SP APLICADA em 22/09 11:33** (`conf/sp_oferta_fila_captura_insert_com_ds_loja.sql`,
  versão anterior em `conf/sp_atual.sql`): `STATUS=VALID`, 0 erro de compilação, `P_DS_LOJA`
  na posição 18. Testada com as **duas formas de chamada** — com e sem o parâmetro, ambas
  `PV_RETORNO='TRUE'`, a nova gravando `DS_LOJA='MERCADO LIVRE'` — e as linhas de teste foram
  desfeitas com `rollback`. **O `CREATE OR REPLACE` não incomodou a captura ao vivo:**
  0 `Erro ao inserir` e 0 `SP retornou FALSE` no run do dia.

**Nomes de loja (item 2) — feito, inclusive o histórico.**
- `_LOJAS` ganhou BELEZA NA WEB (`blz.to`), EPOCA COSMETICOS, SHEIN, ZZ MALL, SKELT,
  ACHADINHOS COM CAROL e LTK; `AMAZON` passou a casar também `amaznlink`.
- `diag/normaliza_loja_cupom.py` (usa a mesma função do parser) corrigiu **287 linhas** no
  Oracle: blz.to 152, epocacosmeticos 105, achadinhoscomcarol 23, skelt 3, on.ltk 2, shein 1,
  zzmall 1. Backup das linhas afetadas em `conf/backup_ds_cupom_loja_22_09_2026_11_23.csv`.
  Não sobrou domínio cru em `DS_CUPOM_LOJA`.

⚠️ **Nada disso está no ar ainda** — o run vivo subiu com o código de antes. Só vale a partir
do **próximo lançamento**.

### 🆕 Miniatura `_small` para o site (implementado hoje, 22/09)

`wa/storage.py` agora gera, ao lado de cada foto, uma miniatura com o **mesmo nome + `_small`**:

```
captura/img/29765_Perfume.jpeg  ->  captura/img/29765_Perfume_small.webp
```

- Sai da imagem **já com a marca d'água**, maior lado **200 px**, proporção mantida e
  **nunca amplia** (foto 150x120 vira miniatura 150x120).
- Só é gerada no **nome definitivo** — as `tmp<N>` do catch-up são renomeadas ou descartadas,
  e miniatura de tmp seria lixo. `renomear_imagem` regenera no nome novo.
- Best-effort igual à marca d'água: falhar não derruba a captura.

**Formato: WEBP, não JPEG.** Medido nas fotos reais do projeto (10 imagens, 200x200, total):

| Formato | Tamanho | Tempo |
|---|---|---|
| JPEG q85 | 70,9 KB | 5,7 ms/img |
| **WEBP q80** | **41,4 KB (-42%)** | 22,7 ms/img |
| AVIF q55 | 29,0 KB (-59%) | 97,0 ms/img |

WEBP é o ponto certo: bem menor que JPEG, suportado por todos os navegadores atuais e barato
de gerar. AVIF economiza mais, mas custa 4x o tempo — só vale se o volume do site pedir.
Tudo calibrável no bloco `imagem` do `config.json`, **sem mexer no código**: `thumb_ativo`,
`thumb_max_px`, `thumb_formato` (`webp`/`jpeg`/`avif`), `thumb_qualidade`. As chaves **não
estão no config.json** — os padrões do código já são os valores desejados, e o arquivo não
podia ser editado com o run vivo.

**Backfill das fotos antigas:** `diag/gerar_thumbs.py` gera o que falta nas **28.333 fotos**
já no disco (2,85 GB; média 98 KB). É interrompível/retomável, pula o que já existe e pode
rodar com a captura no ar (só lê as fotos e escreve arquivos que a captura nunca abre).
✅ **Backfill rodado em 22/09 (89 min):** 28.307 miniaturas geradas, 33 puladas (as dos
testes), **0 falha**. **2.848 MB de fotos → 118,4 MB de miniaturas (4,2%)**. Rodou junto com a
captura ao vivo, sem atrapalhar. **Rodar de novo depois do próximo lançamento** para cobrir as
fotos capturadas pelo run de hoje, que subiu com o código antigo (é idempotente: pula o que já
existe).

```powershell
.venv\Scripts\python.exe diag\gerar_thumbs.py            # gera o que falta
.venv\Scripts\python.exe diag\gerar_thumbs.py --dry-run  # só mede
```

---

## HISTÓRICO (04/08, ~01:00) — resgate confirmado; 2 guardas novas; **nada rodando**

**NADA ESTÁ RODANDO.** O run das 23:23 terminou às **00:56:31**, quando o browser foi fechado
— última linha do log é `Target page, context or browser has been closed` e **o `finally` não
rodou** (não há a linha `Total capturado`). Perfil do Chrome liberado, 0 processo, 0 imagem
`tmp` órfã.

⚠️ **A armadilha do contador se repetiu no mesmo dia** — e foi corrigida: o config tinha
**5504**, o trabalho real ia até **5515**. Conferido contra `MAX(ID_OFERTA)` do Oracle **e** o
maior ID dos CSVs (`checa_contador.py`) e **corrigido para 5515**; sem isso o próximo run
reemitiria os IDs 5505-5515. Backup `conf/config.json.bak_04_08_fim_sessao`.
**Rode essa conferência sempre que a parada não tiver sido um Ctrl+C.**

**Estado:** `ultimo_id_processado=5515`, Oracle ligado (4951 linhas), marcadores Ly **03/08
22:07**, #03 **03/08 22:56**, carol **03/08 21:45**.

**Para retomar** (log do dia seguinte):

```powershell
Start-Process -FilePath "E:\Work\besave\src\AgenteCapturaWhatsapp\.venv\Scripts\python.exe" `
  -ArgumentList "-u","run_captura.py" `
  -WorkingDirectory "E:\Work\besave\src\AgenteCapturaWhatsapp" `
  -RedirectStandardOutput "E:\Work\besave\src\AgenteCapturaWhatsapp\run_captura_04_08.log" `
  -RedirectStandardError  "E:\Work\besave\src\AgenteCapturaWhatsapp\run_captura_04_08.log.err" `
  -WindowStyle Minimized
```

⚠️ **Nunca lançar com outro run vivo** — ver a armadilha de 21:26 abaixo. E o próximo run sobe
com **as duas guardas novas** (voltas cegas + browser morto encerra com saída 3); **nenhuma
rodou em produção ainda**, então vale observar o primeiro dia.

Lixo inofensivo: `captura/03_08_2026_21_26.csv` (só cabeçalho, do lançamento que crashou).

---

### O dia 03/08 — run das 08:40

### O resgate de 02/08 funcionou — 01/08 voltou

O catch-up do arranque levou **24 min** (08:42 → 09:04) e trouxe **594 ofertas**:
Ly=250, #03=216, carol=128. Contagem por `DT_OFERTA` no Oracle:

| Dia | Antes | Depois |
|---|---|---|
| 31/07 | 589 | 589 |
| **01/08** | **0** | **284** ✅ |
| 02/08 | 21 | 280 |
| 03/08 | — | 367 (subindo) |

**Qualidade do run** (849 linhas na medição): IDs 4313-5161 **contíguos**, **0 duplicata
interna**, **96,2% com imagem**, **0 imagem referenciada faltando no disco**, 0 `tmp` órfão,
`DT_CAPTACAO − DT_OFERTA` sem nenhum valor negativo (relógio são; mediana 17,6h é só o
atraso de 2 dias que o catch-up puxou).

### ⚠️ 48 min de apagão por um MODAL do WhatsApp Web — falha NOVA, sem perda

Entre **12:35:59 e 13:23:59**, **83 erros consecutivos**, todo ciclo, nos 3 grupos. Não é o
timeout transitório de 29-30/07 (aquele é isolado, 1 grupo por vez). A causa está explícita
no `Call log` do Playwright, 249 vezes:

```
<div role="dialog" aria-modal="true" …> … subtree intercepts pointer events
```

Um **diálogo modal ficou aberto** e interceptou o clique na lista de conversas. Às 13:24 ele
saiu e a captura voltou sozinha; **0 erro depois disso**.

**PERDA: NENHUMA — medido, não suposto.** Minuto a minuto na janela há ofertas em 12:37,
12:51, 12:55, 12:58, 13:00, 13:02, 13:04, 13:16(×6), 13:28… O **maior buraco do dia inteiro é
de 14 min**, e existe um igual às 08:32→08:46, fora do apagão. Ao destravar, a leitura ao vivo
recolheu o atraso de cada grupo (13 novas de uma vez às 13:24-13:25) porque 48 min ainda cabem
na **viewport renderizada**.

**O PONTO CEGO QUE ISSO REVELOU:** o `_recuperar_lacuna` (fix de 02/08) **não cobria este
caso**. Ele dispara quando o **relógio de parede salta** entre voltas — e aqui as voltas
continuaram girando **na hora certa** (~105s cada), só que falhando todas. Se o modal ficasse
aberto algumas horas, o atraso sairia da viewport e a perda seria **silenciosa**.

### CORREÇÃO APLICADA (03/08) — guarda de VOLTAS CEGAS

`VOLTAS_CEGAS_RESGATE = 5` + contador no rodízio (`wa/monitor.py`). Volta **cega** = **TODOS**
os grupos falharam ao abrir (falha de 1 grupo é o ruído de sempre e **não** conta). 5 voltas
cegas ≈ 9 min → marca `resgate_pendente`, o mesmo caminho que o `_recuperar_lacuna` já criou.

Enquanto o bloqueio durar, o catch-up também falha (ele clica) — **o ganho é que o resgate
fica PENDENTE e dispara sozinho assim que a página destravar**, em vez de o atraso se perder
em silêncio.

Também novo: **`_relatar_bloqueio(page)`** — na 1ª volta cega, imprime no log **QUAL** modal
está aberto (`aria-label`/título + 240 chars do texto) e se o `#pane-side` ainda existe. Só
observa: **não clica, não fecha nada**. Existe porque hoje o log não dizia se era atualização
de versão, chamada, visualizador de mídia ou outra coisa.

Validado com simulação da máquina de estados (`sim_guarda_cega.py`, scratchpad) contra o
episódio real: dispara **uma vez** nas 27 voltas cegas, insiste enquanto travado, reseta ao
destravar; ruído de 1 grupo não dispara; 4 voltas ficam abaixo do limiar, 5 disparam.

⚠️ **O processo que está rodando tem o código ANTIGO** — a guarda entra no próximo lançamento.

### 🚨 ARMADILHA NOVA (03/08 21:26) — lançar um 2º run com o 1º VIVO mata o browser do 1º

Descoberto ao ir reiniciar a captura para pegar a guarda nova. Sequência medida:

1. **21:26:29** — um segundo `run_captura.py` foi lançado com o 1º ainda rodando. Ele criou
   seu CSV (`03_08_2026_21_26.csv`, só cabeçalho).
2. **21:26:35** — morreu em `launch_persistent_context`, porque o perfil `user_data/` estava
   travado pelo run das 08:40. O traceback foi parar em `run_captura_03_08.log.err` (o
   comando reusava os mesmos arquivos de redirecionamento).
3. **~21:28** — **o browser do run das 08:40 morreu junto**. A tentativa de abrir o mesmo
   perfil derruba a instância que já estava de pé.
4. **21:28 → 22:16 (e seguiria para sempre)** — o run das 08:40 ficou **girando em falso**,
   logando `Page.wait_for_selector: Target page, context or browser has been closed` a cada
   5s, **sem capturar nada**. Última captura real: **#5490 às 21:28:06**.

**O 2º run não "não subiu" — ele DERRUBOU o 1º.** Um lançamento que falha em 6 segundos custou
~2h de captura.

**A guarda de voltas cegas (feita horas antes, neste mesmo dia) teria pegado isso** — os 3
grupos falhando em toda volta. O processo em execução tinha o código antigo.

### CORREÇÃO APLICADA (04/08) — browser morto ENCERRA o processo

`_browser_morreu(page, erro)` + `SAIDA_BROWSER_MORTO = 3` (`wa/monitor.py`). A distinção
importa porque **bloqueio e morte se parecem no log** (todo grupo falhando em toda volta) e
pedem reações **opostas**: bloqueio passa e a página volta → vale insistir; **browser fechado
não volta** — não há página para revitalizar, e o resgate da guarda de voltas cegas falharia
para sempre.

Detecta por **assinatura da mensagem OU `page.is_closed()`** (a mensagem sozinha pode mudar
entre versões do Playwright; `is_closed()` sozinho não cobre quando quem morreu foi o
contexto/browser e não a page; se nem responder, conta como morte). Assinaturas: `target page,
context or browser has been closed`, `browser has been closed`, `target closed` e
`connection closed while reading from the driver` (esta última vista em 30/07).

Ao detectar: loga, sai do rodízio e **encerra com código 3** — `run_captura.py` propaga, então
quem lança distingue "encerrei" de "perdi o browser". A checagem vem **antes** do bloco de
voltas cegas, para não disparar um "destravado" falso.

**`finally` endurecido junto:** cada passo (salvar estado / desconectar Oracle / fechar
contexto) em seu próprio `try`. Sair com o browser morto faz `context.close()` levantar
exceção, e uma exceção ali **pularia o resto da limpeza — inclusive o salvar do estado**, que
é justamente o que impede o contador de reemitir IDs no run seguinte.

Testado com as mensagens reais dos logs (`test_browser_morreu.py`, scratchpad): 5 assinaturas
de morte detectadas; **timeout de clique e o bloqueio por modal de 03/08 NÃO** são lidos como
morte (senão o run passaria a se encerrar por ruído); página fechada ou muda → morte.

### ⚠️ `Stop-Process` NÃO roda o `finally` — confira o contador antes de relançar

O `finally` do `captura_msg_whatsapp` é quem salva o estado ao sair. Matar o processo à força
pula isso, e o `conf/config.json` fica **atrasado** em relação ao trabalho já gravado no CSV e
no Oracle. Medido hoje: disco em **5480**, trabalho real até **5490** (o 5480 foi escrito pelo
`finally` do run que CRASHOU às 21:26, com o estado que ele tinha lido segundos antes).

Relançar assim **reemitiria os IDs 5481-5490** — colisão de `ID_OFERTA` no Oracle. Antes de
relançar: comparar `ultimo_id_processado` com `MAX(ID_OFERTA)` do Oracle **e** o maior ID dos
CSVs, e corrigir para o maior deles. Script `checa_contador.py` (scratchpad) faz exatamente
isso e só reporta.

### Reinício executado (03/08 23:23) — ✅ limpo

Backup `conf/config.json.bak_03_08_pre_relance`; contador corrigido 5480 → **5490**; zumbi das
08:40 morto (o `python.exe` do **CaptureAmazon**, outro projeto, foi preservado — filtrar
`run_captura\.py` no `CommandLine`, nunca matar todo `python.exe`); perfil do Chrome liberado
(0 processo). Novo run: log `run_captura_03_08_b.log`, CSV `03_08_2026_23_23.csv`.

Recuperação da janela perdida: catch-up 0+3+3 e o rodízio ao vivo pegou o resto que ainda
estava na viewport (**14 do Ly + 20 do #03** logo na 1ª volta). **IDs 5491-5515, sem colisão**;
**0 erro**, `.err` vazio, rodízio girando limpo.

### Duplicatas do resgate: 14, **decisão do usuário = DEIXAR COMO ESTÁ**

Como os marcadores foram rebobinados para 31/07, o catch-up re-capturou parte do que já havia
sido gravado em 02/08: **14 pares confirmados no Oracle** (novas 4536-4544 e 4891-4895;
gêmeas antigas 4292-4306).

**Detalhe que inverteria a direção da limpeza, se um dia for feita:** as cópias **antigas**
estão com `ST_CAPTURA` em `'1'`/`'9'` (**já consumidas a jusante**) e as **novas** em `'0'`.
Ou seja, o certo seria apagar as **novas** — o contrário do "fica a mais recente".

---

## ONDE PARAMOS (02/08, ~23:50) — ⚠️ buraco de 45h diagnosticado e corrigido _(HISTÓRICO)_

**NADA ESTÁ RODANDO.** O run antigo (lançado em 31/07 16:17, PID 9996) foi encerrado às
**23:31** de propósito, para que o próximo run suba já com as correções de hoje. O perfil do
Chrome está liberado (0 processo `chrome.exe` do projeto), 0 imagem `tmp` órfã.

**PRIMEIRA COISA AMANHÃ — relançar:**

```powershell
cd E:\Work\besave\src\AgenteCapturaWhatsapp
Start-Process -FilePath ".venv\Scripts\python.exe" `
  -ArgumentList "-u","run_captura.py" `
  -WorkingDirectory "E:\Work\besave\src\AgenteCapturaWhatsapp" `
  -RedirectStandardOutput "run_captura_03_08.log" `
  -RedirectStandardError  "run_captura_03_08.log.err" `
  -WindowStyle Minimized
```

⚠️ **O catch-up do arranque vai puxar ~2 dias de atraso** (marcadores rebobinados para 31/07
~22h). É run longo e pesado — é exatamente para isso que o `TETO_ITENS` subiu para 6000. O
log de amanhã já sai com **carimbo de hora em cada linha**.

Estado salvo: `ultimo_id_processado=4312`, Oracle `habilitado=true`. Marcadores **rebobinados**
para a última oferta REAL de 31/07 de cada grupo: Ly **31/07 22:40**, #03 **31/07 22:22**,
carol **31/07 20:10** — e o `ultimo_data_id` foi **APAGADO** dos três (ver armadilha abaixo).
Backup: `conf/config.json.bak_02_08_pre_resgate`.

### 🎯 O QUE ACONTECEU: a máquina dormiu 45h e o rodízio ao vivo não volta no histórico

O usuário notou que quase não havia dado novo. O run **nunca morreu** — sobreviveu a tudo —
e mesmo assim: **01/08 = 0 linha; 02/08 = só 21 linhas, todas depois das 21:40**. CSV do run
(`captura/31_07_2026_16_17.csv`): 341 linhas, IDs 3972-4312, sendo **320 de 31/07 e 21 de
02/08** — nada no meio.

**A medição que fechou o caso** (event log do Windows: `Kernel-Power` 42/107 +
`Power-Troubleshooter` 1): stand by em **01/08 00:31:00**, despertar em **02/08 22:00:37** =
**45h29m**. Bate exato com o buraco no CSV (última captura 31/07 22:40 ID 4291 → primeira
02/08 22:06 ID 4292). Ao acordar, o programa teve ~8 ciclos de timeout em `#side` (a página
tinha morrido) e **se recuperou sozinho** — mas só para o rodízio ao vivo.

**CAUSA RAIZ (de projeto, não bug):** o **catch-up (Fase 1) só roda UMA VEZ, no arranque do
processo**; o **rodízio ao vivo (Fase 2) só lê o que está RENDERIZADO na viewport e nunca
volta no histórico**. Entre os dois havia um buraco: processo que para e volta nunca lê o
atraso acumulado. **AGRAVANTE:** o marcador avançou para as mensagens novas e
`atualizar_grupo` **não retrocede** (decisão de 30/07) → **reiniciar não recuperava**; só
editando o `config.json` à mão.

### As correções (02/08)

1. **`_recuperar_lacuna` (`wa/monitor.py:930`), nova** — ao fim de cada volta do rodízio a
   Fase 2 mede o **relógio de PAREDE** (`datetime.now()`, **não** `time.monotonic()`, que no
   Windows não conta o tempo suspenso). Se passou `LACUNA_RECAPTURA_S = 10min`, re-executa o
   catch-up de todos os grupos. Tem `resgate_pendente`, que insiste na volta seguinte, porque
   ao acordar a página leva vários ciclos para revitalizar.
2. **`TETO_ITENS` 2000 → 6000** — bater no teto **PARA A SUBIDA**, ou seja perde a parte mais
   ANTIGA do atraso, o oposto do que se quer. Com ~600 ofertas/dia nos 3 grupos, 2000 não
   cobria nem 2 dias de atraso.
3. **Carimbo de hora em CADA linha do log** (`_PrefixoHora`, `run_captura.py:29`) — embrulha
   stdout+stderr e prefixa **na transição de linha**, para carimbar também o `Call log`
   multilinha do Playwright. O log antigo, só com `[browser] Abrindo grupo` repetido, tornava
   um buraco de 45h **invisível** — foi por isso que o problema só apareceu 2 dias depois.
4. **`powercfg /change standby-timeout-ac 0` + `hibernate-timeout-ac 0`** (era 30min na
   tomada). O perfil DC (bateria) continua em 15min, mas **é irrelevante: a máquina é
   DESKTOP** (confirmado pelo usuário em 03/08), então ela roda sempre em AC. Não há
   caminho de bateria — este risco está **encerrado**, não é pendência.

### ⚠️ ARMADILHA DO RESGATE (quase caí)

Rebobinar só o `ultima_data_hora` e deixar o `ultimo_data_id` novo faz o recorte **POR
POSIÇÃO** vencer (`wa/monitor.py:819-822`) e o resgate falha em silêncio. **É preciso APAGAR
o `ultimo_data_id`** para cair no corte por data (`inclusivo=False` → `> cutoff`).

### 🔬 A LIÇÃO

**Processo vivo ≠ processo capturando.** O `Start-Process` (30/07) resolveu a fragilidade do
LANÇAMENTO, mas não protege contra a máquina inteira congelar. **Sinal de vida tem que ser
DADO CAPTURADO com carimbo de tempo, não "o PID ainda existe".**

## HISTÓRICO (30/07) — ✅ 3 defeitos achados e corrigidos; sessão encerrada

**NADA ESTÁ RODANDO** — sessão encerrada a pedido do usuário (~22:25). Perfil do Chrome
liberado (matar o Python **não** fecha o browser: sobraram 5 processos e foi preciso
encerrá-los à parte, senão o perfil fica travado para o próximo run), 0 imagem `tmp` órfã.
**Para retomar:**

```
.venv\Scripts\python.exe -u run_captura.py
```

Cada grupo faz catch-up sozinho pelo `conf/config.json`. Estado salvo:
`ultimo_id_processado=3702`, Oracle `habilitado=true`. Marcadores: Ly **30/07 22:22**,
#03 **30/07 22:16**, carol **30/07 19:15**.

### 📊 O DIA (3 runs: `30_07_2026_01_36.csv`, `10_25`, `18_06`)

| | |
|---|---|
| linhas capturadas | **606** (IDs 3059-3702; os 38 ausentes são os apagados na limpeza) |
| ofertas com `DT_OFERTA` de hoje | **590** — #03 233, Ly 222, carol 135 |
| por hora (hoje) | 08h:14 09h:53 10h:60 11h:58 12h:40 13h:52 14h:50 15h:45 16h:27 17h:25 18h:53 19h:23 20h:47 21h:34 22h:9 |
| com imagem | 592/606 (**98%**) |
| duplicatas reais | **0** (conferidas também por URL) |
| imagens faltando no disco | **0** |
| erros | 7 no dia (run b: 2; run c: 5), **todos** timeout de clique na troca de grupo, todos recuperados no ciclo seguinte |

**Sobre os timeouts de clique:** ~5 em 4h no run c, contra 3 em ~5h em 29/07 — taxa um pouco
maior, espaçamento regular no log (nada de degradação progressiva), **0 perda** (o grupo é
relido no ciclo seguinte e o marcador só avança quando há oferta gravada). Não é o defeito do
grupo renomeado (aquele falha em TODO ciclo). Candidato a investigar se sobrar tempo.

**`carol` segue o mais baixo dos três** (135 contra 233 e 222), agora com uma janela de
horário nobre para comparar — o item "a vigiar" de 29/07 continua aberto e sem causa medida.

**Atenção ao conferir duplicata:** a chave `(grupo, data, nome, preço)` dá **falso positivo
quando o nome é vazio**. Hoje os IDs 3300/3301 pareciam duplicata e são ofertas DISTINTAS —
URLs e imagens diferentes, nomes não extraídos (o caso raro em que o nome só existe dentro
da imagem). Conferir URL antes de acusar duplicata.

**COMO A SESSÃO TERMINOU (armadilha de ambiente, não do código):** o processo foi **morto de
fora** às 13:48 junto com as tarefas de background; a última linha do log é o efeito colateral
(`Keyboard.type: Connection closed while reading from the driver`) — driver do browser
desaparecendo no meio de uma ação, **não** um defeito da captura. Sintoma parecido já visto
em 14/07 ("processos longos são mortos em ~25min"); este durou ~3h20. Se for preciso um run
longo, considerar lançar **destacado** (`Start-Process` do PowerShell, sem ficar como filho
do shell da sessão).

Para encerrar uma captura, filtrar `run_captura\.py` no `CommandLine` e matar **todos** os
processos que casarem — o lançador em background sobe 5 (bash + python), matar o PID do
shell não basta.

A retomada de hoje saiu torta e o diagnóstico separou **três defeitos independentes** que se
disfarçavam de um só. Os dois primeiros são regressões recentes; o terceiro é a causa raiz.

### 1. Relógio do Windows 7h03m37s ATRASADO (fora do código)

Sintoma: `DT_OFERTA` aparecia **no futuro** (30/07 08:37 com o relógio em 01:38). Estava
certo — vem do `data-pre-plain-text` (hora do WhatsApp). Errado estava o `DT_CAPTACAO`
(`datetime.now()` local).

```
w32tm /stripchart /computer:time.windows.com /samples:2 /dataonly   ->  +25417,03s
```

**Teste que separa os dois sem depender de NTP:** `DT_CAPTACAO − DT_OFERTA` por CSV — os de
29/07 dão mediana **0,02h**; o de 30/07 dava **−7,03h**. Usuário corrigiu o relógio. O
histórico no Oracle **não** foi contaminado (só o run de 01:36).

### 2. Duplicata no rodízio ao vivo — regressão do fix de hidratação de 29/07

`_ler_novas_do_grupo`: `_coletar_novas` **não** marca `vistos` (quem marca é o laço, depois).
Com pendentes, a recoleta pós-`_hidratar_pendentes` devolvia o **primeiro lote inteiro de
novo** e o `novas.extend(extras)` duplicava cada mensagem → 2 linhas no CSV e 2 inserts no
Oracle. Assinatura no log: `#3094-3099` repetindo `#3086-3091`.

**Fix:** guarda `if data_id in vistos: continue` no laço + contar o que foi de fato lido.
O catch-up é **imune** (`processados.add` acontece ANTES de processar).

### 3. 🎯 CAUSA RAIZ: `cronologico` deixou de sair em ordem cronológica

O comentário *"dentro de cada chunk a ordem já é cronológica"* era verdade **antes** do
assentamento (28/07) e da hidratação (29/07). Agora a passada 1 colhe os balões já montados
e as passadas **seguintes anexam ao mesmo chunk** os que hidrataram depois — que são
cronologicamente **anteriores**. O `reversed(chunks)` está correto; o problema é *dentro* do
chunk.

Isso destrói o **recorte por POSIÇÃO** de `_capturar_desde_ultima`
(`cronologico[indice_do_marcador + 1:]`), e **o sintoma é sorteado pela posição em que o
marcador cai**:

| marcador cai… | resultado | grupo afetado hoje |
|---|---|---|
| no **início** da lista | devolve o histórico velho inteiro | carol: 27 linhas, **todas anteriores ao próprio marcador** |
| perto do **fim** | devolve **zero**, o dia se perde | Ly e #03: "0 novas" tendo mensagens de 08:37 |

**Um bug, dois sintomas opostos** — foi por isso que "0 novas" parecia problema de caminhada
e as linhas velhas do carol pareciam problema de recorte. São a mesma causa.

**Efeito colateral:** `_gravar_cronologico` avança o marcador com a **última linha gravada**,
supondo que seja a mais nova. Com a lista fora de ordem, o marcador do carol **andou para
trás** (21:42 → 15:29) — o que faria a captura seguinte re-varrer 6h e duplicar em massa.

### As correções (30/07)

| arquivo | correção |
|---|---|
| `wa/monitor.py` — `_ordenar_cronologico` (novo) | ordena a subida por `data_hora` de verdade (sort estável; item sem data herda a do vizinho anterior, para não mudar de vizinhança no recorte) |
| `wa/monitor.py` — `_ler_novas_do_grupo` | guarda de `data_id` (mata a duplicata) |
| `wa/monitor.py` — `_capturar_desde_ultima` | descarta **e avisa** se algo depois do marcador tiver data anterior a ele |
| `wa/estado.py` — `atualizar_grupo` | **marcador nunca retrocede** (avisa e ignora; `permitir_retrocesso=True` para quem precisar). Limita o estrago de qualquer regressão futura de ordenação a UM run |

### 🔬 Como medir: `diag/diag_ordem.py`

Rodar **sempre que mexer na caminhada da subida** (`_coletar_subindo`, assentamento,
hidratação, âncora). Ele roda `_coletar_subindo` de verdade e só **reporta**: ordem da lista
(pares asc/desc + blocos), **índice do marcador** e **o que cada um dos dois recortes
devolveria**.

```
.venv\Scripts\python.exe -u diag\diag_ordem.py ["trecho do nome do grupo"]
```

É read-only quanto a estado: não grava CSV, não toca Oracle, não chama `_gravar_cronologico`
(é ele quem avança marcador e contador), e apaga as imagens `tmp*` no fim. **Precisa da
captura parada** — o perfil do Chrome é exclusivo. O argumento casa por **trecho** com a
chave do `config.json`, então o emoji perdido no shell não atrapalha.

**O sinal que decide é os dois recortes CONCORDAREM:**

| | antes do fix | depois |
|---|---|---|
| pares descendentes | 2 (3 blocos) | **0 (1 bloco)** |
| itens pré-marcador no recorte | **19** | **0** |
| recorte por posição × por data | 46 vs 27 | **43 vs 43** |

### Validação em produção (run `captura/30_07_2026_10_25.csv`)

Ly=17, #03=**24** (com o **mesmo marcador 08:40** que antes do fix devolvia **0**), carol=47
→ **88 linhas, IDs 3127-3214 contíguos, 0 duplicata interna, 0 linha que já existisse em CSV
anterior**, 97% com imagem, 0 imagem faltando no disco, `DT_CAPTACAO−DT_OFERTA` mediana
0,55h. **Nenhum dos dois avisos novos disparou.**

### Limpeza do run sujo (IDs 3059-3126) — feita e verificada

Das 68 linhas: **38 apagadas** (19 duplicatas internas + 19 que já existiam) do Oracle + CSV
+ disco (36 imagens), e **30 legítimas mantidas** com `DT_CAPTACAO += 25417s`. As 30 são
dado real que **não voltaria** num novo run (os marcadores já passaram delas) — foi o motivo
de não apagar a faixa inteira.

Duas guardas do script que valeram: conferir **`ST_CAPTURA` antes** (as 38 estavam em `'0'`,
nada consumido a jusante) e **só apagar imagem que nenhuma linha sobrevivente referencia**
(lição do glob de faixa numérica, 19/07). Backup em `captura/backup_38_apagadas.csv`.
Contador e marcadores **não** foram tocados — buraco de ID é inofensivo (já houve um em
926-955). Verificação final: Oracle **2697 linhas, 0 caminho de imagem quebrado**.

### Arrumação

`captura/15_07_2026_12_24.csv` → **`captura/historico/`**. Ele referenciava 162 imagens
inexistentes, mas é inerte: são os IDs **1-162**, de antes de o Oracle entrar (o banco começa
no ID 496, `DT_OFERTA` a partir de 17/07), e **nenhuma linha do banco aponta para eles**. As
imagens 1-162 foram apagadas em algum momento — o disco começa exatamente em 163. Com ele
fora de `captura/`, a checagem de integridade passa limpa: **2928 imagens referenciadas, 0
faltando**.

### 🔬 A LIÇÃO, pela 6ª vez: medir antes de teorizar

Eu afirmei que a lista estava saindo **descendente por inteiro** e que o `reversed(chunks)`
seria o culpado. O diagnóstico mostrou **ordem MISTA em blocos** e o problema **dentro** do
chunk — conclusão diferente, correção diferente. Duas outras hipóteses que a medição matou
no caminho: "o catch-up parou cedo" (não: ele coletou 47 balões, o recorte é que descartou) e
"`DT_OFERTA` está no futuro" (não: o relógio local é que estava atrasado).
**Corolário novo:** quando um mesmo defeito produz sintomas *opostos* em grupos diferentes,
procurar uma causa cujo efeito dependa de uma **posição** ou de um **limiar**, não duas
causas distintas.

## HISTÓRICO (29/07) — ✅ A AMOSTRAGEM FOI RESOLVIDA + captura 2,3x mais rápida

> _Seção histórica: descreve o estado **no fim de 29/07**. O estado atual está em ONDE
> PARAMOS (30/07), no topo._

**NADA ESTAVA RODANDO ao fim de 29/07** — sessão encerrada a pedido do usuário (~23h). O `run_captura.py` foi
finalizado e o perfil do Chrome liberado. **Para retomar amanhã:**

```
.venv\Scripts\python.exe -u run_captura.py
```

Cada grupo faz catch-up sozinho a partir do `conf/config.json`. Usar **sempre** o lançador —
nunca passar os nomes para o `main.py` (o emoji perde o variation selector no shell e o
marcador não é encontrado; armadilha de 25/07). Para encerrar depois, filtrar `*run_captura*`
no CommandLine — o PID do shell não serve (armadilha de 15/07).

Estado salvo: `ultimo_id_processado=3058`, Oracle `habilitado=true`, 0 imagem `tmp` órfã.
Marcadores: Ly **29/07 22:16**, #03 **29/07 22:43**, carol **29/07 21:42**.
Run final: `captura/29_07_2026_17_51.csv` (270 ofertas), log `run_captura_29_07_c.log`.

O grande item que estava aberto desde 28/07 — **"a captura é uma AMOSTRA (~39%), não um
censo"** — está **CORRIGIDO E VALIDADO**. O aproveitamento da subida foi de **13% para
100%** e o run ficou **2,3x mais rápido**.

**Decisão do usuário (29/07):** *não* recuperar o histórico antigo. "Os dados anteriores
são só para treinarmos e refinarmos o programa, ainda estamos em tempo de desenvolvimento."
Foco = código preciso e rápido. Consequência aceita: o que está no Oracle de antes de
29/07 é amostra (~39%), não censo.

### 🎯 CAUSA RAIZ: o filtro de `_coletar_novas` envenenava mensagem não hidratada

**Não era densidade no minuto** (hipótese de 28/07) **e não era a caminhada** — por isso as
5 correções de 28/07, todas sobre *como caminhar*, renderam pouco. O código fazia:

```python
if msg.query_selector('[data-testid="msg-container"]') is None:
    vistos.add(data_id)      # ← marcava como "notificação do sistema", PARA SEMPRE
    continue
```

Item sem `msg-container` **não é notificação do sistema**. A lista virtualizada **reserva a
caixa do balão** antes de ter conteúdo — medido: caixas de **~694x570 com `innerText`
VAZIO** (um separador de data tem ~30px, logo não é separador). Como nada relê um id já
visto — **nem o assentamento, que só recolhe `data-id` inédito** — a mensagem se perdia
para sempre e em silêncio.

**O número:** **47 de 60 data-ids (78%)** estavam nesse estado no instante em que a subida
amostra (650 ms após o scroll), e **nenhum** hidratou esperando 4 s parado. Hidratar depende
de **PROXIMIDADE DA VIEWPORT, não de tempo** — a mesma física do bug da imagem de 19/07:
fora da viewport o elemento existe no DOM sem estar montado.

### Cadeia de medição (scripts no scratchpad da sessão)

| script | o que mediu |
|---|---|
| `analisa_amostragem.py` / `analisa_janela.py` | OFFLINE (só CSV). Recortando as 3 baselines de 28/07 na **janela comum de 42,1 h** — confundidor que faltava: cada run cobria até o próprio horário de início — união = **190 ofertas**, cada run ~39%, e **75% da perda é de MINUTO INTEIRO ZERADO** (60 dos 102 minutos). Só 25% era amostragem parcial do lote ⇒ rebaixou a tese "densidade no minuto" a fator MENOR. |
| `checa_chave.py` | A interseção exatamente 0 entre `ancora` e os outros **não** era chave quebrada: com chave frouxa (nome, URL, nome+preço) segue 1–3, enquanto `sob × ass` mantém 47%. Os runs são mesmo quase disjuntos. |
| `diag_destino.py` | Instrumenta o destino de cada balão. Sweep de 60 no #03 → `baloes vistos=458` mas **só 60 chegaram à extração**. Os ~398 morriam no filtro. |
| `diag_filtro.py` + `diag_transicao.py` | Os descartados são caixas de 694x570 vazias, e **78% dos ids** estavam assim no instante da amostragem, sem hidratar em 4 s. |

### A correção (em `wa/monitor.py`)

- `_coletar_novas` devolve **`(novas, pendentes)`** e **não** põe pendente em `vistos`.
- Novo **`_hidratar_pendentes()`**: rola o pendente até a viewport para montá-lo.
  `HIDRATACAO_TENTATIVAS=3` (só depois disso o id é aceito como notificação de sistema
  de verdade — senão separador de data seria revisitado para sempre),
  `HIDRATACAO_POR_PASSADA=40`, `HIDRATACAO_ESPERA_MS=150`.
- No assentamento, **pendente conta como progresso** (`if novas or tocados`) — senão o laço
  encerrava justamente em cima do lote que se tenta ler.
- `_ler_novas_do_grupo` (ao vivo) hidrata e recoleta também.

**Validação no MESMO sweep de 60 no #03:**

| | antes | depois |
|---|---|---|
| iterações para 60 ofertas | 9 | **1** |
| balões vistos | 458 | **60** |
| aproveitamento | 13% | **100%** |
| histórico consumido p/ achar 60 ofertas | ~40 h (até 27/07 21:14) | **~4,5 h** (até 29/07 10:17) |

E a linha que fecha o caso: **`0 aceitos como notificação do sistema`** — os 103 pendentes
hidrataram **todos** em mensagem real. O filtro não descartava notificação nenhuma.

### ⚡ VELOCIDADE: 97,7 s → ~42 s (2,3x), precisão idêntica

Instrumentei **TEMPO POR FASE** em `_coletar_subindo` (mesmo `WA_DEBUG_SUBIDA=1`): sem isso
"está lento" não diz ONDE, e o gargalo aqui é **round-trip com o browser, não CPU**.

Baseline: `hidratar=78,9s (81%)` | imagem=11,0s | coletar=5,1s | extrair=0,3s | navegar=0,0s

1. **Hidratação em UMA ida ao browser** (a grande). Eram 156 scrolls a ~0,5 s cada. O custo
   **não era rolar**: era `scroll_into_view_if_needed` por elemento, que faz as checagens de
   *actionability* do Playwright (espera visível + estável) com um round-trip por chamada.
   Para montar o balão nada disso é necessário. Novo `_JS_HIDRATAR` (async, um `evaluate`
   só) usa `scrollIntoView({block:'center'})` nativo, com `HIDRATACAO_PASSO_MS=60` entre um
   e outro. **Fase: 78,9s → ~15s (~5x).**
2. **Inventário do DOM em UMA ida.** Novo `_JS_INVENTARIO` devolve `[[data-id, hidratado]]`.
   Antes `_coletar_novas` fazia `query_selector_all` + um `get_attribute` **e** um
   `query_selector` **por elemento** (~120 round-trips por passada com ~60 balões, repetido
   a cada passada do assentamento). Agora só os que serão de fato lidos custam um handle.
   Também migrados: `_ids_renderizados`, `_ancora_mais_antiga`, `_ids_baloes`.
   **Fase coletar: 6,7s → 1,1s (~5x).**
3. **`_achar_balao` virou busca DIRETA** (`page.query_selector` com `_seletor_do_id`, que usa
   `json.dumps` para as aspas). Antes varria todos os balões comparando `get_attribute` para
   achar UM — e é chamado dentro de laços.

Três runs pós-otimização: **35,6 s / 40,6 s / 50,9 s** (média ~42 s), sempre 60/60
coletados, 0 vazios, 0 sem conteúdo.

### ⚠️ IMAGEM NÃO É GARGALO — E NÃO MEXER NA ESPERA

Instrumentei por chamada (`lentas_img`: mediana + 5 mais lentos): **mediana 0,17 s**, pior
caso 3,36 s (mensagem sem foto real, que paga a graça). **Não existe timeout de 8 s/20 s
sendo estourado** — a suspeita inicial de "3 × 8 s" estava ERRADA. A variação da fase entre
runs (11,0 / 13,9 / 16,0 / 29,3 s) é **quantas mensagens não têm foto real** + velocidade de
download do blob. Encurtar `espera_imagem_s` / `_GRACE_MIN_S` é **armadilha já cometida em
16/07** (o atalho `_JS_TEM_FOTO_REAL` derrubou 4 fotos) — não repetir.

### Novo parâmetro `janela` e o script de re-varrimento (NÃO rodou)

- `_coletar_subindo(..., janela=(inicio, fim))` descarta fora da faixa **antes** do
  `salvar_imagem` (o passo caro). Inerte para quem não passa `janela`.
- `revarrer_janela.py` (scratchpad) recupera uma janela de datas **sem mexer no marcador** —
  tem dry-run e confere no fim que nenhum marcador se moveu. **Motivo de existir a proteção:**
  `_gravar_cronologico` chama `atualizar_grupo`, o que puxaria o marcador para trás e faria a
  captura seguinte re-capturar tudo por cima, duplicando.
- Levantamento feito (`mapa_buraco.py`): **20, 21 e 22/07 têm ZERO linha** na tabela
  (18/07=190, 19/07=198, 23/07=118, 24/07=218, 25/07=151, 26/07=279; total 2206 linhas de
  17/07 a 29/07). O usuário dispensou recuperar.

### Estado e monitoramento (29/07, noite)

Runs do dia: `29_07_2026_13_24.csv` (136 ofertas, pré-correção), `29_07_2026_15_06.csv`
(50), `29_07_2026_17_51.csv` (**o run atual**). Após ~4 h ao vivo com as correções:

| grupo | ofertas | imagem | IDs |
|---|---|---|---|
| Promos da Ly ✨ | 153 | 96% | 2789–3052 |
| Achadinhos diaenoite #03 👩 | 84 | 100% | 2827–3055 |
| @achadinhoscomcarol 🛍️ 9 | 30 | 100% | 2833–3025 |

Saúde: **0 traceback, 0 browser fechado, 0 falha de Oracle, 0 trechos perdidos** (este
último é o contador que passou a denunciar perda silenciosa). `ultimo_id_processado=3055`.

**3 timeouts de clique transitórios** (2 no Ly, 1 no carol). **Não é o grupo renomeado de
27/07:** ali a falha era determinística, em todo ciclo, e o locator não resolvia; aqui o log
mostra `locator resolved to <div ... list-item-1>` e o que estourou foi a espera por
"visible, enabled and stable". Os grupos abriram normalmente antes e depois; o tratamento de
erro pulou o ciclo sem derrubar o processo.

**Detalhe de projeto descoberto ao investigar:** `_processar` retorna **antes** do
`atualizar_grupo` quando a mensagem não tem promoção, então **o marcador só avança por
oferta capturada**, não por mensagem lida. Marcador parado significa "nenhuma oferta nova",
não "não está lendo" — foi o que explicou o carol parecer travado às 21:42. Efeito colateral:
em período quieto o marcador fica atrás do presente e, se o processo reiniciar, o catch-up
relê as mensagens sem promoção do intervalo. Desperdício de trabalho, não duplicação.

### 🔬 A LIÇÃO, pela 4ª vez: medir antes de teorizar

Três sessões calibraram **como caminhar** porque a perda parecia de percurso. O sinal que
faltava era o **destino de cada balão visto** (`vistos=458` × `lidos=60`). E cuidado com o
instrumento: o `diag_filtro` guardava o estado do **primeiro contato** (`if id not in
vistos`), o que fez os placeholders parecerem permanentes; o `diag_hidrata`, amostrando
depois, deu 0 e quase me fez concluir "filtro inocente". Só o `diag_transicao` — seguindo o
**mesmo id ao longo do tempo** — separou "transitório" de "depende da viewport".

---

## HISTÓRICO (28/07, ~01:15) — catch-up feito; grupo #03 tinha sido RENOMEADO

Rodamos o catch-up desde os marcadores. **313 ofertas capturadas, IDs 1855–2167**,
Oracle gravou tudo (`db=ok`). **NADA ESTÁ RODANDO** — o usuário pediu pausa e o
`run_captura.py` foi encerrado. Retomar após as 7h.

> ### ✅ RESOLVIDO EM 29/07 — era o filtro de `_coletar_novas` (ver seção do topo)
>
> _Este bloco fica como registro do raciocínio da época. A hipótese abaixo ("a subida para
> cedo") explicava só parte: as correções de 28/07 fizeram a subida atravessar 2 dias e
> fecharam o buraco de 3,5 h, mas a perda continuou porque **78% dos balões eram descartados
> pelo filtro antes de serem lidos**. Não reabrir por aqui._
>
> O usuário observou que (a) a retroação ficou **mais rápida** que o normal e (b) o
> `Achadinhos diaenoite #03 👩` **tem mais mensagens** do que as 65 capturadas.
>
> Pistas já medidas, **ainda não investigadas**:
> - o grupo tinha **448 mensagens não lidas**, saíram **65 ofertas**;
> - o marcador era **26/07 16:58**, mas a 1ª capturada é de **26/07 20:34** (~3,5h sem nada);
> - **7 linhas de 26/07** contra 58 de 27/07.
>
> Hipótese a testar (medir antes de teorizar): é o mesmo "a subida para cedo" da pendência
> de 20–22/07 — `_coletar_subindo` (`wa/monitor.py:200-211`) declara fim do histórico após
> 3 iterações com `scrollTop<=2` e só 650 ms de espera.
>
> **Atenção:** o marcador do #03 **já avançou para 27/07 23:21**, então rodar normal não
> traz o que faltou. Recuperar exige rebobinar o marcador ou um sweep `--max N`.

| run | CSV | Ly | #03 | carol | IDs |
|---|---|---|---|---|---|
| 1 (27/07 22:14) | `27_07_2026_22_14.csv` | 130 | **0 (falhou)** | 116 | 1855–2100 |
| 2 (28/07 01:02, pós-fix) | `28_07_2026_01_02.csv` | 2 | **65** | 0 | 2101–2167 |

O #03 do run 2 cobre 26/07 20:34 → 27/07 23:21, **100% com imagem**.
Estado: `controle.ultimo_id_processado=2167`, `db.habilitado=true`, os 3 grupos com
marcador em 27/07–28/07. Backup do config antes do reparo: `conf/config.json.bak_27_07`.

### ARMADILHA NOVA: grupo renomeado no WhatsApp

O `#03` não capturava nada desde 26/07 16:58, dando `Locator.click: Timeout 30000ms` no
`list-item-1` a cada ciclo do rodízio. **O erro aponta para o seletor, mas a causa era outra:
o grupo foi RENOMEADO.**

| | nome |
|---|---|
| em `conf/config.json` | `#03 achadinhos.dediaedenoite 💄` (💄 = U+1F484) |
| no WhatsApp | `Achadinhos diaenoite #03 👩` (👩 = U+1F469) |

A busca do WhatsApp casa por **prefixo de palavra**: o nome antigo devolvia **zero**
resultados (medido — `'achadinhos'` devolvia 3, `'dediaedenoite'` zero). O
`wait_for(visible)` passava num piscar e o `click()` ficava 30s esperando um elemento
inexistente.

**Fix:** renomear a **chave** do grupo em `conf/config.json` preservando
`ultima_data_hora`/`ultimo_data_id` — assim o catch-up recupera desde o marcador antigo.
Nenhuma mudança de código foi necessária.

Dois aprendizados do diagnóstico (scripts `diag_busca_03{,b,c}.py`, no scratchpad da sessão —
inventariam `[data-testid^="list-item"]` com `title` e codepoints):

- **`list-item-0` é o cabeçalho "Conversas"**, não um chat. O `list-item-1` do código está
  **correto** — não "consertar" para 0.
- **Primeira coisa a checar** quando um grupo dá timeout ao abrir: ele foi renomeado?

**Consequência a vigiar:** `DS_ORIGEM` passa a gravar o nome novo; as linhas históricas ficam
com o nome antigo. Quem agrupar por `DS_ORIGEM` no downstream vai ver dois nomes para o mesmo
grupo.

### Pendência antiga que continua aberta

Os dias **20, 21 e 22/07 seguem faltando** (a subida para em ~3 dias). Nada foi feito nessa
frente nesta sessão — detalhes na seção abaixo.

## HISTÓRICO (retomar 26/07) — catch-up dos 6 dias parciais: FALTAM 20, 21 e 22/07

Depois de 6 dias parado (19→25/07), rodamos o catch-up. **Pegou 488 ofertas, mas só de
23, 24 e 25/07 — os dias 20, 21 e 22 não vieram, nos TRÊS grupos.** É isso que fica para
analisar amanhã.

**Estado ao fim de 25/07 (noite):** **NADA rodando.** `conf/config.json`:
`controle.ultimo_id_processado=1582`, `db.habilitado=true`, marcadores já em **25/07**
(Ly 21:28, #03 20:55, carol 15:27). Backup do config antes dos reparos:
`conf/config.json.bak_25_07`.

Rodar (use o lançador novo, NÃO passe os nomes na linha de comando — ver armadilha abaixo):
`.venv\Scripts\python.exe -u run_captura.py`

### O QUE ACONTECEU EM 25/07

**Run 1 (23:11) — dois problemas, capturou 1 linha só.**

1. **ARMADILHA NOVA E CARA: nome de grupo perde caractere ao passar pela linha de comando.**
   O emoji 🛍️ do `@achadinhoscomcarol` são DOIS codepoints: `U+1F6CD` + `U+FE0F`
   (variation selector). No copy/paste → PowerShell → `argv`, o **`U+FE0F` foi descartado**.
   Como `estado.get_grupo` casa a chave por **igualdade exata**, o marcador não foi
   encontrado → caiu em `_marcar_baseline` → **não capturou nada** e ainda criou uma
   **chave duplicada lixo** (`'@achadinhoscomcarol 🛍 9'`, sem VS16) no `config.json`.
   A busca do grupo no WhatsApp funciona mesmo com o nome truncado (casa por texto
   parcial), então o sintoma NÃO aparece na abertura do grupo — só no estado.
   - **MITIGAÇÃO: novo `run_captura.py` na raiz**, que lê os nomes DIRETO das chaves do
     `conf/config.json` e chama `captura_msg_whatsapp`. Zero shell no caminho do nome.
     Verificado: entrega `['0x1f6cd', '0xfe0f']` intacto.
   - Chave lixo removida do config.
2. **#03 devolveu "1 nova" e queimou o marcador** (avançou 19/07 21:33 → 25/07 20:55
   gravando só a mensagem mais recente). Rebobinei o marcador para 19/07 21:33 /
   `data_id 3EB0AB9C2D3572123A0C36` e apaguei o ID 1095 (Oracle + CSV + imagem +
   contador de volta a 1094) para não duplicar.

**Run 2 (23:39) — o lançador resolveu o problema do nome. Resultado:**

| grupo | novas | 23/07 | 24/07 | 25/07 | 20-22/07 |
|---|---|---|---|---|---|
| Promos da Ly ✨ | 150 | 59 | 54 | 37 | **0** |
| #03 achadinhos 💄 | 141 | 22 | 69 | 50 | **0** |
| @achadinhoscomcarol 🛍️ 9 | 197 | 37 | 96 | 64 | **0** |

CSV `captura/25_07_2026_23_39.csv`: **488 linhas, IDs 1095-1582 CONTÍGUOS, 98% com
imagem** (5 sem), 17 sem `DS_OFERTA`. Oracle gravou tudo (`db=ok` em todas). Os três
grupos entraram no rodízio ao vivo e o processo foi encerrado depois.

### A INVESTIGAR EM 26/07 — por que a subida para em ~3 dias

O corte em 23/07 é **idêntico nos três grupos**, com marcador em 19/07 nos três. Como o
marcador de 19/07 não foi alcançado, o recorte caiu no fallback por data — ou seja, a
coleta simplesmente **não carregou** 20-22/07. A subida parou cedo.

**Hipótese principal (NÃO CONFIRMADA — medir antes de mexer):** a condição de parada de
`_coletar_subindo` (`wa/monitor.py:200-211`) é agressiva demais. Ela declara "início do
chat" após **3 iterações seguidas** em que `scrollTop<=2` e `scrollHeight` não cresceu,
com apenas **650 ms** de espera entre elas. Quando o WhatsApp precisa buscar histórico
mais antigo (round-trip para o celular/servidor), 650 ms × 3 pode não ser suficiente →
o loop conclui que acabou o histórico e para. Suspeitos secundários: `TETO_ITENS=2000`
(improvável, imprime aviso e não apareceu no log) e `passou_cutoff` disparado por uma
data espúria (não explicaria o corte idêntico nos três).

**Como investigar (lição de 19/07: MEDIR o DOM antes de teorizar):** instrumentar
`_coletar_subindo` para logar por iteração — `scrollTop`, `scrollHeight`, nº de balões,
data mais antiga vista, e **qual condição encerrou o loop**. Aí dá para separar "parou por
`estavel>=3`" de "parou por cutoff/marcador".

**Atenção ao recuperar 20-22/07:** os marcadores **já estão em 25/07**, então rodar normal
não traz mais esses dias. Vai precisar de rebobinada de marcador (como fiz com o #03) ou de
um backfill dedicado por janela de data. E o contador está em 1582.

## HISTÓRICO — retomar 20/07 (fix de imagem VALIDADO; sem pendência bloqueante)
Sessão de 19/07 fechou 3 frentes: (1) `ST_CAPTURA='0'` na SP; (2) catch-up dos 2 dias
parados; (3) **causa raiz da perda de fotos do carol ACHADA E CORRIGIDA** (não era o que
supúnhamos). A migração Oracle segue FEITA e rodando registro-a-registro (CSV + tabela
`OFERTA_FILA_CAPTURA`, best-effort).

**Estado ao fim de 19/07:** **NADA rodando** (o usuário fechou o browser ~21:33; encerrei o
`main.py`, que tinha ficado num loop inútil tentando reabrir grupos na página morta — estado
é salvo por mensagem, nada perdido). `conf/config.json`: `db.habilitado=true`,
`controle.ultimo_id_processado=1094`, marcadores em 19/07 (Ly 21:32, #03 21:33, carol 18:07).
Tabela `OFERTA_FILA_CAPTURA` com `ST_CAPTURA='0'` em 100% das linhas.

Rodar normal amanhã (catch-up automático desde os marcadores, grava CSV + Oracle):
`.venv\Scripts\python.exe -u main.py "#03 achadinhos.dediaedenoite 💄" "@achadinhoscomcarol 🛍️ 9" "Promos da Ly ✨"`

### O QUE FOI FEITO EM 19/07 ✅
- **`ST_CAPTURA='0'` na SP** (`sql/STP_OFERTA_FILA_CAPTURA_INSERT.STP`): coluna adicionada ao
  INSERT com literal `'0'` (constante, não vem do CSV). Motivo: OUTRO projeto downstream usa
  esse campo como **status de leitura** ('0' = não lido). `ST_CAPTURA` é VARCHAR2(30) → grava
  a STRING '0'. SP recompilada VALID. **Backfill** das 155 linhas antigas (`UPDATE ... WHERE
  ST_CAPTURA IS NULL`) → tabela 100% em '0'.
- **Catch-up dos 2 dias parados** (run 11:06): #03=56, carol=124, Ly=87 = 275 ofertas, IDs
  651-925 contíguos, gravadas no Oracle sem falha.
- **FIX DA IMAGEM DO CAROL (o grande achado do dia):** a hipótese antiga ("corrida de
  carregamento, subir `espera_imagem_s`") estava **ERRADA**. Diagnóstico ao vivo mostrou 8/8
  mensagens com a foto blob JÁ presente (nat 500-640) mas `clientWidth=0` (fora da viewport a
  `<img>` perde layout). O seletor `_JS_IMG_QUADRADA` filtrava `w<120||h<120` (tamanho
  RENDERIZADO) e por isso devolvia "não tem foto". Esse filtro era da época do `screenshot()`;
  **desde a migração p/ CANVAS (16/07) ficou obsoleto — canvas lê de naturalWidth, não precisa
  de layout.** FIX: seletor passou a filtrar por TAMANHO NATIVO (`_MIN_NATURAL_FOTO=200`),
  render só como desempate; limiar de "carregada" baixado de 500 p/ 200. **Resultado sweep
  carol: 55% → 100%.**
- **Backfill das 58 imagens** do run da manhã (`backfill_imagens.py`, scratchpad): casa CSV↔msg
  por (grupo, DT_OFERTA ao minuto, nome). 56/56 do carol recuperadas com `UPDATE` no Oracle;
  as 2 restantes (IDs 835 'Bom diaaa pessoal', 911 'Domingou...') NÃO têm foto porque **não
  são produto** — são saudações/hype (pendência de PARSER, ver abaixo).
- **Validação em produção (run 20:49):** catch-up dos 3 grupos com o fix — #03=33/33, carol=15/15,
  Ly=77/78 = **125/126 = 99% com imagem, 0 erro de Oracle.** O carol 100% no catch-up confirma
  o fix. A única sem foto é oferta só-preview legítima.

### ⚠️ ERRO DE LIMPEZA (recuperado) — cuidado com glob de faixa numérica
Ao limpar artefatos de teste, o glob `captura/img/9{2,3,4,5}[0-9]_*.jpeg` casou **920-959** e
apagou as imagens **920-925 (produtos REAIS)** junto com as de teste (926-955). CSV e Oracle
ficaram íntegros (só os arquivos sumiram). Recuperado com `recuperar_920_925.py`: como o nome
do arquivo é DETERMINÍSTICO, regravei a mesma foto no mesmo caminho. 6/6 OK, 0 imagem
referenciada faltando. **LIÇÃO: conferir o alcance de um glob de números antes de `rm`.**

### PENDÊNCIAS (não bloqueantes) para quando fizer sentido
1. **Parser captura saudação/hype como oferta** (IDs 835 'Bom diaaa pessoal', 911 'Domingou
   com muita energia'): viram linha sem preço/sem foto. Raro. Decidir: filtrar no `_tem_conteudo`
   ou aceitar.
2. `imagem.resolucao_minima=400` está PERTO de origens legítimas (existe foto 450x450) — risco
   de descartar foto boa; calibrar se aparecer caso real.
3. Preço virando nome em msgs de assinatura (não recorre há tempo, monitorar).

## MIGRAÇÃO CSV -> ORACLE — FEITO E VALIDADO (17/07) ✅
Grava cada oferta na tabela `OFERTA_FILA_CAPTURA` (schema BESAVE) via a stored procedure
`STP_OFERTA_FILA_CAPTURA_INSERT`, **sem tirar o CSV** (é adicional e best-effort: se o banco
estiver off/mal-configurado, loga e segue só com CSV, sem derrubar a captura).

- **Driver (decidido por pesquisa + arquitetura da máquina):** `python-oracledb` em **THICK
  mode**. O `thin` só conecta em Oracle 12.1+ (o XE é 11.2), e o `thick` do python-oracledb
  atual (4.0.2, único com wheel p/ Python 3.14 64-bit) exige **Oracle Client >= 19**. Por isso
  os 2 clients antigos do usuário NÃO serviam (o 11gR2 é 32-bit → não carrega em Python 64-bit;
  o Instant Client 12.2 é antigo demais). **Solução: Instant Client 19c x64** em
  `C:\oraclexe\app\instantclient_19_30` (conecta no XE 11.2 numa boa — client novo + banco
  antigo é suportado).
- **Arquivos:** NOVO `wa/oracle_db.py` (classe `OracleDB`: `conectar`/`desconectar`/
  `executar_stored_procedure(nome,params,out_vars)`/`inserir_oferta(linha)`; conversores
  `_preco_para_numero` pt-BR '182,90'→182.9 e '3.499'→3499, `_data_para_dt`, `_imagem_relativa`
  = relativo a `captura/` → `img/NN_x.jpeg`). NOVO `sql/STP_OFERTA_FILA_CAPTURA_INSERT.STP`
  (PROCEDURE, 17 params IN = colunas do CSV + `PV_RETORNO OUT VARCHAR2` 'TRUE'/'FALSE' +
  `PV_ERRO OUT`; BOOLEAN de PL/SQL não pode ser bind no 11g; `NVL(DS_OFERTA,'-')` pq CUPOM tem
  nome vazio e a coluna é NOT NULL; `SUBSTR` defensivo; SEM commit — o cliente commita 1/linha;
  colunas extras da tabela, p/ o programa de enriquecimento, ficam NULL). EDITADOS:
  `wa/monitor.py` (cria `OracleDB` no arranque, insere logo após `gravar_linha`, log
  `db=ok/ERRO`, fecha no finally; param `db` propagado); `conf/config.json` (bloco `db`);
  `requirements.txt` (`oracledb>=4.0`).
- **Decisões:** imagem → **`DS_IMAGEM_OFERTA`** como caminho RELATIVO a `captura/`
  (`img/NN_x.jpeg`); `DS_URL_ORIGEM` mantém o link do produto. Charset do XE = **AL32UTF8**
  (emoji/acento gravam intactos — NÃO é 1252).
- **BUG DPI-1047 (resolvido):** num run o Oracle falhou (`DPI-1047 Cannot locate 64-bit Oracle
  Client`) porque o `instant_client_dir` ganhou **espaços no fim** ("...19_30   ") numa edição
  no IDE → `init_oracle_client` apontou p/ pasta inexistente. Corrigido nos 2 lados: **`.strip()`
  defensivo em `oracle_db.py`** (path, host, servico, usuario) + config limpo.
- **RECUPERAÇÃO de linhas CSV-only:** re-rodar o catch-up NÃO recupera (o estado já avançou —
  marcadores/`ultimo_id_processado` sobem por mensagem mesmo com o DB fora). Recuperar = fazer
  **backfill do CSV do run** chamando `inserir_oferta` por linha (script `smoke_oracle.py` no
  scratchpad da sessão faz isso). Foi assim que as 152 do backlog entraram (152/152 OK).
- **Pré-requisitos (feitos):** IC 19c x64 baixado; user BESAVE/senha no config; a SP foi criada
  rodando o `.STP` pela própria conexão (o usuário tinha aberto o arquivo mas não executado).

### RENOMEAÇÃO dos campos do CSV — FEITO (15/07)
Só os NOMES de saída no CSV mudaram (lógica/estrutura intactas). Alterado em
`storage.COLUNAS` (nomes+ordem) e `monitor._montar_linha` (chaves do dict). `parser.py`
NÃO mudou (chaves internas do dict `campos` seguem antigas). Novo cabeçalho/ordem:
`DS_TIPO_ORIGEM` (constante "WHATSAPP"), `DS_ORIGEM`(←nome_do_grupo), `DS_TIPO_OFERTA`
(←tipo_anuncio), `ID_OFERTA`(←numero_da_captura), `DT_CAPTACAO`(←data_hora_captura),
`DT_OFERTA`(←data_hora_mensagem), `DS_OFERTA`(←nome_do_produto), `DS_IMAGEM_OFERTA`
(←imagem_principal), `DS_OFERTA_AVISO`(←msg_aviso), `VL_PRECO_DE`, `VL_PRECO_POR`,
`DS_DESCRICAO_PAGAMENTO`, `DS_URL_ORIGEM`(←url), `DS_MSG_FINAL`(←mensagem_final),
`DS_CUPOM`, `DS_CUPOM_COMENTARIO`(←comentario_cupom), `DS_CUPOM_LOJA`(←loja_cupom).
CSVs antigos (10–14/07) ficam no cabeçalho ANTIGO (usuário dispensou converter).

### FULL SCAN 14/07 (formato novo) — resultado
Rebobinei o estado dos 3 grupos p/ 13/07 09:00 e rodei catch-up. 621 linhas, cabeçalho
novo OK, **0 duplicatas reais**. Imagem: `#03`=136 **100%**, `Promos da Ly`=266 **100%**,
`@achadinhoscomcarol`=219 **90%** (21 sem imagem = pendência B). Total imagem 96%.

### DESCOBERTA (14/07): processos longos são MORTOS pelo harness em ~25min
`run_in_background` (Bash) é encerrado pelo ambiente em ~25 min → catch-up de grupo
grande não termina. SOLUÇÃO: lançar o python **DESTACADO** e fazer polling do log/estado:
`cd projeto && export PYTHONUTF8=1 && nohup .venv/Scripts/python.exe -X utf8 -u
run_fullscan.py > LOG 2>&1 </dev/null & disown`. (PowerShell tool deu EPERM nesta sessão;
`start //b` via cmd não subiu; nohup+disown FUNCIONOU e sobreviveu ao catch-up inteiro.)
Catch-up é retomável por GRUPO (estado avança quando cada grupo termina), mas NÃO dentro
de um grupo (só grava/salva estado no fim de `_capturar_desde_ultima`).

## RESOLUÇÃO DAS IMAGENS — causa raiz achada e corrigida (16/07) ✅
Usuário reclamou de imagens "pequenas e borradas" e pediu **tamanho de captura por
grupo no config.json**. Medindo o CSV `16_07_2026_16_36.csv` (229 linhas): `#03` =
330×330 (93%), `@achadinhoscomcarol` = 474×480 (68%), `Promos da Ly` = nativo
500..1254 (92% boa).

**Tamanho por grupo era o lever ERRADO — NÃO reintroduzir.** 330 vs 474 é a **caixa de
render** de cada layout, não a foto: a origem varia (500/640/1024/1500) e o canvas
simplesmente pega o que existe. Configurar um número fixo por grupo seria chutar um
valor que não corresponde à origem, e não recupera pixel nenhum.

### Causa 1 — `screenshot()` rasteriza no tamanho RENDERIZADO
`handle.screenshot()` tira um print da tela: a foto nativa 1024×1024 desenhada numa
caixa de 330px virava arquivo 330×330 (**redução 3,1× irreversível**), e ainda herdava
o **recorte do CSS** (`object-fit`) — voltava faltando borda. O contexto é criado sem
`device_scale_factor` (`browser.py`), então escala 1 = CSS px vira pixel do arquivo.
`Promos da Ly` só era bom **por acidente**: não tem foto blob, cai no decode base64,
que grava os bytes ORIGINAIS. Ou seja, **o código tentava o caminho pior primeiro**.

**Correção: CANVAS** (`storage._JS_CANVAS_NATIVO` + `_salvar_via_canvas`) — desenha a
`<img>` num canvas em `naturalWidth × naturalHeight` e exporta com
`toDataURL('image/jpeg', q)`. Os blobs do WhatsApp são **mesma origem** → o canvas
**NÃO fica tainted** (validado ao vivo: 6/6 sem taint). É mais rápido que o screenshot
(não rasteriza nem precisa rolar). O screenshot virou **fallback**: se um dia a Meta
servir a foto de outra origem, o canvas lança e a captura degrada ao comportamento
antigo em vez de quebrar.

### Causa 2 (a maior; ERA a pendência B) — o WhatsApp só carrega a foto perto da viewport
`_coletar_novas` devolve **TODOS os balões renderizados no DOM**, não só os visíveis, e
o sweep chamava `salvar_imagem` neles direto (`monitor.py:178`) → **a foto nunca chegava
a existir** → caía no thumbnail 72×72 do preview. Isso ficou meses despercebido porque
a linha *parecia* completa (tinha imagem, só que lixo).

**Correção: `storage._trazer_para_viewport`** (`msg.scroll_into_view_if_needed`) antes de
extrair → `#03` foi de **6/10 para 10/10**. Não atrapalha o sweep: cada chunk só traz
mensagens novas (mais antigas, acima), então a rolagem segue progredindo para cima.

### ARMADILHA (erro cometido nesta sessão — não repetir)
Criei `_JS_TEM_FOTO_REAL` como atalho ("mensagem sem foto → não espera") e ele **derrubou
4 fotos**: o WhatsApp monta o balão e só **DEPOIS** cria a `<img>` com o `blob:`, então
perguntar cedo dá "não tem foto" para mensagem que tem. Fix: **`_GRACE_MIN_S = 3.0`**
incondicional antes do atalho passar a valer.

### Resultado (`--max 10` nos 3 grupos)
| Grupo | Antes | Depois |
|---|---|---|
| `#03 achadinhos` | 330×330 (93%) | **1024×1024, 10/10** |
| `@achadinhoscomcarol` | 474×480, 26% lixo 72×72, 15 sem imagem | **nativo 500..976, 0 sem imagem por corrida** |
| `Promos da Ly` | já nativo | nativo mantido |

### Novas chaves no `conf/config.json` (bloco `imagem`)
`qualidade_jpeg` (0.95), `resolucao_minima` (400 — piso; abaixo disso o preview é
descartado em vez de virar foto do produto), `espera_imagem_s` (8).

### 5/30 sem imagem é CORRETO (não é bug) — e o que VIGIAR
Rodei o sweep **2×** e comparei por nome do produto: **19/20 produtos deram desfecho
IDÊNTICO** → as falhas são **determinísticas** = mensagens cuja única imagem é um
thumbnail de preview pequeno (não existe foto do produto no DOM para extrair). Antes
viravam um 72×72 inútil. Se preferir ter o thumbnail a não ter nada, baixar
`resolucao_minima`.
- **Corrida residual ~5%**: "Gloss Too Faced" saiu 450×450 num run e sem imagem no
  outro → subir `espera_imagem_s` se incomodar.
- **`resolucao_minima=400` está PERTO de tamanhos legítimos** (existe origem 450×450):
  foto menor que 400 seria descartada indevidamente. Vigiar.

## HISTÓRICO — pendência de imagem do catch-up (14/07, RESOLVIDA em 16/07)
Teste de virada de dia (14/07) PASSOU: catch-up retomou do marcador exato de cada
grupo (13/07 manhã) e recuperou ontem+hoje, **0 duplicatas**. Mas o grupo 3
`@achadinhoscomcarol` teve ~7–9% de linhas SEM imagem — SÓ durante o catch-up
(rolagem no histórico); no rodízio **ao vivo a captura é ~100%**. Duas causas:
- **(A) FOTO EM RETRATO — JÁ CORRIGIDO (14/07).** Esse grupo posta muitas fotos
  ALTAS (ex.: natural 1072×1600, render 474×676), não quadradas. O antigo
  `_JS_IMG_QUADRADA` (storage.py) só aceitava aspecto 0.85–1.18 → rejeitava a foto
  → vazio. Trocado por seleção da FOTO REAL (blob) de maior `naturalWidth` (desempate
  por área), aspecto LIVRE, ignorando ícones (<120px) e `data:` (placeholder/banner).
  Validado: Good Girl 1072×1600 passou a salvar.
- **(A2) grace period — JÁ APLICADO (14/07).** `storage._esperar_img_carregar` ganhou
  `grace_sem_img_s=3.0`: quando ainda não há foto (idx<0, blob sem layout), espera
  ~3s antes de desistir (antes desistia NA HORA). Recupera parte das corridas.
- **(B) — RESOLVIDA em 16/07.** O diagnóstico de 14/07 ("corrida de carregamento") estava
  no caminho certo mas errou a causa: não era a rolagem ser rápida demais, e sim o
  **WhatsApp não carregar a foto de balões fora da viewport** — que é justamente o que o
  sweep processa. A prova de 14/07 ("Body Splash" TEM blob 534×534 quando assenta)
  encaixa: a foto existe, mas só depois de o balão chegar perto da tela. Fix =
  `_trazer_para_viewport` antes de extrair (ver "RESOLUÇÃO DAS IMAGENS"). Nenhuma das 3
  opções cogitadas era necessária.


## Objetivo
Ler mensagens promocionais de **um ou vários grupos** do WhatsApp Web via
**Playwright** (contexto persistente = QR só 1x), monitorar o DOM e extrair
campos para um CSV, salvando também a imagem do produto/cupom.

## Estado atual: FUNCIONANDO (validado com dados reais, multi-grupo)
Validado nos 3 grupos `#03 achadinhos.dediaedenoite 💄`, `@achadinhoscomcarol 🛍️ 9`,
`Promos da Ly ✨`. Modos: catch-up (retoma do estado salvo), sweep (`--max N`) e
rodízio ao vivo. Último run (12/07): **catch-up + ~dia inteiro ao vivo, 250+
capturas**, dedup ok, qualidade boa (url/imagem 100%, nome 96%, preço-virando-
nome=0). Classificação PRODUTO/CUPOM, `descricao_pagamento`, `loja_cupom`,
`data_hora_mensagem`, imagens em `captura/img/` — tudo OK.

## ONDE PARAMOS (retomar 13/07 ou próxima sessão)
Run de 12/07 (`captura/12_07_2026_12_25.csv`) rodou o dia todo em catch-up +
rodízio ao vivo (250+ capturas, qualidade validada — ver "Feito em 12/07").
O **grande próximo passo** continua sendo **migrar CSV -> Oracle**.
- Rodar (catch-up automático desde a última leitura salva por grupo):
  `.venv\Scripts\python.exe -u main.py "#03 achadinhos.dediaedenoite 💄" "@achadinhoscomcarol 🛍️ 9" "Promos da Ly ✨"`
  (sem `--max` = retoma do estado; com `--max N` = varre ~N de cada grupo antes).
- **DESCOBERTA (12/07)**: os 3 grupos NÃO postam de madrugada (00h–05h = 0
  capturas); concentram posts ~06h–21h. "Hoje vs ontem" na prática = dia vs noite.
- Casos de nome ainda abertos (raros, ~1–2%): nome só na imagem / hype maiúsculo
  (fica vazio, sem solução por texto) e hype colado ao nome na MESMA linha
  (ex.: #206 "É DE 1 LITROS CADAAA…Kit Wella Professional").

## Estrutura
```
run_captura.py     # LANÇADOR (usar sempre): lê os nomes do conf/config.json
main.py            # entrada crua: python -u main.py "Grupo A" [...] [--max N] [--seg-grupo S]
requirements.txt   # playwright>=1.61
wa/
  browser.py       # contexto persistente, login, abrir/trocar grupo
  monitor.py       # captura_msg_whatsapp(): sweep + catch-up + rodízio multi-grupo + dedupe
  parser.py        # reconstrói texto (emoji->alt) + classifica (PRODUTO/CUPOM) + extrai
  storage.py       # salva imagem + escreve CSV
  estado.py        # marcador por grupo + contador global (conf/config.json)
  oracle_db.py     # gravação no Oracle via stored procedure (best-effort)
diag/
  diag_ordem.py    # confere a ORDEM da subida — rodar ao mexer na caminhada (30/07)
conf/config.json   # marcadores por grupo, ultimo_id_processado, bloco db e imagem
sql/               # a stored procedure de insert
user_data/         # sessão salva (NÃO commitar) — QR só na 1ª vez
captura/           # saída: CSV (NÃO commitar)
captura/img/       # imagens dos anúncios (NÃO commitar)
captura/historico/ # CSVs antigos fora de uso (não entram nas conferências)
```

## Como rodar
```bash
# um grupo, só mensagens novas
.venv\Scripts\python.exe -u main.py "#03 achadinhos.dediaedenoite 💄"

# VÁRIOS grupos em rodízio (lê novas, espera, pula p/ o próximo, e repete)
.venv\Scripts\python.exe -u main.py "Grupo A" "Grupo B" "Grupo C"

# SWEEP: varre as últimas ~N msgs de CADA grupo e depois entra no rodízio
.venv\Scripts\python.exe -u main.py "Grupo A" "Grupo B" --max 40

# tempo (s) parado em cada grupo antes de pular (padrão 5)
.venv\Scripts\python.exe -u main.py "Grupo A" "Grupo B" --seg-grupo 8
```
- Sempre usar `-u`; no Windows, se der erro de emoji no console: `set PYTHONUTF8=1`.
- Sessão já está salva em `user_data/` (não pede QR).

## Decisões e DESCOBERTAS importantes (não-óbvias)
1. **Ambiente**: Python 3.14 → playwright 1.48 NÃO instala (greenlet sem wheel).
   Usar **playwright>=1.61** (instalado: 1.61.0) + `playwright install chromium`.
2. **Seletores**: as classes `x1lliihq`, `xnpuxes`... são rotacionadas pela Meta.
   NUNCA usar. Usar `data-testid`, `data-id`, `#main`, `#pane-side`.
3. **Login concluído** = esperar `#pane-side` (estável, independe de idioma).
   O seletor antigo `data-tab="3"` dava timeout.
4. **Caixa de busca** = é um `<input aria-label="Pesquisar...">` (NÃO contenteditable).
5. **Clique no resultado** (`data-testid="list-item-1"`): usar `locator` (re-tenta),
   não `ElementHandle` — senão dá "Element is not attached to the DOM"
   (lista virtualizada re-renderiza).
6. **Emoji**: no DOM vira `<img alt="⏰">`. `innerText` não lê o alt.
   O parser reconstrói o texto trocando emoji pelo `alt` (walk em JS).
7. **IMAGEM (crítico) — ATUALIZADO 16/07**: cada mensagem tem até 2 imagens:
   - thumbnail do preview de link, em `data:` base64 — às vezes é um banner cortado
     (~330×95) ou um thumb minúsculo (72×72), às vezes é grande (500..1254).
   - **foto real do produto em `blob:`** → é a que queremos. Aspecto LIVRE (nem todo
     grupo posta quadrado) e resolução NATIVA variável por grupo: 500, 640, 1024, 1500.
   `storage.py` escolhe a foto real (blob) de maior `naturalWidth` (≥120px, ignorando
   `data:`) e extrai por **CANVAS na resolução nativa** — **NÃO por screenshot**:
   screenshot rasteriza no tamanho RENDERIZADO (330×330 para foto 1024×1024) e herda o
   recorte do CSS. Screenshot só como fallback. Ver "RESOLUÇÃO DAS IMAGENS" p/ o porquê.
   - **TRAZER O BALÃO PARA A VIEWPORT antes de extrair** (`_trazer_para_viewport`): o
     WhatsApp só carrega a foto do que está perto da tela; sem isso a foto nem existe.
   - **ESPERAR carregar** (senão sai borrado + spinner): `storage._esperar_img_carregar`
     espera `img.complete && naturalWidth ≥ 500`, timeout 20s, re-selecionando a cada
     passo; `_GRACE_MIN_S=3.0` incondicional antes de concluir "não tem foto" (o `<img>`
     do blob é criado DEPOIS do balão). **Retry 1x**: a lista é virtualizada e o elemento
     pode "detachar" (Element not attached to DOM).
8. **headless NÃO funciona** com WhatsApp Web (não carrega `#pane-side`).
   Rodar sempre com janela (headless=False).
9. **SWEEP / lista virtualizada (item 3)**: o WhatsApp só mantém no DOM os balões
   perto da viewport. DESCOBERTA CRÍTICA: rolar para BAIXO via JS **NÃO
   re-renderiza** as mensagens já carregadas (só some tela vazia); rolar para
   CIMA carrega o histórico antigo de forma confiável (`scrollHeight` cresce).
   Por isso o sweep (`_varrer_ultimas` em monitor.py) **processa na SUBIDA**
   (extrai + salva imagem em nome `tmp*`), agrupando por iteração; no fim
   **reordena para cronológico** (chunks do mais novo→antigo, revertidos),
   numera, **renomeia as imagens** (`storage.renomear_imagem`) e grava o CSV.
   `--max N` é a nº de mensagens a varrer (aprox.); promoções gravadas = as
   com conteúdo (não-promoções são puladas por `_tem_conteudo`).
   O botão `[data-testid="ic-chevron-down-wide"]` salta pro fim (usado no início).

## Múltiplos grupos (rodízio)
`main.py` aceita 1+ grupos como argumentos posicionais. Fluxo em
`captura_msg_whatsapp(nomes_grupos, ...)`:
1. **Fase sweep** (se `--max N`): para CADA grupo, `abrir_grupo` (troca via busca)
   + `_varrer_ultimas` das últimas ~N. Numeração `numero_da_captura` é GLOBAL e
   contínua entre grupos; imagens não colidem.
2. **Fase rodízio ao vivo**: loop infinito — para cada grupo: troca, vai ao fim,
   processa as NÃO vistas (dedupe global por `data-id`), espera `--seg-grupo` s,
   próximo grupo; ao terminar a lista volta ao 1º. 1ª visita sem sweep faz
   baseline (marca visíveis como vistas).
- A coluna `nome_do_grupo_do_whatsapp` recebe o grupo correto de cada captura.
- Erro ao abrir um grupo (nome não bate) é logado e PULA o grupo (não derruba o run).
- Validado com 3 grupos (`--max 40`): 40+40+23 = 103, nomes de grupo corretos,
  imagens em `./captura/img`, **preço-virando-nome não recorreu** (0 casos).

## Tipos de anúncio: PRODUTO vs CUPOM
O grupo posta 2 tipos de mensagem (coluna `tipo_anuncio`):
- **PRODUTO**: promoção de um produto (nome + preço + foto; pode ter 1 cupom).
- **CUPOM**: mensagem que só divulga cupons (1+), sem produto/preço.

**Classificação** (`_eh_anuncio_cupom`): é CUPOM se a 1ª linha tem `CUPOM/CUPONS`
E (`NOVO/NOVOS/SAIU/+N` OU nome de loja) — ex.: "NOVO CUPOM SHOPEE", "SAIU NOVOS
CUPONS NO MELI", "+1 CUPOM NOVO MELI". ARMADILHA resolvida: "84% COM ESSE CUPOM"
é PRODUTO (não tem NOVO/SAIU/loja). Reforço: 2+ linhas "Cupom:/Código:" e sem
preço De/Por também vira CUPOM.

**Extração dos cupons** (`_extrair_cupons`): cada `Cupom: CODE` / `Código: CODE`
(CODE MAIÚSCULO — evita pegar "https"). Comentário: `Código:` → linha ABAIXO;
`Cupom:` → linha ACIMA. Vários cupons → `cupom` e `comentario_cupom` separados
por ` | ` (índice i do cupom casa com índice i do comentário).
**loja_cupom**: nome CANÔNICO (MERCADO LIVRE, SHOPEE, AMAZON, MAGALU...) por
domínio do link + 1ª linha. **CLASSIFICAR ANTES** evita que "R$79" da descrição
do cupom vire preço.

## Campos extraídos (colunas do CSV)
`nome_do_grupo_do_whatsapp, tipo_anuncio, numero_da_captura, data_hora_captura,
data_hora_mensagem, nome_do_produto, imagem_principal, msg_aviso, preco_de,
preco_por, descricao_pagamento, url, mensagem_final, cupom, comentario_cupom,
loja_cupom`
(além da lista original: `nome_do_produto`, `descricao_pagamento`,
`tipo_anuncio`, `comentario_cupom`, `loja_cupom`)

- **data_hora_mensagem** (novo 12/07): horário REAL da mensagem no WhatsApp
  (`DD/MM/AAAA HH:MM`, precisão de minuto), lido do `data-pre-plain-text` via
  `parser.extrair_data_hora`. É diferente de `data_hora_captura` (=quando o
  agente gravou). Permite separar "hoje vs ontem/madrugada" por linha. Preenchido
  em 100% das linhas no run de 12/07.
- **preço**: análise por LINHA. `preco_de` = `De: R$`; `preco_por` = `Por: R$`;
  se NÃO houver "Por", usa o 1º `R$` que não seja o "de" (msgs que só têm o
  preço final). Linhas de **hype** são ignoradas na busca de preço (senão
  "POR MENOS DE R$70" virava `preco_de`).
- **descricao_pagamento** (novo): texto logo após o preço (ex.: "à vista",
  "via Pix", "parcelado"). Decisão do usuário: aceita qualquer texto curto.
- **url**: 1º link `http` da mensagem (decisão do usuário).
- **cupom**: token MAIÚSCULO logo após "cupom" (ou após "cupom …:"), completo
  (lookahead contra letra acentuada, p/ não cortar "DISPONÍVEL"→"DISPON"),
  ≥4 chars ou com dígito, e fora de uma blocklist (VAI, COM, DISPONÍVEL…).
  Ex.: KERASTASE15, MODASEMPRE, QUEROOFF, FULL15.
- **nome_do_produto**: ANCORADO no preço — a linha qualificada mais próxima
  ACIMA da linha de preço (pula hype/lixo/link/selo "34% OFF"). Fallbacks: a
  heurística antiga (1ª linha substancial) e, por último, o TÍTULO do card de
  link (`previewTitle`, p/ msgs cujo nome só está no preview). Limpa selo
  "% OFF" do início e `!`/pontuação do fim. O filtro do selo só derruba a linha
  quando ela é SÓ o selo (ex.: "34% OFF"); "34% OFF Cafeteira" é mantido/limpo.
  Obs.: se o nome só existe DENTRO da imagem do produto (não no texto), fica
  vazio — não há como ler (raro).
- **msg_aviso**: heurística — 1ª linha "hype" (maiúscula) ou curta terminando em "!".

## Limitações conhecidas / a refinar
- **msg_aviso**: hoje pega só a PRIMEIRA linha de hype. Mensagens com várias
  (ex.: "84% COM ESSE CUPOM 🤯👇🏻") podem pegar a "errada". Decidir se junta todas.
- **nome_do_produto / msg_aviso / cupom** são heurísticos → vão errar em
  formatos novos. Estratégia: coletar casos reais que falharem e refinar.
- `mensagem_final` fica vazio quando a msg não tem "Promoção sujeita...".
- Campo obrigatório faltando → grava vazio (decisão do usuário).
- **Item 2 (espera de imagem)** foi validado só em `--historico` (imagens já
  carregadas). A prova real é ao vivo com mensagem NOVA chegando — mecanismo
  está pronto, mas confirmar quando rodar ao vivo.
- **O marcador só avança por OFERTA capturada**, não por mensagem lida (`_processar` sai
  antes do `atualizar_grupo` quando `_tem_conteudo` é falso). Em período sem promoção o
  marcador fica atrás do presente, e um reinício faz o catch-up reler as mensagens sem
  promoção do intervalo. Não duplica nada — só gasta trabalho. Diagnosticado em 29/07 ao
  investigar um grupo que *parecia* travado.
- **Custo do catch-up subiu por design** (29/07): a hidratação de pendentes gasta scroll, e a
  subida agora lê ~tudo em vez de ~13%. É a troca certa (precisão), mas backlog grande
  demora mais e traz muito mais linha.

## Avisos
- Automatizar WhatsApp Web viola os ToS → risco de ban. Usar número descartável.
- Mensagens "temporárias" somem → polling de 3s reduz, mas não zera, o risco.

## Próximos passos
1. ~~Migrar saída CSV -> Oracle~~ → **FEITO E VALIDADO (17/07)**.
2. ~~Perda de fotos no catch-up~~ → **RESOLVIDA em 19/07** (era o filtro por tamanho
   RENDERIZADO em `_JS_IMG_QUADRADA`, obsoleto desde a migração para canvas).
3. ~~A captura é uma amostra (~39%), não um censo~~ → **RESOLVIDA em 29/07** (era o filtro
   de `_coletar_novas` envenenando balão não hidratado). Aproveitamento 13% → 100%.
4. Casos de nome ainda abertos (raros): (a) nome do produto embutido na linha de
   HYPE toda maiúscula (ex.: "OLHA ISSO 🔥BALDE DOBRÁVEL DE PLÁSTICO...") → nome
   vazio; (b) linha de preço virando nome em msgs de assinatura ("R$ 25,82 na
   recorrência") — não recorreu no teste de 110, monitorar.
5. Vigiar o piso `resolucao_minima=400` (existe origem legítima de 450x450).
6. **Parser pega saudação/hype como oferta** (ex.: "Bom diaaa pessoal", "Domingou com muita
   energia por aí?"). Vira linha sem imagem porque não é produto — o backfill de 19/07
   confirmou que estava certo em não inventar foto. É do PARSER, não da imagem.
7. `TETO_ITENS=2000` pode ser atingido em backlog grande, agora que a subida lê ~tudo.
8. Se algum dia quiserem **censo do passado**: `revarrer_janela.py` está pronto (dry-run +
   proteção de marcador). Hoje o histórico anterior a 29/07 é amostra (~39%) — decisão
   consciente do usuário, que considera esses dados só material de desenvolvimento.

## Imagem dos anúncios de CUPOM
Como CUPOM não tem `nome_do_produto`, o arquivo é nomeado
`<numero>_cupom_<loja>_<1o codigo>.jpeg` (ex.: `13_cupom_MERCADO_LIVRE_BEBESEPETS10.jpeg`)
via `monitor._rotulo_imagem`.

## Feito em 12/07/2026
- **Nova coluna `data_hora_mensagem`** no CSV (storage.COLUNAS + `_montar_linha`
  com param `data_hora_msg`, alimentado por `_gravar_cronologico` e `_processar`).
  Grava o horário REAL da msg (antes só tínhamos a hora da captura).
- **Blocklist de nome (`parser._LIXO_NOME`)**: +`"loja oficial"`, +`"vendido e
  entregue"`. Resolveu nomes-lixo que viravam produto ("loja oficial ✅",
  "Grandes marcas com loja oficial na Shopee", "é vendido e entregue pela
  Amazon"). Verificado: nomes válidos preservados; se o lixo vem antes do nome
  real na msg, o parser pula o lixo e pega o nome certo.
- **Run do dia** (`12_07_2026_12_25.csv`): catch-up desde 11/07 ~17h + rodízio ao
  vivo, 250+ capturas. Qualidade: url/imagem 100%, nome 96%, preco_por 90%,
  preço-virando-nome 0. Loja dominante Mercado Livre (137 vs 4 Shopee); cupons
  fixos ADRENALINA/SUPERPROMO; preço mediano R$69 (R$8,69–R$3.499).

## Feito em 10/07/2026 (itens 1, 2 e 3)
- **Item 1**: nome ancorado no preço; preço só com `R$` + limpeza de pontuação;
  novo campo `descricao_pagamento`; cupom endurecido (só MAIÚSCULO/codey +
  blocklist + padrão "cupom …: CODE"); pula balões sem conteúdo.
- **Item 2**: espera de carregamento da imagem (`naturalWidth`) + retry no
  screenshot (sem borrado/spinner; imagens 330×330). _Obs.: o "nítidas" aqui era
  ilusório — 330×330 já era a foto 1024×1024 reduzida 3×; só descoberto em 16/07._
- **Item 3**: sweep `--max N` (rola o chat, processa na subida, reordena
  cronológico, renomeia imagens). Validado: `--max 30` → 27 promoções em ordem,
  sem imagens temporárias sobrando. Parser 12/12 nos testes de cupom.
