# BSV-11 · Worker: geração de chunks + manifest em disco (sem S3)

**Papel:** Backend Rust · **Pasta:** `apps/worker/` · **Depende de:** BSV-10 (mergeado), MANIFEST.md §2, §3, §6, §7; CONTRATO.md §3, §7

## Contexto
BSV-10 entregou `FonteOfertas`, `para_card`/`para_pagina`, `Manifest`/`ChunkRef` em `modelo.rs`
e o `--dry-run`. Este ticket transforma cards em **arquivos**: chunks comprimidos, endereçados por
hash, e o `manifest.json`, escritos numa pasta local que espelha o layout do bucket. O S3 fica
para BSV-12; aqui nasce a abstração de publicação e sua implementação em disco.

## Objetivo
`besave-worker --gerar --saida ./out` lê a fonte, gera `out/data/chunks/{n}-{hash}.json.br` e
`out/manifest.json` conforme MANIFEST.md, reaproveita chunks inalterados, remove órfãos e é
idempotente. Páginas HTML e imagens **não** fazem parte (BSV-21, BSV-13).

## Entradas
- `FonteOfertas` (real ou fake) já filtrando `ST_ATIVO = 1 OR DT_DESATIVACAO >= hoje-7` (BSV-10).
- Pasta de saída existente ou vazia; se houver `manifest.json` anterior, ele é o estado anterior.

## Saídas (lib)
```rust
pub trait Publicador {
    fn existe(&self, chave: &str) -> Result<bool>;
    fn ler(&self, chave: &str) -> Result<Option<Vec<u8>>>;
    fn gravar(&mut self, chave: &str, bytes: &[u8], meta: &Meta) -> Result<()>;  // meta: content_type, content_encoding, cache_control (MANIFEST §4)
    fn remover(&mut self, chave: &str) -> Result<()>;
    fn listar(&self, prefixo: &str) -> Result<Vec<String>>;
}
pub struct PublicadorLocal { raiz: PathBuf }   // grava bytes + `<chave>.meta.json` com os headers
pub struct PublicadorMemoria { .. }            // para testes

pub fn particionar(cards: Vec<OfertaCard>) -> BTreeMap<u64, Vec<OfertaCard>>;   // n = id/1000, ordenado por id
pub fn serializar_chunk(cards: &[OfertaCard]) -> (Vec<u8> /*json*/, String /*hash16*/);
pub fn comprimir_br(json: &[u8]) -> Vec<u8>;    // brotli nível 9
pub fn gerar(fonte: &dyn FonteOfertas, m: &Mapeamento, pub_: &mut dyn Publicador, agora: i64) -> Result<Relatorio>;
```
`Relatorio`: lidas, válidas, rejeitadas por motivo, chunks escritos / reaproveitados / removidos,
bytes totais, maior chunk, `versao`.

## Regras
1. Chunk = array de `OfertaCard` **ordenado por `id`**, JSON compacto (sem espaços), UTF-8.
   `hash` = 16 hex do SHA-256 do JSON **antes** de comprimir. Nome `data/chunks/{n}-{hash}.json.br`.
2. Se `existe(nome)` → não regrava (reaproveitado). Só chunks com hash novo são escritos.
3. `manifest.json` conforme `Manifest` (já em `modelo.rs`): `contrato` = versão do
   `packages/contract/package.json` lida em build (`include_str!` ou constante), `versao` =
   `YYYYMMDDhhmmss` UTC de `agora`, `gerado_em` ISO, `total_ofertas`, `chunks` ordenados por `n`
   com `ids = [min, max]` **reais** do chunk, `qtd`, `bytes` = tamanho **comprimido`, `busca: null`,
   `areas` = contagem de cards **ativos** (sem `x`) por área.
4. Ordem de escrita: chunks → manifest (último). Nunca gravar manifest se algum chunk falhou.
5. Órfãos: após gravar o manifest, listar `data/chunks/` e remover o que não está no manifest
   atual **nem** no anterior (o anterior segura 1 ciclo — cliente com manifest antigo em cache
   ainda pode pedir aqueles arquivos; MANIFEST §3 fala em 24 h, mas com 1 ciclo de proteção e
   `max-age=300` no manifest, 2 ciclos bastam: implementar "não está nos 2 últimos manifests",
   guardando o anterior em `manifest.prev.json` na saída).
6. Orçamento: chunk comprimido **≤ 61 440 bytes**; se exceder, `gerar` falha com erro nomeado
   (não publica) — é sinal de card fora do contrato ou faixa anormal.
7. Idempotência: duas execuções seguidas sem mudança na fonte → zero chunks escritos, zero
   removidos; só o manifest muda (`versao`/`gerado_em`).
8. `--gerar` e `--dry-run` são mutuamente exclusivos; `--saida` obrigatório com `--gerar`.
   Remover o `bail!` de `main.rs` que aponta para este ticket.
9. Sem `unwrap` fora de teste; `tracing` (INFO: resumo; DEBUG: por chunk); erros com `thiserror`.
10. Dependências novas permitidas: `brotli`, `sha2`, `hex`. Qualquer outra, justificar no PR.

## Fora de escopo
Upload S3 (BSV-12), imagens (BSV-13), índice de busca (BSV-34), páginas HTML e sitemap (BSV-21),
KVS de redirects (BSV-12), agendamento (BSV-14).

## Critério de aceite (testes com `FakeFonte` + `PublicadorMemoria`)
- Partição: ids 999, 1000, 1999, 2000 caem em n=0, 1, 1, 2; ordem por id dentro do chunk.
- Round-trip: descomprimir um chunk gerado → JSON válido contra `chunk.schema.json` (usar as
  fixtures do contrato como entrada esperada: `chunk-ok.json` → 1 chunk com hash determinístico,
  asserção do hash literal no teste).
- Manifest gerado valida contra `manifest.schema.json`; `areas` ignora cards com `x:1`;
  `ids` são min/max reais; `bytes` é o tamanho comprimido.
- Reaproveitamento: segunda execução sem mudança → `chunks_escritos == 0`.
- Mudança em 1 oferta do chunk 5 → só o chunk 5 é reescrito; o antigo vira órfão e é removido
  **só** na terceira execução (regra 5).
- Oferta que sai da fonte (expurgo) → chunk dela muda de hash; se a faixa esvazia, some do manifest.
- Chunk > 61 440 bytes (fixture sintética com títulos de 200 chars) → erro, nenhum manifest gravado.
- Desempenho: fixture sintética de 30 000 cards → `gerar` em memória ≤ 30 s, em teste `#[ignore]`
  rodado só localmente (`cargo test -- --ignored`); no CI fica o teste funcional sem limite de tempo
  (ajustado após BSV-12: instável sob carga do runner)
  (o orçamento de 2 min do MANIFEST §7 inclui HTML, que não está aqui).
- `cargo run -- --gerar --saida /tmp/out` com `BESAVE_FONTE=fake` produz a árvore e o relatório;
  contra o Oracle real (dono roda): relatório coerente com o `--dry-run` de BSV-10.
- `cargo clippy --all-targets -- -D warnings` limpo.

## Definition of done
PR com README atualizado (`--gerar`, layout da saída, `.meta.json`), testes verdes, relatório de
uma execução real colado no PR (contagens, maior chunk em bytes, tempo).
