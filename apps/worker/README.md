# besave-worker

Lê OFERTA/PRODUTO do Oracle e converte cada linha em `OfertaCard` e `OfertaPagina`
(`docs/CONTRATO.md`). Linhas inválidas são rejeitadas com motivo (CONTRATO §9) e logadas.
Nesta versão (BSV-10) só existe `--dry-run`: lê, converte e imprime contagens. Geração e
publicação vêm em BSV-11 e BSV-12.

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

## Rodar contra o Oracle

Pré-requisitos:

- **Oracle Instant Client ≥ 19, 64 bits**, no `PATH` (Windows) ou em `LD_LIBRARY_PATH` (Linux).
  A crate `oracle` embute o ODPI-C e carrega o OCI em runtime: compila sem o client, mas falha
  ao conectar sem ele. Um client 32 bits no `PATH` antes do 64 bits também faz a conexão falhar.
  O Instant Client 19 conecta no Oracle XE 11.2.
- Variáveis de ambiente (nunca em arquivo versionado; `.env` está no `.gitignore`):

| variável | obrigatória | exemplo |
|---|---|---|
| `BESAVE_ORACLE_DSN` | sim | `localhost:1521/XE` |
| `BESAVE_ORACLE_USER` | sim | |
| `BESAVE_ORACLE_PASS` | sim | |
| `BESAVE_ORACLE_TZ` | não | fuso das colunas `DATE`; padrão `-03:00` |
| `BESAVE_FONTE` | não | `oracle` (padrão) ou `fake` |
| `BESAVE_MAPEAMENTO` | não | padrão `../../packages/contract/mapeamento.json` |
| `RUST_LOG` | não | nível de log; padrão `info` |

```sh
cd apps/worker
BESAVE_ORACLE_DSN=localhost:1521/XE BESAVE_ORACLE_USER=... BESAVE_ORACLE_PASS=... \
  cargo run --release -- --dry-run
```

O worker lê `OFERTA` e `PRODUTO` do schema do usuário conectado, com o filtro de publicação
`ST_ATIVO = 1 OR DT_DESATIVACAO >= SYSDATE - 7`. Não lê `DT_ULT_ATUALIZACAO`: funciona com ou
sem a coluna. As colunas `DATE` são tratadas como hora local no fuso `BESAVE_ORACLE_TZ` e
convertidas para UTC no SQL. O padrão é offset fixo porque o arquivo de fuso do XE 11.2 ainda
aplica horário de verão em `America/Sao_Paulo`.

Rejeições saem no log (`WARN ... id=… motivo=…`) e no relatório. Erro de conexão ou de SQL
encerra com código ≠ 0 e a mensagem do Oracle, sem panic.

## Testes

```sh
cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test
```

Os testes não tocam o Oracle. Usam `FakeFonte` e as fixtures de `packages/contract/fixtures/`
como resultado esperado (JSON idêntico byte a byte, mesma ordem de chaves).
