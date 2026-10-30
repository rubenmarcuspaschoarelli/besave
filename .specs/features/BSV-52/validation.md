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
