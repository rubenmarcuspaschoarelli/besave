# BSV-62 · Envio: fila do canal do WhatsApp, espelho do Telegram

**Papel:** Backend Rust + SQL · **Pasta:** `apps/worker/` (+ `docs/CONTRATO.md` §11 e a versão em `packages/contract/package.json`, como na BSV-40) · **Depende de:** BSV-61
mergeada (mesmo módulo `envio/`). BSV-40, BSV-50. Lições 14, 22, 29

## Contexto
O dono criou o canal do WhatsApp **"BeSave - Preços Baixos e Ofertas incríveis"**. A ideia: a **mesma oferta**
que vai ao Telegram vai ao WhatsApp, pelos mesmos critérios. Não há API oficial para postar em canal do
WhatsApp, então quem posta é um publicador com navegador na inst2 (BSV-63), com número próprio.

A seleção e a legenda continuam num lugar só, o `besave-envio`, que já é testado. O publicador só executa.
Esta spec cria a fila entre os dois.

## Saídas
1. **SQL** `apps/worker/sql/bsv-62.sql` (rodado pelo dono; checagem 0 como em `bsv-40.sql`):
   - `CANAL_ENVIO` 2: `DS_NOME 'WhatsApp'`, `DS_CHAT_ID` = nome do canal como aparece no WhatsApp Web.
   - `PARAMETROS_ENVIO` 2: `QT_MAX_DIA 40`, `NR_HORA_INICIO 8`, `NR_HORA_FIM 22`. É o teto do número novo; o dono
     sobe por semana, sem código. Os demais campos ficam no padrão e o canal 2 não os usa.
   - `ENVIO_WHATSAPP`:
     - `ID_ENVIO_WA` (sequence `SQ_ENVIO_WHATSAPP`), `ID_CANAL` (FK), `ID_OFERTA`, `ID_ENVIO_TELEGRAM`;
     - `DS_LEGENDA VARCHAR2(4000 BYTE)`;
     - `DS_AREA_SLUG VARCHAR2(20)`: slug de URL da área (CONTRATO §2.3, ex.: `meu-lar`), para o publicador usar
       o mesmo placeholder do Telegram quando a oferta não tiver foto;
     - `ST_ENVIO CHAR(1)`: `P` pendente, `E` enviado, `D` duvidoso, `X` descartado;
     - `DS_MOTIVO VARCHAR2(60)`, `DT_FILA`, `DT_ENVIO`;
     - únicos: `ID_CANAL` + `ID_OFERTA`;
     - índice em (`ID_CANAL`, `ST_ENVIO`, `DT_FILA`);
     - sem FK para `OFERTA`, igual a `ENVIO_TELEGRAM`;
     - `GRANT`s comentados para outro usuário.
2. **Espelho:** com `BESAVE_ENVIO_ESPELHO_WHATSAPP=<ID_CANAL>` (ex.: `2`), depois de **confirmar** um post de
   **oferta** no Telegram (`NR_MESSAGE_ID` gravado), o envio insere a linha `P` com a legenda do WhatsApp.
   - Avisos (BSV-41) e a edição "Oferta encerrada" não entram.
   - Falha ao inserir → WARN (`id`, motivo), o post do Telegram fica como está, a execução segue. O WhatsApp
     nunca atrasa nem desfaz o Telegram.
   - Duplicata (único violado) → ignora em silêncio, porque a linha já está na fila.
   - Variável ausente → não enfileira nada (comportamento de hoje).
3. **Legenda do WhatsApp** (`envio/legenda.rs`, função nova; a do Telegram não muda), mesmas linhas e mesma
   ordem da regra 6 da BSV-40, na marcação do WhatsApp:
   ```
   *{titulo}*
   {destaque}
   🔥 *-{pct}%*  ~R$ {de}~  *R$ {por}*  🔁 _(Recorrência)_
   📉 *Caiu mais o preço!!!*
   🎟️ Cupom: `{cupom}`          (Cupons: `A` · `B` · `C`)
   Promoção {Loja}: https://besave.io/{id}?utm_source=whatsapp
   ```
   - Mesmas regras de linha opcional, selo, preço `R$ 1.234,56`, nome da loja e "Caiu mais o preço" (o mesmo
     `caiu` do post do Telegram).
   - **Texto variável** (título, destaque, cupom): `*`, `_`, `~` e `` ` `` são removidos, porque o WhatsApp
     não tem escape e eles quebrariam a marcação. Espaços repetidos viram um.
   - Limite: **1024 caracteres e 4000 bytes UTF-8**. Corta os cupons do fim (fica 1) e depois o título
     (fronteira de palavra + `…`), reusando `ajustar`/`caber`.
4. **CONTRATO §11:** subseção "Legenda do WhatsApp" com o modelo acima, o `utm_source=whatsapp` e a fila;
   versão **1.7.0**. Sem schema novo: a projeção é a mesma `OfertaCanal`.
5. README do worker: a variável, o SQL e como pausar o espelho (tirar a variável).

## Regras
1. A seleção (critérios, repetição, ordem) é a do canal do Telegram. O canal 2 só define teto e janela, que
   o publicador aplica.
2. Sem dependência nova. Nenhum segredo novo: a fila não guarda número, sessão nem link de convite.
3. A fila não altera `ENVIO_TELEGRAM` nem o cálculo de cota do canal 1.

## Fora de escopo
- O publicador (BSV-63).
- Avisos e "Oferta encerrada" no WhatsApp.
- Seleção própria do WhatsApp.

## Critério de aceite
Fakes de Oracle, Telegram e relógio, como nos testes da BSV-40.
- **Espelho:** Telegram confirma → 1 linha `P` com legenda, `ID_ENVIO_TELEGRAM` e `DS_AREA_SLUG` da área
  da oferta (`MEU_LAR` → `meu-lar`); Telegram falha → 0 linhas;
  sem a variável → 0 linhas; falha ao inserir → WARN, código 0, `ENVIO_TELEGRAM` confirmado intacto;
  inserir a mesma oferta duas vezes → 1 linha, sem erro.
- **Legenda**, comparada inteira (lição 14):
  - com e sem `pd`; `pct` 29% (sem selo) e 45%; recorrência; 1 e 3 cupons; destaque; `caiu`;
  - título com `*promo* _top_ ~x~` → sem os marcadores;
  - link com `utm_source=whatsapp`;
  - título longo → ≤ 1024 caracteres;
  - título de emojis → ≤ 4000 bytes. O mutante que só mede caracteres falha.
- **Isolamento:** a legenda do Telegram dos testes da BSV-40 não muda (testes de hoje verdes).
- **Gates:** `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`;
  `cd packages/contract && npm run validate`.
- **Real (dono, bloqueia o merge):** rodar o SQL; binário da branch na inst2 com a variável; ao longo de 2 h,
  cada post confirmado no Telegram tem uma linha `P` com a legenda certa (`SELECT` redigido no PR).

## Definition of done
PR para `develop` com SQL, código, CONTRATO 1.7.0, README, testes, `validation.md` do Verifier
independente (com sensor de discriminação) e as decisões propostas: o WhatsApp espelha o Telegram; a
legenda é gerada em Rust; a fila fica no Oracle.
