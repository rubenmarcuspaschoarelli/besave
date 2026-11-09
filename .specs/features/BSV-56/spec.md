# BSV-56 `ID_OFERTA` por sequence no Oracle Specification

Fonte: `docs/specs/BSV-56.md`. Lições 14, 28, 29, 31. Depende de BSV-54 (em `develop`).

## Problem Statement

O `ID_OFERTA` nasce de `controle.ultimo_id_processado` do `config.json`, gravado no `finally`. Parada
que não é Ctrl+C deixa o contador atrás do que já foi gravado; por isso a partida roda
`checa_contador.py` e recusa subir, o que impede reinício automático e um segundo produtor na fila.

## Goals

- [ ] Todo id vem de `SQ_OFERTA_FILA.NEXTVAL`; o arquivo deixa de numerar.
- [ ] Banco fora: nada é gravado, marcador parado, aviso no Telegram e espera.
- [ ] Partida sem conferência de contador; reinício diário confirma só por `Grupo aberto`.
- [ ] Trigger preenche `ID_OFERTA` nulo (robô de sites, rede de segurança).

## Out of Scope

Robô de sites, vigia externo (BSV-57), partida sem perguntas das lojas (BSV-55), renumerar ids
existentes, robô das lojas (só conferido), execução real na inst1 (dono).

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Falha de `NEXTVAL` que não é de conexão (ex.: ORA-02289, sequence ausente) | Também levanta `ErroSemId` e entra na espera | Regra 1: nenhum id fora do banco; o aviso mostra o código ORA | n |
| Retentativa durante a espera | `db.disponivel()` (`SELECT 1 FROM DUAL`, com reconexão) a cada `db.espera_segundos` | Não queima número da sequence a cada tentativa | n |
| Retomada depois da espera | Marca o resgate (catch-up pelo marcador de cada grupo) | O catch-up relê desde o marcador, que não andou | n |
| Bloco `db` desligado no config (ou sem `oracledb`) | O robô não sobe: sai com código 4 e mensagem | Sem banco não há id; esperar para sempre esconderia erro de configuração | n |
| "Voltou" | Enviado quando `disponivel()` volta a responder, antes do reprocessamento | "ao normalizar" | n |
| Texto do aviso | Tipo da exceção e código ORA/DPY, nunca a mensagem inteira | Mensagem do driver pode trazer DSN/host | n |
| Contagem no log do catch-up | Quantidade de linhas gravadas, não diferença de ids | Ids podem ter buracos | n |

Open questions: none

---

## User Stories

### P1: Id pela sequence ⭐ MVP

**Acceptance Criteria**:

1. SEQ-01: WHEN o robô ao vivo processa uma mensagem com oferta, THE SYSTEM SHALL obter o id de `proximo_id()` e usá-lo no nome da imagem, na linha do CSV e em `P_ID_OFERTA`.
2. SEQ-02: THE SYSTEM SHALL NOT ler `controle.ultimo_id_processado` para numerar (um valor absurdo no config não muda o id).
3. SEQ-03: WHEN o catch-up grava os itens, THE SYSTEM SHALL renomear cada imagem temporária com o id de `proximo_id()`, em ordem cronológica.
4. SEQ-04: WHEN `NEXTVAL` falha por conexão, THE SYSTEM SHALL reconectar uma vez e, se falhar de novo, levantar `ErroSemId` sem devolver número.
5. SEQ-05: THE SYSTEM SHALL gravar o último id usado em `ultimo_id_processado` só como informação, e SHALL NOT logar "Retomando contador".

### P1: Banco fora ⭐ MVP

1. FORA-01: IF `proximo_id()` falha, THEN THE SYSTEM SHALL NOT gravar a mensagem (nem CSV, nem imagem definitiva) e SHALL NOT avançar o marcador do grupo.
2. FORA-02: WHEN o banco fica fora, THE SYSTEM SHALL avisar no Telegram uma vez, lembrar a cada 2 h e avisar "voltou" ao normalizar.
3. FORA-03: WHILE o banco está fora, THE SYSTEM SHALL tentar de novo a cada `db.espera_segundos` (padrão 60) sem andar nenhum grupo.
4. FORA-04: WHEN o banco volta, THE SYSTEM SHALL reprocessar a mesma mensagem com id novo (resgate pelo marcador).
5. FORA-05: IF o catch-up para no meio por banco fora, THEN THE SYSTEM SHALL apagar as imagens temporárias não gravadas e manter o marcador no último item gravado.

### P1: Partida e reinício

1. PAR-01: WHEN `iniciar_captura.sh` sobe o robô, THE SYSTEM SHALL NOT chamar `checa_contador.py` (nem o `.ps1`), mantendo as conferências de run vivo, perfil travado e scope vivo e o comando montado do scope.
2. PAR-02: WHEN o log novo tem `Grupo aberto`, THE SYSTEM SHALL confirmar o reinício sem aviso; sem marca de partida, SHALL avisar.

### P1: SQL

1. SQL-01: THE SYSTEM SHALL criar `SQ_OFERTA_FILA` com `START WITH` = `GREATEST` dos `MAX(ID_OFERTA)` da fila e da `OFERTA` + 1, `INCREMENT BY 1 NOCACHE`, via `EXECUTE IMMEDIATE`.
2. SQL-02: THE SYSTEM SHALL criar `TRG_OFERTA_FILA_ID` `BEFORE INSERT FOR EACH ROW WHEN (NEW.ID_OFERTA IS NULL)`.
3. SQL-03: THE SYSTEM SHALL trazer bloco de conferência e bloco de reversão comentado.

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| SEQ-01 | Id pela sequence | Execute | Pending |
| SEQ-02 | Id pela sequence | Execute | Pending |
| SEQ-03 | Id pela sequence | Execute | Pending |
| SEQ-04 | Id pela sequence | Execute | Pending |
| SEQ-05 | Id pela sequence | Execute | Pending |
| FORA-01 | Banco fora | Execute | Pending |
| FORA-02 | Banco fora | Execute | Pending |
| FORA-03 | Banco fora | Execute | Pending |
| FORA-04 | Banco fora | Execute | Pending |
| FORA-05 | Banco fora | Execute | Pending |
| PAR-01 | Partida e reinício | Execute | Pending |
| PAR-02 | Partida e reinício | Execute | Pending |
| SQL-01 | SQL | Execute | Done |
| SQL-02 | SQL | Execute | Done |
| SQL-03 | SQL | Execute | Done |

## Success Criteria

- [ ] `python -m unittest discover -s tests` (robô), `pytest` em `tools/`, `ruff check vps/ tests/` e `shellcheck vps/*.sh` verdes.
- [ ] Execução real na inst1 pela ordem de virada (dono; bloqueia o merge).
