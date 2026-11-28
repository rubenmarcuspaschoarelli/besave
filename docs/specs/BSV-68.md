# BSV-68 · Caractere invisível na URL da oferta: limpar na captura e no robô das lojas

**Papel:** Python (stdlib) · **Pasta:** `tools/capture-chat-groups/wa/parser.py` e
`tools/capture-store-pages/` (`main.py`, `core/shopee_api.py`, módulo novo `core/url.py`) + testes em
`tools/capture-chat-groups/tests/` e `tools/tests/` · **Depende de:** nada (BSV-65 em `main`). Não conflita
com a BSV-67 (que mexe em `wa/browser.py`). Lições 14, 29

## Contexto
Em 27/11, a partir de 12:37, um grupo de WhatsApp passou a mandar links com um **U+2060 (word joiner)**
invisível colado no fim. O WhatsApp Web põe esse caractere dentro do `href` do link; o robô do WhatsApp grava o
`href` como está em `DS_URL_ORIGEM` (`wa/parser.py`, `parse_campos`). Até as 16:46, cinco linhas:

| linha | link | o que aconteceu |
|---|---|---|
| 64926, 65359, 65368 | `meli.la/…⁠` | `'9'` `pagina_sem_produto`: o Chromium abre o link curto com `%E2%81%A0` no fim e cai numa página que não existe — **oferta perdida** |
| 65104 | `s.shopee.com.br/…⁠` | `'0'` retida para sempre: o HEAD do `urllib` em `shopee_api.resolver` levanta `UnicodeEncodeError`, que é `ValueError` e cai no ramo de rede fora → `api_indisponivel` (passageiro) a cada varredura |
| 65206 | site próprio do grupo | `loja_desconhecida` (correto, independe do caractere) |

Antes de 27/11 não havia nenhuma linha com U+2060. Os 6 casos antigos de não-ASCII na fila (✨ e 🚨 em
`http://✨GA.MA…`) são texto que não é link e foram descartados corretamente; ficam como estão.

## Saídas
1. **Limpeza da URL, uma regra.** `limpar_url(texto) -> str`: tira todo caractere de categoria Unicode `Cf`
   (formatação: U+00AD, U+200B–U+200F, U+202A–U+202E, U+2060–U+2064, U+FEFF e os demais `Cf`) em qualquer
   posição e depois faz `strip()`. `None`/vazio → `''`. Nada mais muda: letra acentuada, `%XX`, emoji e
   maiúsculas ficam como vieram (não é normalizador de URL). A função existe nos dois robôs (pacotes
   separados, sem import cruzado), com o **mesmo corpo** e a **mesma tabela de teste** (Saída 5).
2. **Robô do WhatsApp.** Em `parse_campos`, cada link de `bruto["links"]` passa por `limpar_url` **antes** de
   `eh_link_whatsapp` e da escolha do 1º link; link que vira vazio é descartado. `DS_URL_ORIGEM` sai limpa.
   Nenhuma outra coluna muda (o texto da mensagem fica intacto).
3. **Robô das lojas.** Em `_adaptar_linhas` (`main.py`), `linha['url'] = limpar_url(DS_URL_ORIGEM)` no lugar
   do `.strip()`. Quando a limpeza mudou algo, uma linha de log por linha da fila:
   `[url] linha 65104: removidos 1 caractere(s) invisivel(is) (U+2060)` (códigos distintos, em ordem de
   aparição). Cobre o que já está na fila e qualquer outra origem (captura web da BSV-66). `DS_URL_ORIGEM` não
   é regravada no banco.
4. **Resolver da Shopee não prende a linha.** Em `core/shopee_api.resolver`, `UnicodeError` (inclui
   `UnicodeEncodeError`) vira `URL_NAO_RECONHECIDA` (não passageiro), com log
   `shopee api: url_nao_reconhecida (resolver: UnicodeEncodeError)`. Os outros `ValueError`/`OSError`/
   `HTTPException` seguem passageiros como hoje. Com a Saída 3 não deve acontecer; é a rede de segurança para
   não haver linha retida para sempre por URL.
5. **Testes.**
   - Tabela única (copiada nos dois lados; teste compara a lista de pares inteira):
     `https://meli.la/AbC123⁠` → `https://meli.la/AbC123`;
     `​https://s.shopee.com.br/XyZ﻿` → `https://s.shopee.com.br/XyZ`;
     `https://amzn.to/a‍b⁠` → `https://amzn.to/ab`;
     ` https://x.com.br/p­ ` → `https://x.com.br/p`;
     `https://www.magazineluiza.com.br/caf%C3%A9/p/123/` → igual;
     `https://exemplo.com.br/café?q=✨` → igual;
     `⁠` → `''`; `''` → `''`; `None` → `''`.
   - Parser: mensagem cujo `links` é `["https://chat.whatsapp.com/Abc⁠", "https://meli.la/AbC123⁠"]`
     → `url == "https://meli.la/AbC123"` (o convite é reconhecido e pulado mesmo com o caractere);
     `links == ["⁠"]` → `url == ""`.
   - Robô das lojas: `_adaptar_linhas` com `DS_URL_ORIGEM` sujo → `url` limpo e a linha de log inteira
     comparada; limpo → sem log.
   - Resolver: `abrir` simulado levantando `UnicodeEncodeError` → `(None, URL_NAO_RECONHECIDA)`; levantando
     `OSError` → `API_INDISPONIVEL` (o de hoje não muda); e o resolver chamado com URL suja depois da Saída 3
     nunca chega ao `abrir` com caractere `Cf` (teste pelo caminho de `_adaptar_linhas` → captura Shopee com o
     `abrir` simulado registrando a URL recebida).
   - Mutantes: tirar `limpar_url` de `_adaptar_linhas`; limpar só as pontas (`strip` com a lista) em vez de
     qualquer posição; trocar `Cf` por uma lista que não tem U+2060; devolver `UnicodeError` como passageiro.

## Regras
1. Sem dependência nova (`unicodedata` é stdlib). Sem mudança de banco ou de unidade.
2. Teste de mensagem e de tabela compara inteiro (lição 14).
3. Fixture e teste sem URL real do grupo nem marca de afiliado: ids inventados como os da Saída 5.

## Fora de escopo
- Reprocessar as linhas de 27/11 (SQL do dono, abaixo).
- Emoji ou outro texto colado à URL (não é `Cf`); os casos antigos já foram descartados como `loja_desconhecida`.
- Idade máxima de linha retida por `shopee_api_indisponivel` (outro assunto; com a Saída 4 a causa desta some).

## Recuperação (dono, independe do merge)
As três ofertas do Mercado Livre perdidas em 27/11 (até 24 h, como no README):
```sql
UPDATE OFERTA_FILA_CAPTURA
   SET DS_URL_ORIGEM = REPLACE(DS_URL_ORIGEM, UNISTR('\2060')), ST_CAPTURA = '0'
 WHERE ID_OFERTA IN (64926, 65359, 65368);
COMMIT;
```
A 65104 fica como está: é o caso do teste real (passo 2).

## Critério de aceite
- Job `tools` verde: `unittest` de `capture-chat-groups/tests` (onde fica o teste do parser), `pytest` em
  `tools/` e `ruff`; sensor de discriminação com os mutantes da Saída 5.
- **Real (dono, inst1, branch da PR; bloqueia o merge):**
  1. checkout da branch, reinício de `besave-captura-lojas` e `besave-captura-whatsapp`;
  2. a 65104 (ou, se já tiver saído da fila, uma linha nova com U+2060) aparece no log com
     `[url] linha …: removidos 1 caractere(s) invisivel(is) (U+2060)` e termina `ok` (ou com um motivo da
     própria oferta, nunca `api_indisponivel`/`pagina_sem_produto` por causa do caractere);
  3. depois do reinício, nenhuma linha nova com caractere `Cf` em `DS_URL_ORIGEM`:
     `SELECT COUNT(*) FROM OFERTA_FILA_CAPTURA WHERE INSTR(ASCIISTR(DS_URL_ORIGEM), '\2060') > 0 AND DT_CAPTACAO > <reinício>`
     = 0 com o grupo tendo mandado link no período (confirmar pelo log do WhatsApp);
  4. evidência redigida (sem URL do grupo, sem nome do grupo).

## Definition of done
PR para `develop` com código, testes, `validation.md` do Verifier independente (sensor de discriminação) e
evidência redigida; decisão proposta para `docs/DECISOES.md` no resumo da PR.
