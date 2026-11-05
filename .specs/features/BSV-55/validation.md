## Validation: BSV-55 — PASS (ciclo de correção 2/3)

Todos os critérios de aceite de `docs/specs/BSV-55.md` e os 14 requisitos EARS têm teste que prova o valor que a
spec define. Os gates passam e o sensor matou os 25 mutantes. A execução real na inst1 é do dono e **bloqueia o
merge**: está pendente e não entra neste veredito.

**Data**: 2026-11-05
**Spec do dono**: `docs/specs/BSV-55.md` · **Spec EARS**: `.specs/features/BSV-55/spec.md`
**Diff**: `9fcd5c1..11c30c6` (7 commits). Produção: 1e13a72, bd65319, f954b4f, 2b2a4da, df9f3c3. Só testes:
597f196 e 11c30c6 (`tools/tests/test_pausa_lojas.py`).
**Verificador**: Verifier independente, sub-agente (autor ≠ verificador). Não alterou código nem testes da árvore real.

### Histórico dos ciclos

| Ciclo | HEAD | Sensor | Veredito | O que mudou |
| --- | --- | --- | --- | --- |
| 0 | df9f3c3 | 22/25 (sobreviveram M22, M23, M24) | FAIL | — |
| 1 | 597f196 | 24/25 (sobreviveu M23) | FAIL | teste do monitor com o laço real e teste do alerta com só uma das chaves; mas `_pausa_padrao` falso devolvia sempre a mesma instância e escondia o M23 |
| 2 | 11c30c6 | **25/25** | **PASS** | `_pausa_padrao` falso cria uma `PausaLojas` nova a cada chamada (como em produção) e o teste confere `len(criadas) == 1` |

---

## Tarefas

| Tarefa | Estado | Notas |
| --- | --- | --- |
| T1 `--sem-perguntas` e unidade | ✅ | — |
| T2 Marcas e linha retida | ✅ | — |
| T3 Motivo do afiliado | ✅ | `sessao` só na Shopee (Observação A) |
| T4 Pausa e Telegram | ✅ | ligação no monitor coberta depois dos ciclos 1–2 |
| T5 README | ✅ | — |

---

## Checagem ancorada na spec

Caminhos relativos a `tools/`.

| Critério (spec do dono) | Resultado que a spec define | Evidência `file:line` | Resultado |
| --- | --- | --- | --- |
| Sem perguntas: com `--sem-perguntas` e um `stdin` que falha se for lido, o monitor chega à 1ª varredura (SEM-01) | nenhum `input()`, chega à varredura | `tests/test_sem_perguntas.py:107-110`: `assert chegou`, `assert perguntas == []` (o `stdin` falso tem `isatty()=True` e falha na leitura, `:45-54`); `main()` real com `argv` real (`:73`) | ✅ |
| SEM-01, lote e gates de afiliado | nenhum `input()` em caminho nenhum | `tests/test_sem_perguntas.py:119-124` | ✅ |
| Sem a opção, a pergunta da Shopee continua (SEM-02) | a pergunta é feita | `tests/test_sem_perguntas.py:113-116`: `"Shopee" in perguntas[0]` | ✅ |
| Navegador aberto com `--sem-perguntas` (SEM-03) | código ≠ 0, nenhum processo morto, mensagem clara | `tests/test_sem_perguntas.py:134-138`: `code not in (0, None)`, `mortos == []`; produção `capture-store-pages/main.py:94` `sys.exit(2)` | ✅ |
| SEM-03 sem a opção | comportamento atual (pergunta) | `tests/test_sem_perguntas.py:141-147` | ✅ |
| Unidade com `--monitorar --sem-perguntas` (SEM-04) | linha de comando exata | `tests/test_unidades.py:57`: `partes[-4:] == ["-u","main.py","--monitorar","--sem-perguntas"]` (cauda inteira, lição 14); `vps/systemd/besave-captura-lojas.service:19` | ✅ |
| Captcha do ML, URL redigida → `bloqueado_ou_login` (BLQ-01) | status `bloqueado_ou_login` | `tests/test_bloqueio_lojas.py:10,95-98` (`/captcha/wall/logged?go=REDACTED` e mais 7 telas das 3 lojas, todas redigidas) | ✅ |
| BLQ-01, falso positivo | página de produto não é bloqueio, nem com a marca só na query | `tests/test_bloqueio_lojas.py:20-26,101-104` | ✅ |
| Captcha: linha em `'0'`, `OFERTA` não gravada (BLQ-02) | nem `'1'`, nem `'9'`, nem OFERTA | `tests/test_bloqueio_lojas.py:110`: `db.capturas == [] and db.erros == [] and db.ofertas == []` | ✅ |
| BLQ-02: o ponteiro não passa da linha (regra da BSV-52) | ponteiro parado antes da linha bloqueada, também no lote seguinte | `tests/test_bloqueio_lojas.py:117-121`: `lojas.ponteiro == [10]` | ✅ |
| Afiliado `sessao` (AFI-01) | motivo `sessao` quando o formulário/login não abre | `tests/test_bloqueio_lojas.py:201-204` (fluxo real `_shopee`) | ✅ |
| Afiliado `outro` (AFI-01) | motivo `outro` quando o gerador não devolve link | `tests/test_bloqueio_lojas.py:207-210` | ✅ |
| `sessao` → linha em `'0'`, `OFERTA` não gravada (AFI-02) | `'0'`, nada gravado, ponteiro travado | `tests/test_bloqueio_lojas.py:229-238` | ✅ |
| `outro` → como hoje (AFI-02) | grava `ok` e OFERTA | `tests/test_bloqueio_lojas.py:241-246` | ✅ |
| Pausa: 3 bloqueios da Shopee → Shopee pausada, ML e Amazon da mesma varredura processadas (PAU-01) | só a Shopee pausa; as outras seguem | `tests/test_pausa_lojas.py:98-105` | ✅ |
| PAU-01 entre varreduras do monitor (produção) | a pausa vale nas varreduras seguintes | `tests/test_pausa_lojas.py:267-297`: `pagina.visitas == [1, 2, 3]` (`:295`), `len(criadas) == 1` (`:296`), com `_pausa_padrao` criando uma instância nova por chamada (`:272-278`) | ✅ |
| Linha pausada em `'0'` sem segurar o ponteiro (Regra 2) | `'0'`, ponteiro segue | `tests/test_pausa_lojas.py:108-117` | ✅ |
| 2 bloqueios + 1 sucesso → sem pausa (PAU-02) | sem pausa, sem aviso | `tests/test_pausa_lojas.py:120-125` | ✅ |
| Contagem por loja (Regra 4) | bloqueio de uma loja não conta para outra | `tests/test_pausa_lojas.py:128-132` | ✅ |
| Fim da pausa com sucesso → "voltou" (PAU-03) | uma linha, "voltou" | `tests/test_pausa_lojas.py:135-146` | ✅ |
| Fim da pausa com falha → nova pausa, nenhum "voltou" (PAU-03) | uma linha só, repausa | `tests/test_pausa_lojas.py:149-158`: `visitas == [4]` | ✅ |
| Telegram: 1 mensagem por entrada; lembrete só depois de 6 h com relógio falso (TEL-01) | 1 aviso; lembrete em ≥ 6 h, não antes | unidade: `tests/test_pausa_lojas.py:161-177` (5 h 59 → 1; 6 h 00 → 2); monitor: `:297` `len(enviados) == 2 and "em pausa por" in enviados[0] and "continua em pausa" in enviados[1]` | ✅ |
| TEL-01: conteúdo (loja, motivo, linhas retidas, VNC :1) | os quatro itens | `tests/test_pausa_lojas.py:180-194` | ✅ |
| Sem as chaves → só log (TEL-02) | não envia, loga | `tests/test_pausa_lojas.py:197-201`; só uma das chaves: `:300-305` (parametrizado) | ✅ |
| Token fora de toda saída capturada (TEL-02) | token e chat ausentes de stdout/stderr, mesmo com exceção que traz a URL | `tests/test_pausa_lojas.py:204-218`, `:305` | ✅ |
| README (DOC-01) | o que é automático, o que chega no Telegram, logar sem parar o robô | `tests/test_pausa_lojas.py:257-264`; `vps/README.md:112-139` (lido) | ✅ |
| Gates | unittest e ruff verdes | ver Gates | ✅ |
| **Execução real na inst1 (dono)** | os 3 passos da spec | — | ⏳ **Pendente do dono, bloqueia o merge** |

**Estado**: todos os critérios cobertos com o valor definido na spec. Os pontos de precisão viraram as
observações A–C, para o dono.

---

## Sensor de discriminação

Worktree temporária em 11c30c6 (`git worktree add --detach <scratchpad>/verif 11c30c6`), um mutante por vez,
restaurado depois de cada execução. Testes: `tests/test_sem_perguntas.py`, `tests/test_bloqueio_lojas.py`,
`tests/test_pausa_lojas.py`, `tests/test_unidades.py`.

| # | Arquivo:linha | Mutação | Resultado |
| --- | --- | --- | --- |
| M01 | `capture-store-pages/main.py:208` | gate da Shopee no arranque ignora `SEM_PERGUNTAS` | ✅ morto |
| M02 | `capture-store-pages/main.py:240` | `_pode_perguntar` sem o flag | ✅ morto |
| M03 | `capture-store-pages/main.py:94` | `sys.exit(2)` → `sys.exit(0)` | ✅ morto |
| M04 | `capture-store-pages/main.py:90` | chama `fechar_chrome_forcado()` com o flag | ✅ morto |
| M05 | `capture-store-pages/main.py:67` | tira `captcha` das marcas | ✅ morto |
| M06 | `capture-store-pages/main.py:76` | casa a marca na URL inteira, não no caminho | ✅ morto |
| M07 | `capture-store-pages/main.py:72` | `STATUS_RETER` sem `sessao_afiliado_ausente` | ✅ morto |
| M08 | `capture-store-pages/main.py:752` | não trava o ponteiro na linha retida | ✅ morto |
| M09 | `capture-store-pages/core/bloqueio.py:17` | `SEGUIDOS = 2` | ✅ morto |
| M10 | `capture-store-pages/core/bloqueio.py:17` | `SEGUIDOS = 4` | ✅ morto |
| M11 | `capture-store-pages/core/bloqueio.py:99` | sucesso não zera a contagem | ✅ morto |
| M12 | `capture-store-pages/core/bloqueio.py:55` | contagem global em vez de por loja | ✅ morto |
| M13 | `capture-store-pages/core/bloqueio.py:77` | sonda que falha não repausa | ✅ morto |
| M14 | `capture-store-pages/core/bloqueio.py:18` | `LEMBRETE = 5 h` | ✅ morto |
| M15 | `capture-store-pages/core/bloqueio.py:95` | "voltou" sem checar se estava em pausa | ✅ morto |
| M16 | `capture-store-pages/core/alerta.py:41` | imprime a exceção (com token) na falha | ✅ morto |
| M17 | `capture-store-pages/core/link_afiliado.py:540` | corta-circuito conta `sessao` | ✅ morto |
| M18 | `capture-store-pages/core/link_afiliado.py:467` | formulário que não abre devolve `{}` (vira `outro`) | ✅ morto |
| M19 | `capture-store-pages/main.py:513` | lote não pula a loja pausada | ✅ morto |
| M20 | `capture-store-pages/core/bloqueio.py:85` | mensagem não conta as linhas restantes do lote | ✅ morto |
| M21 | `capture-store-pages/main.py:920` | monitor não tira do lote as linhas pausadas | ✅ morto |
| M22 | `capture-store-pages/main.py:910` | monitor nunca chama `pausa.lembrar()` | ✅ morto (ciclo 1) |
| M23 | `capture-store-pages/main.py:937` | monitor não passa `pausa` ao `_processar_lote` | ✅ morto (ciclo 2) |
| M24 | `capture-store-pages/core/alerta.py:34` | envia com token e sem `chat_id` | ✅ morto (ciclo 1) |
| M25 | `capture-store-pages/main.py:982` | a CLI não liga `SEM_PERGUNTAS` | ✅ morto |

**Profundidade**: P0 manual (25 mutantes; a fila de captura é integridade de dado).
**Placar do sensor**: 25/25 mortos, nenhum sobrevivente, nenhum equivalente.

Isolamento: `git status --porcelain` da árvore real igual antes e depois (só `?? .specs/features/BSV-55/validation.md`);
worktree removida (`git worktree list` sem `verif`).

---

## Gates (em 11c30c6)

| Gate (job `tools` do CI) | Comando | Saída |
| --- | --- | --- |
| unittest | `cd tools/capture-chat-groups && python -m unittest discover -s tests` | `Ran 15 tests … OK` |
| pytest | `cd tools && python -m pytest -q` | `270 passed in 48.37s` |
| ruff | `cd tools && python -m ruff check vps/ tests/` | `All checks passed!` |
| shellcheck | `shellcheck ../vps/*.sh` | **não rodou**: shellcheck não está instalado nesta máquina. O diff não toca nenhum `.sh`; o CI roda no `ubuntu-latest` (lição 12: conferir o check da PR) |

Contagem: 229 testes em `9fcd5c1` → 270 em 11c30c6 (+41). Nenhum teste apagado nem pulado. A única asserção
antiga alterada (`tests/test_unidades.py:57-58`) ficou mais estrita.

---

## Qualidade do código

| Princípio | Estado |
| --- | --- |
| Código mínimo / sem escopo extra | ✅ |
| Mudanças cirúrgicas (pasta da spec, `.service`, README) | ✅ |
| Segue os padrões (relógio e envio injetados; token nunca no log, mesma regra de `capture-chat-groups/wa/alerta.py`) | ✅ |
| Asserções batem com a spec | ✅ |
| Cobertura em quem chama (monitor), lição 23 | ✅ |
| Todo teste mapeia a um requisito | ✅ |
| Diretrizes | `CLAUDE.md`, `docs/WORKFLOW-AGENTES.md` (lições 11, 14, 23, 29) |

---

## Observações para o dono (não reprovam)

- **A. `sessao` só vale para a Shopee.** Cumpre a letra da Saída 4: só a Shopee tem formulário (`custom_link`),
  e no ML e na Amazon a falta do widget não separa "deslogado" de "produto sem widget". O risco que fica: se
  cair a sessão de afiliado do ML ou da Amazon, as ofertas são gravadas sem `DS_URL_AFILIADO` e sem aviso no
  Telegram. Depois de 5 falhas, o corta-circuito (`capture-store-pages/core/link_afiliado.py:540`) desliga a
  loja até o próximo arranque, e com `--sem-perguntas` o arranque só registra no log
  (`capture-store-pages/main.py:256-262`). Sugestão: ticket de acompanhamento com aviso no Telegram quando o
  corta-circuito disparar ou o gate de afiliado do arranque achar tela de login.
- **B. "Navegador do próprio perfil".** `processos.chrome_aberto()` vê qualquer `chrome.exe`, e só no
  Windows. No Linux (VPS) quem barra é o perfil travado: `launch_persistent` falha e sai com `exit 1`. Atende a
  "código ≠ 0, nunca mata", e o README avisa ("só no Windows").
- **C. "Tenta uma linha".** Um resultado neutro (erro de navegação, descarte) não fecha a sonda, e a linha
  seguinte da loja também é tentada. Faz sentido (só bloqueio ou sucesso dizem algo da sessão), mas a spec não
  define. `tests/test_pausa_lojas.py:156` prova só a sonda que bloqueia.

---

## Rastreabilidade

| Requisito | Antes | Agora |
| --- | --- | --- |
| SEM-01..04, BLQ-01..02, AFI-01..02, PAU-01..03, TEL-01..02, DOC-01 | Done | ✅ Verificado |

---

## Resumo

- **Pronto?** ✅ Sim, para a PR. O merge depende da execução real do dono.
- **Checagem ancorada na spec**: todos os critérios batem com a spec; observações A–C para o dono.
- **Sensor**: 25/25 mortos.
- **Gates**: 270 pytest, 15 unittest e ruff passaram; shellcheck não rodou localmente (não instalado; o diff
  não tem `.sh`).
- **Pendente do dono, bloqueia o merge**: execução real na inst1 com a branch:
  1. instalar a `.service` nova e subir sem responder nada; conferir no log que a varredura começou;
  2. deslogar o afiliado da Shopee e conferir a pausa, o Telegram e as linhas da Shopee em `'0'`;
  3. logar de novo e conferir o "voltou" e as linhas processadas.

  A evidência vai redigida (regra 11).
- **Decisões a propor para `docs/DECISOES.md`**: limiar de 3, pausa de 60 min, lembrete de 6 h; `sessao` só na
  Shopee (Observação A); marca de bloqueio casada no caminho da URL, em minúsculas.
