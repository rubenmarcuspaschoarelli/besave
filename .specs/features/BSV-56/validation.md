# BSV-56 Validation — PASS

**Veredito: PASS** (3ª verificação, ciclo 3 de 3, mais a rodada T10 só sobre SQL e README, também PASS). Todos os critérios de aceite da spec do dono têm teste com o valor que a
spec manda. O sensor de discriminação não deixou mutante não equivalente vivo: os sobreviventes das rodadas anteriores
(M19, M27, N1, N4) e a regressão do "voltou" cedo morrem. Os gates do job `tools` passam. **O merge continua bloqueado
pela execução real do dono na inst1** (seção final).

**Date**: 2026-11-09
**Spec**: `docs/specs/BSV-56.md` (fonte da verdade) e `.specs/features/BSV-56/spec.md`
**Diff range**: `origin/develop...HEAD`, 11 commits (`8cba013`..`ef456d1`): 7 da implementação, `7a1a1ec` (T8, correções da
1ª verificação), `9bde70a` (T9, só testes; `git diff 7a1a1ec..9bde70a -- tools/capture-chat-groups tools/vps` vazio),
`4ff6e47` (este `validation.md`) e `ef456d1` (T10: SQL reexecutável e roteiro real no README; `git diff 9bde70a..ef456d1`
não toca em `wa/` nem nos `.sh`)
**Verifier**: Verifier independente (sub-agente); autor ≠ verificador. Worktree nasceu de `develop`
(`git merge-base --is-ancestor origin/develop HEAD` OK).

---

## Task Completion

| Task | Status | Notes |
| --- | --- | --- |
| T1 SQL | ✅ Done | conferido lendo o arquivo |
| T2 `proximo_id`/`disponivel` | ✅ Done | — |
| T3 `VigiaBanco` | ✅ Done | — |
| T4 monitor | ✅ Done | — |
| T5 partida | ✅ Done | `.ps1` conferido só por leitura (a spec só exige o teste do `.sh`) |
| T6 reinício | ✅ Done | — |
| T7 README | ✅ Done | `tools/vps/README.md:315-345`, `tools/capture-chat-groups/RESUMO.md:5-8` |
| T8 correções da 1ª verificação | ✅ Done | "voltou" só depois do 1º id; resgate refeito antes do rodízio |
| T9 testes da 2ª verificação | ✅ Done | N1 e N4 cobertos |
| T10 SQL reexecutável e roteiro real | ✅ Done | rodada T10 abaixo |

---

## Spec-Anchored Acceptance Criteria (docs/specs/BSV-56.md)

| Critério | Resultado definido pela spec | Teste (`arquivo:linha` + asserção) e código | Resultado |
| --- | --- | --- | --- |
| **Ao vivo**: 2 mensagens → N e N+1 de `proximo_id()`; mesmo id na imagem, no CSV e em `P_ID_OFERTA` | 46100/46101 nos três | `tools/tests/test_id_sequence_whatsapp.py:150-154` (`reg.imagens`, `ID_OFERTA`, `DS_IMAGEM_OFERTA`, `db.inseridos`); `tools/capture-chat-groups/wa/monitor.py:1452` | ✅ PASS |
| **Ao vivo**: `ultimo_id_processado` absurdo (5) não influencia | id = sequence | `test_id_sequence_whatsapp.py:150` (config 5) e `:165` (5 e 999999 → 46100); `monitor.py:1189` (`numero = 0`) | ✅ PASS |
| **Catch-up**: tmp renomeada com o id do `NEXTVAL`, ordem cronológica | `tmp_a`→700, `tmp_b`→701 | `test_id_sequence_whatsapp.py:177`; `monitor.py:812` | ✅ PASS |
| **Banco fora**: não processada, marcador inalterado, nada no CSV | vazio; marcador `m0` | `test_id_sequence_whatsapp.py:193-196`; `monitor.py:958-961` | ✅ PASS |
| **Banco fora**: 1 aviso | 1 "fora" | `test_id_sequence_whatsapp.py:315-316`, `:277-278`, `:421-422`; `tools/tests/test_alerta_banco.py:24` | ✅ PASS |
| **Banco volta**: a mesma mensagem com id novo e "voltou" (FORA-04) | `a` com 46100, uma vez; "voltou" | `test_id_sequence_whatsapp.py:310-313,316` | ✅ PASS |
| **"voltou" ao normalizar** (FORA-02): `NEXTVAL` falhando com o banco respondendo | 1 "fora" + 1 "voltou", sem alternar | `test_id_sequence_whatsapp.py:277-282`; código `monitor.py:1127,1130-1133,1136-1139` | ✅ PASS |
| **"voltou" só depois do id** (FORA-02, ordem) | "voltou" depois do id novo; só o "fora" antes dele | `test_id_sequence_whatsapp.py:434-435` (`ev.index("id:46100") < i_voltou`) | ✅ PASS |
| **Queda depois de ids já entregues** (FORA-02) | ids antigos não contam: 1 "fora", 1 "voltou" depois do id novo | `test_id_sequence_whatsapp.py:421-427` (`ev.index("id:46100") < i_fora < ev.index("id:46101") < i_voltou`); `monitor.py:1127` | ✅ PASS |
| **Contador da classe real** (base do "voltou") | soma só id entregue (inclusive após reconectar); falha e `SELECT 1` não contam | `tools/tests/test_sequence_oracle.py:158-175` (`ids_entregues == 1` após `disponivel` e após as 2 falhas; `== 2` após reconectar); `oracle_db.py:390` | ✅ PASS |
| **Lembrete só depois de 2 h** (relógio falso) | nada aos 119 min; lembrete aos 120 | `test_id_sequence_whatsapp.py:323-324,330`; `test_alerta_banco.py:30-39`; `alerta.py:121` (`>=`) | ✅ PASS |
| **Espera a cada `db.espera_segundos`** (padrão 60) | sleeps de 60 s | `test_id_sequence_whatsapp.py:279,298,308`; `test_sequence_oracle.py:149-155` | ✅ PASS |
| **Outros grupos não andam** ao vivo (FORA-03) | g2 não abre com o banco fora | `test_id_sequence_whatsapp.py:393-396`; `monitor.py:1291-1293` (`break`) | ✅ PASS |
| **Outros grupos não andam** no resgate (FORA-03) | nenhum `abrir:` entre a falha e o `disponivel()` seguinte; robô não cai; g1 e g2 uma vez | `test_id_sequence_whatsapp.py:294-301`; `monitor.py:1095-1096,1273-1277` (`continue`) | ✅ PASS |
| **Partida**: `iniciar_captura.sh` sem `checa_contador.py`, comando montado inteiro (lição 14) | ordem e cauda exatas, `py.log` vazio | `tools/tests/test_scope_whatsapp.py:128-144`, `tools/tests/test_iniciar_captura.py:121-128`; `tools/vps/iniciar_captura.sh:13,89` | ✅ PASS |
| **Partida**: run vivo, perfil travado, scope vivo continuam | recusa sem lançar | `test_iniciar_captura.py:95-118`, `test_scope_whatsapp.py:58-63` | ✅ PASS |
| **Reinício**: só `Grupo aberto` → confirmado sem aviso | rc 0, sem aviso | `tools/tests/test_reinicio_whatsapp.py:92-98`; `tools/vps/reiniciar_whatsapp.sh:30,83` | ✅ PASS |
| **Reinício**: sem marca de partida → aviso; mutante "Retomando contador" falha | 1 aviso; M15 morto | `test_reinicio_whatsapp.py:121-127`; `ABORTADO:` trocado em `:143-149` | ✅ PASS |
| **SQL** (leitura do Verifier) | ver seção SQL | `tools/capture-chat-groups/sql/BSV-56_sequence_id_oferta.sql`, `tools/tests/test_sql_sequence.py:17-53` | ✅ PASS |
| **Gates** | 4 comandos verdes | seção Gate Check | ✅ PASS |
| **Real na inst1** | dono | — | ⏳ **bloqueia o merge** |

**Status**: ✅ todos os critérios cobertos; sem lacuna de precisão aberta (a da 2ª rodada, ordem do "voltou", está em `:434-435`).

### Requisitos de `.specs/features/BSV-56/spec.md`

| Req | Evidência | Resultado |
| --- | --- | --- |
| SEQ-01 | `test_id_sequence_whatsapp.py:144-156` | ✅ Verified |
| SEQ-02 | `test_id_sequence_whatsapp.py:159-165` | ✅ Verified |
| SEQ-03 | `test_id_sequence_whatsapp.py:170-180` | ✅ Verified |
| SEQ-04 | `test_sequence_oracle.py:84-116`; `oracle_db.py:367-391` | ✅ Verified |
| SEQ-05 | `test_id_sequence_whatsapp.py:318`, `:155` | ✅ Verified |
| FORA-01 | `test_id_sequence_whatsapp.py:185-196` | ✅ Verified |
| FORA-02 | `test_id_sequence_whatsapp.py:273-282,304-330,413-435`; `test_sequence_oracle.py:158-175`; `test_alerta_banco.py:21-74` | ✅ Verified |
| FORA-03 | `test_id_sequence_whatsapp.py:285-301,333-396` | ✅ Verified |
| FORA-04 | `test_id_sequence_whatsapp.py:304-318`, `:300` | ✅ Verified |
| FORA-05 | `test_id_sequence_whatsapp.py:199-210` | ✅ Verified |
| PAR-01 | `test_scope_whatsapp.py:128-144`; `.ps1` por leitura (`iniciar_captura.ps1:15,53`) | ✅ Verified |
| PAR-02 | `test_reinicio_whatsapp.py:92-127` | ✅ Verified |
| SQL-01..03 | `test_sql_sequence.py:17-53` + leitura | ✅ Verified |
| Sem banco configurado (decisão do autor: sai com 4) | `test_id_sequence_whatsapp.py:399-410`; `monitor.py:1175-1178` | ✅ Verified |

### Regras da spec

- **Regra 1** (nada numera sem `NEXTVAL`): só `monitor.py:812` e `:1452` numeram, ambos por `db.proximo_id()`;
  `estado.get_ultimo_id` não é chamado em `wa/` nem em `main.py`. ✅
- **Regra 2** (sem id não grava nem move marcador; sem fila local): FORA-01, FORA-05. ✅
- **Regra 3** (robô das lojas lê a fila desde 0 no monitor): confirmado. `tools/capture-store-pages/main.py:968`
  `ultimo_id = args.desde if args.desde is not None else 0`, sem reatribuição no laço (uso em `:1000`);
  `tools/capture-store-pages/core/oracle_db.py:437-439` `WHERE ST_CAPTURA = '0' AND ID_OFERTA > :ultimo_id ORDER BY ID_OFERTA`.
  A spec cita `main.py:807`; a linha atual é **968** (citar assim no PR). O diff não toca nesse robô. ✅
- **Regra 4** (buracos aceitos): `NOCACHE NOCYCLE`; contagem do catch-up por linhas gravadas. ✅
- **Regra 5** (token e chat nunca em log; sem dependência nova): `alerta.py:56-65` loga só o texto e o tipo da exceção;
  `oracle_db.py:163-166` reduz o erro do driver ao código; `test_id_sequence_whatsapp.py:317`,
  `test_alerta_banco.py:67-74`, `test_sequence_oracle.py:99,108,116`. Nenhum import novo. ✅

### SQL (conferido lendo `tools/capture-chat-groups/sql/BSV-56_sequence_id_oferta.sql`)

| Item | Linha | Resultado |
| --- | --- | --- |
| Cabeçalho: aplicar como `BESAVE` (o robô também conecta como `BESAVE`); produção Oracle Autonomous (`bsvdb_tp`) | 4-6 | ✅ |
| Reexecutável: sequence existente (`COUNT(*)` em `USER_SEQUENCES`) → só imprime o `LAST_NUMBER`, sem `CREATE`/`ALTER`/`DROP` | 25-34, 44-46 | ✅ |
| `START WITH` = `GREATEST(NVL(MAX fila,0), NVL(MAX OFERTA,0)) + 1`, por `EXECUTE IMMEDIATE` (só no `ELSE`) | 34-43 | ✅ |
| `INCREMENT BY 1 NOCACHE NOCYCLE` | 41-42 | ✅ |
| Trigger `CREATE OR REPLACE … BEFORE INSERT … FOR EACH ROW WHEN (NEW.ID_OFERTA IS NULL)`, `:NEW.ID_OFERTA := SQ_OFERTA_FILA.NEXTVAL` (idêntica a `9bde70a`) | 48-56 | ✅ |
| Conferência (`LAST_NUMBER > maior` e trigger `ENABLED`, senão `RAISE_APPLICATION_ERROR(-20056)`), **idêntica a `9bde70a`** (diff do bloco vazio) | 58-81 | ✅ |
| Reversão comentada (`DROP TRIGGER`, `DROP SEQUENCE`) | 83-85 | ✅ |
| SP `STP_OFERTA_FILA_CAPTURA_INSERT` não muda | ausente do arquivo | ✅ |

Validade em Oracle Autonomous, até onde dá sem banco: `SELECT COUNT(*) INTO …` em `USER_SEQUENCES` nunca levanta
`NO_DATA_FOUND`; o `SELECT LAST_NUMBER INTO` só roda com a linha existente; subconsulta escalar dentro de `GREATEST(NVL(...))`
em `SELECT … INTO … FROM DUAL` é válida; DDL por `EXECUTE IMMEDIATE` em bloco anônimo é permitida (o dono do schema cria a
sequence); `WHEN (NEW.ID_OFERTA IS NULL)` sem dois-pontos e `:NEW` no corpo estão certos; `SQ.NEXTVAL` como expressão
PL/SQL é aceito; a trigger é criada depois da sequence; `LAST_NUMBER` é o próximo valor exato porque a sequence é
`NOCACHE`; terminadores `/` certos. Na 2ª execução seguida: o bloco 1 só imprime, a trigger é substituída por ela mesma e o
bloco 3 confere de novo; nenhum número da sequence é consumido (não há `NEXTVAL` no script fora do corpo da trigger). O robô
conecta como `BESAVE`, então `SQ_OFERTA_FILA` sem schema resolve sem grant nem sinônimo.

---

## Discrimination Sensor

Worktree temporário em `C:\Users\REDACTED\AppData\Local\Temp\claude\…\scratchpad\vrf`, um por rodada, sempre removido
(`git worktree remove --force`). `git status --porcelain` da árvore real conferido antes e depois de cada rodada: só o
`validation.md` não rastreado. Sem `git stash`. Mutantes em lotes de 7 a 10, só os testes relevantes
(`test_id_sequence_whatsapp.py`, `test_fiacao_whatsapp.py`, `test_rodizio_destravar.py`, `test_sequence_oracle.py` e, por
mutante, `test_alerta_banco.py`, `test_reconexao_oracle.py`, `test_iniciar_captura.py`, `test_scope_whatsapp.py`,
`test_reinicio_whatsapp.py`).

### Rodada 1 (`202557e`): 26/28 mortos

| # | Arquivo:linha (na época) | Mutação | Resultado |
| --- | --- | --- | --- |
| M1 | `monitor.py:1452` | `numero += 1` no lugar de `db.proximo_id()` | ✅ morto |
| M2 | `monitor.py:1452` | `numero = estado_mod.get_ultimo_id(estado) + 1` | ✅ morto |
| M3 | `monitor.py:812` | catch-up `numero = numero + 1` | ✅ morto |
| M4 | `monitor.py:958-961` | `_ler_novas_do_grupo` engole `ErroSemId` | ✅ morto |
| M5 | `monitor.py:960` | não remove o id de `vistos` | ✅ morto |
| M6 | `monitor.py:814` | apaga só o 1º tmp restante | ✅ morto |
| M7 | `monitor.py` (laço ao vivo) | sem `break` no banco fora | ✅ morto |
| M8 | `monitor.py` `_esperar_banco` | sem `voltou` | ✅ morto |
| M9 | `alerta.py:121` | lembrete com `>` | ✅ morto |
| M10 | `oracle_db.py` `proximo_id` | sem reconexão | ✅ morto |
| M11 | `oracle_db.py` `proximo_id` | 2ª falha devolve `0` | ✅ morto |
| M12 | `oracle_db.py` `proximo_id` | reconexão falha devolve número local | ✅ morto |
| M13 | `oracle_db.py` `_responde` | `disponivel` usa `NEXTVAL` | ✅ morto |
| M14 | `vps/iniciar_captura.sh:89` | volta a chamar `checa_contador.py` | ✅ morto |
| M15 | `vps/reiniciar_whatsapp.sh:83` | exige também "Retomando contador" | ✅ morto |
| M16 | `monitor.py` (laço ao vivo) | resgate não marcado depois da espera | ✅ morto |
| M17 | `monitor.py` (arranque) | resgate não marcado depois da espera | ✅ morto |
| M18 | `monitor.py` `_esperar_banco` | `dormir(1)` | ✅ morto |
| M19 | `monitor.py:1095-1096` | `_recuperar_lacuna` engole `ErroSemId` | ❌ sobreviveu → T8 |
| M20 | `monitor.py` `_esperar_banco` | sem `falhou` a cada tentativa | ✅ morto |
| M21 | `alerta.py:117` | `VigiaBanco` avisa a cada falha | ✅ morto |
| M22 | `monitor.py:818` | `_gravar_cronologico` engole o erro | ✅ morto |
| M23 | `monitor.py:1175` | sobe sem banco configurado | ✅ morto |
| M24 | `oracle_db.py:158` | espera padrão 30 s | ✅ morto |
| M25 | `oracle_db.py` `proximo_id` | `ErroSemId(str(e))` (mensagem inteira do driver) | ✅ morto |
| M26 | `monitor.py:1452-1454` | salva a imagem antes de pedir o id | ✅ morto |
| M27 | `monitor.py` (resgate no laço) | laço não trata `ErroSemId` do resgate | ❌ sobreviveu → T8 |
| M28 | `monitor.py` (arranque) | arranque não trata `ErroSemId` | ✅ morto |

Defeito provado na rodada 1 (fora/voltou alternando a cada ~1 min com ORA-02289) → corrigido em T8.

### Rodada 2 (`7a1a1ec`)

R19, R27, RV, N2, N3, N6 mortos; N5 e N7 equivalentes na prática (as duas chamadas de `_confirmar_volta` se cobrem: a mensagem
que falhou é sempre renumerada no resgate, e um dos dois pontos manda o "voltou" na mesma volta); **N1 e N4 sobreviveram → T9**.

### Rodada 3 (`9bde70a`, esta verificação)

| # | Arquivo:linha | Mutação | Resultado |
| --- | --- | --- | --- |
| R19 | `monitor.py:1095-1096` | `_recuperar_lacuna` engole `ErroSemId` | ✅ morto (`test_fora02_sequence_falhando…`) |
| R27 | `monitor.py:1273` | laço não trata `ErroSemId` do resgate | ✅ morto (`test_fora02_sequence_falhando…`) |
| RV | `monitor.py:1130` | `vigia_banco.voltou()` de volta no `_esperar_banco` | ✅ morto (`test_fora02_sequence_falhando…`) |
| RV completo | `monitor.py:1130,1138` | `voltou()` no `_esperar_banco` **e** `_confirmar_volta` inerte (defeito original) | ✅ morto (4 testes: `test_fora02_sequence_falhando…`, `test_fora03_banco_cai_no_resgate…`, `test_fora02_queda_depois_de_ids…`, `test_fora02_voltou_vem_depois_do_id`) |
| N1 | `oracle_db.py:390` | `ids_entregues` não incrementa | ✅ morto (`test_sequence_oracle.py::test_ids_entregues_conta_so_numero_de_verdade`) |
| N4 | `monitor.py:1127` | `ids_na_queda` não registrado na queda | ✅ morto (`test_fora02_queda_depois_de_ids_entregues…`) |
| N2 | `monitor.py:1138` | `_confirmar_volta` sem checar `ids_na_queda` | ✅ morto (`test_fora02_sequence_falhando…`) |
| N3 | `monitor.py:1277` | tira o `continue` do resgate | ✅ morto (`test_fora02_sequence_falhando…`) |

**Sensor depth**: P0 (integridade do id), 45 mutações em 3 rodadas.
**Result**: **PASS** — rodada 3 com 8/8 mortos; nenhum sobrevivente não equivalente em aberto (N5 e N7 equivalentes na prática).

---

## Edge Cases

- [x] Catch-up para no meio: tmp restantes apagadas, marcador no último gravado (FORA-05).
- [x] Banco fora na partida: o 1º id reconecta (`test_sequence_oracle.py:119-123`) e o arranque espera (`:304-318`).
- [x] Sequence ausente (ORA-02289) sem reconectar (`test_sequence_oracle.py:111-116`).
- [x] `NEXTVAL` falhando com o banco respondendo, sem e com ids antes da queda (`:273-282`, `:413-427`).
- [x] Banco cai durante o resgate com 2 grupos (`:285-301`).
- [x] Reconexão no `NEXTVAL` conta o id; falha não conta (`test_sequence_oracle.py:158-175`).
- Observação (sem correção pedida): se o banco volta e nenhuma mensagem nova chega, o "voltou" só sai no 1º id, e nesse
  intervalo não há lembrete. É coerente com "normalizado = `NEXTVAL` funcionando".

---

## Gate Check (job `tools`, `.github/workflows/ci.yml:155-179`, sobre `9bde70a`)

| Comando | Resultado |
| --- | --- |
| `cd tools/capture-chat-groups && python -m unittest discover -s tests -v` | `Ran 15 tests … OK` |
| `cd tools && python -m pytest -q` | `410 passed in 172.13s` |
| `cd tools && python -m ruff check vps/ tests/` | `All checks passed!` |
| `cd tools && shellcheck vps/*.sh` (ShellCheck 0.11.0) | sem achados, rc 0 |

- **Antes** (`origin/develop`): 368 (pytest) + 15 (unittest). **Depois**: 410 + 15. **Delta**: +42.
- Nenhum teste apagado nem pulado. Asserções trocadas sem enfraquecer: `test_sh03` passou de "recusa" para "sobe sem conferir"
  (exigência nova da spec); casos do reinício perderam a linha "Retomando contador" e o REI-03 trocou para "perfil travado",
  mantendo `len(avisos) == 1` e o motivo no texto.

---

## Code Quality

| Princípio | Status |
| --- | --- |
| Minimum code / surgical changes | ✅ |
| No scope creep (robô das lojas intocado; `checa_contador.py` só ganhou nota histórica) | ✅ |
| Matches patterns (reconexão de `oracle_db`, `_avisar` de `VigiaCaptura`, falsos de `tests/falsos.py`) | ✅ |
| Spec-anchored outcome check | ✅ |
| Cobertura por camada (banco: `test_sequence_oracle.py`; aviso: `test_alerta_banco.py`; monitor: `test_id_sequence_whatsapp.py`; scripts: testes de shell) | ✅ |
| Todo teste mapeia a requisito | ✅ |
| Diretrizes: `CLAUDE.md`, `docs/WORKFLOW-AGENTES.md` (lições 11, 14, 29) | ✅ |
| Docstring de `tools/capture-chat-groups/main.py:22-26` atualizada | ✅ |

---

## Fix Plans

Nenhum aberto. Itens para o PR (não bloqueiam a validação):
- citar a regra 3 como `tools/capture-store-pages/main.py:968` (a spec diz `:807`);
- decisões propostas para o `docs/DECISOES.md`: `NOCACHE`, espera de 60 s, marcador parado com o banco fora, "voltou" só
  depois do 1º id do `NEXTVAL`, robô não sobe sem banco configurado (código 4).

---

## Requirement Traceability Update

| Requirement | Previous | New |
| --- | --- | --- |
| SEQ-01..05 | Done | ✅ Verified |
| FORA-01..05 | Done / Needs Fix | ✅ Verified |
| PAR-01, PAR-02 | Done | ✅ Verified |
| SQL-01..03 | Done | ✅ Verified |

---

## Execução real (dono) — bloqueia o merge

Na inst1, pela ordem de virada (`tools/vps/README.md:329-338`) e a conferência real (`tools/vps/README.md:340-349`):
1. 1ª captura com o id inicial da sequence (o `DBMS_OUTPUT` do bloco 1 mostra o `START WITH`) e `db=ok`;
2. `INSERT` de teste com `ID_OFERTA` nulo numa transação, `ROLLBACK` no fim (prova a trigger);
3. `KILL SESSION` da conexão do robô + `kill -9` no `run_captura.py` (a unidade sobe de novo): sobe sem conferir contador,
   **sem id repetido, sem aviso de "fora"** (o `proximo_id` reconecta sozinho);
4. banco fora de verdade: `sudo iptables -I OUTPUT -p tcp --dport 1522 -j DROP` por ~3 min e depois `-D` com a mesma regra.
   Esperado: 1 "Banco Oracle fora" no Telegram, nada novo no CSV, marcador do grupo parado; ao liberar, a mesma mensagem sai
   com id novo e chega o "voltou";
5. `systemctl --user start besave-reinicio-whatsapp` à mão: reinício confirmado, sem aviso no Telegram.

Riscos do item 4 para o dono observar (não verificáveis sem banco; não bloqueiam a validação):
- **`DROP` não derruba a conexão aberta, ele a congela.** `wa/oracle_db.py` não define `call_timeout` nem `expire_time`;
  com a regra ativa, o `NEXTVAL` numa conexão já estabelecida pode ficar bloqueado até o timeout de retransmissão do TCP do
  Linux (~15 min com `tcp_retries2` padrão), em vez de falhar. Aí, em ~3 min não chega o "fora" e, ao tirar a regra, a chamada
  continua sem "fora" nem "voltou". Se acontecer: manter o `DROP` até o "fora" aparecer, ou conferir
  `retry_count`/`connect_timeout`/`expire_time` no `tnsnames.ora` do wallet. É comportamento do teste, não regressão da
  BSV-56; se o dono quiser o "fora" em minutos, vale um ticket para `call_timeout`.
- **"A mesma mensagem"** só existe se chegar oferta durante a janela: sem mensagem, nada é numerado e nada avisa (o `NEXTVAL`
  só é pedido quando há o que gravar).

Regra 3 da spec, para o PR: o robô das lojas lê a fila desde 0 no modo monitor em `tools/capture-store-pages/main.py:968`
(a spec cita `:807`).

Evidência redigida pela regra 11 antes do commit.

---

## Rodada T10 (`ef456d1`, só SQL e README) — PASS

| Item pedido | Evidência | Resultado |
| --- | --- | --- |
| (a) bloco 1 reexecutável: sequence existente não é criada nem alterada, imprime `LAST_NUMBER` e segue; 2ª execução sem erro e sem mudar a sequence | SQL `:25-46`; trigger `CREATE OR REPLACE` `:49`; `tools/tests/test_sql_sequence.py:56-68` (`CREATE`/`ALTER`/`DROP` ausentes do ramo "existe", `count("CREATE SEQUENCE") == 1`, sem `ALTER SEQUENCE`) | ✅ |
| (b) bloco 3 inalterado desde `9bde70a` e barrando sequence ≤ maior id | `diff` do bloco `-- 3. Conferencia` entre `9bde70a` e `ef456d1` vazio; `IF v_proximo > v_maior AND v_status = 'ENABLED'`, senão `RAISE_APPLICATION_ERROR` (`:73-78`) | ✅ |
| (c) cabeçalho: produção Oracle Autonomous (`bsvdb_tp`), não XE 11.2 | SQL `:4-6` | ✅ |
| (d) PL/SQL válido para Autonomous (sem banco) | seção SQL acima | ✅ |
| README sem grant/sinônimo; robô conecta como `BESAVE` | `tools/vps/README.md:333-334`; busca por grant/sinônimo/synonym sem resultado | ✅ |
| README: `KILL SESSION` + `kill -9` esperando só "sem id repetido" (sem "fora") | `tools/vps/README.md:343-345` | ✅ |
| README: teste real com `iptables` por ~3 min e `-D`; 1 "fora", nada no CSV, marcador parado; ao liberar, a mesma mensagem com id novo e o "voltou" | `tools/vps/README.md:346-348` | ✅ (riscos na seção de execução real) |

Mutante T10 (worktree temporário em `C:\Users\REDACTED\AppData\Local\Temp\claude\…\scratchpad\vrf`, removido; sem `git stash`):

| # | Arquivo:linha | Mutação | Resultado |
| --- | --- | --- | --- |
| S1 | `BSV-56_sequence_id_oferta.sql:30-44` | sem `COUNT`/`IF`/`ELSE`/`END IF`; `CREATE SEQUENCE` incondicional | ✅ morto (`test_sql_sequence.py::test_sql_reexecutavel_nao_recria_sequence_existente`) |

Gates T10: `cd tools && python -m pytest -q tests/test_sql_sequence.py` → `7 passed`; `python -m ruff check vps/ tests/` →
`All checks passed!`; `shellcheck vps/*.sh` → rc 0. O diff do T10 não toca em `.sh` nem em código Python de produção; a
suíte inteira (410 testes) rodou verde sobre `9bde70a`. `git status --porcelain` da árvore real vazio antes e depois.

---

## Summary

**Overall**: ✅ Ready para PR; merge só depois da execução real do dono.

**Spec-anchored check**: 20/20 critérios automatizáveis com teste e valor exato; nenhuma lacuna de precisão aberta.
**Sensor**: rodada 3 com 8/8 mortos (M19, M27, "voltou" cedo, N1, N4 e controles); 45 mutações nas 3 rodadas, sobreviventes
anteriores fechados por T8 e T9; N5/N7 equivalentes na prática.
**Gate**: unittest 15 OK; pytest 410 passed (sobre `9bde70a`); T10: `test_sql_sequence.py` 7 passed, ruff OK, shellcheck OK.

**What works**: id pela sequence nos dois caminhos; banco fora sem gravar nem mover marcador; espera de 60 s; um aviso por
ocorrência, lembrete aos 120 min e "voltou" só depois de um id novo (sem alternar com ORA-02289, inclusive depois de ids já
entregues); resgate com banco fora espera e se refaz antes do rodízio; partida sem `checa_contador.py` com o comando montado
inteiro; reinício só por `Grupo aberto`; SQL conforme a spec e reexecutável (mutante S1 morto); regra 3 confirmada
(`tools/capture-store-pages/main.py:968`).
