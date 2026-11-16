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
