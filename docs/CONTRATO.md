# CONTRATO.md — Schema canônico (BSV-1)

Fonte da verdade para todo dado que sai do Oracle e chega ao site, ao app e aos bots.
Os arquivos JSON Schema em `packages/contract/schema/` são a forma executável deste documento;
se divergirem, o JSON Schema vence e este arquivo é corrigido.

Versão do contrato: **1.3.0** (SemVer; mudança incompatível = major).
Histórico: 1.3.0 — área `OUTROS`, slug de URL por área, sinônimos INFANTIL (Bebes/Menina/Menino). 1.2.0 — URL da oferta é `/oferta/{id}/`, slug removido do card, da página e do Oracle; expurgo sem apagar do banco. 1.1.0 — `ST_ATIVO` do Oracle, campo `x` no card, expurgo em 7 dias, `DT_ULT_ATUALIZACAO` opcional.

---

## 1. Princípios

1. **Duas projeções, não uma.** `OfertaCard` (compacta, vai em chunks para a lista/busca) e
   `OfertaPagina` (completa, só existe embutida no HTML estático da oferta). Nunca enviar
   `OfertaPagina` em lista.
2. **Sem URL de loja fora do redirect.** Nem card nem página carregam `DS_URL_AFILIADO`.
   O CTA aponta para `/ir/{id}`, que faz o 302 e registra o clique (BSV-23). Motivos:
   log de clique desde o dia 1, Google não indexa link de afiliado, troca de rede de
   afiliado sem regerar 30k páginas.
3. **Dinheiro é inteiro em centavos.** `preco_de: 19990` = R$ 199,90. Nunca float.
4. **Datas em ISO 8601 UTC** (`2026-09-24T13:05:00Z`). "há 2 horas" é calculado no cliente.
5. **Enums, não texto livre.** `loja`, `publico`, `area` são enums fechados; valor fora do
   enum = registro rejeitado pelo worker (e logado), não publicado.
6. **Imagem é derivada do id**, nunca campo. Ver §6.
7. **Identidade e URL vêm do `ID_OFERTA`.** URL da oferta é `/oferta/{id}/`; não há slug (AD-018).

---

## 2. Enums

### 2.1 `Loja`
| valor | origem em `DS_LOJA` (normalizado: maiúsculas, sem acento, trim) |
|---|---|
| `AMAZON` | `AMAZON` |
| `SHOPEE` | `SHOPEE` |
| `MERCADO_LIVRE` | `MERCADO LIVRE`, `MERCADOLIVRE`, `ML` |

### 2.2 `Publico`
| valor | origem em `DS_PUBLICO` |
|---|---|
| `FEMININO` | `FEMININO`, `MULHER`, `F` |
| `MASCULINO` | `MASCULINO`, `HOMEM`, `M` |
| `UNISSEX` | `UNISSEX`, `UNISEX`, `U` |
| `INFANTIL` | `INFANTIL`, `CRIANCA`, `I` |

### 2.3 `Area` (as 9 áreas de interesse + Outros)
| valor | rótulo de exibição | slug de URL | origem em `DS_COMUNIDADE` |
|---|---|---|---|
| `TECH` | Tech | `tech` | `TECH`, `TECNOLOGIA` |
| `PLAYERS` | Players | `players` | `PLAYERS`, `GAMES`, `GAMER` |
| `MEU_LAR` | Meu Lar | `meu-lar` | `MEU LAR`, `LAR`, `CASA` |
| `ELAS` | Elas | `elas` | `ELAS` |
| `ELES` | Eles | `eles` | `ELES` |
| `CULTURA` | Cultura | `cultura` | `CULTURA` |
| `FAMILIA` | Família & filhos | `familia` | `FAMILIA`, `FAMILIA & FILHOS`, `FAMILIA E FILHOS` |
| `PETS` | Pets | `pets` | `PETS`, `PET` |
| `ESPORTE_VIDA` | Esporte & vida | `esporte-vida` | `ESPORTE`, `ESPORTE & VIDA`, `ESPORTE E VIDA` |
| `OUTROS` | Outros | `outros` | `OUTROS` — gravado pelo robô quando não classifica; vazio continua rejeitado |

O slug de URL é o path da página de área (`/{slug}/`, `/{slug}/{publico}/`), usado pelo site,
pelo worker e pela `404.html`. `Publico` usa o valor em minúsculas (`feminino`, `masculino`,
`unissex`, `infantil`). `OUTROS` existe no menu, não na primeira dobra da home (regra para BSV-33).

A tabela de mapeamento texto → enum vive em `packages/contract/mapeamento.json` e é o
único lugar onde novos sinônimos entram. O worker rejeita o que não mapear.

---

## 3. `OfertaCard` — projeção compacta (chunks da lista e da busca)

Orçamento: **≤ 220 bytes por registro em JSON bruto** (meta ~150). Chaves curtas por isso.

| campo | tipo | origem | regra |
|---|---|---|---|
| `id` | integer ≥ 1 | `ID_OFERTA` | chave |
| `l` | `Loja` | `DS_LOJA` | enum |
| `t` | string 1..200 | `DS_TITULO` | trim; se > 200, corta em 197 + `…` na última fronteira de palavra |
| `pd` | integer ≥ 0 \| null | `VL_PRECO_DE` | centavos; `null` se ausente ou ≤ `pp` |
| `pp` | integer ≥ 1 | `VL_PRECO_POR` | centavos; obrigatório |
| `c` | string 1..30 \| ausente | `DS_CUPOM` | só presente se houver cupom; trim, maiúsculas |
| `dt` | string date-time | `DT_OFERTA` | ISO 8601 UTC |
| `a` | `Area` | `DS_COMUNIDADE` | enum |
| `p` | `Publico` | `DS_PUBLICO` | enum |
| `x` | `1` \| ausente | `ST_ATIVO = 0` | **expirada**; só presente quando inativa (custa 6 bytes só nelas) |

Não entram no card (decidido): slug (não existe), `ID_PRODUTO`, URLs, `VR_PRECO_1`, `DS_CUPOM_COMENTARIO`,
nota/qtd de avaliação, `DT_CAPTACAO`, `DT_PUBLICACAO`, campos de afiliado.

Cliente: lista esconde `x:1` por padrão (toggle "mostrar expiradas"); busca mostra em cinza.

Desconto (%) **não é campo**: o cliente calcula `round((1 - pp/pd) * 100)` quando `pd != null`.

Exemplo:
```json
{"id":5412,"l":"AMAZON","t":"Fone Bluetooth XYZ com ANC","pd":29990,"pp":19990,"c":"BESAVE10","dt":"2026-09-24T12:40:00Z","a":"TECH","p":"UNISSEX"}
```

---

## 4. `OfertaPagina` — projeção completa (embutida no HTML da oferta)

Consumida só pelo template do worker. Chaves legíveis (não há orçamento de bytes aqui).

### 4.1 Oferta
| campo | tipo | origem | regra |
|---|---|---|---|
| `id` | integer | `ID_OFERTA` | |
| `id_produto` | integer | `ID_PRODUTO` | liga ao §4.2 |
| `loja` | `Loja` | `DS_LOJA` | |
| `titulo` | string 1..400 | `DS_TITULO` | integral |
| `preco_de` | integer \| null | `VL_PRECO_DE` | centavos |
| `preco_por` | integer | `VL_PRECO_POR` | centavos |
| `desconto_pct` | integer 0..99 \| null | derivado | `round((1 - por/de)*100)`; pré-calculado aqui porque vai no HTML e no `schema.org` |
| `cupom` | string \| null | `DS_CUPOM` | exibido abaixo do preço quando presente |
| `nota` | number 0..5 \| null | `NR_NOTA_AVALIACAO` | 1 casa decimal |
| `qt_avaliacoes` | integer ≥ 0 \| null | `QT_AVALIACAO` | |
| `dt_oferta` | date-time | `DT_OFERTA` | |
| `area` | `Area` | `DS_COMUNIDADE` | |
| `publico` | `Publico` | `DS_PUBLICO` | |
| `status` | `ATIVA` \| `ENCERRADA` | `ST_ATIVO` (1/0) | ver §7 |
| `produto` | `Produto` \| null | join | §4.2 |

Não entram: nenhuma URL (CTA = `/ir/{id}`), `VR_PRECO_1`, `DS_CUPOM_COMENTARIO`,
`DT_CAPTACAO`, `DT_PUBLICACAO`, campos de afiliado.

### 4.2 `Produto` (subconjunto da tabela PRODUTO)
Campos opcionais só aparecem no HTML quando não nulos/vazios.

| campo | tipo | origem |
|---|---|---|
| `descricao` | string ≤ 600 | `DS_DESCRICAO_PRODUTO` — primeiro bloco de "Detalhes" |
| `marca` | string \| null | `DS_MARCA` |
| `fabricante` | string \| null | `DS_FABRICANTE` |
| `modelo` | string \| null | `DS_MODELO` |
| `pais_origem` | string \| null | `DS_PAIS_ORIGEM` |
| `genero` | string \| null | `DS_GENERO` |
| `faixa_etaria` | string \| null | `DS_FAIXA_ETARIA` |
| `preco_min` | integer \| null | `VR_PRECO_MINIMO` — centavos |
| `preco_max` | integer \| null | `VR_PRECO_MAXIMO` — centavos |

Indicador de faixa de preço (barra de calor min → atual → max) só renderiza quando
`preco_min`, `preco_max` são não nulos e `preco_min < preco_max`.

---

## 5. URL da oferta e links curtos

- URL canônica: **`/oferta/{id}/`** (ex.: `/oferta/5412/`). Sem slug de título: o dono quer
  links curtos numéricos para canais (`https://besave.io/5412`), e título na URL é um sinal de
  SEO pequeno comparado a `<title>`, `<h1>` e `schema.org`. Ganhos: URL nunca muda, nenhuma coluna
  extra, card 30–40 bytes menor, encurtador trivial (AD-018).
- Domínio curto (`besave.io` ou `besave.me`, a definir): distribuição CloudFront própria com uma
  Function que faz `301 https://besave.com.br/oferta/{id}/` para `/{id}`. Sem KVS, sem estado.
  Variante para conversão direta em canais: `/{id}/ir` → mesmo redirect de afiliado de `/ir/{id}`.
  Entra em BSV-4 como distribuição opcional (ticket separado quando o domínio for escolhido).
- `<title>` e `<h1>` da página carregam o título integral; `<link rel="canonical">` aponta para
  `https://besave.com.br/oferta/{id}/`.

## 6. Imagens

Derivadas do id, nunca campo de dado:

| uso | chave S3 | tamanho |
|---|---|---|
| card da lista | `img/ofertas/{id}_small.webp` | lado maior 320 px, ≤ 25 KB |
| página da oferta | `img/ofertas/{id}.webp` | lado maior 1200 px |
| produto (futuro) | `img/produtos/{id_produto}.webp` | |

Sem imagem no Oracle/S3 → card e página usam placeholder por `area`
(`img/placeholder/{area}.webp`). Ausência de imagem **não** bloqueia publicação.

---

## 7. Ativação, desativação e expurgo — colunas no Oracle

Colunas já criadas pelo dono: `ST_ATIVO NUMBER(1)` (1 ativa, 0 inativa) e `DT_DESATIVACAO DATE`
(preenchida pelo robô quando `ST_ATIVO` vai a 0).

Opcional (decisão do dono; o worker funciona sem ela):

```sql
ALTER TABLE OFERTA ADD (DT_ULT_ATUALIZACAO DATE);  -- trigger BEFORE UPDATE; regerar só o que mudou
```

Sem ela, o worker regera tudo a cada ciclo (30k páginas ≤ 2 min) e o hash evita uploads
repetidos — funciona, só gasta CPU local. `DS_SLUG` **não é mais necessária** (§5).

Regras:
- **Ativa** = `ST_ATIVO = 1`. **Expirada** = `ST_ATIVO = 0`.
- Expiradas **continuam** nos chunks (com `x:1`) e nas páginas, até o expurgo.
- **Expurgo do site** (política do dono): o registro **fica no Oracle**; o worker deixa de
  publicar quando `ST_ATIVO = 0 AND DT_DESATIVACAO < SYSDATE - 7`. Query de publicação:
  `WHERE ST_ATIVO = 1 OR DT_DESATIVACAO >= SYSDATE - 7`. Ids que estavam no último manifest
  e saíram do resultado → worker apaga `oferta/{id}/`, `img/ofertas/{id}*` e a chave na KVS.
  Depois disso a URL responde 404 (410 via função de borda fica para depois).

### 7.1 Página de oferta expirada
- Renderizada **pelo worker** com `status: ENCERRADA` (não por JavaScript: o worker sabe o status
  na geração; JS não é necessário e o Google vê o HTML final). Classe `encerrada` no `<body>`:
  imagem em tons de cinza via CSS (`filter: grayscale(1)`), faixa "Oferta expirada" abaixo do
  título, CTA desabilitado (sem link para `/ir/`), `<meta name="robots" content="noindex">`,
  links para a área e para ofertas ativas similares.
- Sai do sitemap no mesmo ciclo em que vira expirada.

## 8. `Cupom` (tabela CUPOM) — reservado para F3/F4

| campo | tipo | origem |
|---|---|---|
| `id` | integer | `ID_CUPOM` |
| `codigo` | string ≤ 30 | `CUPOM` |
| `descricao` | string ≤ 150 \| null | `DS_CUPOM` |
| `loja` | `Loja` | `DS_LOJA` |
| `dt_cadastro` | date-time | `DT_CADASTRO` |
| `dt_atualizacao` | date-time | `DT_ULT_ATUALIZACAO` |

Não é consumido em F1/F2. Definido aqui para o schema não mudar quando entrar.

---

## 9. Regras de rejeição do worker (registro não publicado, logado com motivo)

- `pp` ausente ou ≤ 0
- `t` vazio após trim
- `l`, `a` ou `p` sem mapeamento em `mapeamento.json`
- `dt` nula
- `pd` presente e `pd ≤ pp` → **não rejeita**: `pd` vira `null`

---

## 10. Perguntas em aberto (respondidas = editar este arquivo e subir a versão)

1. ~~`DS_URL_AFILIADO` sempre preenchida?~~ **Respondido:** sim, oferta sem ela não é gerada. O
   redirect `/ir/{id}` usa `DS_URL_AFILIADO`; `DS_URL_BESAVE`/`DS_URL_FINAL` ficam só no banco.
2. `DS_GENERO`/`DS_FAIXA_ETARIA` do produto são texto livre — ok por ora (só exibição).
3. Cupons da tabela `CUPOM` aparecem na home (F3) ou só em página própria (F4)?
4. `DT_ULT_ATUALIZACAO`: criar ou não? (ver §7)
5. Domínio curto: `besave.io` ou `besave.me`?
