# besave-worker

Lê OFERTA/PRODUTO do Oracle e converte cada linha em `OfertaCard` e `OfertaPagina`
(`docs/CONTRATO.md`). Linhas inválidas são rejeitadas com motivo (CONTRATO §9) e logadas.

- `--dry-run` (BSV-10): lê, converte e imprime contagens.
- `--gerar --saida <dir>` (BSV-11): gera os chunks e o `manifest.json` numa pasta com o layout
  do bucket (`docs/MANIFEST.md`). Upload para o S3 vem em BSV-12; páginas HTML em BSV-21.

Um dos dois modos é obrigatório; eles são mutuamente exclusivos.

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

## Testes

```sh
cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test
```

Os testes não tocam o Oracle nem a AWS. Usam `FakeFonte`, `PublicadorMemoria` e as fixtures de
`packages/contract/fixtures/` como resultado esperado (JSON idêntico byte a byte, mesma ordem de
chaves); chunks e manifest gerados são validados contra `packages/contract/schema/`.
