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

## Rodada 3 (fix e9aacc6)
Verifier independente (autor != verificador), escopo: `fim_mais_recente` e o ajuste em `VigiaCaptura.registrar_volta`
(`tools/capture-chat-groups/wa/alerta.py:31-37` e `:77-81`) e os 2 testes novos (`tools/tests/test_alerta.py:121-140`).

**Veredito: PASS.** Nenhum bug encontrado; nenhum sobrevivente que fira o achado de 30/10.

Evidencia:
- Teste novo falha no codigo anterior (alerta.py de ecaaff3): `test_tempo_parado_conta_do_fim_da_janela...` FAIL ("ha 20 min" na 1a volta cega, test_alerta.py:127); passa no atual. O 2o teste (`fim_da_janela_de_ontem_nao_atrapalha...`) passa nos dois: e guarda de regressao, nao de correcao.
- Cenario do achado reproduzido fora do pytest (limite 2 min, ultima volta 07:41): 08:00:00 e 08:01:59 nao alertam; 08:02:00 alerta "ha 2 min"; "voltou" (teste) diz ~16 min a partir do fim da janela.
- Bordas conferidas por script: janela que cruza a meia-noite (22-08) e que nao cruza (01-05, alerta as 05:02); sem janela identico ao anterior; reinicio as 14:00 (inicio=14:00, fim de hoje 08:00 < ultimo, sem ajuste); noite inteira sem abrir; agora exatamente 08:00:00 (parado=0); alerta/lembrete/voltou intactos (`desde` = ultimo_aberto ajustado).

Gates: `cd tools && pytest` 185 passed; `ruff check vps/ tests/` OK; `capture-chat-groups: unittest discover -s tests` 15 OK.

Mutantes (so test_alerta.py + test_rodizio_destravar.py; arquivo restaurado, git limpo):

| Mutante | Resultado |
|---|---|
| F1 remove `fim > ultimo_aberto` | morto |
| F2 `>` -> `>=` | sobrevive: equivalente (atribui o mesmo valor) |
| F3 `>` -> `<` | morto |
| F4 `janela[1]` -> `janela[0]` | morto |
| F5 `fim <= agora` -> `<` | sobrevive: so difere com `agora` exatamente igual ao fim (microssegundo 08:00:00.000000); praticamente equivalente, lacuna de borda |
| F6 fim sempre de ontem | morto |
| F7 fim sempre de hoje | sobrevive: equivalente para 22-08 (fora da janela e sempre depois do fim de hoje); LACUNA para janela que nao cruza (ex.: 01-05, as 00:30 ultimo_aberto iria ao futuro e travaria o alerta) |
| F8 ontem = -2 dias | sobrevive: mesma lacuna (so ocorre antes do fim, janela nao cruzante) |
| F9 `is not None` -> `is None` | morto |
| F10 sem ajuste | morto |
| F11 `desde = agora` | morto |
| F12 janela None devolve datetime.min | sobrevive: equivalente (min nunca > ultimo_aberto) |
| F13 `fim <= agora` -> `>=` | morto |
| F14 `max(fim, agora)` | morto |
| F15 devolve None sempre | morto |

Sobreviventes nao equivalentes (lacunas de teste, nao de codigo; opcionais): F5 (teste com `agora` exatamente 08:00:00.000000), F7/F8 (teste com janela nao cruzante, ex. 01:00-05:00, chamada antes do fim). A producao usa 22-08, onde sao equivalentes.

Pós-rodada 3: F5, F7 e F8 viraram teste (`test_no_instante_exato_do_fim_da_janela_parado_e_zero`, `test_janela_que_nao_cruza_meia_noite_chamada_antes_do_fim`); só testes. F2 e F12 equivalentes (justificados acima).
