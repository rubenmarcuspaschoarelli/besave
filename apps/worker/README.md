# besave-worker

Lê OFERTA/PRODUTO do Oracle e converte cada linha em `OfertaCard` e `OfertaPagina`
(`docs/CONTRATO.md`). Linhas inválidas são rejeitadas com motivo (CONTRATO §9) e logadas.

- `--dry-run` (BSV-10): lê, converte e imprime contagens.
- `--gerar --saida <dir>` (BSV-11): gera os chunks e o `manifest.json` numa pasta com o layout
  do bucket (`docs/MANIFEST.md`), mais páginas, CSS, sitemap e robots (BSV-21, ver abaixo).
- `--publicar [--sim]` (BSV-12): o mesmo que `--gerar`, mas no bucket S3, e sincroniza a KVS de
  redirects `id → DS_URL_AFILIADO`. Sem `--sim` só imprime o plano.
- `--ciclo [--env-file <.env>]` (BSV-14): `--publicar --sim` para o Agendador de Tarefas, com
  trava, log em arquivo e alerta no Telegram (ver abaixo). O binário `besave-ciclo` faz o mesmo
  sem janela de console.

Um dos quatro modos é obrigatório; eles são mutuamente exclusivos. `--gerar` e `--publicar` exigem
`--imagens-dir`/`BESAVE_IMAGENS_DIR` (BSV-13, ver abaixo); `--dry-run` não usa.

## Imagens (`BESAVE_IMAGENS_DIR`, BSV-13)

O robô já grava, por oferta, `{BESAVE_IMAGENS_DIR}/{id}/{id}.webp` (tamanho natural) e
`{id}/{id}-small.webp` (lista). O worker **não processa imagem por padrão**: copia para o bucket
com os nomes do contrato, como passo 1 da ordem de publicação (MANIFEST §6), antes de qualquer
chunk:

| origem (robô) | chave no bucket | orçamento |
|---|---|---|
| `{dir}/{id}/{id}-small.webp` | `img/ofertas/{id}-small.webp` | ≤ 25 600 B, lado maior ≤ 320 px |
| `{dir}/{id}/{id}.webp` | `img/ofertas/{id}.webp` | aviso (`WARN`) acima de 300 000 B; publica assim mesmo |

Política de orçamento:

- **Dentro do orçamento**: copia os bytes como vieram (nunca reprocessa sem necessidade).
- **`-small.webp` acima de 25 600 B**: `ajustar_small` decodifica, reduz o lado maior
  progressivamente (320 px → ×¾ a cada volta) e recodifica em WebP sem perdas até caber no
  orçamento; conta em `imagens_reprocessadas` e emite `WARN`.
  **Decisão aceita pelo dono (vira AD em `docs/DECISOES.md`):** o encoder WebP embutido na crate
  `image` (via `image-webp`) só faz VP8L sem perdas — não existe "qualidade" ajustável sem trocar
  para uma crate com libwebp nativo (`webp`/`libwebp-sys`, exige toolchain C, fora da regra de
  dependências do ticket). Reduzir a resolução progressivamente e recodificar sem perdas é o
  fallback aceito: cumpre o mesmo orçamento (≤ 25 600 B, WebP válido, lado ≤ 320 px) com uma
  única dependência pura-Rust.
- **Reaproveitamento**: se as duas chaves já existem no destino, pula (nunca compara conteúdo;
  a imagem de um id não muda depois de publicada).
- **Sem origem** (pasta ausente ou faltando um dos dois arquivos): não publica nada para o id;
  card e página usam `img/placeholder/{slug}.webp`. **Nunca bloqueia a oferta.**
- **Placeholders**: os 10 (um por `Area`, incluindo `OUTROS`) usam o **slug de URL** do
  CONTRATO §2.3 como chave de arquivo (`tech`, `meu-lar`, `esporte-vida`, …), não o valor do enum
  — BSV-20 já referencia esses caminhos. Estão embutidos no binário (`assets/placeholder/*.webp`,
  gerados por `cargo run --example gerar_placeholders`) e são publicados uma vez, reaproveitados
  depois pelo mesmo critério de `existe`.
- **Expurgo**: id que sai do conjunto publicado (CONTRATO §7) tem as duas chaves de imagem
  removidas, junto com a página e a chave na KVS.

```sh
cd apps/worker
BESAVE_FONTE=fake BESAVE_IMAGENS_DIR=/caminho/para/imagens cargo run -- --gerar --saida ./out
```

Relatório no stdout (além das contagens de `--gerar`/`--publicar`):

```
imagens_publicadas: 3
imagens_reaproveitadas: 0
imagens_sem_origem: 1
imagens_reprocessadas: 0
imagens_falhas: 0
imagens_maior_small: 18420
imagens_maior_grande: 142031
```

## Páginas, CSS, sitemap e robots (BSV-21)

Depois dos chunks e antes da KVS (MANIFEST §6 passo 3), `gerar()` publica, nesta ordem:

| chave | conteúdo | headers |
|---|---|---|
| `assets/besave.css` | `assets/css/besave.css`, embutido no binário; o template referencia `/assets/besave.css` | `text/css; charset=utf-8`, `public, max-age=3600, stale-while-revalidate=86400` |
| `oferta/{id}/index.html` | uma página por oferta publicada (ativa ou expirada ≤ 7 dias), `TemplateOferta` (BSV-20) | `text/html; charset=utf-8`, `public, max-age=600, stale-while-revalidate=300` |
| `sitemap-{n}.xml` | só ofertas **ATIVAS**, até 45 000 URLs cada, `<loc>{base}/oferta/{id}/</loc>`, `<lastmod>` = data de `dt_oferta` | `application/xml`, `public, max-age=300` |
| `sitemap.xml` | sitemap index apontando para os `sitemap-{n}.xml` | idem |
| `robots.txt` | `BESAVE_INDEXAVEL` falso: `Disallow: /`; verdadeiro: `Allow: /` + `Sitemap: {base}/sitemap.xml` | `text/plain; charset=utf-8`, `public, max-age=300` |
| `_estado/paginas.json` | índice do que já está no bucket (ver abaixo) | `application/json`, `no-store` |

| variável | obrigatória | uso |
|---|---|---|
| `BESAVE_BASE_URL` | não | base das URLs do sitemap e do `robots.txt`; padrão `https://besave.com.br` (`/` final é removida; precisa começar com `http://` ou `https://`) |
| `BESAVE_INDEXAVEL` | não | `true`/`1` libera a indexação; `false`/`0`/ausente bloqueia (padrão). Outro valor: erro nomeando a variável. Enquanto o site está em `*.cloudfront.net`, fica falso; a virada de DNS liga |

O `<link rel="canonical">` da página continua `https://besave.com.br/oferta/{id}/`, qualquer que
seja `BESAVE_BASE_URL`.

**Só sobe o que mudou.** `_estado/paginas.json` é um objeto plano com o hash16 (SHA-256, 16 hex)
de cada objeto publicado: chave numérica = id da página, `_css`, `_robots` e cada `sitemap*.xml`.
É lido uma vez por execução; objeto com o mesmo hash não é enviado. Sem índice (primeira vez) ou
com índice ilegível, tudo sobe (páginas são idempotentes) e o ciclo segue; nesse caminho (e só
nele) o conjunto anterior de páginas é reconstruído com `listar("oferta/")`, então páginas de ids
que saíram do conjunto são removidas mesmo sem índice, e o índice é regravado. O índice só é
regravado quando muda: execução sem mudança sobe só `manifest.prev.json` e `manifest.json`.

- Produtos vêm do Oracle em lote (`FonteOfertas::produtos`, `IN` com até 1 000 ids por query),
  nunca uma query por oferta; `--dry-run` usa o mesmo caminho.
- Páginas sobem via `gravar_lote` em blocos de 64 (paralelo no S3, BSV-13).
- **Expurgo:** id do índice anterior que saiu do conjunto → `oferta/{id}/index.html` é removida e
  sai do índice e do sitemap. `sitemap-{n}.xml` que deixou de ser gerado é removido.
- Oferta que vira ENCERRADA: a página muda (hash novo, `noindex`) e é reenviada; sai do sitemap
  no mesmo ciclo.
- Orçamento: página acima de 30 720 bytes → erro `PaginaAcimaDoOrcamento { id, bytes }`, o índice,
  a KVS e o manifest não são gravados. Erro de render numa página: loga o id, conta em
  `paginas_falhas`, não publica aquela página e segue. Falha de upload aborta antes do manifest.

Relatório no stdout (além das contagens de chunks e imagens):

```
paginas_renderizadas: 3
paginas_publicadas: 3
paginas_inalteradas: 0
paginas_removidas: 0
paginas_falhas: 0
maior_html: 3284
tempo_render_ms: 3
css_publicado: true
sitemaps_publicados: 2
sitemaps_removidos: 0
robots_publicado: true
```

No plano do `--publicar` (sem `--sim`), as páginas aparecem resumidas:
`páginas a gravar: 25095 (ex.: oferta/1/index.html, …)` e `páginas a remover: N (ex.: …)`, com
até 5 exemplos, em vez de uma linha por página.

## Rodar com a fonte fake (sem banco)

```sh
cd apps/worker
BESAVE_FONTE=fake cargo run -- --dry-run
```

PowerShell: `$env:BESAVE_FONTE='fake'; cargo run -- --dry-run`.

A fake de demonstração tem as 3 ofertas das fixtures, uma linha por motivo de rejeição e uma
inativa há 8 dias (fora da janela de expurgo). Saída:

```
lidas: 10
validas: 3
rejeitadas: 7
  preco_por ausente ou <= 0: 1
  ...
```

## Gerar chunks e manifest (`--gerar`)

```sh
cd apps/worker
BESAVE_FONTE=fake cargo run -- --gerar --saida ./out
```

PowerShell: `$env:BESAVE_FONTE='fake'; cargo run -- --gerar --saida ./out`.

Saída (a pasta espelha o bucket):

```
out/
  manifest.json                         ← único arquivo mutável (MANIFEST §2)
  manifest.json.meta.json
  manifest.prev.json                    ← manifest da execução anterior
  manifest.prev.json.meta.json
  data/chunks/{n}-{hash}.json.br        ← OfertaCard[] do id n*1000 a n*1000+999, Brotli 9
  data/chunks/{n}-{hash}.json.br.meta.json
```

- `hash` = 16 hex do SHA-256 do JSON antes da compressão. Chunk que já existe não é regravado.
- `.meta.json` guarda os headers que o upload vai aplicar (MANIFEST §4):
  `{"content_type":"application/json","content_encoding":"br","cache_control":"public, max-age=31536000, immutable"}`
  nos chunks; no manifest, `content_encoding: null` e `public, max-age=300, stale-while-revalidate=60`.
- Ordem: chunks → `manifest.prev.json` → `manifest.json`. Depois, remove de `data/chunks/` o que
  não está no manifest novo nem no anterior (um chunk substituído dura mais um ciclo).
- Chunk comprimido acima de 61 440 bytes: erro, nada é gravado.
- Mesmas rejeições do `--dry-run` (card sem `id_produto` não é publicado: a página não existiria).

Relatório no stdout:

```
lidas: 10
validas: 3
rejeitadas: 7
  ...
chunks_escritos: 1
chunks_reaproveitados: 0
chunks_removidos: 0
bytes_totais: 265
maior_chunk: n=5 bytes=265
versao: 20260925160252
tempo: 0.01s
```

As datas da fake de demonstração acompanham o relógio, então cada execução com ela regrava o
chunk 5. Com a fonte parada (testes, Oracle sem mudança) a segunda execução grava 0 chunks.

## Publicar no S3 e na KVS (`--publicar`)

```sh
cd apps/worker
export BESAVE_BUCKET=besave-site
export BESAVE_KVS_ARN=arn:aws:cloudfront::<conta>:key-value-store/<id>
export BESAVE_IMAGENS_DIR=/caminho/para/imagens/do/robo
export AWS_REGION=sa-east-1          # região do bucket
export AWS_PROFILE=besave-worker     # ou AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
cargo run --release -- --publicar          # plano: não escreve nada
cargo run --release -- --publicar --sim    # executa
```

| variável | obrigatória | uso |
|---|---|---|
| `BESAVE_BUCKET` | sim | bucket de destino |
| `BESAVE_KVS_ARN` | sim | ARN da KeyValueStore da Function `/ir/{id}` |
| `BESAVE_IMAGENS_DIR` | sim | raiz `{id}/{id}[-small].webp` do robô (BSV-13, ver seção Imagens) |
| `AWS_REGION` | sim (ou região no perfil) | região do bucket |
| credenciais | sim | só pela cadeia padrão do SDK: `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`, `AWS_PROFILE`, SSO |

Nenhuma credencial vai em arquivo versionado, argumento de CLI ou log. `BESAVE_BUCKET` e
`BESAVE_KVS_ARN` são checadas antes de abrir o Oracle.

**Plano (sem `--sim`).** O worker lê o destino de verdade (`manifest.json`, `HeadObject` dos
chunks, `ListObjectsV2`, `_estado/redirects.json`, `DescribeKeyValueStore` e, só na reconstrução,
`ListKeys`) e imprime cada escrita que faria, sem executá-la:

```
PLANO: nada foi escrito. Rode com --sim para executar.
bucket: besave-site
kvs: arn:aws:cloudfront::…:key-value-store/…
S3:
  gravar data/chunks/2-bfa8be13c9003787.json.br (104 B, public, max-age=31536000, immutable)
  gravar data/chunks/5-ac3ee4364a3fd04e.json.br (106 B, public, max-age=31536000, immutable)
  gravar manifest.prev.json (334 B, public, max-age=300, stale-while-revalidate=60)
  gravar manifest.json (431 B, public, max-age=300, stale-while-revalidate=60)
  remover data/chunks/1-6abb38a0bc3368d4.json.br
KVS (aplicada antes do manifest.json):
  putKey 2001 https://loja.example/2001
  deleteKey 5413
lidas: …
redirects_put: 1
redirects_del: 1
redirects_total: 3
```

**Execução (`--sim`).** Ordem de MANIFEST §6: imagens → chunks novos → CSS, páginas, sitemaps,
robots e `_estado/paginas.json` (BSV-21) → KVS → `_estado/redirects.json` → `manifest.prev.json` →
`manifest.json` → remoção de chunks órfãos. Se a KVS falhar, o manifest não é gravado e o anterior
continua valendo.

- Headers de cada objeto pela tabela de MANIFEST §4 (`meta_para`): chunks com
  `Content-Encoding: br` e `immutable`; manifest com `max-age=300, stale-while-revalidate=60`.
- Chunk que já existe (`HeadObject`) não é regravado; o nome carrega o hash.
- KVS: só o diff, em chamadas `UpdateKeys` de até 50 chaves (puts e deletes no mesmo lote),
  com `If-Match` do ETag. Chave não numérica na KVS é ignorada. URL vazia, URL > 1 024 bytes ou
  KVS > 5 MB: erro, nada é escrito na KVS nem no manifest. Acima de 40 000 entradas: `WARN`
  (MANIFEST §5).
- **A KVS espelha o conjunto publicado** (`ST_ATIVO = 1 OR DT_DESATIVACAO >= hoje - 7`), não
  `ST_ATIVO`: oferta expirada mantém o redirect até o expurgo e some junto com a página.
- **Índice da KVS (`_estado/redirects.json`, BSV-12c).** `{"kvs_item_count": N, "kvs_etag":
  "…", "urls": {"<id>": "<hash16 da URL>"}}`, `application/json`, `no-store`. Guarda o hash
  (SHA-256, 16 hex), nunca a URL de afiliado. Por ciclo: 1 `GetObject` do índice + 1
  `DescribeKeyValueStore`.
  - **Modo `indice`:** índice legível e `ETag`/`ItemCount` iguais aos da KVS. O diff e a base do
    expurgo de imagens saem do índice; `ListKeys` não é chamado.
  - **Modo `reconstrucao`:** índice ausente, ilegível ou KVS alterada por fora. `WARN` com o motivo
    (`indice_ausente`, `indice_ilegivel`, `etag_divergente`, `item_count_divergente`), um
    `ListKeys` completo, diff e índice reconstruído.
  - O diff vai com `If-Match` do `ETag` lido no início do ciclo (sem `DescribeKeyValueStore` extra;
    os lotes seguintes encadeiam o `ETag` devolvido). KVS alterada nesse meio-tempo →
    `ConflictException` → erro `Concorrencia`: o ciclo aborta antes do índice e do manifest, e o
    seguinte reconstrói.
  - Depois do diff, o índice é gravado com o `ETag`/`ItemCount` da última `UpdateKeys`, só quando
    muda. Falha ao gravar o índice aborta antes do manifest; o ciclo seguinte reconstrói.
  - A saída traz `redirects_modo` e `redirects_motivo_reconstrucao` (`-` no modo `indice`). No
    `--gerar` local a KVS é uma memória vazia a cada execução, então o modo é sempre
    `reconstrucao`.
- Segunda execução sem mudança: 0 chunks e 0 put/del na KVS; `manifest.json` e
  `manifest.prev.json` são regravados (`versao` nova).
- **Imagens em paralelo (BSV-13):** o trait `Publicador` tem `existem`/`gravar_lote` (checagem e
  gravação em lote); o default é sequencial (`PublicadorLocal`/`PublicadorMemoria` não mudam).
  `PublicadorS3` sobrescreve os dois com um pool de até 16 pares `HeadObject`/`PutObject` em voo
  — `gerar()` não muda: `imagens::publicar_imagens` só troca `existe`/`gravar` por
  `existem`/`gravar_lote` em blocos de 64 ids, e o paralelismo aparece automaticamente quando o
  destino é o S3.
- Retentativas: as do SDK.

Permissões IAM mínimas: `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`, `s3:ListBucket` no
bucket; `cloudfront-keyvaluestore:DescribeKeyValueStore`, `ListKeys`, `UpdateKeys` na KVS.

## Rodar contra o Oracle

Pré-requisitos:

- **Oracle Instant Client ≥ 19, 64 bits**, apontado por `BESAVE_ORACLE_CLIENT_DIR` ou no `PATH`
  (Windows) / `LD_LIBRARY_PATH` (Linux). A crate `oracle` embute o ODPI-C e carrega o OCI em
  runtime: compila sem o client, mas falha ao conectar sem ele. Com `BESAVE_ORACLE_CLIENT_DIR`
  o `PATH` é ignorado; sem ela, um `oci.dll` 32 bits antes no `PATH` (ex.: o do próprio XE em
  `C:\oraclexe\app\oracle\product\11.2.0\server\bin`) dá `DPI-1047`.
- Variáveis de ambiente (nunca em arquivo versionado; `.env` está no `.gitignore`):

| variável | obrigatória | exemplo |
|---|---|---|
| `BESAVE_ORACLE_DSN` | sim | `localhost:1521/XE` |
| `BESAVE_ORACLE_USER` | sim | |
| `BESAVE_ORACLE_PASS` | sim | |
| `BESAVE_ORACLE_CLIENT_DIR` | não | `C:\oraclexe\app\instantclient_19_30` |
| `BESAVE_ORACLE_TZ` | não | fuso das colunas `DATE`, só offset `±HH:MM`; padrão `-03:00` |
| `BESAVE_FONTE` | não | `oracle` (padrão) ou `fake` |
| `BESAVE_MAPEAMENTO` | não | padrão `../../packages/contract/mapeamento.json` |
| `RUST_LOG` | não | nível de log; padrão `info` |

```sh
cd apps/worker
BESAVE_ORACLE_DSN=localhost:1521/XE BESAVE_ORACLE_USER=... BESAVE_ORACLE_PASS=... \
  cargo run --release -- --dry-run
```

Para gerar os arquivos, troque `--dry-run` por `--gerar --saida ./out`.

O worker lê `OFERTA` e `PRODUTO` do schema do usuário conectado, com o filtro de publicação
`ST_ATIVO = 1 OR DT_DESATIVACAO >= SYSDATE - 7`. Não lê `DT_ULT_ATUALIZACAO`: funciona com ou
sem a coluna. As colunas `DATE` são tratadas como hora local no offset `BESAVE_ORACLE_TZ` e
convertidas para UTC só com aritmética de `DATE` (sem `FROM_TZ`/`SYS_EXTRACT_UTC`, que dão
`ORA-01882` com Instant Client 19 no XE 11.2). Offset fixo porque o arquivo de fuso do XE 11.2
ainda aplica horário de verão em `America/Sao_Paulo`.

Rejeições saem no log (`WARN ... id=… motivo=…`) e no relatório. Erro de conexão ou de SQL
encerra com código ≠ 0 e a mensagem do Oracle, sem panic.

## Execução agendada (`--ciclo` e `besave-ciclo`, BSV-14)

O ciclo é o `--publicar --sim` feito para o Agendador de Tarefas do Windows: a cada 5 min,
com trava (nunca dois ciclos juntos), log em arquivo e alerta no Telegram quando um ciclo falha.
Ciclo ok é silencioso (só log). Não há loop interno: quem repete é o Agendador.

Dois executáveis, o mesmo caminho (`worker::ciclo::executar`):

| executável | uso | saída |
|---|---|---|
| `besave-ciclo.exe --env-file <arq>` | o Agendador | **sem janela de console**; nada em stdout/stderr, só o log em arquivo e o código de saída |
| `besave-worker.exe --ciclo --env-file <arq>` | rodar à mão, ver o que acontece | log também no stderr e relatório no stdout |

```powershell
besave-worker.exe --ciclo --env-file C:\besave\worker.env
```

| código de saída | quando |
|---|---|
| 0 | ciclo publicado, ou pulado porque o anterior ainda roda |
| 1 | falha no ciclo (Oracle, S3, KVS…) |
| 2 | configuração: `.env` ausente/ilegível, variável obrigatória ausente ou inválida, `TELEGRAM_*` pela metade, região AWS ausente |

### 1. Bot do Telegram

1. No Telegram, abra o **@BotFather**, mande `/newbot`, escolha nome e usuário. Ele responde com
   o **token** (`123456789:AA…`). Guarde só no `.env`.
2. Mande qualquer mensagem para o bot novo (ou adicione-o a um grupo e mande uma mensagem lá).
3. No navegador, abra `https://api.telegram.org/bot<TOKEN>/getUpdates` e copie
   `"chat":{"id": …}` — é o **chat_id** (negativo em grupo). Não cole essa URL em lugar nenhum:
   ela contém o token.

### 2. `.env` fora do repositório

Exemplo `C:\besave\worker.env` (o `.env` não entra no repo). **Caminhos do Windows entre aspas
simples**: sem aspas, `\` é lido como escape e o `.env` fica ilegível (código 2).

```ini
BESAVE_FONTE=oracle
BESAVE_ORACLE_DSN=localhost:1521/XE
BESAVE_ORACLE_USER=...
BESAVE_ORACLE_PASS=...
BESAVE_ORACLE_CLIENT_DIR='C:\oracle\instantclient_19_25'
BESAVE_MAPEAMENTO='C:\git\besave\packages\contract\mapeamento.json'
BESAVE_IMAGENS_DIR='C:\robo\imagens'
BESAVE_BUCKET=...
BESAVE_KVS_ARN=arn:aws:cloudfront::...:key-value-store/...
BESAVE_BASE_URL=https://...
AWS_REGION=sa-east-1
AWS_PROFILE=besave-worker
TELEGRAM_BOT_TOKEN=123456789:AA...
TELEGRAM_CHAT_ID=-100...
```

`BESAVE_MAPEAMENTO` precisa ser absoluto: o padrão é relativo à pasta do repo, e a tarefa roda na
pasta do executável. Variável já definida no ambiente **vence** a do `.env`.

Variáveis novas:

| variável | obrigatória | uso |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | não (as duas ou nenhuma) | token do bot; nunca vai para o log |
| `TELEGRAM_CHAT_ID` | não (as duas ou nenhuma) | chat que recebe os alertas |
| `BESAVE_LOG_DIR` | não | pasta dos logs; padrão `%LOCALAPPDATA%\besave\logs` |
| `BESAVE_LOCK` | não | arquivo de trava; padrão `%LOCALAPPDATA%\besave\worker.lock` |
| `BESAVE_DESTINO_LOCAL` | não (ensaio/teste) | publica numa pasta (layout do bucket) com KVS em memória, em vez do S3/KVS; dispensa `BESAVE_BUCKET`/`BESAVE_KVS_ARN` |
| `BESAVE_AGORA` | não (ensaio/teste) | segundos Unix que fixam o relógio; **só vale com `BESAVE_DESTINO_LOCAL`** |

Sem as duas `TELEGRAM_*`, o alerta fica desligado (`INFO alerta desligado` no log), útil em dev.

### 3. Registrar a tarefa

```powershell
cd apps\worker
cargo build --release
# Copie o .exe para uma pasta estável: um build novo não sobrescreve o .exe enquanto a tarefa roda.
Copy-Item "$env:CARGO_TARGET_DIR\release\besave-ciclo.exe" C:\besave\   # ou target\release\
.\scripts\registrar-tarefa.ps1 -Executavel C:\besave\besave-ciclo.exe -EnvFile C:\besave\worker.env
```

A tarefa "Besave Worker" roda a cada 5 min, indefinidamente, e 1 min após o logon; não abre
nova instância se a anterior ainda roda; para a execução que passar de 20 min; roda com o seu
usuário **somente quando você está conectado** (o Oracle e as imagens estão no seu perfil), sem
senha gravada. Rodar o script de novo atualiza a tarefa. O script só aceita o `besave-ciclo.exe`,
que não abre janela de console.

Histórico: Agendador de Tarefas → Biblioteca → "Besave Worker" → aba Histórico (habilite em
"Ações → Habilitar Histórico de Todas as Tarefas", se estiver desligado); a coluna "Resultado da
última execução" mostra o código de saída (`0x0`, `0x1`, `0x2`). Remover:

```powershell
.\scripts\remover-tarefa.ps1
```

### Logs

Um arquivo por dia de Brasília em `%LOCALAPPDATA%\besave\logs\besave-worker.AAAA-MM-DD.log`.
No início de cada ciclo, arquivos com mais de 14 dias são apagados. Cada ciclo ok deixa uma
linha `relatorio` em `chave=valor`:

```
2026-10-01T13:05:41Z  INFO worker::execucao: relatorio lidas=11630 validas=11598 rejeitadas=32 chunks_escritos=1 … tempo_ms=24310
```

Falha deixa uma linha `ERROR … falha no ciclo fase=… variante=… erro=…`. Ciclo pulado pela trava:
`INFO … ciclo anterior em andamento`. A trava (`worker.lock`) guarda `pid=… inicio=… fim=…`; se
um processo morre sem soltar, o próximo ciclo a toma e loga `WARN trava órfã tomada`.

### Alerta

Mensagem de falha (sem URL, token ou caminho):

```
⚠️ Besave worker: falha no ciclo
erro: Redirects::Kvs
fase: redirects
horário: 01/10/2026 10:05 (-03:00)
host: BESAVE-PC
```

- Mesma variante de erro: no máximo 1 mensagem a cada 2 h. Variante diferente alerta na hora.
- Primeiro ciclo ok depois de falhas: `✅ Besave worker: recuperado após N falhas (desde HH:MM)`.
- Estado em `%LOCALAPPDATA%\besave\alerta.json` (pode apagar para zerar).
- Telegram fora do ar: `WARN` no log, o código de saída não muda e o envio é tentado de novo no
  ciclo seguinte.

Fases: `env_file`, `config`, `trava`, `conexao_oracle`, `contexto_aws`, `leitura_fonte`,
`imagens`, `chunks`, `paginas`, `redirects`, `manifest`, `s3`.

## Testes

```sh
cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test
```

O teste de desempenho (30 000 cards em ≤ 30 s) é `#[ignore]`: instável sob carga, fica fora do
CI. Rode localmente com `cargo test -- --ignored`. A parte funcional dos 30 000 cards (gera,
valida, conta) roda no `cargo test` normal, sem limite de tempo.

Os testes não tocam o Oracle nem a AWS. Usam `FakeFonte`, `PublicadorMemoria` e as fixtures de
`packages/contract/fixtures/` como resultado esperado (JSON idêntico byte a byte, mesma ordem de
chaves); chunks e manifest gerados são validados contra `packages/contract/schema/`.
