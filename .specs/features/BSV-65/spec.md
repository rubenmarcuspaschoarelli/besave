# BSV-65 Navegador quebrado do robô das lojas não queima linha, reabre e avisa — Specification

Fonte: `docs/specs/BSV-65.md`. Pasta: `tools/capture-store-pages/` (+ `tools/vps/vigia_robos.py`, `tools/tests/`).

## Problem Statement

De 18/11 a 23/11 e de novo em 24/11 o Chromium do robô das lojas morreu (`Page crashed` em toda navegação)
com o processo Python vivo: 3.697 + 794 linhas foram para `'9'`, o batimento seguia renovado e ninguém soube.

## Goals

- [ ] Navegador quebrado é classificado por uma função só e nunca queima linha.
- [ ] O robô reabre a aba, depois relança o navegador, e sai com código 3 quando não consegue.
- [ ] Telegram avisa quebra, saída e volta; o vigia vê captura por navegador parada.
- [ ] Diagnóstico da causa no log e relançamento preventivo a cada N horas.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Reprocessar as linhas dos incidentes | SQL do dono |
| Corrigir a causa do crash | ticket próprio com os dados da Saída 8 |
| WhatsApp, publicador, Shopee pela API | spec |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Testes | em `tools/tests/` (pytest), onde já vivem todos os testes do robô das lojas; `capture-store-pages` não tem pasta de testes | CI `tools` roda `pytest` em `tools/` | n |
| Status da linha quebrada | o `DS_CAPTURA` de hoje (`erro: <tipo>: <msg>`) só no log; a linha fica `'0'` (`oracle=retida(0)`) | mantém o sinal legível no log e o teste BAT-08 da BSV-57 | n |
| "Exceção do Playwright" | classificada pela mensagem (o tipo não é testável sem Playwright); timeout = classe `TimeoutError` no `goto` | regra 2: uma função só | n |
| Exceções engolidas (`prepare`, imagens, link de afiliado, ponte) | `prepare`, ponte e `link_afiliado.capturar` relançam o que a função classifica; o evento `crash` da `page` marca a aba e vale no fim da linha | Saída 2 cobre todas as fases | n |
| "Primeira navegação da aba nova" | o `goto` da primeira linha depois da aba nova; se quebrar → relançamento direto | Saída 3b | n |
| 3 relançamentos em 60 min | o 3º pedido de relançamento por falha dentro de 60 min sai com código 3 sem relançar; 2 seguem | Saída 3c, critério "3 → código 3; 2 → segue" | n |
| Retidas (N) nas mensagens | linhas retidas pelo navegador desde a última `ok` por navegador | Saída 5 | n |
| `ultimo_ok_navegador` antes do primeiro `ok` | instante da primeira gravação do batimento do processo | o vigia precisa de uma referência; reinício conta como andar | n |
| Linha de diagnóstico | `[navegador] diagnostico: mem_disponivel=<MB> MB \| chromium=<n> \| rss_chromium=<MB> MB \| maior=<MB> MB \| desde_lancamento=<min> min \| navegacoes=<n>`; fora do Linux só os dois últimos | Saída 8 | n |
| Chromium "filho do robô" | descendente do pid do robô (o Chromium é filho do driver Node) com nome contendo `chrom` | Saída 8 | n |
| Preventivo | conferido no topo de cada volta do monitor (entre lotes; na janela noturna a volta é a rodada) | Saída 9 | n |
| Lote sem `--monitorar` | recupera e continua do ponto em que parou | Saída 3 vale para os dois modos | n |

**Open questions:** none.

---

## User Stories

### P1: Navegador quebrado não queima linha, reabre e avisa ⭐ MVP

Como dono, quero que um Chromium quebrado não mande linhas para `'9'`, se recupere sozinho e me avise.

**Acceptance Criteria (EARS):**

- **CLS-01**: WHEN uma exceção ou status contém (minúsculas) `page crashed`, `target crashed`, `has been closed`, `target closed` ou `target page, context or browser` THEN `navegador.sinal` SHALL devolver o sinal; senão `None`.
- **CLS-02**: WHEN a linha tem navegador quebrado THEN `batimento.bater_linha` SHALL não renovar o batimento.

- **LIN-01**: WHEN navegador quebrado ocorre em `goto`, `prepare`, `capture`, imagens, link de afiliado ou ponte THEN a linha SHALL ficar `'0'` (`oracle=retida(0)`), sem `marcar_erro`, travando o ponteiro.
- **LIN-02**: WHEN uma linha tem navegador quebrado THEN o lote SHALL parar e as linhas seguintes não SHALL ser navegadas.

- **REC-01**: WHEN o lote para por navegador THEN o robô SHALL fechar a aba e abrir outra no mesmo contexto antes da próxima linha.
- **REC-02**: WHEN abrir a aba falha OR a primeira navegação da aba nova quebra THEN o robô SHALL fechar o contexto e relançar `launch_persistent` com o mesmo perfil, refazendo `preparar_contexto`.
- **REC-03**: WHEN o relançamento falha OR seria o 3º relançamento por falha em 60 min THEN o robô SHALL sair com código 3 sem gravar batimento depois.

- **TMO-01**: WHEN `TimeoutError` no `goto` de loja por navegador THEN a linha SHALL ficar `'0'` retida e somar na sequência.
- **TMO-02**: WHEN 3 timeouts seguidos sem `ok` por navegador no meio THEN o robô SHALL disparar REC-01.
- **TMO-03**: WHEN a mesma linha acumula 3 timeouts na execução THEN ela SHALL ir para `'9'` com o motivo de hoje.

- **TEL-01**: WHEN uma recuperação acontece THEN o robô SHALL mandar uma mensagem `Robo das lojas: navegador quebrou (<sinal>); <aba nova | navegador relancado>. N linha(s) retida(s).`
- **TEL-02**: WHEN sai com código 3 THEN SHALL mandar `Robo das lojas: navegador nao reabriu; saindo (codigo 3) para o vigia reiniciar.`
- **TEL-03**: WHEN a primeira `ok` por navegador depois de uma ocorrência THEN SHALL mandar `Robo das lojas: navegador voltou (N linha(s) retida(s) voltam a ser processadas).`; `ok` da Shopee pela API não fecha.

- **VIG-01**: WHEN uma linha de loja por navegador termina THEN o batimento SHALL levar `ultimo_ok_navegador` e `tentativas_navegador`; Shopee pela API e `loja_pausada` não mexem.
- **VIG-02**: WHEN `tentativas_navegador ≥ 10` AND `ultimo_ok_navegador` há mais de 60 min THEN o vigia SHALL avisar sem reiniciar, com lembrete a cada 2 h e "voltou" quando o campo andar; batimento sem os campos → nada.

- **DIA-01**: WHEN uma recuperação, um preventivo ou o evento `crash` da `page` THEN o robô SHALL logar a linha de diagnóstico; leitura que falha vira `?`, nunca exceção.

- **PRE-01**: WHEN passaram `monitor.relancar_navegador_horas` (padrão 6; `0` desliga; inválida → 6 com WARN) desde o último lançamento THEN o robô SHALL relançar entre lotes, sem Telegram e sem contar para REC-03; falha → REC-03.

- **DOC-01**: README com "Navegador quebrado", código 3, mensagens, preventivo e SQL de reprocessar com `DT_OFERTA >= SYSDATE - 1`; `config.example.json` com a chave opcional.

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| CLS-01 | P1 | T1 | Done |
| CLS-02 | P1 | T1 | Done |
| LIN-01 | P1 | T2 | Done |
| LIN-02 | P1 | T2 | Done |
| REC-01 | P1 | T3 | Done |
| REC-02 | P1 | T3 | Done |
| REC-03 | P1 | T3 | Done |
| TMO-01 | P1 | T2 | Done |
| TMO-02 | P1 | T2 | Done |
| TMO-03 | P1 | T2 | Done |
| TEL-01 | P1 | T2/T3 | Done |
| TEL-02 | P1 | T2/T3 | Done |
| TEL-03 | P1 | T2/T3 | Done |
| VIG-01 | P1 | T1/T2/T4 | Done |
| VIG-02 | P1 | T1/T2/T4 | Done |
| DIA-01 | P1 | T1/T3 | Done |
| PRE-01 | P1 | T1/T3 | Done |
| DOC-01 | P1 | T5 | Done |

## Success Criteria
- `pytest` e `ruff check vps/ tests/` em `tools/` verdes; testes do vigia no WSL.
- Execução real do dono (inst1) — bloqueia o merge.
