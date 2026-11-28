# Validation: BSV-68 - PASS

**Veredito (ciclo 2)**: PASS. O merge continua bloqueado até a execução real do dono na inst1 (ver o fim).

**Data**: 2026-11-28
**Spec**: `.specs/features/BSV-68/spec.md` (EARS do autor) contra `docs/specs/BSV-68.md` em `origin/docs/bsv-68-url-invisivel` (fonte da verdade)
**Faixa do diff**: `b39d155..HEAD` (0e8ee2b, e5731e4, a92ffee, b2ae40d)
**Verifier**: sub-agente independente (autor ≠ verificador); não alterou código nem testes no tree real e não commitou

---

## Histórico

| Ciclo | HEAD | Veredito | Resumo |
|---|---|---|---|
| 1 | a92ffee | FAIL | os mutantes obrigatórios A–D morreram; **E** (limpar só depois de `eh_link_whatsapp`) e **F** (não descartar link vazio) sobreviveram: os testes do parser não distinguiam as duas regras da Saída 2. A spec EARS também deixava de fora "nenhum outro campo muda", "sem regravar `DS_URL_ORIGEM`" e a execução real. 12 mutantes, 10 mortos. |
| 2 | b2ae40d | PASS | o autor acrescentou 3 testes em `test_parser_url.py` e completou a spec EARS (WA-01, LJ-01, AC 2 e AC 6). E e F agora morrem; A–D continuam mortos. Lacunas 3, 4 e 6 do ciclo 1 ficam como decisões do autor, para o dono decidir no resumo da PR. |

---

## Gates (job `tools` do CI), ciclo 2

| Gate | Resultado |
|---|---|
| `tools/capture-chat-groups`: `python -m unittest discover -s tests -v` | OK, 21 testes (18 no ciclo 1 + 3 novos) |
| `tools`: `python -m pytest` (suite inteira, rodada por último e sem outra carga) | 875 passaram, 44 pulados, 0 falhas (266 s). Os 44 pulados são de arquivos que só rodam em Linux (`test_vnc.py`, `test_scope_*`, `test_config_permissao.py` etc.); nenhum está no diff |
| `tools`: `python -m ruff check vps/ tests/` | sem achados |
| `shellcheck ../vps/*.sh` | **não executado** (shellcheck fora do PATH); o diff não mexe em `.sh` e o CI roda |

Rodado com Python 3.14.7 local (o CI usa 3.12); os caracteres da tabela são `Cf` nas duas versões do Unicode.
Nenhum teste foi removido nem enfraquecido. Delta da feature: +10 no pytest e +6 no unittest.

---

## Fidelidade da spec EARS à spec original (ciclo 2)

| Ponto | Situação |
|---|---|
| URL-01/02, WA-01, LJ-01/02, SH-01/02/03 | fiéis às Saídas 1–5 |
| "Nenhum outro campo muda" (Saída 2) | entrou em WA-01 e no AC 2; teste em `test_parser_url.py:66` |
| "`DS_URL_ORIGEM` não é regravada" (Saída 3) | entrou em LJ-01; o código cumpre: nenhum UPDATE de `DS_URL_ORIGEM` em `core/oracle_db.py` (só a lista de colunas na linha 94); sem teste, só lendo o código |
| Critério "Real (dono, inst1)" | entrou como AC 6 |
| Separador `, ` entre códigos; log só quando sai `Cf` | suposições declaradas do autor; o dono decide (lacunas 1 e 2 abaixo) |

---

## Critérios ancorados na spec

| Critério | Resultado definido na spec | `file:line` + assert | Resultado |
|---|---|---|---|
| Tabela da Saída 5, robô do WhatsApp (lista de pares inteira) | 9 pares exatos, conferidos caractere por caractere contra a spec | `tools/capture-chat-groups/tests/test_parser_url.py:35` - `assertEqual(obtido, TABELA_LIMPAR_URL)` | PASS |
| Tabela da Saída 5, robô das lojas | a mesma lista | `tools/tests/test_url_lojas.py:27` - `assert obtido == TABELA_LIMPAR_URL` | PASS |
| Mesma tabela nos dois lados | igualdade das listas | `tools/tests/test_url_lojas.py:34` - `ast.literal_eval(no.value) == TABELA_LIMPAR_URL` | PASS |
| Mesmo corpo nos dois robôs, sem import cruzado | corpo idêntico | `tools/tests/test_url_lojas.py:38` - `getsource(url_lojas.limpar_url) == getsource(parser_wa.limpar_url)`; `wa/parser.py:563-567`, `core/url.py:8-12` | PASS |
| Parser: convite com U+2060 no fim é pulado | `url == "https://meli.la/AbC123"` | `test_parser_url.py:44` | PASS |
| Parser: convite com U+2060 no início é pulado (limpa antes de `eh_link_whatsapp`) | `url == "https://meli.la/AbC123"` | `test_parser_url.py:60` - `assertEqual(campos["url"], "https://meli.la/AbC123")` | PASS (mata o mutante E) |
| Parser: `links == ["⁠"]` | `url == ""` | `test_parser_url.py:48` | PASS |
| Parser: link que fica vazio é descartado e não tampa o seguinte | `url == "https://meli.la/AbC123"` | `test_parser_url.py:53` - `assertEqual(campos["url"], "https://meli.la/AbC123")` | PASS (mata o mutante F) |
| Parser: nenhum outro campo muda | dict sujo == dict limpo | `test_parser_url.py:66` - `assertEqual(sujo, limpo)` | PASS |
| Lojas: URL suja vira limpa e loga a linha inteira | `[url] linha 65104: removidos 1 caractere(s) invisivel(is) (U+2060)` | `tools/tests/test_url_lojas.py:44` e `:46` - `out == "[url] linha 65104: removidos 1 caractere(s) invisivel(is) (U+2060)\n"` | PASS |
| Lojas: vários códigos distintos, em ordem de aparição | distintos, na ordem | `test_url_lojas.py:53` - `"... removidos 5 ... (U+200B, U+2060, U+FEFF)\n"` | PASS (o separador é decisão do autor) |
| Lojas: URL limpa não loga | saída vazia | `test_url_lojas.py:60-61` | PASS |
| Resolver: `UnicodeEncodeError` | `(None, URL_NAO_RECONHECIDA)` + log exato | `tools/tests/test_shopee_api.py:363-364` | PASS |
| Resolver: `OSError`, outro `ValueError` e `HTTPException` continuam passageiros | `API_INDISPONIVEL` | `test_shopee_api.py:367-369`; `HTTPException` em `:356-357` | PASS |
| Caminho `_adaptar_linhas` → captura Shopee: o `abrir` nunca recebe `Cf` | URL recebida sem `Cf` | `tools/tests/test_shopee_lote.py:277-279` - `recebidas == [CURTO.format(1)]`, nenhum `Cf`, `status_captura == "ok"` | PASS |
| Sem dependência nova | só stdlib | nenhum `requirements*.txt` no diff; único import novo é `unicodedata` | PASS |
| Fixtures sem URL real do grupo nem marca de afiliado | ids inventados | `AbC123`, `XyZ`, `Abc`, `REDACTED{n}` | PASS |

**Status**: todos os critérios cobertos; 2 lacunas de precisão da spec, que ficam para o dono decidir.

---

## Sensor de discriminação, ciclo 2

Worktree temporária no scratchpad (`git worktree add --detach … HEAD` em b2ae40d), removida com
`git worktree remove --force`. Testes rodados em cada mutante: `unittest` de `capture-chat-groups` e
`pytest -x` em `test_url_lojas.py`, `test_shopee_api.py` e `test_shopee_lote.py`.

| # | Mutante | Arquivo | Ciclo 1 | Ciclo 2 | Teste que matou (ciclo 2) |
|---|---|---|---|---|---|
| A (obrigatório) | `_adaptar_linhas` volta a `bruta.strip()` | `main.py:346` | morto | **morto** | `test_url_lojas.py::test_adaptar_linhas_limpa_e_loga_a_linha_inteira` (no ciclo 1, rodado sozinho, `test_shopee_lote.py::test_bsv68_…` também matou) |
| B (obrigatório) | limpa só as pontas (`strip` com a lista `Cf`), nos dois robôs | `parser.py:567`, `url.py:12` | morto | **morto** | `test_tabela_inteira` (unittest e pytest) |
| C (obrigatório) | `Cf` trocado por lista fixa sem U+2060, nos dois robôs | `parser.py:567`, `url.py:12` | morto | **morto** | `test_tabela_inteira` e os testes do parser |
| D (obrigatório) | `UnicodeError` devolve `API_INDISPONIVEL` | `shopee_api.py:295` | morto | **morto** | `test_shopee_api.py::test_res_unicode_nao_codifica_e_nao_reconhecida` |
| E | parser limpa só depois de `eh_link_whatsapp` | `parser.py:600-601` | sobreviveu | **morto** | `test_parser_url.py::…test_convite_com_caractere_no_inicio_e_pulado` |
| F | parser não descarta link vazio | `parser.py:601` | sobreviveu | **morto** | `test_parser_url.py::…test_link_vazio_descartado_nao_tampa_o_seguinte` |

Os mutantes B2, D2, G, H, I e J do ciclo 1 (todos mortos) não foram repetidos: o b2ae40d só mexe em testes do
parser e na spec.

**Resultado**: 6/6 mortos no ciclo 2 (somando o ciclo 1: 12/12 mutantes distintos mortos na versão final).
**Isolamento**: `git status --porcelain` do tree real igual antes e depois (só `?? .specs/features/BSV-68/validation.md`).

---

## Qualidade do código

| Item | Status |
|---|---|
| Código mínimo, sem escopo extra | OK |
| Mudança cirúrgica, só nas pastas da spec | OK |
| `except UnicodeError` antes do ramo `ValueError` (é subclasse dele) | OK, `shopee_api.py:292` |
| Testes comparam o valor inteiro (lição 14) | OK |
| Todo teste corresponde a um critério | OK |
| Estilo | cosmético: em `test_parser_url.py:49-50` há duas linhas em branco dentro da classe antes do método novo, e só uma antes do `if __name__` (`:68`); fora do escopo do ruff do CI |

---

## Lacunas restantes, da mais importante para a menos (nenhuma bloqueia o PASS)

1. **Precisão da spec: separador entre vários códigos no log.** O autor escolheu `, ` (`test_url_lojas.py:53`).
   O dono confirma no resumo da PR ou na spec.
2. **Precisão da spec: "quando a limpeza mudou algo".** O autor só loga quando sai caractere `Cf`; espaço nas
   pontas não gera log (`test_url_lojas.py:57-61`). O dono confirma.
3. Não existe `tasks.md`, embora a spec cite T1–T3. São 4 commits, um por tarefa mais a correção. Só informativo.
4. "`DS_URL_ORIGEM` não é regravada" foi conferido lendo o código, sem teste. É um risco baixo: o robô das lojas
   não tem UPDATE dessa coluna.
5. `shellcheck` não rodou localmente (o CI roda).

## Depende da execução real do dono (inst1, branch da PR): bloqueia o merge

1. Checkout da branch e reinício de `besave-captura-lojas` e `besave-captura-whatsapp`.
2. Devolver a 64926 a `'0'` com o U+2060 reposto (`DS_URL_ORIGEM || UNISTR('\2060')`). Esperado: o log
   `[url] linha 64926: removidos 1 caractere(s) invisivel(is) (U+2060)` e término pelo motivo da própria oferta
   (`ok` ou duplicidade), nunca `pagina_sem_produto` por página inexistente. O SQL de devolver e o de desfazer vão
   na evidência.
3. Depois do reinício, `SELECT COUNT(*) FROM OFERTA_FILA_CAPTURA WHERE INSTR(ASCIISTR(DS_URL_ORIGEM), '\2060') > 0
   AND DT_CAPTACAO > <reinício>` deve dar 0, com o grupo tendo mandado link no período (confirmar pelo log do
   WhatsApp).
4. Evidência redigida (sem URL nem nome do grupo).

## Resumo

**Geral**: PASS no código e nos testes; o merge fica bloqueado até a execução real.
**Checagem contra a spec**: todos os critérios com evidência e valor da spec; 2 lacunas de precisão que o dono decide.
**Sensor**: ciclo 2 com 6/6 mortos (A–D, E, F).
**Gates**: unittest 21 OK; pytest 875 passaram, 44 pulados, 0 falhas; ruff sem achados; shellcheck não executado.
