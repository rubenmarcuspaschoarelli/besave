# BSV-13 · Worker: imagens WebP (`{id}_small` e `{id}`), placeholders e `Area::Outros`

**Papel:** Backend Rust · **Pasta:** `apps/worker/` · **Depende de:** BSV-12 (mergeado). CONTRATO.md §2.3, §6, §7; MANIFEST.md §1, §4, §6, §7

## Contexto
O robô grava a imagem integral de cada oferta em disco como `{id_oferta}.jpg` (pasta configurável).
O site precisa de duas versões WebP por oferta (CONTRATO §6) e de um placeholder por área. O
contrato 1.3 acrescentou a área `OUTROS` e o enum Rust ainda não a conhece.

## Objetivo
`gerar()` passa a publicar imagens no passo 1 da ordem de MANIFEST §6, reaproveitando o que já
existe, e o enum `Area` do worker fica sincronizado com `enums.schema.json`.

## Entradas
- `BESAVE_IMAGENS_DIR` (env/CLI): pasta com `{id}.jpg` (aceitar também `.jpeg`, `.png`, `.webp`).
- Placeholders versionados em `apps/worker/assets/placeholder/{area}.webp` (o agente cria 10 imagens
  simples, 320 px, fundo neutro com o rótulo da área; peso ≤ 8 KB cada).
- Conjunto publicado (ativos + expiradas ≤ 7 dias), como já sai da fonte.

## Saídas (lib)
```rust
pub struct Imagem { pub id: i64, pub small: Vec<u8>, pub grande: Vec<u8> }
pub fn processar(origem: &[u8]) -> Result<Imagem, ErroImagem>;   // decodifica, redimensiona, codifica WebP
pub fn chave_small(id: i64) -> String;  // "img/ofertas/{id}_small.webp"
pub fn chave_grande(id: i64) -> String; // "img/ofertas/{id}.webp"
pub fn publicar_imagens(ids: &[i64], dir: &Path, pub_: &mut dyn Publicador) -> Result<RelatorioImagens>;
```
`RelatorioImagens`: processadas, reaproveitadas, sem_origem, falhas (id + motivo), bytes, maior_small.

## Regras
1. **`Area::Outros`** primeiro: variante no enum, `mapeamento.rs` lê "OUTROS" do `mapeamento.json`,
   `areas` do manifest inclui a chave quando houver ativas. Teste: card com `DS_COMUNIDADE = "Outros"`
   vira `a: "OUTROS"`; manifest valida contra `manifest.schema.json` 1.3.
2. `_small`: lado maior 320 px, WebP com qualidade ajustada **até caber em 25 KB** (começar em 80,
   descer de 10 em 10 até 40; abaixo disso, aceitar e registrar WARN). Grande: lado maior 1200 px,
   qualidade 82, sem limite rígido (meta ≤ 150 KB).
3. Nunca ampliar: origem menor que o alvo é codificada no tamanho original.
4. Reaproveitamento: se `existe(chave_small)` **e** `existe(chave_grande)` → pula (as imagens
   nunca mudam para um mesmo id). Não comparar conteúdo.
5. Sem origem → não publica nada para o id; o card e a página usam o placeholder da área
   (referência fixa `img/placeholder/{area}.webp`; o worker publica os 10 placeholders uma vez,
   reaproveitando pelo mesmo critério). Ausência **nunca** bloqueia a oferta (CONTRATO §6).
6. Falha de decodificação (arquivo corrompido) → conta em `falhas`, loga o id e o motivo, segue.
7. Headers: `meta_para` já cobre `img/**` (`image/webp`, `immutable`); só usar.
8. Expurgo: `gerar()` já apaga `img/ofertas/{id}*` para ids que saíram do conjunto (BSV-12);
   confirmar que apaga as duas chaves e cobrir com teste.
9. Paralelismo: processar com `rayon` (ou threads padrão) — 30k imagens sequenciais não cabem
   no orçamento; medir e registrar no PR.
10. Dependências permitidas: `image` (decodificação/resize), `webp` ou o encoder do próprio `image`
    se suportar qualidade; `rayon`. Justificar a escolha do encoder no PR (qualidade × velocidade).

## Fora de escopo
Imagens de produto (`img/produtos/`), CDN de imagens externa, HTML (BSV-20/21), agendamento (BSV-14).

## Critério de aceite
- `Area::Outros` round-trip com as fixtures do contrato 1.3; `mapeamento.json` carrega sem erro.
- `processar` sobre 3 fixtures (paisagem 2000×1200, retrato 800×1600, pequena 200×200): dimensões
  corretas, `_small` ≤ 25 KB nas duas primeiras, a pequena não é ampliada.
- Fixture corrompida → `ErroImagem`, sem panic; `publicar_imagens` continua e reporta.
- Id sem arquivo → `sem_origem`, nada publicado, card/página apontam para o placeholder.
- Segunda execução → `processadas: 0`, `reaproveitadas: N`.
- Desempenho (teste `#[ignore]`, local): 1000 imagens de 1500×1500 processadas ≤ 60 s.
- `cargo clippy -D warnings` limpo; `cargo test` sem rede.
- Real (dono): `--publicar --sim` com `BESAVE_IMAGENS_DIR` apontando para a pasta do robô;
  `curl -I https://<cf>/img/ofertas/<id>_small.webp` → 200, `image/webp`, `immutable`;
  relatório com `maior_small` ≤ 25 600 bytes.

## Definition of done
PR com README (`BESAVE_IMAGENS_DIR`, formatos aceitos, política de qualidade), testes verdes,
relatório real colado (contagens, tempo, maior `_small`), placeholders em `assets/`.
