# BSV-12 · Worker: `PublicadorS3` + atualização da KeyValueStore de redirects

**Papel:** Backend Rust · **Pasta:** `apps/worker/` · **Depende de:** BSV-11 (mergeado); BSV-4 para o teste real (bucket, KVS, usuário IAM). MANIFEST.md §4, §5, §6; CONTRATO.md §1.2

## Contexto
BSV-11 deixou o trait `Publicador` com `PublicadorLocal` e `PublicadorMemoria`, e `gerar()` já
escreve chunks + manifest na ordem certa. Este ticket adiciona a implementação S3 e o passo 4
da ordem de publicação (KVS de redirects), sem mudar `gerar()` além do necessário para receber
os redirects.

## Objetivo
`besave-worker --publicar` (ou `--gerar --destino s3`) faz o mesmo que `--gerar`, mas no bucket,
com os headers de MANIFEST.md §4, e mantém a KVS `id → DS_URL_AFILIADO` sincronizada. Todo o
código é testável sem AWS.

## Saídas (lib)
```rust
pub struct PublicadorS3 { .. }       // aws-sdk-s3; bucket e região por env/CLI
impl Publicador for PublicadorS3 { .. }   // gravar = PutObject com ContentType/ContentEncoding/CacheControl da Meta

pub trait Redirects {                // KVS
    fn listar(&self) -> Result<BTreeMap<i64, String>>;
    fn aplicar(&mut self, put: &[(i64, String)], del: &[i64]) -> Result<()>;
}
pub struct RedirectsKvs { .. }       // aws-sdk-cloudfrontkeyvaluestore
pub struct RedirectsMemoria { .. }   // testes
pub fn sincronizar_redirects(ativos: &[(i64, String)], kvs: &mut dyn Redirects) -> Result<RelatorioRedirects>;  // diff: só o que mudou
```
`LinhaOferta` já tem `DS_URL_AFILIADO`? Se BSV-10 não a carregou, adicionar ao SELECT e à struct
(campo `url_afiliado: String`, obrigatório: CONTRATO §10.1 diz que sem ela a oferta não existe).

## Regras
1. **Headers exatos** de MANIFEST.md §4 por prefixo; `PublicadorMemoria` já guarda `Meta`, então
   o teste compara a `Meta` que `PublicadorS3` montaria (função pura `meta_para(chave) -> Meta`,
   testável) — não precisa de AWS para testar a tabela de headers.
2. `existe` no S3 = `HeadObject` (404 → false). `listar` = `ListObjectsV2` paginado. Nunca
   `GetObject` de chunk para comparar: o nome já carrega o hash.
3. Ordem de MANIFEST §6: chunks → HTML/sitemap (ainda não existem: no-op) → **KVS** → manifest
   → órfãos. Se a KVS falhar, o manifest **não** é publicado nesta rodada (o manifest antigo
   continua válido).
4. KVS: `PutKey`/`DeleteKey` só do diff; chave = `id` decimal como string, valor = URL. Valor
   máximo por chave e limite total de 5 MB são erros nomeados, não panics. Se `ativos` passar de
   40 000 entradas, `WARN` (limite documentado em MANIFEST §5).
5. `--publicar` sem `--sim` faz `plan`: imprime o que gravaria/removeria/putKey/deleteKey e sai
   com 0. Com `--sim`, executa. (Proteção contra rodar contra o bucket errado.)
6. Credenciais **só** pela cadeia padrão do SDK (env `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`
   ou perfil). Nenhum campo de credencial em config, CLI ou log. Bucket/região/ARN da KVS por env
   (`BESAVE_BUCKET`, `AWS_REGION`, `BESAVE_KVS_ARN`).
7. Retentativas: usar o retry do SDK; sem loop próprio.
8. Dependências permitidas: `aws-config`, `aws-sdk-s3`, `aws-sdk-cloudfrontkeyvaluestore`, `tokio`
   (o worker vira async só na borda: `gerar()` continua síncrono; o `PublicadorS3` usa um runtime
   interno — justificar a abordagem escolhida no PR).

## Fora de escopo
Criar bucket/KVS (BSV-4), imagens (BSV-13), HTML (BSV-21), invalidação de CloudFront (desnecessária:
manifest tem TTL 300 s e o resto é imutável), agendamento (BSV-14).

## Critério de aceite
- `meta_para` retorna, para cada prefixo de MANIFEST §4, exatamente os três headers da tabela
  (teste tabular).
- `sincronizar_redirects` com `RedirectsMemoria`: estado inicial {1→a, 2→b}, ativos {1→a, 2→c, 3→d}
  → put {2→c, 3→d}, del {}; ativos {1→a} → del {2, 3}; mesma entrada duas vezes → segunda é no-op.
- Falha injetada na KVS → `gerar` retorna erro e o manifest **não** foi gravado no `PublicadorMemoria`.
- `--publicar` sem `--sim` não chama nenhum método de escrita (testar com um `Publicador` que
  registra chamadas).
- `cargo test` passa sem credenciais e sem rede.
- Contra a AWS (dono roda, após BSV-4): `--publicar --sim` com `BESAVE_FONTE=oracle` publica;
  `curl -I https://<cf>/manifest.json` mostra `Cache-Control: public, max-age=300, ...`;
  `curl -I` de um chunk mostra `Content-Encoding: br` e `immutable`; `curl -I https://<cf>/ir/<id>`
  retorna 302 para a URL de afiliado; segunda execução reporta zero escritas.

## Definition of done
PR com README (`--publicar`, envs, plan/sim), testes verdes, saída do `plan` e de uma execução real
coladas no PR, sem credencial no diff.
