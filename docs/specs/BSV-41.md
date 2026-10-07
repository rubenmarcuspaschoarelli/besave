# BSV-41 · Worker: avisos programados no canal e páginas `/avisos/{id}/`

**Papel:** Backend Rust · **Pasta:** `apps/worker/` (+ `docs/MANIFEST.md` §1, §4) ·
**Depende de:** BSV-40 (mergeado: `besave-envio`, `CANAL_ENVIO`, foto 800×800, cliente do bot do canal).
MANIFEST.md §1, §4, §6; AD-006, AD-032, AD-034, AD-041, AD-072 · DDL: `apps/worker/sql/bsv-41.sql`

## Contexto
Além de ofertas, o dono quer postar no canal mensagens próprias (aviso de afiliado, campanhas, "ofertas
do dia") com foto, título e link para uma página do site, repetidas numa frequência escolhida por canal
(ex.: a cada 2 h). O conteúdo é cadastrado no Oracle; o template da página será refinado depois.

## Objetivo
`besave-ciclo` publica `/avisos/{id}/` para cada aviso ativo; `besave-envio` posta cada aviso no(s)
canal(is) ligado(s) a ele, na frequência própria, dentro da janela do canal.

## Saídas
1. **Oracle:** `apps/worker/sql/bsv-41.sql` (rodado pelo dono antes do ticket; usar como está):
   `AVISO` (`DS_TITULO` ≤ 120, `DS_TEXTO` ≤ 800, `DS_IMAGEM` = nome de arquivo em `BESAVE_AVISOS_DIR`,
   `DS_LINK_INTERNO` = caminho do site começando com `/`, `ST_ATIVO`, `DT_INICIO`, `DT_FIM`,
   `DT_PUBLICACAO_SITE`);
   `AVISO_CANAL` (`ID_AVISO`, `ID_CANAL`, `NR_INTERVALO_MIN` padrão 120, `ST_ATIVO`);
   `ENVIO_AVISO` (registro de cada post, `NR_MESSAGE_ID`, `DT_ENVIO`).
2. **Página** `avisos/{id}/index.html` (minijinja, mesmo `besave.css`; `noindex` por ora): título, imagem,
   texto em parágrafos (escapado, sem HTML do banco), botão para `DS_LINK_INTERNO` quando houver, link
   para o canal. Imagem publicada em `img/avisos/{id}.{webp|jpg}`.
3. **Ciclo:** índice `_estado/avisos.json` (id → hash da página e da imagem), como o de páginas
   (AD-041): só sobe o que mudou; aviso inativo, fora de `[DT_INICIO, DT_FIM]` ou apagado → remove a página
   e a imagem e sai do índice. O ciclo grava `AVISO.DT_PUBLICACAO_SITE = SYSDATE` quando a página vai
   ao ar e volta para nula quando ela sai (como a OFERTA na BSV-40; o envio não lê o S3). Fase nova no relatório (`avisos_publicados`, `avisos_removidos`, `t_avisos`).
4. **Envio:** a cada execução, antes do lote de ofertas, no máximo **1 aviso** por canal: o de
   `AVISO_CANAL` ativo com `AVISO.DT_PUBLICACAO_SITE` preenchida, vigente, com o maior atraso
   (`agora − último envio ≥ NR_INTERVALO_MIN`; nunca enviado = atraso máximo). Mesma janela e mesmo
   horário silencioso do canal (`PARAMETROS_ENVIO`); avisos **não** contam na cota `QT_MAX_DIA` de ofertas.
5. **MANIFEST.md:** §1 com `avisos/{id}/index.html`, `img/avisos/{id}.{webp,jpg}`, `_estado/avisos.json`;
   §4 com os headers (`avisos/*` igual a `oferta/*`; `img/avisos/*.jpg` = `image/jpeg`, imutável não:
   `public, max-age=3600`, porque a imagem do aviso pode ser trocada no mesmo nome).
6. README: cadastrar um aviso (SQL de exemplo), pasta de imagens, como pausar.

## Regras
1. **Legenda** (`parse_mode=HTML`, ≤ 1024, escapada): `<b>{titulo}</b>` / `{texto}` /
   `<a href="https://besave.com.br/avisos/{id}/?utm_source=telegram">Saiba mais</a>`. Sem imagem →
   `sendMessage` com o mesmo texto e prévia do link ligada.
2. **Foto:** `BESAVE_AVISOS_DIR/{DS_IMAGEM}` (só `.webp` ou `.jpg`; outro formato → aviso ignorado com
   WARN), 800×800 branco como na BSV-40 para o Telegram; na página, o arquivo original (≤ 1 MB, senão WARN
   e página sem imagem).
3. **`DS_LINK_INTERNO`** só aceita caminho do próprio site (`^/[a-z0-9/_-]*$`); qualquer outra coisa →
   botão omitido + WARN. Nunca URL de afiliado ou externa na página (regra 6 do CLAUDE.md).
4. **Sem duplicata:** reserva → envia → confirma, como `ENVIO_TELEGRAM` (BSV-40 regra 7).
5. Falha no aviso não impede o lote de ofertas da mesma execução; 429 encerra a execução (BSV-40 regra 9).
6. Sem dependência nova.

## Fora de escopo
Template definitivo da página, indexação dos avisos, edição/remoção de posts antigos de aviso, link curto
`besave.io` para avisos, agendamento por dia da semana, mais formatos de imagem.

## Critério de aceite
- Ciclo (fakes): 2 avisos ativos → 2 páginas + 2 imagens + índice; segunda execução → 0 uploads; aviso
  desativado → página e imagem removidas; `DT_FIM` no passado → removido; texto com `<script>` → escapado;
  `DS_LINK_INTERNO` `https://loja.com` → sem botão + WARN; imagem `.png` → aviso ignorado + WARN.
- Envio (fakes, relógio): intervalo 120 → enviado às 08:00, não às 09:55, de novo às 10:00; fora da janela
  → 0; dois avisos vencidos → só o mais atrasado; `DT_PUBLICACAO_SITE` nula → não envia; ciclo grava a data ao publicar e a anula ao remover; aviso não reduz a cota
  de ofertas; falha no Telegram → linha apagada e o lote de ofertas segue; sem imagem → `sendMessage`.
- Legenda com link `utm_source=telegram`, ≤ 1024, escapada.
- `cargo fmt --check`, `clippy -D warnings`, `cargo test` sem rede.
- **Real (dono):** rodar o DDL; cadastrar um aviso de afiliado com imagem, ligado ao canal 1 a cada 120 min;
  `https://besave.com.br/avisos/{id}/` abre com imagem e texto; `--sim` mostra o aviso; ao longo de um dia,
  o aviso aparece a cada ~2 h entre 8 h e 22 h; desativar → página some no ciclo seguinte e o envio para.

## Definition of done
PR com README, MANIFEST §1/§4 atualizados, prints do canal e da página, `validation.md` do Verifier
independente, testes verdes.
