# BSV-62 · Envio: legenda nova (Telegram e WhatsApp) e fila do canal do WhatsApp

**Papel:** Backend Rust + SQL · **Pasta:** `apps/worker/` (+ `docs/CONTRATO.md` §11 e a versão em `packages/contract/package.json`, como na BSV-40) · **Depende de:** BSV-61
mergeada (mesmo módulo `envio/`). BSV-40, BSV-50. Lições 14, 22, 29

## Contexto
O dono criou o canal do WhatsApp **"BeSave - Preços Baixos e Ofertas incríveis"**. A ideia: a **mesma oferta**
que vai ao Telegram vai ao WhatsApp, pelos mesmos critérios. Não há API oficial para postar em canal do
WhatsApp, então quem posta é um publicador com navegador na inst2 (BSV-63), com número próprio.

A seleção e a legenda continuam num lugar só, o `besave-envio`, que já é testado. O publicador só executa.
Esta spec cria a fila entre os dois e muda o layout da legenda nos **dois** canais (pedido do dono, 13/11):
- uma linha em branco depois do título;
- uma linha em branco e uma **frase de aviso** depois do link. A frase avisa que o preço pode mudar a qualquer
  momento; ela e o ícone variam por oferta e vêm de um JSON que o dono edita.

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
3. **Frases de aviso** em `apps/worker/frases_canal.json`, embutido no binário (`include_str!`, como o
   mapeamento embutido) e com troca sem recompilar por `BESAVE_FRASES_CANAL=<caminho>`:
   ```json
   {
     "_obs": "Frase de aviso no fim do post (Telegram e WhatsApp). Uma frase e um ícone por oferta.",
     "icones": ["🚨", "⚠️", "☝️", "❗", "🆘", "🙈", "🏃‍♂️", "🏃‍♀️", "🏃", "🙉", "🙊"],
     "frases": [
       "Atenção, esta promoção pode acabar logo!",
       "Atenção, esta oportunidade pode acabar daqui a pouco...",
       "Aproveite enquanto o preço ainda está baixo!",
       "Garanta agora, antes que o preço mude!",
       "Tudo que é bom dura pouco, aproveite!",
       "Não deixe para depois, pode acabar!",
       "Aproveite agora, essa oferta é só por instantes!",
       "Não fique de fora, a promoção já está no fim!",
       "Compre hoje e fuja do próximo aumento de preço!",
       "Atenção, a oferta pode expirar...",
       "Seja rápido, descontos assim não duram muito tempo!",
       "Clique e garanta o seu antes que o preço mude!"
     ]
   }
   ```
   - Cada ícone é um item da lista, não um caractere: `🏃‍♂️` é uma sequência de vários pontos de código.
   - Arquivo da variável ausente, ilegível, fora do formato ou com lista vazia → WARN no início da execução e
     uso do embutido. Frase com mais de 120 caracteres ou vazia → descartada com WARN.
   - **Escolha por oferta, determinística:** `frase = frases[h(id, "frase") mod n]` e
     `icone = icones[h(id, "icone") mod m]`, com `h` = um hash fixo (por exemplo, os primeiros 8 bytes do
     SHA-256, crate `sha2` já no projeto) de `"{id}:{sal}"`. Vale a mesma frase no Telegram e no WhatsApp da
     mesma oferta, e o resultado é testável. Ofertas diferentes variam, e ids vizinhos não seguem a ordem da
     lista.
   - A linha é `{icone} {frase}`. No Telegram vai em itálico (`<i>…</i>`, texto escapado); no WhatsApp,
     `_…_`, com os marcadores do texto removidos (Saída 5).
4. **Layout novo da legenda nos dois canais** (`envio/legenda.rs`). Hoje o corpo vem colado ao título e o post
   termina no link; passa a ser:
   ```
   {título}
                                  ← linha em branco
   {destaque}
   {preço}
   {caiu mais o preço}
   {cupom}
   {link}
                                  ← linha em branco
   {icone} {frase}
   ```
   - Linhas opcionais vazias continuam sumindo; as duas linhas em branco ficam sempre.
   - Limite: a frase **nunca** é cortada. Se a legenda passar do limite, saem os cupons do fim (fica 1) e
     depois o título, como hoje (`ajustar`/`caber`), já contando a frase e as linhas em branco.
   - "Oferta encerrada" (Telegram, `legenda_encerrada`): também com a linha em branco depois do título, **sem**
     a frase e sem o link, como hoje.
   - Avisos programados (BSV-41): não mudam.
5. **Legenda do WhatsApp** (`envio/legenda.rs`, função nova), mesmas linhas e mesma ordem do item 4, na
   marcação do WhatsApp:
   ```
   *{titulo}*

   {destaque}
   🔥 *-{pct}%*  ~R$ {de}~  *R$ {por}*  🔁 _(Recorrência)_
   📉 *Caiu mais o preço!!!*
   🎟️ Cupom: `{cupom}`          (Cupons: `A` · `B` · `C`)
   Promoção {Loja}: https://besave.io/{id}?utm_source=whatsapp

   {icone} _{frase}_
   ```
   - Mesmas regras de linha opcional, selo, preço `R$ 1.234,56`, nome da loja e "Caiu mais o preço" (o mesmo
     `caiu` do post do Telegram).
   - **Texto variável** (título, destaque, cupom, frase): `*`, `_`, `~` e `` ` `` são removidos, porque o
     WhatsApp não tem escape e eles quebrariam a marcação. Espaços repetidos viram um.
   - Limite: **1024 caracteres e 4000 bytes UTF-8**, com o corte do item 4.
6. **CONTRATO §11:** o layout do item 4 (Telegram) e uma subseção "Legenda do WhatsApp" com o modelo do item
   5, as frases (`frases_canal.json`, escolha por id), o `utm_source=whatsapp` e a fila; versão **1.7.0**. Sem
   schema novo: a projeção é a mesma `OfertaCanal`.
7. README do worker: a variável do espelho, a das frases (como trocar e incluir uma frase sem recompilar), o
   SQL e como pausar o espelho (tirar a variável).

## Regras
1. A seleção (critérios, repetição, ordem) é a do canal do Telegram. O canal 2 só define teto e janela, que
   o publicador aplica.
2. Sem dependência nova. Nenhum segredo novo: a fila não guarda número, sessão nem link de convite.
3. A fila não altera `ENVIO_TELEGRAM` nem o cálculo de cota do canal 1.
4. O texto das frases é do dono; o código não as reescreve nem filtra além das regras do item 3. Ficam de fora
   frases que afirmam estoque, exclusividade ou "última chance" (decisão do dono, 13/11): o Besave não sabe o
   estoque da loja.

## Fora de escopo
- O publicador (BSV-63).
- Avisos e "Oferta encerrada" no WhatsApp.
- Seleção própria do WhatsApp.
- Reeditar posts antigos do Telegram com o layout novo: só a edição de "Oferta encerrada" usa o layout novo,
  porque já regrava a legenda.

## Critério de aceite
Fakes de Oracle, Telegram e relógio, como nos testes da BSV-40.
- **Espelho:** Telegram confirma → 1 linha `P` com legenda, `ID_ENVIO_TELEGRAM` e `DS_AREA_SLUG` da área
  da oferta (`MEU_LAR` → `meu-lar`); Telegram falha → 0 linhas;
  sem a variável → 0 linhas; falha ao inserir → WARN, código 0, `ENVIO_TELEGRAM` confirmado intacto;
  inserir a mesma oferta duas vezes → 1 linha, sem erro.
- **Layout (Telegram e WhatsApp)**, legenda comparada inteira (lição 14):
  - linha em branco depois do título e antes da frase; frase como última linha;
  - com e sem `pd`; `pct` 29% (sem selo) e 45%; recorrência; 1 e 3 cupons; destaque; `caiu`; sem nenhuma
    opcional, as duas linhas em branco continuam;
  - o exemplo do dono, oferta 51217 (Mercado Livre, R$ 104,00 → R$ 50,00, -52%, cupom `MANTECORP15`), nos
    dois canais.
- **Frases:**
  - a mesma oferta dá a mesma frase e o mesmo ícone no Telegram e no WhatsApp, e em duas execuções;
  - 1.000 ids seguidos usam todas as frases e todos os ícones, nenhuma frase passa de 15% dos ids e ids
    vizinhos não seguem a ordem da lista (o mutante `id mod n` falha);
  - `🏃‍♂️` sai inteiro (o mutante que separa por caractere falha);
  - variável com arquivo válido de 2 frases → só essas 2 aparecem; arquivo inválido ou lista vazia → WARN e
    as frases embutidas;
  - frase com `<&>` → escapada no Telegram; frase com `*` → sem o `*` no WhatsApp.
- **Limite:** título longo com 3 cupons → saem cupons, depois o título é cortado, a frase fica inteira e a
  legenda ≤ 1024 (Telegram, UTF-16) e ≤ 1024 caracteres e 4000 bytes (WhatsApp). O mutante que corta a
  frase falha; o mutante que só mede caracteres no WhatsApp falha.
- **Encerrada:** linha em branco depois do título, sem frase e sem link.
- **Isolamento:** a legenda do aviso (BSV-41) não muda. Os testes de legenda da BSV-40 e da BSV-50 que
  comparam o layout são **atualizados** para o layout novo, e só neles; o PR lista cada teste alterado e o
  porquê (regra 2: mudança de requisito, não afrouxamento).
- **Gates:** `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`;
  `cd packages/contract && npm run validate`.
- **Real (dono, bloqueia o merge):**
  1. rodar o SQL;
  2. `besave-envio --sim` com o binário da branch na inst2 mostra o layout novo com frase e ícone;
  3. ao longo de 2 h, posts do Telegram com o layout novo, frases variando, e cada post confirmado com uma
     linha `P` no WhatsApp com a legenda certa (`SELECT` redigido no PR);
  4. trocar uma frase no arquivo de `BESAVE_FRASES_CANAL`: a próxima execução já usa o texto novo, sem
     recompilar.

## Definition of done
PR para `develop` com SQL, código, `frases_canal.json`, CONTRATO 1.7.0, README, testes, `validation.md` do
Verifier independente (com sensor de discriminação) e as decisões propostas: o WhatsApp espelha o
Telegram; a legenda é gerada em Rust; a fila fica no Oracle; frase escolhida por hash do id.
