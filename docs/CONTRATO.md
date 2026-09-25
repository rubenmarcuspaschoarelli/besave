# CONTRATO.md — Schema canônico (BSV-1)

Fonte da verdade para todo dado que sai do Oracle e chega ao site, ao app e aos bots.
Os arquivos JSON Schema em `packages/contract/schema/` são a forma executável deste documento;
se divergirem, o JSON Schema vence e este arquivo é corrigido.

Versão do contrato: **1.0.0** (SemVer; mudança incompatível = major).

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
7. **Identidade e ordem vêm do Oracle** (`ID_OFERTA`); `slug` é derivado e estável.

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

### 2.3 `Area` (as 9 áreas de interesse)
| valor | rótulo de exibição | origem em `DS_COMUNIDADE` |
|---|---|---|
| `TECH` | Tech | `TECH`, `TECNOLOGIA` |
| `PLAYERS` | Players | `PLAYERS`, `GAMES`, `GAMER` |
| `MEU_LAR` | Meu Lar | `MEU LAR`, `LAR`, `CASA` |
| `ELAS` | Elas | `ELAS` |
| `ELES` | Eles | `ELES` |
| `CULTURA` | Cultura | `CULTURA` |
| `FAMILIA` | Família & filhos | `FAMILIA`, `FAMILIA & FILHOS`, `FAMILIA E FILHOS` |
| `PETS` | Pets | `PETS`, `PET` |
| `ESPORTE_VIDA` | Esporte & vida | `ESPORTE`, `ESPORTE & VIDA`, `ESPORTE E VIDA` |

A tabela de mapeamento texto → enum vive em `packages/contract/mapeamento.json` e é o
único lugar onde novos sinônimos entram. O worker rejeita o que não mapear.

---

## 3. `OfertaCard` — projeção compacta (chunks da lista e da busca)

Orçamento: **≤ 220 bytes por registro em JSON bruto** (meta ~150). Chaves curtas por isso.

| campo | tipo | origem | regra |
|---|---|---|---|
| `id` | integer ≥ 1 | `ID_OFERTA` | chave |
| `s` | string | derivado | slug, ver §5 |
| `l` | `Loja` | `DS_LOJA` | enum |
| `t` | string 1..200 | `DS_TITULO` | trim; se > 200, corta em 197 + `…` na última fronteira de palavra |
| `pd` | integer ≥ 0 \| null | `VL_PRECO_DE` | centavos; `null` se ausente ou ≤ `pp` |
| `pp` | integer ≥ 1 | `VL_PRECO_POR` | centavos; obrigatório |
| `c` | string 1..30 \| ausente | `DS_CUPOM` | só presente se houver cupom; trim, maiúsculas |
| `dt` | string date-time | `DT_OFERTA` | ISO 8601 UTC |
| `a` | `Area` | `DS_COMUNIDADE` | enum |
| `p` | `Publico` | `DS_PUBLICO` | enum |

Não entram no card (decidido): `ID_PRODUTO`, URLs, `VR_PRECO_1`, `DS_CUPOM_COMENTARIO`,
nota/qtd de avaliação, `DT_CAPTACAO`, `DT_PUBLICACAO`, campos de afiliado.

Desconto (%) **não é campo**: o cliente calcula `round((1 - pp/pd) * 100)` quando `pd != null`.

Exemplo:
```json
{"id":5412,"s":"5412-fone-bluetooth-xyz-anc","l":"AMAZON","t":"Fone Bluetooth XYZ com ANC","pd":29990,"pp":19990,"c":"BESAVE10","dt":"2026-09-24T12:40:00Z","a":"TECH","p":"UNISSEX"}
```

---

## 4. `OfertaPagina` — projeção completa (embutida no HTML da oferta)

Consumida só pelo template do worker. Chaves legíveis (não há orçamento de bytes aqui).

### 4.1 Oferta
| campo | tipo | origem | regra |
|---|---|---|---|
| `id` | integer | `ID_OFERTA` | |
| `slug` | string | derivado | §5 |
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
| `status` | `ATIVA` \| `ENCERRADA` | derivado de `DT_DESATIVACAO` | ver §7 |
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

## 5. Slug

`slug = "{id}-{titulo_slugificado}"`

- `titulo_slugificado`: NFKD, remove diacríticos, minúsculas, `[^a-z0-9]+` → `-`, trim de
  `-`, máximo **60 caracteres** cortando na última fronteira de `-`.
- O `id` na frente garante unicidade e estabilidade; o título só serve ao SEO.
- Slug **nunca muda** depois de publicado, mesmo que o título mude no Oracle.
- URL da oferta: `/oferta/{slug}/`. Se alguém acessar `/oferta/{id}` ou um slug com título
  antigo, o site resolve pelo prefixo numérico (client-side em F3; redirect de borda depois).

---

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

## 7. Versão, atualização e desativação — **exige 3 colunas novas no Oracle**

A tabela `OFERTA` atual não tem como o worker saber *o que mudou* nem *o que foi
desativado*. Adicionar (robô ou trigger preenche):

```sql
ALTER TABLE OFERTA ADD (
  DT_DESATIVACAO      DATE,                           -- robô grava quando a oferta morre
  DT_ULT_ATUALIZACAO  DATE DEFAULT SYSDATE NOT NULL,  -- trigger BEFORE UPDATE
  DS_SLUG             VARCHAR2(80 CHAR)               -- worker grava na 1ª publicação, nunca altera
);
CREATE INDEX IX_OFERTA_ULT_ATU ON OFERTA (DT_ULT_ATUALIZACAO);
```

Regras:
- **Ativa** = `DT_DESATIVACAO IS NULL`.
- O worker seleciona ativas para os chunks; para páginas HTML, seleciona ativas + desativadas
  nos últimos 30 dias (para publicar a versão "encerrada", §7.1).
- `DT_ULT_ATUALIZACAO` permite ao worker regerar só o que mudou (`> última execução`).
  Sem ela, o worker regera tudo a cada ciclo — funciona, só custa mais.
- `DS_SLUG` guardado no banco evita que um retítulo mude a URL.

### 7.1 Oferta encerrada
- Sai dos chunks (o hash do chunk muda; o cliente rebaixa o chunk — ver MANIFEST.md).
- A página HTML é **regerada** como "oferta encerrada": mesmo layout, preço riscado,
  CTA desabilitado, `<meta name="robots" content="noindex">`, links para a área. Não é
  apagada por 30 dias (tráfego residual do Google vira navegação, não 404).
- Após 30 dias da desativação, a página é apagada e sai do sitemap. (410 real via função
  de borda fica para depois; noindex resolve o SEO agora.)

---

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

1. `DS_URL_BESAVE` vs `DS_URL_FINAL`: nenhuma entra no contrato. O redirect usa
   `DS_URL_AFILIADO` (a curta, ex.: `https://s.shopee.com.br/...`). Confirmar que
   `DS_URL_AFILIADO` está sempre preenchida nas 3 lojas.
2. `DS_GENERO`/`DS_FAIXA_ETARIA` do produto são texto livre — ok por ora (só exibição).
3. Cupons da tabela `CUPOM` aparecem na home (F3) ou só em página própria (F4)?
