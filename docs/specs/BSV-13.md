# BSV-13 · Worker: imagens WebP (`{id}_small` e `{id}`), placeholders e `Area::Outros`

**Papel:** Backend Rust · **Pasta:** `apps/worker/` · **Depende de:** BSV-12 (mergeado). CONTRATO.md §2.3, §6, §7; MANIFEST.md §1, §4, §6, §7

## Contexto
O robô já grava, por oferta, uma pasta `{BESAVE_IMAGENS_DIR}/{id}/` com dois WebP prontos:
`{id}.webp` (tamanho natural, página) e `{id}-small.webp` (lista). O worker **não processa imagem
por padrão**: copia para o S3 com os nomes do contrato, verificando o orçamento. O contrato 1.3
acrescentou a área `OUTROS` e o enum Rust ainda não a conhece.

## Objetivo
`gerar()` passa a publicar imagens no passo 1 da ordem de MANIFEST §6, reaproveitando o que já
existe, e o enum `Area` do worker fica sincronizado com `enums.schema.json`.

## Entradas
- `BESAVE_IMAGENS_DIR` (env/CLI): raiz com `{id}/{id}.webp` e `{id}/{id}-small.webp`.
  Exemplo do dono: `E:\Work\besave\server\s3\ofertas\img`.
- Placeholders versionados em `apps/worker/assets/placeholder/{area}.webp` (o agente cria 10 imagens
  simples, 320 px, fundo neutro com o rótulo da área; ≤ 8 KB cada).
- Conjunto publicado (ativos + expiradas ≤ 7 dias), como já sai da fonte.

## Saídas (lib)
```rust
pub fn chave_small(id: i64) -> String;   // "img/ofertas/{id}_small.webp"  (S3 usa underscore: contrato §6)
pub fn chave_grande(id: i64) -> String;  // "img/ofertas/{id}.webp"
pub fn origem(dir: &Path, id: i64) -> (PathBuf, PathBuf);  // {dir}/{id}/{id}-small.webp, {dir}/{id}/{id}.webp
pub fn ajustar_small(bytes: &[u8]) -> Result<Vec<u8>, ErroImagem>;  // só quando > 25 KB: recodifica (ver regra 3)
pub fn publicar_imagens(ids: &[i64], dir: &Path, pub_: &mut dyn Publicador) -> Result<RelatorioImagens>;
```
`RelatorioImagens`: publicadas, reaproveitadas, sem_origem, reprocessadas, falhas (id + motivo),
bytes, maior_small, maior_grande.

## Regras
1. **`Area::Outros`** primeiro: variante no enum, `mapeamento.rs` lê "OUTROS" do `mapeamento.json`,
   `areas` do manifest inclui a chave quando houver ativas. Teste: card com `DS_COMUNIDADE = "Outros"`
   vira `a: "OUTROS"`; manifest valida contra `manifest.schema.json` 1.3.
2. Cópia direta: `-small.webp` ≤ 25 600 bytes → sobe como está em `chave_small`; `{id}.webp` sobe
   como está em `chave_grande`. Verificar que os bytes começam com a assinatura WebP (`RIFF....WEBP`);
   caso contrário, `falhas` com motivo `nao_webp`.
3. Orçamento estourado: `-small.webp` > 25 600 bytes → `ajustar_small` recodifica (crate `image` +
   encoder WebP com qualidade descendo de 80 até 40, lado maior limitado a 320 px), publica o
   resultado e conta em `reprocessadas` com WARN (sinal para ajustar o robô). Grande > 300 KB →
   WARN, publica assim mesmo (não bloqueia), conta em `maior_grande`.
4. Reaproveitamento: se `existe(chave_small)` **e** `existe(chave_grande)` → pula. Imagem de um id
   nunca muda. Não comparar conteúdo.
5. Sem pasta ou sem um dos dois arquivos → `sem_origem`, nada publicado para o id; card e página
   usam `img/placeholder/{area}.webp` (o worker publica os 10 placeholders uma vez, reaproveitando
   pelo mesmo critério). Ausência **nunca** bloqueia a oferta (CONTRATO §6).
6. Headers: `meta_para` já cobre `img/**` (`image/webp`, `immutable`); só usar.
7. Expurgo: `gerar()` já apaga `img/ofertas/{id}*` para ids que saíram do conjunto (BSV-12);
   confirmar que apaga as duas chaves e cobrir com teste.
8. Paralelismo no upload: `HeadObject` + `PutObject` para ~50k objetos na primeira carga é o
   gargalo, não a CPU. Usar um pool de tarefas (8–16 em voo) no `PublicadorS3`; `PublicadorMemoria`
   e `Local` continuam sequenciais. Medir e registrar no PR.
9. Dependências permitidas: `image` (só para `ajustar_small`), `rayon` ou `tokio` já presente para
   o pool. Justificar o encoder WebP escolhido no PR.

## Fora de escopo
Imagens de produto (`img/produtos/`), CDN de imagens externa, HTML (BSV-20/21), agendamento (BSV-14).

## Critério de aceite
- `Area::Outros` round-trip com as fixtures do contrato 1.3; `mapeamento.json` carrega sem erro.
- Fixture `{id}/{id}-small.webp` de 12 KB e `{id}.webp` de 90 KB → publicadas com as chaves do
  contrato (`_small`), bytes idênticos aos de origem, `Meta` de `img/**`.
- `-small.webp` de 40 KB (fixture) → `ajustar_small` devolve ≤ 25 600 bytes, WebP válido, lado
  maior ≤ 320 px; contado em `reprocessadas`.
- Arquivo com extensão `.webp` mas conteúdo JPEG → `falhas: nao_webp`, sem panic, execução continua.
- Id sem pasta, ou pasta com um só arquivo → `sem_origem`, nada publicado.
- Segunda execução → `publicadas: 0`, `reaproveitadas: N`.
- Desempenho (teste `#[ignore]`, local): 5000 ids contra `PublicadorMemoria` ≤ 5 s (mede o caminho
  sem rede; o upload real é medido pelo dono).
- `cargo clippy -D warnings` limpo; `cargo test` sem rede.
- Real (dono): `--publicar --sim` com `BESAVE_IMAGENS_DIR` apontando para a pasta do robô;
  `curl -I https://<cf>/img/ofertas/<id>_small.webp` e `<id>.webp` → 200, `image/webp`, `immutable`;
  relatório com `maior_small` ≤ 25 600 bytes, `reprocessadas` e `sem_origem` anotados no PR.

## Definition of done
PR com README (`BESAVE_IMAGENS_DIR`, layout `{id}/{id}[-small].webp` → `img/ofertas/{id}[_small].webp`, política de orçamento), testes verdes,
relatório real colado (contagens, tempo, maior `_small`), placeholders em `assets/`.
