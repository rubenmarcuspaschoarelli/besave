# CaptureAmazon (Besave)

Captura os dados das ofertas que chegam na fila `BESAVE.OFERTA_FILA_CAPTURA`
(Oracle, alimentada pelo AgenteCapturaWhatsapp): abre a URL de cada oferta
(Amazon, Mercado Livre, Shopee e outras), grava preço, imagens, link de afiliado,
produto, cupom e publica em `BESAVE.OFERTA`.

Histórico detalhado das decisões: `resumo.md`.

## Estrutura

```
CaptureAmazon/
├── main.py                  # CORE: captura (rodar com --monitorar em produção)
├── manutencao_arquivos.py   # CORE: rotina periódica de compactação/arquivo de destino/
├── core/                    # CORE: módulos compartilhados (banco, browser, ofertas, imagens...)
│   └── caminhos.py          #   pastas de saída (destino/log, bkp, img, arquivo)
├── stores/                  # CORE: uma classe por loja
├── programas_ajuste/        # AJUSTE: backfills, correções, dumps, logins manuais, testes
├── conf/
│   ├── config.example.json  # modelo versionado (sem senha)
│   └── config.json          # config real -- NÃO vai p/ o git (senha do banco + estado)
├── sql/                     # DDL e stored procedures (.STP)
├── Docs/                    # especificações
└── destino/                 # NÃO vai p/ o git
    ├── log/                 #   CSVs de captura, logs/TSV de backfills, dumps HTML
    ├── bkp/                 #   backups gerados antes de alterar banco/arquivos
    │                        #   + zips de manutencao_arquivos.py (log_*, bkp_*, img_*_a_*)
    └── img/<ID_OFERTA>/     #   fotos capturadas de cada oferta
```

## Regras

1. **Core x ajuste.** Só fica na raiz o que roda todo dia (`main.py`,
   `manutencao_arquivos.py`) + os pacotes `core/` e `stores/`. Qualquer
   programa de ajuste, backfill, correção pontual, diagnóstico, login manual ou
   teste vai para **`programas_ajuste/`**.
2. **Todo script em `programas_ajuste/` começa com `import _raiz`** (antes dos
   imports de `core`/`main`/`stores`). Isso coloca a raiz no `sys.path` e como
   pasta atual, então o script roda igual de qualquer lugar:
   ```
   python programas_ajuste/backfill_qt_opinioes.py --dry-run
   ```
3. **Arquivos gerados** -- usar sempre `core/caminhos.py`, nunca `'destino'` solto:
   - CSV, log, TSV, dump HTML → `em_log('nome')` → `destino/log/`
   - backup antes de alterar dados → `em_bkp('nome')` → `destino/bkp/`
   - fotos → `IMG_DIR` → `destino/img/<ID_OFERTA>/`
4. **Nunca rodar dois processos Playwright ao mesmo tempo** (o `.chrome_perfil`
   é um só para todas as lojas). Antes de um backfill com navegador, parar o
   `main.py --monitorar`.

## Rodando

```
python main.py --monitorar --intervalo 3    # produção
python main.py --help
```

No `--monitorar` o `controle.ultimo_id_processado` do `config.json` é só informativo: o monitor lê a fila
inteira (`ST_CAPTURA = '0'`) e ignora o ponteiro. Ponteiro parado por horas (linha retida ou queda de
conexão seguram o avanço até reiniciar) não perde oferta. Ele só vale para o lote sem `--monitorar`.

## Manutenção de espaço (VPS)

`manutencao_arquivos.py` compacta o que é antigo em zips em
`destino/bkp/` e apaga os originais (só depois de conferir o zip). Os `.zip`
que já estão em `destino/bkp/` nunca são compactados de novo.

| pasta          | padrão   | zip                      |
|----------------|----------|--------------------------|
| `destino/log`  | 30 dias  | `log_AAAA-MM.zip`        |
| `destino/bkp`  | 30 dias  | `bkp_AAAA-MM.zip`        |
| `destino/img`  | 60 dias  | `img_<ID_INICIAL>_a_<ID_FINAL>.zip`, lotes de 1000 pastas (`--lote-img`), sem compressão (foto já é comprimida) |

O padrão de `img` fica acima da validade das ofertas (45 dias), para não
arquivar fotos de ofertas ainda ativas que os backfills de imagem leem do disco.

```
python manutencao_arquivos.py                          # simula (padrão)
python manutencao_arquivos.py --executar               # arquiva de verdade
python manutencao_arquivos.py --executar --copiar-para F:\backup_besave
python manutencao_arquivos.py --restaurar 12345        # volta destino/img/12345/
```

Agendar 1x/semana (Agendador de Tarefas no Windows / cron na VPS) com
`--executar` e copiar os `.zip` de `destino/bkp/` para fora da máquina (`--copiar-para`
ou sync para o S3).

## Configuração

Copiar `conf/config.example.json` para `conf/config.json` e preencher
`db.senha`. `s3.raiz` é a pasta local espelhada no S3 do site (padrão
`E:\Work\besave\server\s3`; dentro dela `ofertas/img/` e `produtos/img/`) --
na VPS, apontar para o caminho de lá. Requer Oracle Instant Client 19c (`db.instant_client_dir`) e
`pip install -r requirements.txt` + `playwright install chromium`.
No Linux, `chmod 600 conf/config.json` (senha do banco e segredo de afiliado): o robô mantém o modo
que encontrar ao gravar `controle` (BSV-60).

## Shopee pela API de afiliados (BSV-59)

Com `shopee_afiliado.habilitado: true` no `conf/config.json`, a linha da Shopee não abre o navegador:
o robô resolve o link curto `s.shopee.com.br` (um pedido sem seguir redirect, até 3 saltos, só para
hosts da Shopee), consulta o produto (`productOfferV2` por `shopId`/`itemId`) e gera o link de afiliado
(`generateShortLink` da URL limpa `https://shopee.com.br/product/<shopId>/<itemId>`, nunca a URL do
grupo, que traz o `utm_source`/afiliado de terceiro). Amazon e Mercado Livre não mudam.

| chave da captura | campo da API |
|---|---|
| `produto_titulo` | `productName` |
| `preco_1` (`VR_PRECO_1`) | `price`, em `Decimal` com 2 casas |
| `avaliacao_nota` | `ratingStar` |
| `quantidade_vendida` | `sales` |
| `url_afiliado` (`DS_URL_AFILIADO`) | `shortLink` |
| `taxa_comissao_afiliado` | `commissionRate` (`"0.13"` → `13%`) |
| `id_produto_afiliado` (`DS_ID_PRODUTO_AFILIADO`) | `<shopId>.<itemId>` |
| foto `img_1.jpg` | `imageUrl` (uma foto) |

**O que se perdeu** em relação à página: descrição, detalhes técnicos, país de origem, quantidade de
avaliações e a galeria com várias fotos. `priceMin`/`priceMax` (faixa de variantes) e `shopName` não são
gravados. O preço final continua vindo da mensagem do grupo (`core/precos.py`).

**Ligar e desligar:** `habilitado: true` liga; `false` ou o bloco ausente volta ao navegador no próximo
lote, sem reiniciar nada além do robô. O código do navegador da Shopee continua no lugar.

**Timeout:** `timeout_segundos` vale por chamada (padrão 20). Acima de 60 vira 60, e abaixo de 1 ou
inválido vira 20, sempre com `[WARN]` no log. Uma linha faz até 5 chamadas e precisa caber nos 10 min do
batimento (BSV-57).

**Credencial:** `app_id` e `app_secret` só no `conf/config.json` da máquina (fora do git; o
`config.example.json` traz valores fictícios). Nunca aparecem em log, CSV, Telegram nem evidência; o log
diz só `shopee api: ok item=<itemId>` ou o motivo. O relógio da máquina precisa seguir o NTP: a assinatura
leva o horário e a API recusa pedido velho (`Request Expired`).

**Motivos** (`DS_CAPTURA`):

| motivo | o que é | linha |
|---|---|---|
| `api_indisponivel` | timeout, rede, HTTP ≠ 200, JSON ilegível, código de erro desconhecido ou exceção inesperada no caminho da API (log com tipo e mensagem redigidos) | retida (`shopee_api_indisponivel`, `'0'`) |
| `api_credencial` | erro `10020`: `Invalid Signature` (conferir `app_id`/`app_secret`) ou `Request Expired` (relógio) | retida |
| `api_limite` | erro `10030`: passou de 8.000 chamadas por hora | retida |
| `fora_do_programa` | o produto não tem oferta de afiliado (ou não existe; a API não distingue) | `'9'` |
| `item_divergente` | a API devolveu outro item, mais de um, ou sem preço | `'9'` |
| `url_nao_reconhecida` | o link não levou a uma URL de produto da Shopee | `'9'` |

A API responde HTTP 200 também nos erros; o robô decide pelo array `errors`. Linha retida trava o ponteiro
e conta para a pausa da Shopee (BSV-55): 3 falhas seguidas pausam só a Shopee por `bloqueio.pausa_minutos`,
com aviso no Telegram (motivo e mensagem da API; em `api_credencial`, "conferir app_id/app_secret"),
lembrete a cada 6 h e "voltou" quando a API responde de novo.

Retidas antigas da Shopee (preço velho) são descartadas antes de ligar:
`sql/BSV-59_retidas_shopee.sql`.

## Navegador quebrado (BSV-65)

Em 18–23/11 e em 24/11 o Chromium morreu com o processo Python vivo: toda navegação dava `Page crashed`,
milhares de linhas foram para `'9'` e nada avisou. Agora o robô reconhece o navegador quebrado, não queima a
linha, se recupera sozinho e avisa.

**Sinais** (uma função só, `core/navegador.sinal`; mensagem da exceção em minúsculas): `page crashed`,
`target crashed`, `has been closed`, `target closed`, `target page, context or browser`. O evento `crash` da
aba também conta (vale para as fases que engolem exceção, como imagens).

**A linha:** navegador quebrado em qualquer fase (`goto`, `prepare`, captura, imagens, link de afiliado, página
ponte) deixa a linha em `'0'` (`oracle=retida(0)` no log, com o erro em `status=`), sem gravar `DS_CAPTURA`, e o
ponteiro para antes dela. O lote para ali: as linhas seguintes não são tentadas na aba quebrada. A linha não
renova o batimento.

**Timeouts:** `TimeoutError` no `goto` de loja por navegador também retém a linha. **3 seguidos** (qualquer loja,
sem uma linha `ok` no meio) disparam a recuperação. A mesma linha com **3 timeouts** na execução vai para `'9'`
com o motivo de sempre (`erro: TimeoutError: …`): link morto não trava o ponteiro para sempre.

**Recuperação**, antes da próxima linha:

1. fecha a aba e abre outra no mesmo contexto;
2. se abrir a aba falhar, ou se quebrar de novo sem nenhuma linha `ok` desde a recuperação anterior (inclusive
   na primeira navegação da aba nova), fecha o contexto e relança o navegador com o mesmo perfil
   (`.chrome_perfil`), refazendo a permissão de área de transferência do link de afiliado;
3. se o relançamento falhar, ou se seria o **3º relançamento em 60 min**, sai com **código 3**, sem gravar
   batimento. O `Restart=on-failure` da unidade sobe o robô de novo em 30 s; se não subir, o vigia reinicia
   pelo prazo do batimento (BSV-57).

| código de saída | quando |
|---|---|
| 0 | fim normal (lote) ou Ctrl+C |
| 1 | sem Oracle, CSV ausente, Chrome não abriu no arranque, opções incompatíveis |
| 2 | `--sem-perguntas` com navegador aberto no arranque (BSV-55) |
| 3 | navegador não reabriu, ou 3 relançamentos em 60 min (BSV-65) |

**Telegram** (bloco `alerta`, como a pausa por loja; uma mensagem por ocorrência, sem URL nem caminho):

- `Robo das lojas: navegador quebrou (Page crashed); aba nova. 1 linha(s) retida(s).` — o sinal pode ser
  `3 timeouts seguidos`; a ação, `navegador relancado`;
- `Robo das lojas: navegador nao reabriu; saindo (codigo 3) para o vigia reiniciar.`;
- `Robo das lojas: navegador voltou (N linha(s) retida(s) voltam a ser processadas).` — na primeira linha `ok`
  de loja por navegador depois da ocorrência (a Shopee pela API não conta).

**Vigia:** o batimento leva `ultimo_ok_navegador` (última linha `ok` por navegador; antes da primeira, a partida
do processo) e `tentativas_navegador` (linhas por navegador sem `ok` desde então; Shopee pela API e loja em pausa
não contam). Com `tentativas_navegador ≥ 10` e o último `ok` há mais de 60 min, o vigia avisa (sem reiniciar),
lembra a cada 2 h e diz "voltou" quando o campo anda.

**Diagnóstico** (a causa ainda não se sabe): em cada recuperação, no relançamento preventivo e no evento
`crash`, o log ganha

```
[navegador] diagnostico: mem_disponivel=4300 MB | chromium=12 | rss_chromium=1500 MB | maior=600 MB | desde_lancamento=95 min | navegacoes=210
```

`MemAvailable` do `/proc/meminfo`; quantidade, soma e maior RSS dos Chromium descendentes do robô (de `/proc`,
sem `ps` nem root); minutos e navegações desde o último lançamento. Leitura que falha vira `?`; fora do Linux
só os dois últimos. Não vai ao Telegram. `grep 'diagnostico:' destino/log/main_monitorar.log`.

**Relançamento preventivo:** `monitor.relancar_navegador_horas` (opcional; padrão `6`; `0` desliga; inválido
vira `6` com `[WARN]`). Entre lotes, nunca no meio de uma linha (na janela noturna, na rodada), o robô loga o
diagnóstico, fecha o contexto e relança pelo mesmo caminho da recuperação. Não manda Telegram e não conta para os
3 em 60 min; se falhar, sai com código 3 como acima.

**Reprocessar por motivo** (SQL do dono, depois de corrigir a causa; só ofertas de até 24 h):

```sql
UPDATE OFERTA_FILA_CAPTURA SET ST_CAPTURA = '0'
 WHERE ST_CAPTURA = '9'
   AND (DS_CAPTURA LIKE '%Page crashed%' OR DS_CAPTURA LIKE '%has been closed%'
        OR DS_CAPTURA LIKE '%Target closed%' OR DS_CAPTURA LIKE '%Timeout 60000ms exceeded%')
   AND DT_OFERTA >= SYSDATE - 1;
```
