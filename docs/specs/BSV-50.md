# BSV-50 · Cupom com vários códigos e faixa "Encerrada" na página da oferta

**Papel:** Backend Rust (+ contrato e CSS) · **Pastas:** `apps/worker/` (conversão, template, envio),
`packages/contract/` (schema e fixtures da `OfertaPagina`), `docs/CONTRATO.md`, e só as classes novas em
`apps/site/src/lib/estilo/besave.css` · **Depende de:** BSV-47 (PR #87) **mergeada** (mesmo crate).
CONTRATO §3, §4, §11; AD-093, AD-096, AD-102

## Contexto
`DS_CUPOM` às vezes traz vários códigos separados por `|` (ex.: `MELI26TODOSITE | SITEMELI26 |
MELI26SITETODO`, `ISDIN15D | SMARTWATCHES10`). O worker valida o campo inteiro contra `^[A-Z0-9_-]+$`
(até 30) e, como não passa, **omite o cupom** (`cupom fora do padrão; omitido`, ~150 ofertas por ciclo em
20/10). A decisão do dono (AD-102, opção B) é separar os códigos: o card leva o primeiro válido, a página
da oferta e a legenda do canal mostram todos. O robô não muda. Junto, a faixa da página da oferta passa de
"Oferta expirada" para **"Encerrada"**, a palavra dos cards e da busca.

## Objetivo
Toda oferta com pelo menos um código válido aparece com cupom no site e no canal, e a página da oferta
mostra todos os códigos, cada um copiável.

## Saídas
1. **Separação** (uma função só, usada por card, página e canal): `DS_CUPOM` dividido por `|`; cada parte
   com trim e maiúsculas; válida se casar `^[A-Z0-9_-]{1,30}$`; duplicadas removidas mantendo a ordem;
   no máximo 5 (o resto sai com WARN). Parte inválida sai com WARN (id e parte). Nenhuma válida → sem
   cupom (como hoje).
2. **Card (`c`):** o primeiro código válido. Sem mudança de formato nem de orçamento.
3. **Página (`OfertaPagina`):** campo novo `cupons` (lista de 0 a 5 códigos); `cupom` continua existindo
   e igual ao primeiro (compatível). Template: lista dos códigos abaixo do preço, cada um com botão de
   copiar (mesmo script mínimo de AD-093, estendido); o botão principal "Copiar cupom e ir para a loja"
   continua com o primeiro (AD-096 vale igual, inclusive o texto sem JavaScript). Classes novas no
   `besave.css`, documentadas no README dos templates.
4. **Faixa "Encerrada"** no lugar de "Oferta expirada" (texto e README do template; a classe `expirada`
   pode continuar).
5. **Canal (`OfertaCanal`, §11):** campo `cupons`; a legenda mostra todos (ex.: `Cupons: A · B · C`),
   dentro do limite de 1.024 caracteres (corta códigos do fim antes de cortar o título).
6. **Contrato:** CONTRATO §3 (regra do `c`), §4 (`cupons`) e §11 (`cupons`); schema e fixtures da
   `OfertaPagina`; versão **1.6.0** (campo novo, compatível). Tudo na mesma PR (regra 10).

## Regras
1. **Ordem do teste real** (como BSV-34/38): primeiro o deploy do site (CSS novo), depois o worker na VPS
   (as ~150 páginas com cupom múltiplo e todas as encerradas mudam uma vez).
2. HTML da oferta ≤ 30 KB; mesmo input → mesmos bytes (idempotência).
3. Nada de cupom na URL nem fora do formato validado (o código vai para a página como texto escapado).
4. Sem dependência nova.

## Fora de escopo
Cupons da tabela `CUPOM` no site, mudança no robô (gravar códigos separados), cupom no card além do
primeiro, filtro por cupom.

## Critério de aceite
- Testes da separação com os casos reais do log de 20/10 (dois e três códigos, repetido, parte inválida,
  mais de 5, só inválidos, espaços e minúsculas).
- Card: primeiro código válido; página: `cupons` completo e `cupom` = primeiro; canal: legenda com todos e
  corte respeitando 1.024.
- Template: lista com botão de copiar por código; sem JavaScript continua link para `/ir/{id}`; faixa
  "Encerrada"; HTML ≤ 30 KB.
- `npm run validate` do contrato com as fixtures novas; gates do worker (`fmt`, `clippy`, `test`) e
  workflow ARM verdes; `pnpm` do site verde se o CSS mudar.
- **Real (dono):** deploy do site; worker da PR na VPS; contagem de `cupom fora do padrão` no log cai de
  ~150 para só as partes realmente inválidas; uma página com 3 códigos conferida no celular (copiar cada
  um); um post do canal com mais de um código; uma oferta encerrada com a faixa "Encerrada".

## Definition of done
PR com contrato, worker e CSS juntos, prints da página (com 1 e com 3 cupons, e encerrada; celular e
computador), `validation.md` do Verifier independente e a execução real antes do merge.
