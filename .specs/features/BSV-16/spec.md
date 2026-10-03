# BSV-16 Specification — virada de DNS e domínios curtos

Fonte: `docs/specs/BSV-16.md`. Pasta: `infra/`.

## Problem Statement

O site novo só responde em `*.cloudfront.net`; `besave.com.br` ainda aponta para o protótipo. O canal do
Telegram (BSV-40) vai postar `besave.io/{id}` em posts permanentes, então os domínios curtos precisam
existir e redirecionar antes do primeiro post.

## Goals

- [ ] `besave.com.br` servido pela distribuição nova; `www` com 301 para o domínio sem www
- [ ] `besave.io/{id}` e `besave.me/{id}` com 301 para `https://besave.com.br/oferta/{id}/`, sem estado
- [ ] Virada em fases controladas por variável, com roteiro e reversão no README

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Desligar o protótipo e o bucket `besave.com.br` | outro ticket, após 2 semanas estável |
| Search Console, HSTS | dono / ticket futuro |
| Home e páginas de área reais | BSV-30..33 |
| 410 para oferta expurgada | ticket futuro |
| Upload de `index.html`/`404.html` pelo Terraform | o deploy do site (BSV-30) os substitui |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| "plan da fase 1 só com adições" | 2 zonas adicionadas + 1 atualização in-place de `rewrite-index` (código novo do `www`); 0 destroy | a regra do `www` só tem efeito depois da virada e precisa estar publicada antes dela | n |
| Function `link-curto` na fase 1 | criada só com `ativar_curto = true` | critério: com `false` só existem as 2 zonas novas | n |
| Faixa de 1–12 dígitos | vale para o segmento como chegou (`/0000000000001` tem 13 e vai para a home) | leitura literal da spec | n |
| id só com zeros (`/0`, `/000`) | home | id ≥ 1 (CONTRATO §3) | n |
| `/{id}/ir/` (barra final) | home | spec lista só `/{id}/ir` | n |
| Query string | remontada `chave=valor` como recebida, `&` entre pares, repetidas preservadas (`multiValue`) | padrão do exemplo oficial da AWS; `test-function` real confirma | n |
| Protocolo na distribuição curta | `allow-all`: a Function responde em HTTP também, sempre com destino `https://` | evita um salto extra (http→https→besave.com.br) no link colado sem esquema | n |
| Cache da distribuição curta | política gerenciada CachingDisabled | a Function sempre responde em viewer-request; nada chega à origem | n |
| Domínio na regra do `www` | literal `www.besave.com.br` → `https://besave.com.br` no `.js` | Function é arquivo estático (`file()`); comparação sem diferenciar maiúsculas | n |
| `Cache-Control` no 301 do `www` | `public, max-age=86400` (igual ao `link-curto`) | spec não define; redirect permanente e estável | n |
| `prevent_destroy` nas zonas curtas | não (fora da spec); proposto no PR | zona recriada muda os NS e quebra a delegação | n |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Virada de `besave.com.br` ⭐ MVP

**User Story**: Como dono, quero `besave.com.br` e `www` na distribuição nova para o site ser indexável no domínio definitivo.

**Acceptance Criteria**:

1. VIR-01: WHERE `ativar_dominios = true` the Terraform SHALL criar registros `A` e `AAAA` alias de `besave.com.br` e `www.besave.com.br`, na zona `besave.com.br`, apontando para o `domain_name`/`hosted_zone_id` da distribuição nova, todos com `allow_overwrite = true`
2. VIR-02: WHILE `ativar_dominios = false` the Terraform SHALL não criar nenhum registro A/AAAA do domínio
3. VIR-03: WHERE `ativar_dominios = true` the Lambda `besave-vigia` SHALL receber `URL_MANIFEST = https://besave.com.br/manifest.json`
4. VIR-04: WHILE `ativar_dominios = false` the Lambda `besave-vigia` SHALL manter `URL_MANIFEST = https://<dominio *.cloudfront.net>/manifest.json`

**Independent Test**: `terraform test` com `ativar_dominios = true` e `false`.

### P1: `www` → domínio sem www ⭐ MVP

**Acceptance Criteria**:

1. WWW-01: WHEN `rewrite-index` recebe `Host: www.besave.com.br` THEN it SHALL responder 301 com `location = https://besave.com.br{uri}{?query}` (uri original, antes do rewrite)
2. WWW-02: WHEN o `Host` é `www.besave.com.br` e não há query THEN the `location` SHALL não ter `?`
3. WWW-03: WHEN o `Host` não é `www.besave.com.br` THEN `rewrite-index` SHALL manter o comportamento atual (FN-01..03)

### P1: Domínios curtos ⭐ MVP

**Acceptance Criteria**:

1. CUR-01: The Terraform SHALL criar as zonas Route53 `besave.io` e `besave.me` independentemente de `ativar_curto`
2. CUR-02: The Terraform SHALL expor um output com os 4 NS de cada zona curta
3. CUR-03: WHILE `ativar_curto = false` the Terraform SHALL não criar certificado, registros de validação, Function `link-curto`, distribuição curta nem registros A/AAAA curtos
4. CUR-04: WHERE `ativar_curto = true` the Terraform SHALL criar certificado ACM `besave.io` + SANs `www.besave.io`, `besave.me`, `www.besave.me`, validação DNS, com `prevent_destroy = true`
5. CUR-05: WHERE `ativar_curto = true` the Terraform SHALL criar um registro de validação por nome, na zona do respectivo domínio curto
6. CUR-06: WHERE `ativar_curto = true` the Terraform SHALL criar a distribuição `besave-curto` com os 4 aliases, certificado validado (`sni-only`, `TLSv1.2_2021`), origem custom `besave.com.br`, `link-curto` em viewer-request e logs em `besave-logs` com prefixo `curto/`
7. CUR-07: WHERE `ativar_curto = true` the Terraform SHALL criar registros A e AAAA alias de cada um dos 4 nomes, na zona do domínio, apontando para a distribuição curta
8. CUR-08: The Function `link-curto` SHALL usar `cloudfront-js-2.0`, `publish = true` e código de `infra/functions/link-curto.js`

### P1: Function `link-curto` ⭐ MVP

**Acceptance Criteria**:

1. LNK-01: WHEN o path é `/{id}` ou `/{id}/` com 1–12 dígitos THEN it SHALL responder 301 para `https://besave.com.br/oferta/{id}/` com zeros à esquerda removidos
2. LNK-02: WHEN o path é `/{id}/ir` THEN it SHALL responder 301 para `https://besave.com.br/ir/{id}`
3. LNK-03: WHEN há query string THEN it SHALL anexá-la ao `location` (`?utm_source=telegram`)
4. LNK-04: IF o path é `/` ou qualquer outro (não dígitos, > 12 dígitos, id zero) THEN it SHALL responder 301 para `https://besave.com.br/`
5. LNK-05: The Function SHALL responder sempre com status 301 e `Cache-Control: public, max-age=86400`

### P2: Páginas provisórias

**Acceptance Criteria**:

1. PAG-01: The `infra/static/index.html` SHALL ter o nome besave, o texto "site em construção" e link `href="{CANAL_TELEGRAM}"`
2. PAG-02: The `infra/static/404.html` SHALL ser `noindex`, dizer "Oferta encerrada ou não encontrada" e ter links para `/` e `{CANAL_TELEGRAM}`
3. PAG-03: The `404.html` SHALL não ter link para nenhuma página de área
4. PAG-04: The páginas SHALL não conter link `t.me/` real nem telefone (repositório público)

### P2: README

1. OPS-01: The README SHALL ter o roteiro da virada (6 passos da spec), o upload manual das páginas, os custos e como reverter
2. OPS-02: The README SHALL ter um passo 0, antes de qualquer `apply`, que cria Functions temporárias pela CLI (`create-function`, `cloudfront-js-2.0`) com o código novo, roda `test-function` em DEVELOPMENT com os eventos de `functions/eventos/` e as apaga (`delete-function`); o upload de `index.html`/`404.html` fica no passo 1 (AD-030)

---

## Edge Cases

- IF `Host` é `WWW.Besave.com.br` THEN `rewrite-index` SHALL redirecionar igual (WWW-01)
- IF a query tem chave repetida THEN `link-curto` SHALL preservar todas as ocorrências (LNK-03)

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| VIR-01 | P1: Virada | Tasks | Implemented |
| VIR-02 | P1: Virada | Tasks | Implemented |
| VIR-03 | P1: Virada | Tasks | Implemented |
| VIR-04 | P1: Virada | Tasks | Implemented |
| WWW-01 | P1: www | Tasks | Implemented |
| WWW-02 | P1: www | Tasks | Implemented |
| WWW-03 | P1: www | Tasks | Implemented |
| CUR-01 | P1: Domínios curtos | Tasks | Implemented |
| CUR-02 | P1: Domínios curtos | Tasks | Implemented |
| CUR-03 | P1: Domínios curtos | Tasks | Implemented |
| CUR-04 | P1: Domínios curtos | Tasks | Implemented |
| CUR-05 | P1: Domínios curtos | Tasks | Implemented |
| CUR-06 | P1: Domínios curtos | Tasks | Implemented |
| CUR-07 | P1: Domínios curtos | Tasks | Implemented |
| CUR-08 | P1: Domínios curtos | Tasks | Implemented |
| LNK-01 | P1: link-curto | Tasks | Implemented |
| LNK-02 | P1: link-curto | Tasks | Implemented |
| LNK-03 | P1: link-curto | Tasks | Implemented |
| LNK-04 | P1: link-curto | Tasks | Implemented |
| LNK-05 | P1: link-curto | Tasks | Implemented |
| PAG-01 | P2: Páginas | Tasks | Implemented |
| PAG-02 | P2: Páginas | Tasks | Implemented |
| PAG-03 | P2: Páginas | Tasks | Implemented |
| PAG-04 | P2: Páginas | Tasks | Implemented |
| OPS-01 | P2: README | Tasks | Implemented |
| OPS-02 | P2: README | Tasks | Implemented |

**Coverage:** 26 total, 26 mapped to tasks, 0 unmapped

---

## Success Criteria

- [ ] `terraform fmt/validate/test` limpos; `npm test` verde
- [ ] Real (dono): `test-function` das duas Functions, `curl` do roteiro e prévia no Telegram
