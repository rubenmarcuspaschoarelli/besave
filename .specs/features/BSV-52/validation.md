# BSV-52 — validation

Verificador: sub-agente independente (autor != verificador), commit 814793f. Nenhum codigo de producao nem teste do autor foi alterado.

## Gates
- `cd tools && python -m pytest -q` -> 179 passed (antes e depois dos mutantes).
- `cd tools/capture-chat-groups && python -m unittest discover -s tests` -> 15 tests OK.
- `git status` / `git diff` limpo apos os mutantes (cada um restaurado com `git checkout -- <arquivo>`).

## Criterios
| item | veredito | evidencia |
|---|---|---|
| Saida 1: `db.transacao(funcao, commit)` sob `_reconecta`, cursor, commit/rollback, close, repete funcao inteira 1x, erro de dado nao reconecta | PASS | tools/capture-store-pages/core/oracle_db.py:573-597 (+_reconecta :65-77); testes tools/tests/test_reconexao_cursores.py:163,175,185,198 |
| Saida 2: 5 modulos usam transacao; sem `db._conn` fora de oracle_db.py; funcoes idempotentes (UPDATE fixo; DELETE+INSERT) | PASS | duplicidade.py (consultar/marcar), afiliados.py (ler), produtos.py (ler/gravar), ofertas.py (_desativar), validade.py (varrer): cada uma uma unica transacao; varredura test_reconexao_cursores.py:389 |
| Saida 3: duplicidade com ErroSemConexao -> nao publica, ponteiro trava; erro nao-conexao loga e publica | PASS | ofertas.py:55-58 (SEM_CONEXAO), main.py:663-665 (_adiar); testes :330, :344, :354 |
| Saida 4: afiliados nao marca carregado na falha, retentativa <=1/min, linha sem cache nao publicada e trava ponteiro, log uma vez + aviso da volta | PASS | afiliados.py:34-85, main.py:636-641; testes :206, :252, :273, :290, :363 |
| Saida 5: produtos/validade best-effort com reconexao, so log; COMUNIDADE sem cache na falha | PASS | produtos.py:32-40,70-73; testes :215,:227,:236,:243 |
| Regra 1: sem queda, comportamento identico | PASS | suite antiga intacta (179 passed, test_reconexao_lojas.py inalterado). Ponteiro agora grava depois da publicacao (main.py:667-670); sem queda o valor final e igual, e nao ha `continue`/excecao nao tratada entre o ponto antigo e o novo (produto e oferta em try/except). Duplicada (`duplicada de N`) e erro de validade/dado avancam o ponteiro como antes; so SEM_CONEXAO e cache de afiliados fora travam |
| Regra 2: 1 repeticao, sem laco | PASS | oracle_db.py:66-77 |
| Regra 3: ponteiro nunca passa de linha nao gravada | PASS | main.py:641,665,669; teste :363 (ponteiro nao pula 200/201) |
| Regras 4-5 | PASS | programas_ajuste/ e dependencias intocados (git show --stat) |
| Criterio: 3 cenarios por modulo (queda unica / persistente / dado) | PASS | test_reconexao_cursores.py:163-250, parametrizado em OPERACOES (:143-153) |
| Duplicidade com queda persistente nao publica (falha no codigo antigo) | PASS | teste :330; mutante M5 o derruba |
| Afiliados: falha no arranque, volta respeitando intervalo, ponteiro nao pula | PASS | teste :363-386 |
| Real na inst1 (KILL SESSION x3) | PENDENTE (dono) | bloqueia o merge |

## Sensor de discriminacao (um mutante por vez, `pytest tests/test_reconexao_cursores.py tests/test_reconexao_lojas.py`)
Todos os 20 mutantes MORTOS, 0 sobreviventes:
M1 sem @_reconecta em transacao; M2 sem rollback; M3 funcao executada 2x; M4 checagem de duplicidade com commit=True; M5 publicar_oferta publica em vez de SEM_CONEXAO; M6 carregar() marca _carregado na falha; M7 intervalo 60->0; M8 sem `_adiar` no gate de afiliados; M9 ponteiro gravado antes da publicacao; M10 sem trava no SEM_CONEXAO; M11 erro de dado reconecta; M12 log de afiliados em toda falha; M13 sem aviso da volta; M14 classificacao sem commit; M15 validade sem commit; M16 _desativar sem commit; M17 marcar_duplicada sem commit; M18 garantir_carregado sem gate de tempo; M19 qualquer erro de duplicidade vira SEM_CONEXAO; M20 carga bem-sucedida nao seta _carregado.

## Achados (nao bloqueantes)
- test_reconexao_cursores.py:123 `assert afiliados._carregado or True` e vacuo (a verificacao real esta em :206). Inofensivo; limpar se quiser.
- Testes de tempo/carga: rodados sem outra carga; nao ha teste de tempo neste ticket.

## Veredito: PASS (condicionado ao teste real do dono, lição 5)

---

# Trecho novo: publicacao pendente recuperada sozinha (commit eb38d28)

Verificador: sub-agente independente (autor != verificador). Nenhum codigo de producao nem teste foi alterado; mutantes restaurados com `git checkout -- <arquivo>`.

## Gates
- `cd tools && python -m pytest -q` -> 187 passed.
- `cd tools/capture-chat-groups && python -m unittest discover -s tests` -> 15 tests OK.
- `git status` limpo fora de `.specs` depois dos mutantes.

## Requisitos
| item | veredito | evidencia |
|---|---|---|
| (a) id vai para `controle.publicacao_pendente` (persistida, dedupe, ordenada) | PASS | core/estado.py:176-198 (`ler/gravar/adicionar_publicacao_pendente`, gravacao atomica via `_gravar_controle`, preserva o resto do config); main.py:424-432 (`_pendente`); chamado em main.py:651 (cache) e :675 (SEM_CONEXAO) |
| (b) inicio de cada volta do monitor e arranque; UPDATE `WHERE ID_OFERTA=:id AND ST_CAPTURA='1'` via `db.transacao`; tira de `adiados` e da lista; causa persistente fica na lista sem laco (cache 1/min) | PASS | main.py:747-776 (`_devolver_a_fila`, `_recuperar_publicacoes`: `garantir_carregado` faz o gate de 1/min, `break` no 1o erro de banco, lista regravada so com o que sobrou); monitor main.py:826; arranque main.py:927; testes test_publicacao_pendente.py:21 (1), :46 (2), :68 (3), :95 (4), :113 (sem laco), :139 (monitor) |
| (c) ponteiro nao passa do menor pendente (inclui os da lista persistida apos reinicio) | PASS | main.py:679-681 (`id_oferta < min(pendentes)`, `pendentes` lido de `estado` no inicio do lote, :426); teste :122 |
| Duplicada de verdade continua '9' (nao volta a '0') | PASS | teste :95 (1 devolucao + 1 marca '9') |
| Monitor ignora o ponteiro (ultimo_id=0), entao a linha devolvida e relida; no modo lote a linha devolvida tem id > ponteiro (ponteiro < menor pendente) | PASS | main.py:807, :933 |
| SQL CONFERE_BSV_52_KILL_SESSION.sql (Oracle 11g, so leitura) | PASS (leitura) | consulta 1 e 2: colunas `ID_PRODUTO`/`DS_URL_FINAL` existem na fila (usadas em programas_ajuste/backfill_*.py), `BESAVE.LOJA_AFILIADA(DS_LOJA, ST_ATIVO)` igual a core/afiliados.py:46; consulta 3: `ABS(date - date) <= 1` e valido em 11g; sem recurso 12c (sem FETCH FIRST, sem IDENTITY). Nao executado no banco. Binds `:ini` repetido: ok no SQL*Plus/SQL Developer |

## Sensor de discriminacao (um por vez; `pytest -x tests/test_publicacao_pendente.py tests/test_reconexao_cursores.py tests/test_reconexao_lojas.py`)
MORTOS (17): M1 nao remove da lista apos UPDATE; M2 remove mesmo com UPDATE falho; M3 sem `adiados.discard`; M5 UPDATE para '9'; M6 UPDATE para '1'; M7 sem recuperacao no monitor; M9 ponteiro ignora pendentes; M10 `<` -> `<=`; M11 `_pendente` nao persiste; M12 `_pendente` sem `adiados.add`; M13 gate de afiliados sem `_pendente`; M14 SEM_CONEXAO sem `_pendente`; M15 recuperacao ignora `garantir_carregado`; M18 `_gravar_controle` nao preserva o config; M19 ponteiro ignora a lista persistida; M20 nao grava `restantes`; M21 gate de afiliados volta ao `_adiar` antigo.

SOBREVIVENTES (4):
- M4 UPDATE sem `AND ST_CAPTURA='1'` (main.py:749): o fake de cursor so confere que o texto contem `ST_CAPTURA = '0'`. Em producao a guarda impede que uma entrada velha reponha a '0' uma linha ja '9' (duplicada) ou ja publicada. Lacuna de teste, nao de codigo.
- M8 sem `_recuperar_publicacoes` no arranque (main.py:927): o teste de reinicio (:46) chama a funcao direto; nada exercita `main()`. Lacuna de teste.
- M16 `break` -> `continue` (main.py:769): com 2 pendentes o numero de tentativas ainda cabe em `conexoes <= 3` (teste :113). Lacuna de sensibilidade (teste com 5+ ids e limite exato resolve).
- M17 `adicionar` sem dedupe: equivalente, `ler_publicacao_pendente` ja deduplica por `set`.

## Achados (nao bloqueantes)
1. Fechar M4/M8/M16 com testes: asserir que o SQL devolvido contem `AND ST_CAPTURA = '1'`; teste de `main()` (ou extrair o arranque) chamando a recuperacao; teste de `break` com 5 ids.
2. Janela pequena: se o UPDATE for confirmado e a regravacao do config.json falhar (disco), a entrada fica na lista e na volta seguinte o UPDATE `AND ST_CAPTURA='1'` pode reabrir uma linha ja republicada (volta a '0' e passa pela duplicidade contra si mesma, que a ignora por id; no pior caso republica o mesmo id). Raro; a guarda '1' reduz, nao elimina.
3. `_recuperar_publicacoes` sai cedo quando o cache de afiliados nao carrega, mesmo para ids pendentes por SEM_CONEXAO; coerente com o requisito (a publicacao precisaria do cache de qualquer forma).
4. Escrita concorrente do config.json: monitor e recuperacao rodam na mesma thread e sequencialmente; `os.replace` atomico. Sem corrida dentro de um processo; dois processos no mesmo config nao sao protegidos (fora do escopo).
5. Execucao real (KILL SESSION) segue PENDENTE do dono e bloqueia o merge.

## Veredito do trecho novo: PASS com ressalvas (codigo atende (a)(b)(c) e os 4 testes exigidos; 3 lacunas de sensibilidade de teste acima, nao bloqueantes). Condicionado ao teste real do dono.

### Nota do autor após o Verifier do trecho novo
Mutantes M4 (UPDATE sem `AND ST_CAPTURA='1'`) e M16 (`break`→`continue`) passaram a ser cobertos por
`test_devolucao_so_reabre_linha_capturada` e `test_banco_fora_para_na_primeira_falha_...`. M17 é equivalente.
M8 (chamada no arranque do `main()`) segue sem teste automatizado; fica para o teste real do dono.
