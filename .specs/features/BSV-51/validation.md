# BSV-51 validation

**Veredito final (rodada 2): PASS.** Criterios de aceite automatizados cobertos; sobreviventes 1-9 da rodada 1 agora morrem; resta o JS do `aria-label` (so provavel no navegador real) e lacunas de borda menores. Execucao real na VPS pendente do dono e bloqueia o merge.
**Verificador:** Verifier independente (sub-agente, autor != verificador). Rodada 1: a81f0dd. Rodada 2: HEAD 8e51c88. Sem acesso a WhatsApp, navegador ou Oracle.

## Criterio -> evidencia

| Criterio | Codigo | Teste | Resultado |
|---|---|---|---|
| DES-01 Escape, depois botao, novo clique | tools/capture-chat-groups/wa/destravar.py:100-122 | tools/tests/test_destravar.py:54-66, 191-196 | PASS |
| DES-02 log do aviso fechado | destravar.py:114 | test_destravar.py:60-65 | PASS |
| DES-03 erro em <= 3 x 5 s, sem laco | destravar.py:19, 111-122 | test_destravar.py:68-78 (2 cliques sem aviso; 3 com, todos timeout=5000) | PASS |
| DES-04 lista fechada, inteira (licao 14) | destravar.py:22,27,66-68,34-53 | test_destravar.py:105-122 (tupla igual, 5 permitidos, 11 negados, lista passada ao navegador, 1 so `.click()` do JS) | PASS (JS em si so e exercido no teste real) |
| DES-05 sem bloqueio = 1 clique, nada mais | destravar.py:92-94 | test_destravar.py:46-51, 81-90 | PASS |
| REC-01 N voltas cegas -> reload, #pane-side, resgate | monitor.py:1198,1252-1257; destravar.py:125-135 | test_rodizio_destravar.py:404-421 (8 recarrega, 7 nao, N=3 repete), test_destravar.py:125-144 | PASS |
| REC-02 contador/marcadores intocados | destravar.py/alerta.py nao tocam estado | test_rodizio_destravar.py:424-429 | PASS |
| ALE-01 limite 45 min e lembrete 2 h | alerta.py:215-222 | test_alerta.py:233-248, 293-298 | PASS (fronteira exata nao testada, ver S3/S4) |
| ALE-02 nada na janela noturna | alerta.py:206-213 | test_alerta.py:251-259 | PASS |
| ALE-03 "voltou" uma vez | alerta.py:208-211 | test_alerta.py:262-272; test_rodizio_destravar.py:437-442 | PASS |
| ALE-04 sem chaves so log; falha sem token no log | alerta.py:193-202 | test_alerta.py:275-290; test_rodizio_destravar.py:445-447 | PASS |
| Saida 5 README VPS | tools/vps/README.md:154-178 (o que faz sozinho, log, Telegram, quando entrar na tela) | revisao manual | PASS |
| config.example documenta chaves | conf/config.example.json:25-34 | test_rodizio_destravar.py:450-455 | PASS |
| Real, VPS (dono) | - | - | PENDENTE (bloqueia merge) |

## Gates (rodada 2, HEAD 8e51c88)
- `cd tools && pytest`: 181 passed.
- `ruff check vps/ tests/`: All checks passed.
- `cd capture-chat-groups && python -m unittest discover -s tests`: 15 OK.
- `git status` limpo apos mutantes (restaurados byte a byte).

## Sensor de discriminacao (3 testes novos por mutante)
Rodada 1: 31 mortos, 11 sobreviventes. Rodada 2: os 43 mutantes originais reaplicados; **42 mortos**, 1 sobrevivente.
Mortos agora (antes sobreviviam): M14 (n=0), A01 e A02 (fronteiras de 45 min e 2 h), A13 (`desde`), B01, M02 e M11
(`antes_de_repetir` ausente ou fora de ordem), B02 (busca direta), M17 (erro no 2o clique), O02 (resgate pendente com N<5),
O07 (`lacuna_s`), O08 (janela no vigia). Os demais 31 da rodada 1 continuam mortos.

Mutantes novos da rodada 2:

| Mutante | Resultado |
|---|---|
| N03 `_INTERCEPTADO` encurtado | morto |
| N05 `recarregar` devolve True sempre | morto |
| N06 2o clique sem timeout | morto |
| N01 `recarregar_voltas` com `n > 1` (valor 1 vira o padrao) | sobrevive: lacuna menor de borda, sem teste com `recarregar_voltas=1` |
| N02 `sem_abrir_minutos` com `>= 0` (0 vira limite 0) | sobrevive: lacuna menor de borda, config 0 nao testada |
| N04 `page.reload()` sem `wait_until` | sobrevive: equivalente nos testes (o stub aceita `**kw`); so muda o Playwright real, coberto pelo teste real do dono |

Sobreviventes finais:
- **M15 JS sem `aria-label`**: inerente, o JS so executa no navegador. Cobrir no teste real (botao identificado so pelo aria-label).
- N01 e N02: lacunas menores, opcionais. N04: equivalente em teste.

Nenhum sobrevivente fere criterio de aceite. Observacao de estilo (nao bloqueia): `conferir_item` em browser.py tem continuacao de
linha com espacos no lugar de `\`; `wa/` nao e coberto pelo ruff do CI.

## Pendente do dono (bloqueia o merge)
Teste real na VPS (spec "Critério de aceite - Real"): sobreposicao aberta a mao fecha sozinha com a linha no log; tela travada
por mais de 45 min dispara o aviso e depois o "voltou"; botao identificado so por `aria-label` (M15).

## Pós-rodada 2
N01 e N02 viraram teste (`test_recarregar_voltas_1_vale_1`, `test_limite_zero_ou_negativo_cai_no_padrao`); só testes, sem mudança de código. N04 equivalente (stub aceita `**kw`); M15 fica para o teste real do dono.
