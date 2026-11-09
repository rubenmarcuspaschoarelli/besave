# BSV-52 · Robô das lojas: reconexão também nos cursores diretos (validade, duplicidade, produtos, afiliados)

**Papel:** Python · **Pasta:** `tools/capture-store-pages/` (+ `tools/tests/`) ·
**Depende de:** e2dc653 (reconexão nos métodos do `OracleDB`, 21/10, em `main`). Lições 29 e 31

## Contexto
Em 21/10, o `KILL SESSION` mostrou que uma queda da sessão Oracle fazia o robô das lojas perder linhas.
O commit e2dc653 corrigiu isso **só nos métodos do `OracleDB`**: o decorador `_reconecta` de
`core/oracle_db.py` reconecta e repete uma vez em erro de conexão (`_ERROS_CONEXAO`). Ele cobre
`ler_fila`, `buscar_para_*` e `executar_stored_procedure`, e o ponteiro trava na primeira linha não gravada.

Cinco módulos ainda abrem cursor direto em `db._conn`, fora do decorador. Numa queda (`DPY-1001`), a
chamada falha, o erro é engolido como *best-effort* e ninguém reconecta até a próxima chamada decorada:

| módulo | trecho | efeito de uma queda hoje |
|---|---|---|
| `core/duplicidade.py` | `_concorrentes`, `marcar_duplicada` | `publicar_oferta` cai no `except` ("checagem de duplicidade falhou — publicando") e **publica a repostagem** que deveria ser barrada |
| `core/afiliados.py` | `carregar` (uma vez, no arranque) | cache vazio com `_carregado = True`: `loja_ativa` fica falsa para todas as lojas e **nenhuma oferta entra em `OFERTA` até reiniciar o robô**, sem nenhum alerta |
| `core/produtos.py` | `_mapa_comunidades`, `gravar_classificacao` | produto sem as linhas de `PRODUTO_COMUNIDADE`/`PRODUTO_PUBLICO` |
| `core/ofertas.py` | `_desativar` | oferta vencida não é desativada |
| `core/validade.py` | `desativar_vencidas` (1×/h) | varredura perdida até a hora seguinte |

A lição 31 (robô do WhatsApp, 20→21/10) mostrou que a queda acontece na prática: 10 h capturando sem gravar.

## Objetivo
Nenhum acesso do robô das lojas ao Oracle fica fora da regra de reconexão. Uma queda nunca publica uma
duplicada nem deixa a publicação parada em silêncio.

## Saídas
1. **Um caminho só para SQL avulso no `OracleDB`**, por exemplo `db.transacao(funcao, commit=True)`, sob
   o mesmo `_reconecta`. Ele faz cinco coisas:
   - abre o cursor;
   - chama `funcao(cur)`;
   - faz `commit` se pedido, e `rollback` em qualquer erro;
   - fecha o cursor;
   - em erro de conexão, reconecta e **repete a função inteira** uma vez.

   Erro de dado (ex.: `ORA-01400`) não reconecta, igual aos métodos atuais.
2. **Os cinco módulos passam a usar esse caminho.** Nenhum arquivo de `core/` nem o `main.py` acessa
   `db._conn` fora de `core/oracle_db.py`. Cada função passada é **uma transação inteira e idempotente**,
   para que a repetição seja segura: `UPDATE` para valores fixos, e `DELETE` + `INSERT` do mesmo produto.
3. **Duplicidade:** se a checagem ou a marcação falhar **por conexão**, mesmo depois da reconexão
   (`ErroSemConexao`), a linha conta como **não gravada**. Ela não é publicada, e o ponteiro trava nela,
   pelo mesmo caminho da falha de SP do e2dc653. Erro que não é de conexão mantém o comportamento de hoje
   (loga e publica).
4. **Afiliados:** uma falha de leitura de `LOJA_AFILIADA` **não** marca o cache como carregado.
   - Enquanto não carregar, o robô tenta de novo antes da próxima linha que precisaria dele, no máximo
     uma vez por minuto.
   - Linha que chega a `loja_ativa` sem o cache carregado conta como **não gravada**: não é publicada e
     o ponteiro trava nela.
   - O log diz `[afiliados] cache não carregado` uma vez por ocorrência, e diz quando volta.
5. **Produtos e validade:** continuam *best-effort*, agora com reconexão. Falha persistente só vai para o
   log, como hoje. A leitura de `COMUNIDADE` que falha continua sem cache.

## Regras
1. Sem queda, o comportamento é idêntico ao de hoje. Os testes atuais de `tools/tests/` passam sem
   alteração.
2. A repetição é de **uma** vez, como no e2dc653. Sem laço de reconexão nem espera longa no caminho da
   captura.
3. O ponteiro (`ultimo_id_processado`) nunca passa de uma linha que não foi gravada nem marcada. É a
   mesma garantia de 21/10, agora estendida à duplicidade e aos afiliados.
4. `programas_ajuste/` fica de fora: são scripts avulsos, rodados à mão.
5. Sem dependência nova.

## Fora de escopo
- O robô do WhatsApp.
- Pool de conexões.
- Mudar a regra de duplicidade (24 h, menor preço) ou a de validade.
- Alerta no Telegram para o robô das lojas (ticket próprio, se o dono quiser).

## Critério de aceite
Testes em `tools/tests/`, com conexão falsa no molde de `test_reconexao_lojas.py`. Cada um destes três
cenários é provado **por módulo**: duplicidade (checagem e marcação), afiliados, produtos (mapa e
classificação), `_desativar` e validade.
- **Queda única:** a conexão cai no primeiro `execute` → reconecta → a operação completa, e a escrita
  acontece **uma vez**.
- **Queda persistente:** a conexão não volta → o comportamento da regra correspondente:
  - duplicidade e afiliados: linha não publicada e ponteiro parado nela;
  - produtos e validade: só log, e a captura segue.
- **Erro de dado:** não reconecta.

Também:
- **Duplicidade com queda persistente:** a repostagem **não** é publicada. Esse é o defeito de hoje, e o
  teste tem de falhar no código atual.
- **Afiliados:**
  - falha no arranque, e a próxima linha não é publicada;
  - o banco volta, o cache carrega na próxima tentativa (respeitando o intervalo mínimo) e as linhas
    seguintes são publicadas;
  - o ponteiro não pula nenhuma linha.
- **Sem `db._conn` fora de `core/oracle_db.py`**, em `core/` e `main.py` (teste de varredura do código).
- **Gate:** CI `tools` (`pytest` em `tools/` e `unittest` do chat-groups) verde.
- **Real (dono), na inst1:** repetir o roteiro da lição 29, com o robô capturando:
  1. Como ADMIN, rodar `ALTER SYSTEM KILL SESSION '<sid>,<serial#>' IMMEDIATE` na sessão do robô
     (`V$SESSION` filtrada pelo usuário do robô). Fazer três vezes, espaçadas.
  2. Conferir no log o `Reconectando...`.
  3. Conferir que nenhuma linha fica com `ST_CAPTURA = '0'` atrás do ponteiro.
  4. Conferir que não entrou duplicada de 24 h na janela do teste. O SQL de conferência vai na PR.

## Definition of done
PR com:
- testes verdes no CI `tools`;
- `validation.md` do Verifier independente, com sensor de discriminação;
- o teste real do dono antes do merge (lição 5);
- as decisões propostas no resumo da PR.
