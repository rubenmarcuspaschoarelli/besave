# BSV-16 · Infra: virada de DNS de besave.com.br e domínios curtos besave.io / besave.me

**Papel:** DevOps · **Pasta:** `infra/` · **Depende de:** BSV-4, BSV-21 (mergeados).
CONTRATO.md §5; MANIFEST.md §5; AD-016, AD-018, AD-020, AD-021, AD-022, AD-030, AD-060

## Contexto
O site novo está no ar só em `*.cloudfront.net`, com `robots.txt` bloqueando. `besave.com.br` ainda
aponta para o protótipo (bucket público + `E28G93A17WHHD`), que pode ser substituído já. O canal do
Telegram (BSV-40) vai postar links `besave.io/{id}`, e post de canal é permanente: os domínios
definitivos precisam existir antes do primeiro post. `besave.io` e `besave.me` estão registrados fora
da AWS; a única zona no Route53 é `besave.com.br`.

## Objetivo
`besave.com.br` servido pela distribuição nova e indexável; `www` com 301 para o domínio sem www;
`besave.io/{id}` e `besave.me/{id}` com 301 para `https://besave.com.br/oferta/{id}/`, sem estado.

## Entregáveis
1. **Virada** (`ativar_dominios = true`, variável que já existe): registros `A` e `AAAA` (alias) de
   `besave.com.br` e `www` apontando para a distribuição nova, com `allow_overwrite = true`, porque
   hoje foram criados no console e apontam para o protótipo.
2. **`www` → domínio sem www:** `rewrite-index.js` responde 301 para `https://besave.com.br{uri}{query}`
   quando `Host` é `www.besave.com.br`; sem mudança para o domínio sem www.
3. **Domínios curtos**, em duas fases controladas por `ativar_curto` (padrão `false`):
   - Fase 1 (sempre): zonas Route53 `besave.io` e `besave.me`; output com os 4 NS de cada uma, para o
     dono configurar no registrador.
   - Fase 2 (`ativar_curto = true`, depois que o NS propagar): certificado ACM (`besave.io`,
     `www.besave.io`, `besave.me`, `www.besave.me`) validado por DNS nas zonas novas, com
     `prevent_destroy` (AD-022); distribuição `besave-curto` com esses aliases e registros A/AAAA.
4. **Function `link-curto`** (viewer-request, `cloudfront-js-2.0`, `infra/functions/link-curto.js`):
   - `/{id}` ou `/{id}/` (só dígitos, 1–12, zeros à esquerda removidos) → 301
     `https://besave.com.br/oferta/{id}/`
   - `/{id}/ir` → 301 `https://besave.com.br/ir/{id}` (CONTRATO §5)
   - `/` e qualquer outro caminho → 301 `https://besave.com.br/`
   - query string de entrada preservada (ex.: `?utm_source=telegram`); `Cache-Control: public, max-age=86400`.
   - Origem da distribuição curta: `besave.com.br` (custom origin), nunca alcançada porque a Function
     sempre responde. Logs no `besave-logs`, prefixo `curto/`.
5. **Página provisória** em `infra/static/index.html` (nome, "site em construção", link para o canal
   `{CANAL_TELEGRAM}`, preenchido pelo dono só na cópia enviada ao S3; nunca telefone ou conta pessoal no repositório, que é público) e `404.html` corrigida: sem links para páginas de área (que
   ainda não existem e dão 404 em laço), com "Oferta encerrada ou não encontrada", link para o início e
   para o canal. Upload manual documentado no README (como já é com a 404). O Terraform **não** gerencia
   esses objetos: o deploy do site (BSV-30) os substitui.
6. **Vigia:** `URL_MANIFEST` passa a `https://besave.com.br/manifest.json` quando `ativar_dominios = true`
   (testa também DNS e certificado).
7. README: roteiro da virada (abaixo), custos e como reverter.

## Roteiro da virada (dono, no README)
1. `apply` com `ativar_curto = false` → anotar os NS → configurar no registrador de `.io` e `.me`.
2. Remover os aliases `besave.com.br`/`www` de `E28G93A17WHHD` no console (AD-021: CNAME não pode estar em
   duas distribuições) → `apply` com `ativar_dominios = true` imediatamente depois. Indisponibilidade
   esperada: os minutos entre os dois passos (protótipo, aceito).
3. Worker: `BESAVE_INDEXAVEL=true` no `.env` → próximo ciclo grava o `robots.txt` com `Allow` + `Sitemap`.
4. Upload de `index.html` e `404.html`.
5. NS propagado (`nslookup -type=NS besave.io`) → `apply` com `ativar_curto = true`.
6. PR `develop → main` (AD-060).

## Regras
- Nada muda na distribuição antiga além da remoção manual dos aliases; desligar o protótipo e o bucket
  `besave.com.br` é outro ticket (depois de 2 semanas estável).
- Domínios continuam no registrador atual; só a delegação de NS muda.
- Custo: zonas US$ 0,50/mês cada (+US$ 1,00/mês); Functions dentro de 2 milhões de execuções/mês gratuitas,
  depois US$ 0,10 por milhão (AWS Pricing API, 02/10/2026); ACM e distribuição sem custo fixo.
- `aws cloudfront test-function` obrigatório para `link-curto` e `rewrite-index` (AD-030).

## Fora de escopo
Desligar o protótipo, Search Console (o dono faz), HSTS, página de área/home real (BSV-30..33),
410 para oferta expurgada.

## Critério de aceite
- `terraform test` (mocks): com `ativar_curto = false` → só as 2 zonas novas, sem certificado ou
  distribuição curta; com `true` → certificado com os 4 nomes e `prevent_destroy`, distribuição com os 4
  aliases e `link-curto` associada; com `ativar_dominios = true` → A/AAAA de `besave.com.br` e `www` com
  `allow_overwrite`, e `URL_MANIFEST` no domínio.
- Testes Node de `link-curto`: `/5412`, `/5412/`, `/05412` → `/oferta/5412/`; `/5412?utm_source=telegram`
  preserva a query; `/5412/ir` → `/ir/5412`; `/`, `/abc`, `/1234567890123` → home; status 301 e `Cache-Control`.
- Testes de `rewrite-index`: `Host: www.besave.com.br` + `/oferta/1/?a=1` → 301 para o domínio sem www com
  caminho e query; domínio sem www → comportamento atual intacto (testes existentes verdes).
- `terraform fmt/validate/test` limpos; `plan` da fase 1 só com adições.
- **Real (dono):** `aws cloudfront test-function` das duas Functions com os eventos de fixture;
  `curl -I https://besave.com.br/oferta/<id>/` → 200; `https://www.besave.com.br/oferta/<id>/` → 301 para o
  domínio sem www; `https://besave.io/<id>` e `https://besave.me/<id>` → 301 para `/oferta/<id>/`;
  `https://besave.com.br/robots.txt` → `Allow` + `Sitemap`; `https://besave.com.br/` → página provisória;
  `https://besave.com.br/nao-existe` → 404 provisória; `lambda invoke` do vigia → ok; link
  `besave.io/<id>` colado num chat do Telegram mostra a prévia da oferta.

## Definition of done
PR com README do roteiro, `plan` das duas fases colado (ARNs e IDs de conta como `REDACTED`), saída do
`test-function` e dos `curl`, testes verdes.
