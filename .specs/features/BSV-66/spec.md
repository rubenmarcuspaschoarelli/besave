# BSV-66 Captura web de apoio (Pelando, Promobit, Pechinchou) Specification

Fonte: `docs/specs/BSV-66.md`. Contrato: `docs/CONTRATO.md` §4.3 (separação de cupons).

## Problem Statement

A fila `OFERTA_FILA_CAPTURA` só recebe ofertas do WhatsApp; quando ele cai, o site para de receber ofertas.
Um programa no PC do dono lê três sites de ofertas (sem navegador, JSON embutido no HTML) e põe algumas
ofertas de Amazon, Mercado Livre e Shopee na fila, como uma linha do WhatsApp; o robô das lojas faz o resto.

## Goals

- [ ] `tools/capture-web-apoio/` (`main.py` + `webapoio/`), só stdlib + `oracledb`, sem importar outro robô.
- [ ] Extratores das três fixtures, URL limpa, filtros, "já vista", cotas com rodízio, `INSERT` na fila.
- [ ] Avisos (uma mensagem por rodada), `--simular`, trava, `agendar.ps1`, usuário `BESAVE_WEB`, README.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Prioridade WhatsApp × web na fila | spec (decisão do dono) |
| Rodar sozinho quando o WhatsApp cair, paginação, imagens, outros sites, Linux/VPS | spec |
| Mudança no robô das lojas, worker ou banco além do usuário `BESAVE_WEB` | spec |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Promobit `COUPON`/`STARTING_AT`, Pechinchou `is_any_text_price` | descartados já na extração como inválidos (`tipo_preco`, `preco_texto`) | o critério de aceite os põe no teste de extração; descartar antes evita um redirect por oferta sem preço | n |
| Rodízio | turno = uma gravação por site (Pelando → Promobit → Pechinchou); dentro do site, o menu seguinte ao da última gravação; menu esgotado passa ao próximo no mesmo turno; lista do menu baixada só quando o turno chega a ele | "rodízio entre sites e, dentro do site, entre menus"; teto atingido não faz requisição a mais | n |
| Promobit: estado local antes do redirect | `site:id` visto localmente é pulado antes de gastar o redirect (motivo `vista_local`) | "para não gastar redirect"; muda só a ordem, não o resultado | n |
| O que entra em `vistas.json` | gravadas e descartes permanentes (inválida, loja fora, URL, já vista, sem preço); não entram `futura`, `encurtador_nao_resolvido`, `sem_url`, erro de `INSERT` | a segunda rodada pula as mesmas; descarte transitório é tentado de novo | n |
| Chave de produto | igual a `duplicidade.chave_loja` (trecho do `LIKE`: ASIN, dígitos do MLB, item da Shopee) | a spec manda a mesma regra; o `LIKE` com `{shop}.{item}` não casaria `/product/{shop}/{item}` | n |
| Já vista no banco | uma consulta por candidata (`UNION ALL`: fila por chave, `OFERTA` ativa por chave e preço, títulos da fila por loja e preço ±1%) | "uma por candidata"; normalização do título em Python | n |
| `sem resposta` | timeout/5xx depois de uma repetição, ou outro código HTTP: o menu falha, o site segue nos outros menus; aparece uma vez por site | só 403/429 param o site | n |
| Banco fora + problema de site | só a mensagem do banco | uma mensagem por rodada; o banco é o problema maior | n |
| `--simular` sem banco | WARN e segue sem as consultas da Saída 5 | é diagnóstico; não grava nada | n |
| Trava | `estado/rodada.lock` com `msvcrt.locking` (Windows) / `fcntl.flock`; liberada pelo SO se o processo morrer | arquivo de trava sem lock do SO ficaria preso depois de uma queda | n |
| Menu do `config.json` fora do host do site ou em `/api/` | ignorado com WARN | regra 2 | n |
| `--remover` no `agendar.ps1` | aceita `--remover` e `-Remover` | a spec escreve `--remover` | n |

**Open questions:** none.

---

## User Stories

### P1: Ler e extrair ⭐ MVP

**Acceptance Criteria**:

1. WHEN a rodada lê um menu THEN o programa SHALL fazer um GET com `User-Agent` do config, `Accept-Language: pt-BR`, sem `Accept-Encoding`, sem cookies, timeout 20 s, com pausa aleatória em `pausa_s` antes de toda requisição depois da primeira, e uma repetição em timeout/5xx.
2. WHEN a resposta é 403 ou 429 THEN o site SHALL parar na rodada (nenhuma requisição a mais nele) e entrar no aviso como `bloqueado (HTTP <código>)`.
3. WHEN o extrator recebe as fixtures THEN ele SHALL devolver as ofertas válidas com os campos das tabelas da Saída 2 e descartar `expired`/`kind: coupon` (Pelando), `COUPON`/`STARTING_AT` (Promobit), `CLOSED` (Pechinchou).
4. IF falta a ilha, o `__NEXT_DATA__`, a chave da lista, ou todo item não tem campo obrigatório THEN o extrator SHALL devolver erro de estrutura sem exceção, e o aviso SHALL dizer `estrutura mudou em <menu>`.
5. WHEN uma oferta do Promobit passa o filtro de loja THEN o programa SHALL buscar `/Redirect/to/{offerId}/` e ler a URL de `l = '...'` ou do `<a href>` do `<p>`; sem URL, descarte `sem_url`.

### P2: URL limpa e filtros ⭐ MVP

**Acceptance Criteria**:

1. The programa SHALL gravar e comparar só a URL limpa da Saída 4 (Amazon `/dp/{ASIN}`, ML sem query nem `#`, Shopee `/product/{shop}/{item}`), descartando loja fora e URL limpa > 350.
2. WHEN a URL é de encurtador THEN o programa SHALL resolver com até 3 requisições sem seguir redirect, lendo `Location`; sem resolver, descarte `encurtador_nao_resolvido`.
3. WHEN a oferta foi publicada há mais de `idade_max_horas` ou mais de 10 min no futuro THEN ela SHALL ser descartada.
4. WHEN qualquer dos 4 casos de "já vista" vale THEN a oferta SHALL ser pulada; IF o preço novo é menor que o da `OFERTA` ativa THEN ela SHALL entrar.
5. The programa SHALL nunca escrever no log nem no banco uma URL com marca de terceiro.

### P3: Gravação, cotas e avisos ⭐ MVP

**Acceptance Criteria**:

1. WHEN uma oferta passa nos filtros THEN o programa SHALL fazer o `INSERT` da Saída 6 (com bind, `RETURNING ID_OFERTA`, `COMMIT` por linha), com `DS_CUPOM` pela regra §4.3.
2. The rodada SHALL respeitar `por_menu` e `teto_rodada` com rodízio entre sites e menus, sem requisição depois do teto.
3. IF a conexão falha numa gravação THEN o programa SHALL reconectar e repetir uma vez e, falhando de novo, parar a rodada e avisar `banco fora do ar`.
4. WHEN a rodada termina com problema THEN o programa SHALL mandar uma só mensagem no formato da Saída 7; WHEN não há problema THEN SHALL não mandar mensagem.
5. WHEN roda com `--simular` THEN o programa SHALL não fazer `INSERT` nem gravar o estado local; WHEN outra instância segura a trava THEN SHALL sair com código 2.

### P4: Operação no PC

**Acceptance Criteria**:

1. The `agendar.ps1` SHALL registrar `besave-captura-web` às 08:00, 12:00 e 17:00 (parâmetros), usuário atual só logado, sem `StartWhenAvailable`, limite 30 min, e `--remover` SHALL apagar a tarefa.
2. The `sql/bsv-66-usuario.sql` SHALL criar `BESAVE_WEB` com a senha por variável de substituição e só os grants da Saída 9.
3. The `config.json` SHALL ter padrões da spec e a chave inválida SHALL cair no padrão com WARN; `BESAVE_WEB_SENHA` vence a senha do arquivo.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| LER-01 | P1 AC1 | Execute | Pending |
| LER-02 | P1 AC2 | Execute | Pending |
| LER-03 | P1 AC3 | Execute | Pending |
| LER-04 | P1 AC4 | Execute | Pending |
| LER-05 | P1 AC5 | Execute | Pending |
| URL-01 | P2 AC1 | Execute | Pending |
| URL-02 | P2 AC2 | Execute | Pending |
| FIL-01 | P2 AC3 | Execute | Pending |
| FIL-02 | P2 AC4 | Execute | Pending |
| URL-03 | P2 AC5 | Execute | Pending |
| GRV-01 | P3 AC1 | Execute | Pending |
| COT-01 | P3 AC2 | Execute | Pending |
| GRV-02 | P3 AC3 | Execute | Pending |
| AVI-01 | P3 AC4 | Execute | Pending |
| ROD-01 | P3 AC5 | Execute | Pending |
| OPS-01 | P4 AC1 | Execute | Pending |
| OPS-02 | P4 AC2 | Execute | Pending |
| CFG-01 | P4 AC3 | Execute | Pending |

## Success Criteria

- [ ] `cd tools && python -m pytest` e `ruff check vps/ tests/ capture-web-apoio/` verdes.
- [ ] Execução real do dono (spec, "Real") antes do merge.
