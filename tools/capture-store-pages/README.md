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
